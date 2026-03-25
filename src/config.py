"""
Dark Factory v2 — Centralized Configuration
=============================================
Loads environment variables from .env and validates all required settings
using pydantic-settings. Exposes a singleton `get_settings()` accessor.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Resolve the project root (parent of the `src/` directory)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM Inference ──────────────────────────────────────────────────────
    llm_api_base: str = Field(
        default="http://localhost:8000/v1",
        description="Base URL for the OpenAI-compatible inference server.",
    )
    llm_model_name: str = Field(
        default="qwen2.5-72b-instruct",
        description="Model identifier on the inference server.",
    )
    llm_api_key: str = Field(
        default="EMPTY",
        description="API key for the inference server (often 'EMPTY' locally).",
    )
    llm_max_tokens: int = Field(
        default=4096,
        description="Maximum tokens per LLM response.",
    )
    llm_temperature: float = Field(
        default=0.1,
        description="Sampling temperature for generation.",
    )

    # ── Parchi Relay ───────────────────────────────────────────────────────
    parchi_relay_url: str = Field(
        default="http://localhost:9222",
        description="URL of the Parchi Relay Daemon.",
    )
    parchi_timeout_seconds: int = Field(
        default=30,
        description="Timeout for browser operations in seconds.",
    )

    # ── WebArena-Infinity ─────────────────────────────────────────────────
    webarena_base_url: str = Field(
        default="http://localhost:4399",
        description="Base URL for the WebArena evaluation environment.",
    )

    # ── Agent Runtime ─────────────────────────────────────────────────────
    skills_directory: str = Field(
        default="skills",
        description="Directory containing agentskills.io skill files.",
    )
    memory_store_path: str = Field(
        default="data/agent_memory.json",
        description="Path for persistent agent memory (JSON).",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging verbosity: DEBUG, INFO, WARNING, ERROR.",
    )

    # ── Derived Paths (resolved relative to project root) ─────────────────
    @property
    def skills_dir(self) -> Path:
        """Absolute path to the skills directory."""
        p = Path(self.skills_directory)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def memory_path(self) -> Path:
        """Absolute path to the memory store file."""
        p = Path(self.memory_store_path)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got '{v}'")
        return upper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached after first call)."""
    return Settings()
