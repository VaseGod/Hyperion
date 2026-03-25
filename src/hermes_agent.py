"""
Dark Factory v2 — Hermes Agent Core
=====================================
Implements the HermesAgent class: the central orchestration engine that manages
conversation history, persistent memory, tool dispatch, sandboxed execution,
and the LLM chat-completion loop with function-calling.

Architecture:
    HermesAgent
    ├── PersistentMemory   — JSON-backed read/write/search memory store
    ├── ToolRegistry       — Registered tool definitions + dispatch
    ├── ConversationBuffer — Rolling message history with summarization
    └── LLM Client         — OpenAI-compatible chat completions
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from openai import OpenAI
from rich.console import Console

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)
console = Console()


# =============================================================================
# Persistent Memory
# =============================================================================

class PersistentMemory:
    """
    JSON-backed persistent memory store for the agent.

    Supports storing, retrieving, searching, and deleting memory entries.
    Each entry has a key, value, metadata dict, and timestamp.
    """

    def __init__(self, store_path: Path):
        self._path = store_path
        self._store: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load memory from disk if the file exists."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._store = json.load(f)
                logger.info("Loaded %d memory entries from %s", len(self._store), self._path)
            except (json.JSONDecodeError, IOError) as exc:
                logger.warning("Failed to load memory store: %s — starting fresh", exc)
                self._store = {}
        else:
            logger.info("No existing memory store at %s — initializing empty", self._path)

    def _save(self) -> None:
        """Persist the current memory state to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._store, f, indent=2, default=str)

    def write(self, key: str, value: Any, metadata: Optional[dict] = None) -> None:
        """Store or overwrite a memory entry."""
        self._store[key] = {
            "value": value,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()
        logger.debug("Memory write: %s", key)

    def read(self, key: str) -> Optional[dict[str, Any]]:
        """Retrieve a memory entry by key, or None if not found."""
        return self._store.get(key)

    def search(self, query: str) -> list[tuple[str, dict[str, Any]]]:
        """
        Search memory entries by substring match on key or stringified value.
        Returns a list of (key, entry) tuples sorted by relevance (key match first).
        """
        results: list[tuple[str, dict[str, Any], int]] = []
        query_lower = query.lower()
        for key, entry in self._store.items():
            score = 0
            if query_lower in key.lower():
                score += 10
            if query_lower in json.dumps(entry.get("value", ""), default=str).lower():
                score += 5
            if query_lower in json.dumps(entry.get("metadata", {}), default=str).lower():
                score += 2
            if score > 0:
                results.append((key, entry, score))
        results.sort(key=lambda x: x[2], reverse=True)
        return [(k, e) for k, e, _ in results]

    def delete(self, key: str) -> bool:
        """Delete a memory entry. Returns True if it existed."""
        if key in self._store:
            del self._store[key]
            self._save()
            return True
        return False

    def list_keys(self) -> list[str]:
        """Return all memory keys."""
        return list(self._store.keys())


# =============================================================================
# Tool Registry
# =============================================================================

@dataclass
class ToolDefinition:
    """Schema for a tool that the agent can invoke."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for parameters
    handler: Callable[..., Any]


class ToolRegistry:
    """
    Registry of tools available to the agent. Tools are registered with their
    JSON Schema definitions and callable handlers. Generates the OpenAI
    function-calling tool list and dispatches invocations.
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a new tool."""
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def get_openai_tools(self) -> list[dict[str, Any]]:
        """Generate the tools list in OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> Any:
        """
        Execute a registered tool by name with the given arguments.
        Returns the tool's output or an error string if dispatch fails.
        """
        tool = self._tools.get(name)
        if tool is None:
            error_msg = f"Unknown tool: {name}"
            logger.error(error_msg)
            return {"error": error_msg}
        try:
            logger.info("Dispatching tool: %s(%s)", name, json.dumps(arguments, default=str)[:200])
            result = tool.handler(**arguments)
            return result
        except Exception as exc:
            error_msg = f"Tool '{name}' failed: {exc}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())


# =============================================================================
# Hermes Agent
# =============================================================================

class HermesAgent:
    """
    Core orchestration agent with persistent memory, tool dispatch,
    and an LLM chat-completion loop supporting function-calling.

    Usage:
        agent = HermesAgent(settings)
        agent.register_tool(some_tool_definition)
        result = agent.run("Analyze the latest 10-K filing for ACME Corp")
    """

    # Maximum number of tool-call rounds before forcing a final answer
    MAX_TOOL_ROUNDS = 15

    # Maximum conversation history messages before summarizing
    MAX_HISTORY_MESSAGES = 50

    def __init__(self, settings: Settings, system_prompt: str = ""):
        self.settings = settings
        self.memory = PersistentMemory(settings.memory_path)
        self.tools = ToolRegistry()
        self._system_prompt = system_prompt
        self._conversation: list[dict[str, Any]] = []
        self._run_id: str = ""

        # Initialize the OpenAI-compatible client
        self._client = OpenAI(
            base_url=settings.llm_api_base,
            api_key=settings.llm_api_key,
        )

        # Register built-in memory tools
        self._register_memory_tools()

        logger.info(
            "HermesAgent initialized — model=%s endpoint=%s",
            settings.llm_model_name,
            settings.llm_api_base,
        )

    # ── Built-in Tools ─────────────────────────────────────────────────────

    def _register_memory_tools(self) -> None:
        """Register the agent's built-in persistent memory tools."""
        self.tools.register(ToolDefinition(
            name="memory_write",
            description="Store a key-value pair in persistent memory for later retrieval.",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Memory key identifier."},
                    "value": {"type": "string", "description": "Value to store."},
                    "metadata": {
                        "type": "object",
                        "description": "Optional metadata tags.",
                        "additionalProperties": True,
                    },
                },
                "required": ["key", "value"],
            },
            handler=lambda key, value, metadata=None: self._handle_memory_write(key, value, metadata),
        ))

        self.tools.register(ToolDefinition(
            name="memory_read",
            description="Retrieve a value from persistent memory by its key.",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Memory key to look up."},
                },
                "required": ["key"],
            },
            handler=lambda key: self._handle_memory_read(key),
        ))

        self.tools.register(ToolDefinition(
            name="memory_search",
            description="Search persistent memory entries by a query string.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                },
                "required": ["query"],
            },
            handler=lambda query: self._handle_memory_search(query),
        ))

    def _handle_memory_write(self, key: str, value: str, metadata: Optional[dict] = None) -> str:
        self.memory.write(key, value, metadata)
        return f"Stored '{key}' in memory."

    def _handle_memory_read(self, key: str) -> str:
        entry = self.memory.read(key)
        if entry is None:
            return f"No memory entry found for key: '{key}'"
        return json.dumps(entry, indent=2, default=str)

    def _handle_memory_search(self, query: str) -> str:
        results = self.memory.search(query)
        if not results:
            return f"No memory entries matched query: '{query}'"
        output = []
        for key, entry in results[:10]:
            output.append(f"- **{key}**: {json.dumps(entry['value'], default=str)[:200]}")
        return "\n".join(output)

    # ── Tool Registration ──────────────────────────────────────────────────

    def register_tool(self, tool: ToolDefinition) -> None:
        """Register an external tool with the agent."""
        self.tools.register(tool)

    # ── Conversation Management ────────────────────────────────────────────

    def _build_messages(self, user_input: str) -> list[dict[str, Any]]:
        """
        Build the message payload for the LLM, including system prompt,
        conversation history, and the new user input.
        """
        messages: list[dict[str, Any]] = []

        # System prompt
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        # Conversation history (trimmed if necessary)
        if len(self._conversation) > self.MAX_HISTORY_MESSAGES:
            # Summarize older messages to save context
            summary = self._summarize_history(self._conversation[:-20])
            messages.append({"role": "system", "content": f"[Conversation Summary]\n{summary}"})
            messages.extend(self._conversation[-20:])
        else:
            messages.extend(self._conversation)

        # New user message
        messages.append({"role": "user", "content": user_input})
        return messages

    def _summarize_history(self, messages: list[dict[str, Any]]) -> str:
        """
        Generate a concise summary of older conversation messages using the LLM.
        Falls back to a simple concatenation if the LLM call fails.
        """
        content_parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                content_parts.append(f"{role}: {content[:300]}")

        combined = "\n".join(content_parts[-30:])  # Last 30 messages for summary

        try:
            response = self._client.chat.completions.create(
                model=self.settings.llm_model_name,
                messages=[
                    {"role": "system", "content": "Summarize this conversation concisely, preserving key facts and decisions."},
                    {"role": "user", "content": combined},
                ],
                max_tokens=500,
                temperature=0.0,
            )
            return response.choices[0].message.content or combined[:500]
        except Exception as exc:
            logger.warning("History summarization failed: %s", exc)
            return combined[:500]

    # ── Core Execution Loop ────────────────────────────────────────────────

    def run(self, user_input: str) -> str:
        """
        Process a user request through the agent's tool-augmented LLM loop.

        The loop:
        1. Send messages (system + history + user input) to the LLM.
        2. If the LLM returns tool calls, dispatch them and feed results back.
        3. Repeat until the LLM produces a final text response or we hit MAX_TOOL_ROUNDS.
        4. Store the exchange in conversation history.

        Returns:
            The agent's final text response.
        """
        self._run_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        logger.info("[%s] Processing: %s", self._run_id, user_input[:100])

        messages = self._build_messages(user_input)
        tools_payload = self.tools.get_openai_tools() or None

        final_response = ""
        rounds = 0

        while rounds < self.MAX_TOOL_ROUNDS:
            rounds += 1
            logger.debug("[%s] LLM round %d", self._run_id, rounds)

            try:
                completion = self._client.chat.completions.create(
                    model=self.settings.llm_model_name,
                    messages=messages,
                    tools=tools_payload,
                    tool_choice="auto" if tools_payload else None,
                    max_tokens=self.settings.llm_max_tokens,
                    temperature=self.settings.llm_temperature,
                )
            except Exception as exc:
                error_msg = f"LLM request failed: {exc}"
                logger.error("[%s] %s", self._run_id, error_msg)
                final_response = f"Error: {error_msg}"
                break

            choice = completion.choices[0]
            assistant_message = choice.message

            # Append the assistant message to our running messages
            msg_dict: dict[str, Any] = {"role": "assistant"}
            if assistant_message.content:
                msg_dict["content"] = assistant_message.content
            if assistant_message.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in assistant_message.tool_calls
                ]
            messages.append(msg_dict)

            # If no tool calls, this is the final response
            if not assistant_message.tool_calls:
                final_response = assistant_message.content or ""
                break

            # Dispatch each tool call and collect results
            for tool_call in assistant_message.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                console.print(f"  ⚙ [bold cyan]{fn_name}[/]({json.dumps(fn_args, default=str)[:120]})")
                result = self.tools.dispatch(fn_name, fn_args)

                # Serialize the result for the LLM
                if isinstance(result, str):
                    result_str = result
                else:
                    result_str = json.dumps(result, indent=2, default=str)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_str[:8000],  # Truncate to avoid context overflow
                })

        # If we exhausted tool rounds without a final answer, force one
        if not final_response and rounds >= self.MAX_TOOL_ROUNDS:
            logger.warning("[%s] Exceeded max tool rounds (%d)", self._run_id, self.MAX_TOOL_ROUNDS)
            messages.append({
                "role": "user",
                "content": "You have exceeded the maximum number of tool calls. Please provide your final answer now based on the information gathered so far.",
            })
            try:
                completion = self._client.chat.completions.create(
                    model=self.settings.llm_model_name,
                    messages=messages,
                    max_tokens=self.settings.llm_max_tokens,
                    temperature=self.settings.llm_temperature,
                )
                final_response = completion.choices[0].message.content or "Unable to complete the task."
            except Exception as exc:
                final_response = f"Error generating final response: {exc}"

        # Update conversation history
        self._conversation.append({"role": "user", "content": user_input})
        self._conversation.append({"role": "assistant", "content": final_response})

        elapsed = time.time() - start_time
        logger.info("[%s] Completed in %.2fs (%d rounds)", self._run_id, elapsed, rounds)

        return final_response

    def reset_conversation(self) -> None:
        """Clear the conversation history (memory persists)."""
        self._conversation.clear()
        logger.info("Conversation history cleared.")
