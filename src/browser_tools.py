"""
Dark Factory v2 — Browser Tools (Parchi Integration)
======================================================
Integration layer connecting the Hermes Agent to the Parchi Relay Daemon.
Exposes browser automation commands as agent tools for navigating financial
portals, extracting content, and interacting with web-based SEC databases.

Each tool function communicates with the Parchi Relay Daemon via HTTP and
returns structured results suitable for the LLM's consumption.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Parchi Relay Client
# =============================================================================

class ParchiRelayClient:
    """
    HTTP client for the Parchi Relay Daemon. Sends browser automation
    commands and receives structured responses.

    The relay daemon exposes a REST API for controlling a headless browser:
        POST /navigate    — Navigate to a URL
        POST /content     — Extract page content
        POST /click       — Click an element by selector
        POST /fill        — Fill a form field
        POST /screenshot  — Take a page screenshot
        GET  /status      — Check relay daemon health
    """

    def __init__(self, relay_url: str, timeout: int = 30):
        self._base_url = relay_url.rstrip("/")
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a POST request to the relay daemon."""
        url = urljoin(self._base_url + "/", endpoint.lstrip("/"))
        try:
            response = self._client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            return {
                "success": False,
                "error": f"Cannot connect to Parchi Relay at {self._base_url}. "
                         f"Ensure the daemon is running.",
            }
        except httpx.HTTPStatusError as exc:
            return {
                "success": False,
                "error": f"Relay returned HTTP {exc.response.status_code}: {exc.response.text[:500]}",
            }
        except Exception as exc:
            return {"success": False, "error": f"Relay request failed: {exc}"}

    def _get(self, endpoint: str) -> dict[str, Any]:
        """Send a GET request to the relay daemon."""
        url = urljoin(self._base_url + "/", endpoint.lstrip("/"))
        try:
            response = self._client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            return {"success": False, "error": f"Relay GET failed: {exc}"}

    def navigate(self, url: str, wait_for: Optional[str] = None) -> dict[str, Any]:
        """Navigate the browser to a URL."""
        payload: dict[str, Any] = {"url": url}
        if wait_for:
            payload["wait_for"] = wait_for
        return self._post("/navigate", payload)

    def get_content(self, selector: Optional[str] = None, content_type: str = "text") -> dict[str, Any]:
        """Extract content from the current page."""
        payload: dict[str, Any] = {"content_type": content_type}
        if selector:
            payload["selector"] = selector
        return self._post("/content", payload)

    def click(self, selector: str) -> dict[str, Any]:
        """Click an element on the page."""
        return self._post("/click", {"selector": selector})

    def fill(self, selector: str, value: str) -> dict[str, Any]:
        """Fill a form field with a value."""
        return self._post("/fill", {"selector": selector, "value": value})

    def screenshot(self, full_page: bool = False) -> dict[str, Any]:
        """Take a screenshot of the current page."""
        return self._post("/screenshot", {"full_page": full_page})

    def health_check(self) -> dict[str, Any]:
        """Check the relay daemon's health status."""
        return self._get("/status")

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


# =============================================================================
# SEC-Specific Extraction Utilities
# =============================================================================

def extract_risk_factors_from_html(html_content: str) -> list[dict[str, str]]:
    """
    Parse risk factors from SEC filing HTML content.

    Looks for common patterns in 10-K/10-Q filings:
    - Item 1A. Risk Factors sections
    - Bold-prefixed risk factor headings
    - Enumerated or bulleted risk items

    Args:
        html_content: Raw HTML or text content from a filing page.

    Returns:
        List of dicts with 'heading' and 'description' keys.
    """
    risk_factors: list[dict[str, str]] = []

    # Pattern: bold or strong tags followed by description text
    # Common in SEC filings for risk factor headers
    heading_pattern = re.compile(
        r"(?:<b>|<strong>|<font[^>]*><b>)\s*(.+?)\s*(?:</b>|</strong>|</b></font>)"
        r"\s*[.\-—]?\s*(.*?)(?=(?:<b>|<strong>|<font[^>]*><b>)|$)",
        re.IGNORECASE | re.DOTALL,
    )

    matches = heading_pattern.findall(html_content)
    for heading, description in matches:
        # Clean HTML tags from extracted text
        clean_heading = re.sub(r"<[^>]+>", "", heading).strip()
        clean_desc = re.sub(r"<[^>]+>", "", description).strip()
        if clean_heading and len(clean_heading) > 10:
            risk_factors.append({
                "heading": clean_heading[:200],
                "description": clean_desc[:1000],
            })

    # Fallback: look for plain text patterns (e.g., "Risk Factor:" prefix)
    if not risk_factors:
        plain_pattern = re.compile(
            r"(?:^|\n)\s*(?:•|\*|\d+\.)\s*(.+?)(?:\n\s*\n|\n(?=\s*(?:•|\*|\d+\.)))",
            re.MULTILINE,
        )
        for match in plain_pattern.finditer(html_content):
            text = match.group(1).strip()
            if len(text) > 20:
                risk_factors.append({
                    "heading": text[:200],
                    "description": "",
                })

    return risk_factors


# =============================================================================
# Browser Toolkit (Agent Tool Interface)
# =============================================================================

class BrowserToolkit:
    """
    Wraps the Parchi Relay Client into HermesAgent-compatible tool definitions.
    Each public method corresponds to a tool the agent can invoke.
    """

    def __init__(self, relay_url: str, timeout: int = 30):
        self._client = ParchiRelayClient(relay_url, timeout)

    # ── Tool Handlers ─────────────────────────────────────────────────────

    def navigate_to_url(self, url: str, wait_for: str = "") -> str:
        """Navigate the browser to a specified URL."""
        result = self._client.navigate(url, wait_for=wait_for or None)
        if result.get("success", False):
            return f"Successfully navigated to: {url}"
        return f"Navigation failed: {result.get('error', 'Unknown error')}"

    def extract_page_content(self, selector: str = "", content_type: str = "text") -> str:
        """
        Extract content from the current page.

        Args:
            selector: CSS selector to target specific elements. Empty = full page.
            content_type: 'text', 'html', or 'links'.
        """
        result = self._client.get_content(
            selector=selector or None,
            content_type=content_type,
        )
        if result.get("success", False):
            content = result.get("content", "")
            # Truncate very long content to preserve context window
            if len(content) > 10000:
                return content[:10000] + "\n\n[... content truncated at 10,000 chars ...]"
            return content
        return f"Content extraction failed: {result.get('error', 'Unknown error')}"

    def click_element(self, selector: str) -> str:
        """Click an element on the current page by CSS selector."""
        result = self._client.click(selector)
        if result.get("success", False):
            return f"Clicked element: {selector}"
        return f"Click failed: {result.get('error', 'Unknown error')}"

    def fill_form_field(self, selector: str, value: str) -> str:
        """Fill a form field identified by CSS selector with the given value."""
        result = self._client.fill(selector, value)
        if result.get("success", False):
            return f"Filled '{selector}' with value."
        return f"Fill failed: {result.get('error', 'Unknown error')}"

    def extract_risk_factors(self, filing_url: str = "") -> str:
        """
        Extract risk factors from an SEC filing page.

        If filing_url is provided, navigates to it first.
        Parses the page content for Item 1A risk factor patterns.
        """
        # Navigate if a URL is provided
        if filing_url:
            nav_result = self._client.navigate(filing_url)
            if not nav_result.get("success", False):
                return f"Failed to navigate to filing: {nav_result.get('error', 'Unknown error')}"

        # Extract the page HTML
        content_result = self._client.get_content(content_type="html")
        if not content_result.get("success", False):
            return f"Failed to extract page content: {content_result.get('error', 'Unknown error')}"

        html = content_result.get("content", "")
        risk_factors = extract_risk_factors_from_html(html)

        if not risk_factors:
            return "No risk factors found on this page. The page may not contain Item 1A content."

        # Format for LLM consumption
        output_lines = [f"Found {len(risk_factors)} risk factor(s):\n"]
        for i, rf in enumerate(risk_factors, 1):
            output_lines.append(f"### Risk Factor {i}")
            output_lines.append(f"**{rf['heading']}**")
            if rf["description"]:
                output_lines.append(rf["description"][:500])
            output_lines.append("")

        return "\n".join(output_lines)

    def screenshot_page(self, full_page: bool = False) -> str:
        """Take a screenshot of the current browser page."""
        result = self._client.screenshot(full_page=full_page)
        if result.get("success", False):
            path = result.get("path", "screenshot saved")
            return f"Screenshot saved: {path}"
        return f"Screenshot failed: {result.get('error', 'Unknown error')}"

    # ── Tool Definitions for HermesAgent ──────────────────────────────────

    def get_tool_definitions(self) -> list:
        """
        Generate HermesAgent-compatible ToolDefinition objects for all
        browser tools.
        """
        from src.hermes_agent import ToolDefinition

        return [
            ToolDefinition(
                name="navigate_to_url",
                description=(
                    "Navigate the browser to a specified URL. Use this to visit "
                    "SEC EDGAR pages, corporate websites, or financial portals."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to navigate to.",
                        },
                        "wait_for": {
                            "type": "string",
                            "description": "Optional CSS selector to wait for before returning.",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.navigate_to_url,
            ),
            ToolDefinition(
                name="extract_page_content",
                description=(
                    "Extract text or HTML content from the current browser page. "
                    "Optionally target specific elements with a CSS selector."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "CSS selector to target. Empty for full page.",
                        },
                        "content_type": {
                            "type": "string",
                            "enum": ["text", "html", "links"],
                            "description": "Type of content to extract.",
                        },
                    },
                },
                handler=self.extract_page_content,
            ),
            ToolDefinition(
                name="click_element",
                description="Click an element on the current page identified by CSS selector.",
                parameters={
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "CSS selector of the element to click.",
                        },
                    },
                    "required": ["selector"],
                },
                handler=self.click_element,
            ),
            ToolDefinition(
                name="fill_form_field",
                description=(
                    "Fill a form field on the current page. Use for search forms, "
                    "login fields, or EDGAR company search inputs."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "CSS selector of the form field.",
                        },
                        "value": {
                            "type": "string",
                            "description": "Value to enter into the field.",
                        },
                    },
                    "required": ["selector", "value"],
                },
                handler=self.fill_form_field,
            ),
            ToolDefinition(
                name="extract_risk_factors",
                description=(
                    "Extract risk factors from an SEC filing page (Item 1A). "
                    "Navigates to the filing URL if provided, then parses the "
                    "page for structured risk factor data."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "filing_url": {
                            "type": "string",
                            "description": "URL of the SEC filing page. If empty, uses the current page.",
                        },
                    },
                },
                handler=self.extract_risk_factors,
            ),
            ToolDefinition(
                name="screenshot_page",
                description="Take a screenshot of the current browser page for visual inspection.",
                parameters={
                    "type": "object",
                    "properties": {
                        "full_page": {
                            "type": "boolean",
                            "description": "If true, capture the entire scrollable page.",
                        },
                    },
                },
                handler=self.screenshot_page,
            ),
        ]
