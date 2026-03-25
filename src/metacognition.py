"""
Dark Factory v2 — Metacognition Engine
========================================
Self-authoring feedback loop that monitors completed task outputs and
autonomously proposes optimizations to the skill files in the skills/
directory. Analyzes recurring data structures, extraction failures, and
task patterns to refine the agent's instruction set over time.

Architecture:
    MetacognitionEngine
    ├── analyze_and_propose()  — Post-task analysis pipeline
    ├── _detect_patterns()     — Identify recurring structures in outputs
    ├── _generate_proposals()  — LLM-driven skill optimization proposals
    └── _write_proposal()      — Write proposals with human-approval gating
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class OptimizationProposal:
    """A proposed modification to a skill file."""
    target_file: str
    summary: str
    reasoning: str
    proposed_content: str
    confidence: float  # 0.0 to 1.0
    patterns_detected: list[str]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = "pending"  # pending, approved, rejected


@dataclass
class TaskAnalysis:
    """Analysis results from a completed task."""
    task_description: str
    output_length: int
    data_structures_found: list[str]
    extraction_patterns: list[str]
    potential_failures: list[str]
    recurring_elements: list[str]


# =============================================================================
# Pattern Detection
# =============================================================================

class PatternDetector:
    """
    Analyzes task outputs to identify recurring structures that could
    inform skill file optimizations.
    """

    # Patterns to look for in task outputs
    JSON_PATTERN = re.compile(r"\{[^{}]{20,}\}", re.DOTALL)
    TABLE_PATTERN = re.compile(r"(?:\|[^|]+)+\|", re.MULTILINE)
    LIST_PATTERN = re.compile(r"(?:^|\n)\s*(?:[-•*]|\d+\.)\s+.+", re.MULTILINE)
    ERROR_PATTERN = re.compile(
        r"(?:error|fail|exception|not found|unable to|cannot|timeout)",
        re.IGNORECASE,
    )
    SEC_FILING_PATTERN = re.compile(
        r"(?:10-K|10-Q|8-K|DEF 14A|S-1|Item\s+\d+[A-Z]?|EDGAR|CIK|accession)",
        re.IGNORECASE,
    )

    def analyze(self, task_description: str, task_output: str) -> TaskAnalysis:
        """
        Perform pattern analysis on a completed task's output.

        Args:
            task_description: What the task was intended to do.
            task_output: The raw output from the task execution.

        Returns:
            TaskAnalysis with detected patterns and structures.
        """
        data_structures = self._detect_data_structures(task_output)
        extraction_patterns = self._detect_extraction_patterns(task_output)
        failures = self._detect_failures(task_output)
        recurring = self._detect_recurring_elements(task_output)

        return TaskAnalysis(
            task_description=task_description,
            output_length=len(task_output),
            data_structures_found=data_structures,
            extraction_patterns=extraction_patterns,
            potential_failures=failures,
            recurring_elements=recurring,
        )

    def _detect_data_structures(self, output: str) -> list[str]:
        """Identify data structure patterns in the output."""
        structures: list[str] = []

        json_matches = self.JSON_PATTERN.findall(output)
        if json_matches:
            structures.append(f"json_objects:{len(json_matches)}")
            # Try to detect common JSON schemas
            for match in json_matches[:5]:
                try:
                    parsed = json.loads(match)
                    if isinstance(parsed, dict):
                        keys = list(parsed.keys())[:5]
                        structures.append(f"json_keys:{','.join(keys)}")
                except json.JSONDecodeError:
                    pass

        if self.TABLE_PATTERN.search(output):
            structures.append("markdown_tables")

        list_matches = self.LIST_PATTERN.findall(output)
        if len(list_matches) > 3:
            structures.append(f"lists:{len(list_matches)}")

        return structures

    def _detect_extraction_patterns(self, output: str) -> list[str]:
        """Identify SEC-specific extraction patterns."""
        patterns: list[str] = []

        sec_matches = self.SEC_FILING_PATTERN.findall(output)
        if sec_matches:
            unique_types = list(set(m.upper() for m in sec_matches))
            patterns.append(f"sec_references:{','.join(unique_types[:5])}")

        # Detect financial data patterns
        money_pattern = re.compile(r"\$[\d,.]+\s*(?:million|billion|M|B)?", re.IGNORECASE)
        money_matches = money_pattern.findall(output)
        if money_matches:
            patterns.append(f"financial_values:{len(money_matches)}")

        # Detect date patterns
        date_pattern = re.compile(
            r"(?:January|February|March|April|May|June|July|August|September|"
            r"October|November|December)\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}"
        )
        date_matches = date_pattern.findall(output)
        if date_matches:
            patterns.append(f"dates:{len(date_matches)}")

        return patterns

    def _detect_failures(self, output: str) -> list[str]:
        """Identify potential failure patterns in the output."""
        failures: list[str] = []

        error_matches = self.ERROR_PATTERN.findall(output)
        if error_matches:
            unique_errors = list(set(e.lower() for e in error_matches))[:5]
            failures.extend(unique_errors)

        # Empty or very short output might indicate a failure
        if len(output.strip()) < 50:
            failures.append("suspiciously_short_output")

        return failures

    def _detect_recurring_elements(self, output: str) -> list[str]:
        """Identify recurring elements that suggest template opportunities."""
        recurring: list[str] = []

        # Look for repeated structural patterns (headers, sections)
        header_pattern = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)
        headers = header_pattern.findall(output)
        if len(headers) > 2:
            recurring.append(f"section_headers:{len(headers)}")

        # Look for repeated key-value patterns
        kv_pattern = re.compile(r"^(?:\*\*)?(\w[\w\s]+)(?:\*\*)?:\s+.+$", re.MULTILINE)
        kv_matches = kv_pattern.findall(output)
        if len(kv_matches) > 3:
            recurring.append(f"key_value_pairs:{len(kv_matches)}")

        return recurring


# =============================================================================
# Metacognition Engine
# =============================================================================

class MetacognitionEngine:
    """
    Post-task analysis engine that proposes skill file optimizations.

    After each completed task, analyzes the output for:
    1. Recurring data structures → suggest output templates
    2. Extraction failures → suggest improved instructions
    3. Common patterns → suggest new reference documents

    All proposals require human approval before being applied.
    """

    # Minimum output length to trigger analysis
    MIN_OUTPUT_LENGTH = 100

    # Minimum confidence to write a proposal
    MIN_CONFIDENCE = 0.6

    def __init__(
        self,
        skills_dir: Path,
        llm_client: Any,
        model_name: str,
    ):
        self._skills_dir = skills_dir
        self._llm_client = llm_client
        self._model_name = model_name
        self._detector = PatternDetector()
        self._history: list[TaskAnalysis] = []
        self._proposals_dir = skills_dir / ".proposals"

    def analyze_and_propose(
        self,
        task_description: str,
        task_output: str,
    ) -> list[dict[str, str]]:
        """
        Analyze a completed task's output and generate optimization proposals.

        Args:
            task_description: What the task was intended to accomplish.
            task_output: The raw output from the completed task.

        Returns:
            List of proposal summaries (dicts with 'target_file' and 'summary').
        """
        # Skip analysis for trivial outputs
        if len(task_output.strip()) < self.MIN_OUTPUT_LENGTH:
            logger.debug("Output too short for metacognition analysis (%d chars)", len(task_output))
            return []

        # Detect patterns in the output
        analysis = self._detector.analyze(task_description, task_output)
        self._history.append(analysis)

        # Check if we have enough signal to generate proposals
        total_signals = (
            len(analysis.data_structures_found)
            + len(analysis.extraction_patterns)
            + len(analysis.potential_failures)
            + len(analysis.recurring_elements)
        )

        if total_signals < 2:
            logger.debug("Insufficient signals for metacognition (%d)", total_signals)
            return []

        # Generate proposals using the LLM
        proposals = self._generate_proposals(analysis)

        # Write qualifying proposals to disk for human review
        written: list[dict[str, str]] = []
        for proposal in proposals:
            if proposal.confidence >= self.MIN_CONFIDENCE:
                self._write_proposal(proposal)
                written.append({
                    "target_file": proposal.target_file,
                    "summary": proposal.summary,
                })

        return written

    def _generate_proposals(self, analysis: TaskAnalysis) -> list[OptimizationProposal]:
        """
        Use the LLM to generate skill optimization proposals based on
        the pattern analysis results.
        """
        # Build the analysis summary for the LLM
        analysis_text = json.dumps({
            "task": analysis.task_description[:500],
            "output_length": analysis.output_length,
            "data_structures": analysis.data_structures_found,
            "extraction_patterns": analysis.extraction_patterns,
            "failures": analysis.potential_failures,
            "recurring_elements": analysis.recurring_elements,
            "history_depth": len(self._history),
        }, indent=2)

        # List current skill files
        skill_files = [f.name for f in self._skills_dir.glob("*.md")]
        ref_files = [f.name for f in (self._skills_dir / "references").glob("*.md")] if (self._skills_dir / "references").exists() else []

        prompt = f"""You are a metacognition engine for an SEC compliance AI agent.

Analyze the following task execution results and propose specific optimizations to the agent's skill files.

## Current Skill Files
- Primary skills: {', '.join(skill_files) or 'none'}
- References: {', '.join(ref_files) or 'none'}

## Task Analysis
{analysis_text}

## Instructions
Based on the patterns detected, propose 0-3 specific optimizations. For each proposal:
1. Identify which skill file to modify (or suggest a new reference file)
2. Describe the specific improvement
3. Rate your confidence (0.0 to 1.0) in the proposal's value
4. Explain your reasoning

Respond in JSON format:
```json
[
  {{
    "target_file": "filename.md",
    "summary": "Brief description of the change",
    "reasoning": "Why this optimization would help",
    "confidence": 0.75,
    "patterns_detected": ["pattern1", "pattern2"]
  }}
]
```

If no optimizations are warranted, respond with an empty array: []"""

        try:
            response = self._llm_client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {"role": "system", "content": "You are a precise analytical engine. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0.2,
            )

            content = response.choices[0].message.content or "[]"

            # Extract JSON from the response (handle markdown code blocks)
            json_match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)

            raw_proposals = json.loads(content)
            if not isinstance(raw_proposals, list):
                return []

            proposals: list[OptimizationProposal] = []
            for rp in raw_proposals:
                proposals.append(OptimizationProposal(
                    target_file=rp.get("target_file", "unknown.md"),
                    summary=rp.get("summary", ""),
                    reasoning=rp.get("reasoning", ""),
                    proposed_content="",  # Will be generated in a follow-up if approved
                    confidence=float(rp.get("confidence", 0.0)),
                    patterns_detected=rp.get("patterns_detected", []),
                ))

            return proposals

        except Exception as exc:
            logger.warning("Metacognition LLM call failed: %s", exc)
            return []

    def _write_proposal(self, proposal: OptimizationProposal) -> None:
        """
        Write an optimization proposal to disk for human review.
        Proposals are stored in skills/.proposals/ and must be manually
        approved before being applied.
        """
        self._proposals_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{proposal.target_file.replace('.md', '')}.md"
        filepath = self._proposals_dir / filename

        content = f"""---
target_file: {proposal.target_file}
confidence: {proposal.confidence}
status: pending
created_at: {proposal.created_at}
---

# Optimization Proposal

**Target:** `{proposal.target_file}`
**Confidence:** {proposal.confidence:.0%}
**Status:** ⏳ Pending human review

## Summary
{proposal.summary}

## Reasoning
{proposal.reasoning}

## Detected Patterns
{chr(10).join(f'- `{p}`' for p in proposal.patterns_detected)}

## Instructions
To apply this proposal:
1. Review the suggested changes above
2. Manually update `{proposal.target_file}` with the improvements
3. Delete this proposal file or change status to `approved`

To reject: Change the status in the front-matter to `rejected`.
"""

        filepath.write_text(content, encoding="utf-8")
        logger.info("Wrote optimization proposal: %s", filepath)

    # ── Aggregate Analysis ───────────────────────────────────────────────

    def get_analysis_summary(self) -> dict[str, Any]:
        """
        Get a summary of all task analyses performed in this session.
        Useful for understanding the agent's operational patterns.
        """
        if not self._history:
            return {"total_tasks": 0, "message": "No tasks analyzed yet."}

        all_structures = []
        all_patterns = []
        all_failures = []
        total_output_length = 0

        for analysis in self._history:
            all_structures.extend(analysis.data_structures_found)
            all_patterns.extend(analysis.extraction_patterns)
            all_failures.extend(analysis.potential_failures)
            total_output_length += analysis.output_length

        return {
            "total_tasks": len(self._history),
            "total_output_chars": total_output_length,
            "unique_structures": list(set(all_structures)),
            "unique_patterns": list(set(all_patterns)),
            "unique_failures": list(set(all_failures)),
            "avg_output_length": total_output_length // len(self._history),
        }
