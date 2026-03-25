"""
Dark Factory v2 — Entry Point
================================
Initializes the Hermes Agent, loads skills, attaches browser tools,
and runs the main agent loop. Supports single-task and interactive modes.

Usage:
    python -m src.main --task "Analyze the latest 10-K for ACME Corp"
    python -m src.main --interactive
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.text import Text

from src.config import get_settings, PROJECT_ROOT
from src.hermes_agent import HermesAgent
from src.skills_manager import SkillsManager
from src.browser_tools import BrowserToolkit
from src.metacognition import MetacognitionEngine

console = Console()


# =============================================================================
# Logging Setup
# =============================================================================

def configure_logging(level: str) -> None:
    """Configure structured logging with Rich handler."""
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )
    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


# =============================================================================
# Agent Assembly
# =============================================================================

def build_agent() -> tuple[HermesAgent, SkillsManager, MetacognitionEngine]:
    """
    Assemble the full agent stack:
    1. Load settings from .env
    2. Initialize the skills manager and build the system prompt
    3. Create the HermesAgent with the system prompt
    4. Register browser tools from the Parchi integration
    5. Initialize the metacognition engine

    Returns:
        Tuple of (agent, skills_manager, metacognition_engine)
    """
    settings = get_settings()

    # ── Skills ──────────────────────────────────────────────────────────
    skills_mgr = SkillsManager(settings.skills_dir)
    system_prompt = skills_mgr.get_system_prompt()
    console.print(
        f"[dim]Loaded {len(skills_mgr.skills)} skill(s), "
        f"{len(skills_mgr.references)} reference(s)[/dim]"
    )

    # ── Agent ───────────────────────────────────────────────────────────
    agent = HermesAgent(settings=settings, system_prompt=system_prompt)

    # ── Browser Tools ───────────────────────────────────────────────────
    browser = BrowserToolkit(
        relay_url=settings.parchi_relay_url,
        timeout=settings.parchi_timeout_seconds,
    )
    for tool_def in browser.get_tool_definitions():
        agent.register_tool(tool_def)
    console.print(f"[dim]Registered {len(browser.get_tool_definitions())} browser tool(s)[/dim]")

    # ── Skill Retrieval Tool ────────────────────────────────────────────
    # Expose reference retrieval as a tool for progressive disclosure
    from src.hermes_agent import ToolDefinition

    agent.register_tool(ToolDefinition(
        name="retrieve_reference",
        description=(
            "Retrieve a regulatory reference document by its ID. "
            "Use this when you need detailed information about a specific "
            "SEC regulation, form type, or compliance requirement."
        ),
        parameters={
            "type": "object",
            "properties": {
                "reference_id": {
                    "type": "string",
                    "description": "The reference file ID (e.g., 'regulation_s_k', 'form_types').",
                },
            },
            "required": ["reference_id"],
        },
        handler=lambda reference_id: skills_mgr.retrieve_reference(reference_id),
    ))

    # ── Metacognition ───────────────────────────────────────────────────
    metacognition = MetacognitionEngine(
        skills_dir=settings.skills_dir,
        llm_client=agent._client,
        model_name=settings.llm_model_name,
    )

    return agent, skills_mgr, metacognition


# =============================================================================
# Execution Modes
# =============================================================================

def run_single_task(agent: HermesAgent, metacognition: MetacognitionEngine, task: str) -> None:
    """Execute a single task and display the result."""
    console.print(Panel(
        Text(task, style="bold white"),
        title="[bold green]Task",
        border_style="green",
    ))

    result = agent.run(task)

    console.print(Panel(
        result,
        title="[bold blue]Result",
        border_style="blue",
    ))

    # Run metacognition analysis on the completed task
    console.print("\n[dim]Running post-task metacognition analysis...[/dim]")
    proposals = metacognition.analyze_and_propose(
        task_description=task,
        task_output=result,
    )
    if proposals:
        console.print(f"[yellow]Metacognition generated {len(proposals)} optimization proposal(s).[/yellow]")
        for p in proposals:
            console.print(f"  📝 {p['target_file']}: {p['summary']}")
    else:
        console.print("[dim]No optimizations proposed.[/dim]")


def run_interactive(agent: HermesAgent, metacognition: MetacognitionEngine) -> None:
    """Run the agent in interactive REPL mode."""
    console.print(Panel(
        "[bold]Dark Factory v2[/bold] — Interactive Mode\n"
        "Type your tasks or questions. Use [bold cyan]/quit[/bold cyan] to exit, "
        "[bold cyan]/reset[/bold cyan] to clear history, "
        "[bold cyan]/memory[/bold cyan] to list memory keys.",
        title="[bold green]🏭 Dark Factory",
        border_style="green",
    ))

    while True:
        try:
            user_input = console.input("\n[bold green]▶ [/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input:
            continue

        # Handle meta-commands
        if user_input.lower() == "/quit":
            console.print("[dim]Goodbye.[/dim]")
            break
        elif user_input.lower() == "/reset":
            agent.reset_conversation()
            console.print("[yellow]Conversation history cleared.[/yellow]")
            continue
        elif user_input.lower() == "/memory":
            keys = agent.memory.list_keys()
            if keys:
                console.print("[bold]Memory Keys:[/bold]")
                for k in keys:
                    console.print(f"  • {k}")
            else:
                console.print("[dim]No memory entries.[/dim]")
            continue
        elif user_input.lower().startswith("/memory "):
            key = user_input[8:].strip()
            entry = agent.memory.read(key)
            if entry:
                console.print_json(data=entry)
            else:
                console.print(f"[red]No entry for key: {key}[/red]")
            continue

        # Run the task
        result = agent.run(user_input)
        console.print(Panel(result, title="[bold blue]Response", border_style="blue"))

        # Background metacognition (non-blocking analysis)
        proposals = metacognition.analyze_and_propose(
            task_description=user_input,
            task_output=result,
        )
        if proposals:
            console.print(
                f"\n[dim yellow]💡 Metacognition: {len(proposals)} optimization(s) proposed. "
                f"Review in skills/ directory.[/dim yellow]"
            )


# =============================================================================
# CLI Entry Point
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dark-factory",
        description="Dark Factory v2 — Automated Financial Compliance & SEC Filing Synthesis",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--task", "-t",
        type=str,
        help="Execute a single task and exit.",
    )
    group.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive REPL mode.",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    console.print("[bold green]🏭 Dark Factory v2[/bold green] — Initializing...\n")

    agent, skills_mgr, metacognition = build_agent()

    if args.task:
        run_single_task(agent, metacognition, args.task)
    else:
        run_interactive(agent, metacognition)


if __name__ == "__main__":
    main()
