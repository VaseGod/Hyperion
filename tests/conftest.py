"""
Dark Factory v2 — Shared Test Fixtures
========================================
Provides reusable pytest fixtures for:
- Mock LLM client (deterministic responses, no network calls)
- Mock Parchi relay server
- Temporary skills directory with test skill files
- Sample SEC filing data
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

# Ensure tests use a controlled environment
os.environ.setdefault("LLM_API_BASE", "http://localhost:8000/v1")
os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("PARCHI_RELAY_URL", "http://localhost:9222")
os.environ.setdefault("LOG_LEVEL", "WARNING")


# =============================================================================
# Mock LLM Client
# =============================================================================

class MockChatMessage:
    """Mock OpenAI chat completion message."""

    def __init__(self, content: str = "", tool_calls: list | None = None):
        self.content = content
        self.tool_calls = tool_calls
        self.role = "assistant"


class MockChatChoice:
    """Mock OpenAI chat completion choice."""

    def __init__(self, message: MockChatMessage):
        self.message = message
        self.finish_reason = "stop"
        self.index = 0


class MockChatCompletion:
    """Mock OpenAI chat completion response."""

    def __init__(self, content: str = "Mock LLM response"):
        self.choices = [MockChatChoice(MockChatMessage(content=content))]
        self.model = "test-model"
        self.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)


class MockLLMClient:
    """
    Mock OpenAI client that returns deterministic responses.
    Configurable response queue for multi-turn conversations.
    """

    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses or ["Mock LLM response"])
        self._call_count = 0
        self.chat = MagicMock()
        self.chat.completions.create = self._create_completion

    def _create_completion(self, **kwargs) -> MockChatCompletion:
        """Return the next queued response."""
        idx = min(self._call_count, len(self._responses) - 1)
        response = self._responses[idx]
        self._call_count += 1
        return MockChatCompletion(content=response)

    @property
    def call_count(self) -> int:
        return self._call_count


@pytest.fixture
def mock_llm_client() -> MockLLMClient:
    """Provide a mock LLM client with default responses."""
    return MockLLMClient()


@pytest.fixture
def mock_llm_responses():
    """Factory fixture for creating mock LLM clients with custom responses."""
    def _factory(responses: list[str]) -> MockLLMClient:
        return MockLLMClient(responses=responses)
    return _factory


# =============================================================================
# Mock Parchi Relay
# =============================================================================

class MockParchiRelay:
    """
    Mock Parchi Relay Daemon that simulates browser operations
    with deterministic responses.
    """

    def __init__(self):
        self.navigation_history: list[str] = []
        self.current_url: str = ""
        self.pages: dict[str, str] = {
            "https://www.sec.gov/cgi-bin/browse-edgar": MOCK_EDGAR_SEARCH_PAGE,
            "https://www.sec.gov/Archives/edgar/data/mock": MOCK_FILING_PAGE,
        }

    def navigate(self, url: str, wait_for: str | None = None) -> dict[str, Any]:
        self.navigation_history.append(url)
        self.current_url = url
        return {"success": True, "url": url}

    def get_content(self, selector: str | None = None, content_type: str = "text") -> dict[str, Any]:
        content = self.pages.get(self.current_url, "<html><body>Page not found</body></html>")
        return {"success": True, "content": content}

    def click(self, selector: str) -> dict[str, Any]:
        return {"success": True, "selector": selector}

    def fill(self, selector: str, value: str) -> dict[str, Any]:
        return {"success": True, "selector": selector, "value": value}

    def screenshot(self, full_page: bool = False) -> dict[str, Any]:
        return {"success": True, "path": "/tmp/mock_screenshot.png"}

    def health_check(self) -> dict[str, Any]:
        return {"success": True, "status": "healthy"}


@pytest.fixture
def mock_parchi_relay() -> MockParchiRelay:
    """Provide a mock Parchi relay server."""
    return MockParchiRelay()


# =============================================================================
# Temporary Skills Directory
# =============================================================================

@pytest.fixture
def temp_skills_dir(tmp_path: Path) -> Path:
    """
    Create a temporary skills directory with a minimal skill file
    and reference document for testing.
    """
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create a minimal skill file
    skill_content = textwrap.dedent("""\
    ---
    name: Test Compliance Skill
    version: 0.1.0
    description: A minimal skill for testing
    capabilities:
      - test_capability
    ---

    # Test Compliance Skill

    You are a test compliance agent.

    ## Workflow
    1. Extract data
    2. Analyze data
    3. Generate report
    """)
    (skills_dir / "test_skill.md").write_text(skill_content)

    # Create references subdirectory
    refs_dir = skills_dir / "references"
    refs_dir.mkdir()

    ref_content = textwrap.dedent("""\
    ---
    title: Test Reference
    summary: A test reference document
    tags:
      - test
    ---

    # Test Reference

    This is a test reference document for unit testing.

    ## Section 1
    Content for section 1.

    ## Section 2
    Content for section 2.
    """)
    (refs_dir / "test_reference.md").write_text(ref_content)

    return skills_dir


# =============================================================================
# Sample SEC Filing Data
# =============================================================================

MOCK_EDGAR_SEARCH_PAGE = """
<html>
<body>
<h1>EDGAR Company Search</h1>
<form action="/cgi-bin/browse-edgar" method="get">
  <input type="text" name="company" id="company" />
  <input type="submit" value="Search" />
</form>
<table>
  <tr><td>ACME CORP</td><td>CIK: 0001234567</td><td>10-K</td><td>2024-03-15</td></tr>
</table>
</body>
</html>
"""

MOCK_FILING_PAGE = """
<html>
<body>
<h1>ACME CORPORATION</h1>
<h2>ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d)</h2>

<h3>Item 1A. Risk Factors</h3>
<p>An investment in our common stock involves a high degree of risk.</p>

<b>We face intense competition in our markets.</b>
Our industry is highly competitive and we may not be able to maintain our market
position. Competitors with greater resources may develop superior products.

<b>Regulatory changes could materially affect our business.</b>
Changes in federal, state, or international regulations could increase our
compliance costs or restrict our operations. Material adverse effects on our
financial condition could result from stricter environmental regulations.

<b>Cybersecurity threats could disrupt our operations.</b>
We rely on information technology systems for business operations. A significant
cybersecurity breach could result in data loss, operational disruption, and
reputational damage.

<h3>Item 7. Management's Discussion and Analysis</h3>
<p>Revenue for fiscal year 2024 was $2.5 billion, up 12% from $2.23 billion.</p>
<p>Net income was $340 million compared to $290 million in the prior year.</p>
</body>
</html>
"""

SAMPLE_10K_DATA = {
    "report_metadata": {
        "target_company": "Acme Corporation",
        "cik": "0001234567",
        "filing_type": "10-K",
        "filing_date": "2024-03-15",
        "accession_number": "0001234567-24-000042",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/mock",
    },
    "risk_factors": [
        {
            "heading": "We face intense competition in our markets",
            "category": "MARKET",
            "severity": "HIGH",
            "key_quote": "Our industry is highly competitive and we may not be able to maintain our market position.",
            "source": "Item 1A, p. 15",
            "change_status": "UNCHANGED",
        },
        {
            "heading": "Regulatory changes could materially affect our business",
            "category": "REGULATORY",
            "severity": "HIGH",
            "key_quote": "Material adverse effects on our financial condition could result from stricter regulations.",
            "source": "Item 1A, p. 17",
            "change_status": "MODIFIED",
        },
    ],
    "financial_summary": {
        "revenue": {"current": 2_500_000_000, "prior": 2_230_000_000, "change_pct": 12.1},
        "net_income": {"current": 340_000_000, "prior": 290_000_000, "change_pct": 17.2},
    },
}


@pytest.fixture
def sample_10k_data() -> dict[str, Any]:
    """Provide sample 10-K filing data for testing."""
    return SAMPLE_10K_DATA.copy()


@pytest.fixture
def sample_filing_html() -> str:
    """Provide sample SEC filing HTML content."""
    return MOCK_FILING_PAGE


# =============================================================================
# Settings Override
# =============================================================================

@pytest.fixture
def test_settings(tmp_path: Path):
    """Provide test settings with temporary paths."""
    from src.config import Settings, get_settings

    # Clear the cached settings
    get_settings.cache_clear()

    settings = Settings(
        llm_api_base="http://localhost:8000/v1",
        llm_model_name="test-model",
        llm_api_key="test-key",
        parchi_relay_url="http://localhost:9222",
        skills_directory=str(tmp_path / "skills"),
        memory_store_path=str(tmp_path / "memory.json"),
        log_level="WARNING",
    )

    # Create the skills directory
    (tmp_path / "skills").mkdir(exist_ok=True)
    (tmp_path / "skills" / "references").mkdir(exist_ok=True)

    yield settings

    # Clean up cached settings
    get_settings.cache_clear()
