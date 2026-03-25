"""
Dark Factory v2 — Skills Manager
==================================
Implements the agentskills.io standard for prompt management. Loads Markdown
skill files with YAML front-matter, provides progressive disclosure of
reference documents to preserve the LLM's context window.

Architecture:
    SkillsManager
    ├── load_skills()       — Parse primary skill files (summaries only)
    ├── load_references()   — Index reference files for on-demand retrieval
    ├── get_system_prompt() — Build the system prompt with skill summaries
    └── retrieve_reference()— Fetch full reference content by ID
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class Skill:
    """Parsed representation of an agentskills.io skill file."""
    id: str
    name: str
    version: str
    description: str
    capabilities: list[str]
    full_content: str
    summary: str  # First N lines for progressive disclosure
    file_path: Path

    @property
    def token_estimate(self) -> int:
        """Rough token estimate (1 token ≈ 4 chars)."""
        return len(self.full_content) // 4


@dataclass
class Reference:
    """A reference document available for on-demand context injection."""
    id: str
    title: str
    summary: str
    full_content: str
    file_path: Path
    tags: list[str] = field(default_factory=list)


# =============================================================================
# Front-Matter Parser
# =============================================================================

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_skill_file(file_path: Path) -> tuple[dict[str, Any], str]:
    """
    Parse a Markdown file with YAML front-matter.

    Returns:
        Tuple of (front_matter_dict, markdown_body).
    """
    content = file_path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(content)
    if match:
        try:
            front_matter = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as exc:
            logger.warning("Failed to parse front-matter in %s: %s", file_path, exc)
            front_matter = {}
        body = content[match.end():]
    else:
        front_matter = {}
        body = content
    return front_matter, body


def extract_summary(body: str, max_lines: int = 30) -> str:
    """
    Extract a summary from the first N lines of a Markdown body.
    Stops at the first level-2 heading after the initial block.
    """
    lines = body.strip().split("\n")
    summary_lines: list[str] = []
    found_first_heading = False

    for line in lines[:max_lines]:
        if line.startswith("## ") and found_first_heading:
            break
        if line.startswith("## ") or line.startswith("# "):
            found_first_heading = True
        summary_lines.append(line)

    return "\n".join(summary_lines).strip()


# =============================================================================
# Skills Manager
# =============================================================================

class SkillsManager:
    """
    Manages agentskills.io skill files and reference documents.

    Progressive Disclosure Strategy:
    - On initialization, only skill summaries are loaded into the system prompt.
    - Full skill content is available but not injected by default.
    - Reference documents are indexed but only retrieved on-demand via
      the `retrieve_reference()` method, preserving context window budget.
    """

    def __init__(self, skills_dir: Path):
        self._skills_dir = skills_dir
        self.skills: dict[str, Skill] = {}
        self.references: dict[str, Reference] = {}

        self._load_skills()
        self._load_references()

    def _load_skills(self) -> None:
        """Load all top-level .md files in the skills directory as skills."""
        if not self._skills_dir.exists():
            logger.warning("Skills directory does not exist: %s", self._skills_dir)
            return

        for md_file in sorted(self._skills_dir.glob("*.md")):
            try:
                front_matter, body = parse_skill_file(md_file)
                skill_id = md_file.stem

                skill = Skill(
                    id=skill_id,
                    name=front_matter.get("name", skill_id.replace("_", " ").title()),
                    version=str(front_matter.get("version", "1.0.0")),
                    description=front_matter.get("description", ""),
                    capabilities=front_matter.get("capabilities", []),
                    full_content=body,
                    summary=extract_summary(body),
                    file_path=md_file,
                )
                self.skills[skill_id] = skill
                logger.info(
                    "Loaded skill: %s v%s (~%d tokens)",
                    skill.name, skill.version, skill.token_estimate,
                )
            except Exception as exc:
                logger.error("Failed to load skill from %s: %s", md_file, exc)

    def _load_references(self) -> None:
        """Load all .md files in the references/ subdirectory."""
        refs_dir = self._skills_dir / "references"
        if not refs_dir.exists():
            logger.info("No references directory found at %s", refs_dir)
            return

        for md_file in sorted(refs_dir.glob("*.md")):
            try:
                front_matter, body = parse_skill_file(md_file)
                ref_id = md_file.stem

                ref = Reference(
                    id=ref_id,
                    title=front_matter.get("title", ref_id.replace("_", " ").title()),
                    summary=front_matter.get("summary", extract_summary(body, max_lines=5)),
                    full_content=body,
                    file_path=md_file,
                    tags=front_matter.get("tags", []),
                )
                self.references[ref_id] = ref
                logger.info("Indexed reference: %s (%d chars)", ref.title, len(body))
            except Exception as exc:
                logger.error("Failed to load reference from %s: %s", md_file, exc)

    # ── System Prompt Construction ────────────────────────────────────────

    def get_system_prompt(self) -> str:
        """
        Build the system prompt using progressive disclosure:
        - Full content of primary skill files (they are kept under 500 lines)
        - Summaries of available references (full content on-demand via tool)

        Returns:
            The assembled system prompt string.
        """
        sections: list[str] = []

        # Primary skills — inject full content (they're designed to be compact)
        for skill in self.skills.values():
            sections.append(
                f"# Skill: {skill.name} (v{skill.version})\n\n"
                f"{skill.full_content}"
            )

        # Reference index — summaries only, retrievable on-demand
        if self.references:
            ref_index_lines = [
                "\n# Available Reference Documents",
                "Use the `retrieve_reference` tool to load full content when needed.\n",
            ]
            for ref in self.references.values():
                tags_str = f" [{', '.join(ref.tags)}]" if ref.tags else ""
                ref_index_lines.append(
                    f"- **{ref.id}**: {ref.title}{tags_str}\n"
                    f"  {ref.summary[:150]}"
                )
            sections.append("\n".join(ref_index_lines))

        return "\n\n---\n\n".join(sections)

    # ── Reference Retrieval ──────────────────────────────────────────────

    def retrieve_reference(self, reference_id: str) -> str:
        """
        Retrieve the full content of a reference document by its ID.
        This is the progressive disclosure mechanism — references are only
        injected into context when explicitly requested.

        Args:
            reference_id: The reference file stem (e.g., 'regulation_s_k').

        Returns:
            The full reference content, or an error message if not found.
        """
        ref = self.references.get(reference_id)
        if ref is None:
            available = ", ".join(self.references.keys()) if self.references else "none"
            return (
                f"Reference '{reference_id}' not found. "
                f"Available references: {available}"
            )

        logger.info("Retrieved reference: %s (%d chars)", ref.title, len(ref.full_content))
        return f"# {ref.title}\n\n{ref.full_content}"

    # ── Utility ──────────────────────────────────────────────────────────

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by its ID."""
        return self.skills.get(skill_id)

    def list_available_references(self) -> list[dict[str, str]]:
        """List all available references with their summaries."""
        return [
            {"id": ref.id, "title": ref.title, "summary": ref.summary}
            for ref in self.references.values()
        ]
