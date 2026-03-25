"""
Dark Factory v2 — Mock Evaluation Environments
=================================================
WebArena-Infinity testing harness. Generates mock endpoints for:
1. Synthetic corporate intranet (Flask-based)
2. Synthetic SEC EDGAR database with sample filings

These mock environments allow safe, deterministic testing of the
Hermes/Parchi agent stack without hitting real financial systems.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from flask import Flask, jsonify, render_template_string, request

logger = logging.getLogger(__name__)


# =============================================================================
# Sample Data
# =============================================================================

MOCK_COMPANIES = [
    {
        "name": "Acme Corporation",
        "cik": "0001234567",
        "ticker": "ACME",
        "sic": "3674",
        "industry": "Electronic Components",
    },
    {
        "name": "Globex Industries",
        "cik": "0009876543",
        "ticker": "GLBX",
        "sic": "2834",
        "industry": "Pharmaceutical Preparations",
    },
    {
        "name": "Initech Systems",
        "cik": "0005551234",
        "ticker": "INTC",
        "sic": "7372",
        "industry": "Prepackaged Software",
    },
]

MOCK_FILINGS = {
    "0001234567": [
        {
            "form_type": "10-K",
            "filing_date": "2024-03-15",
            "accession": "0001234567-24-000042",
            "description": "Annual Report",
            "url": "/filing/0001234567-24-000042",
        },
        {
            "form_type": "10-Q",
            "filing_date": "2024-08-14",
            "accession": "0001234567-24-000098",
            "description": "Quarterly Report (Q2 2024)",
            "url": "/filing/0001234567-24-000098",
        },
        {
            "form_type": "8-K",
            "filing_date": "2024-06-01",
            "accession": "0001234567-24-000075",
            "description": "Current Report - Officer Change",
            "url": "/filing/0001234567-24-000075",
        },
    ],
    "0009876543": [
        {
            "form_type": "10-K",
            "filing_date": "2024-02-28",
            "accession": "0009876543-24-000011",
            "description": "Annual Report",
            "url": "/filing/0009876543-24-000011",
        },
    ],
}

MOCK_10K_CONTENT = """
<!DOCTYPE html>
<html>
<head><title>ACME CORPORATION - 10-K Annual Report</title></head>
<body>
<div class="filing-header">
    <h1>UNITED STATES SECURITIES AND EXCHANGE COMMISSION</h1>
    <h2>FORM 10-K</h2>
    <p><strong>ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE
    SECURITIES EXCHANGE ACT OF 1934</strong></p>
    <p>For the fiscal year ended December 31, 2024</p>
    <p>Commission File Number: 001-12345</p>
    <h2>ACME CORPORATION</h2>
    <p>CIK: 0001234567</p>
</div>

<div class="toc">
    <h3>TABLE OF CONTENTS</h3>
    <ul>
        <li><a href="#item1">Item 1. Business</a></li>
        <li><a href="#item1a">Item 1A. Risk Factors</a></li>
        <li><a href="#item7">Item 7. Management's Discussion and Analysis</a></li>
        <li><a href="#item8">Item 8. Financial Statements</a></li>
    </ul>
</div>

<div id="item1">
    <h3>Item 1. Business</h3>
    <p>Acme Corporation ("Acme" or the "Company") is a leading provider of
    advanced electronic components and semiconductor solutions. Founded in 1985,
    the Company operates in three primary segments: Consumer Electronics,
    Industrial Automation, and Automotive Technologies.</p>

    <p>As of December 31, 2024, the Company employed approximately 12,500 people
    worldwide, with operations in 15 countries.</p>

    <h4>Products and Services</h4>
    <p>The Company's principal products include microcontrollers, sensors,
    power management ICs, and connectivity modules. Revenue is derived from
    product sales (85%) and licensing/services (15%).</p>
</div>

<div id="item1a">
    <h3>Item 1A. Risk Factors</h3>
    <p>An investment in our common stock involves a high degree of risk.
    You should carefully consider the following risk factors.</p>

    <b>We face intense competition in our semiconductor markets.</b>
    <p>The semiconductor industry is intensely competitive. We compete with
    large multinational corporations that have substantially greater financial,
    technical, and marketing resources. Our inability to compete effectively
    could have a material adverse effect on our business, financial condition,
    and results of operations. During fiscal year 2024, competitive pricing
    pressure reduced our gross margins by approximately 2.3 percentage points.</p>

    <b>Global supply chain disruptions could materially impact manufacturing.</b>
    <p>Our manufacturing operations depend on a complex global supply chain for
    raw materials, specialized equipment, and third-party fabrication services.
    Geopolitical tensions, natural disasters, or pandemics could cause significant
    supply chain disruptions, leading to production delays and increased costs.</p>

    <b>Regulatory changes in international markets pose compliance risks.</b>
    <p>We operate in multiple jurisdictions with varying regulatory requirements.
    Changes in trade policies, export controls, environmental regulations, or tax
    laws could increase our compliance costs or restrict market access. The
    estimated additional compliance cost from recent EU regulations is $15 million
    annually.</p>

    <b>Cybersecurity vulnerabilities could result in data breaches.</b>
    <p>Our operations rely heavily on information technology infrastructure.
    A significant cybersecurity incident could result in the loss of proprietary
    technology, customer data, and business disruption. We invested $45 million
    in cybersecurity measures during fiscal year 2024.</p>
</div>

<div id="item7">
    <h3>Item 7. Management's Discussion and Analysis</h3>
    <h4>Results of Operations</h4>
    <p>Revenue for fiscal year 2024 was $2.50 billion, an increase of 12.1%
    from $2.23 billion in fiscal year 2023. The increase was primarily driven
    by strong demand in our Automotive Technologies segment.</p>

    <p>Net income for fiscal year 2024 was $340 million, compared to $290 million
    in the prior year, representing a 17.2% increase.</p>

    <p>Operating expenses were $1.85 billion, up from $1.68 billion, reflecting
    increased R&D investment of $180 million (up 22% YoY).</p>

    <h4>Liquidity and Capital Resources</h4>
    <p>Cash and cash equivalents at December 31, 2024 were $890 million.
    Operating cash flow was $520 million. Total debt was $1.2 billion with
    a debt-to-equity ratio of 0.45.</p>
</div>

<div id="item8">
    <h3>Item 8. Financial Statements</h3>
    <table border="1" cellpadding="5">
        <tr><th>Metric</th><th>FY 2024</th><th>FY 2023</th></tr>
        <tr><td>Revenue</td><td>$2,500,000,000</td><td>$2,230,000,000</td></tr>
        <tr><td>Cost of Revenue</td><td>$1,500,000,000</td><td>$1,340,000,000</td></tr>
        <tr><td>Gross Profit</td><td>$1,000,000,000</td><td>$890,000,000</td></tr>
        <tr><td>Operating Expenses</td><td>$1,850,000,000</td><td>$1,680,000,000</td></tr>
        <tr><td>Net Income</td><td>$340,000,000</td><td>$290,000,000</td></tr>
        <tr><td>Total Assets</td><td>$4,200,000,000</td><td>$3,800,000,000</td></tr>
        <tr><td>Total Liabilities</td><td>$2,100,000,000</td><td>$1,950,000,000</td></tr>
        <tr><td>Cash & Equivalents</td><td>$890,000,000</td><td>$720,000,000</td></tr>
        <tr><td>EPS (Basic)</td><td>$6.80</td><td>$5.80</td></tr>
        <tr><td>EPS (Diluted)</td><td>$6.72</td><td>$5.74</td></tr>
    </table>
</div>
</body>
</html>
"""

MOCK_8K_CONTENT = """
<!DOCTYPE html>
<html>
<body>
<h1>FORM 8-K — Current Report</h1>
<h2>ACME CORPORATION</h2>
<p>Date of Report: June 1, 2024</p>

<h3>Item 5.02 — Departure of Directors or Certain Officers</h3>
<p>On May 28, 2024, John Smith resigned as Chief Financial Officer of
Acme Corporation, effective June 15, 2024. Mr. Smith served as CFO since 2019.</p>
<p>On May 30, 2024, the Board of Directors appointed Sarah Chen as the new
Chief Financial Officer, effective June 16, 2024. Ms. Chen previously served
as VP of Finance at GlobalTech Inc.</p>
</body>
</html>
"""


# =============================================================================
# Mock EDGAR Application (Flask)
# =============================================================================

def create_mock_edgar_app() -> Flask:
    """
    Create a Flask application simulating SEC EDGAR's core endpoints.

    Routes:
        GET  /                          — EDGAR homepage
        GET  /cgi-bin/browse-edgar      — Company search
        GET  /cgi-bin/browse-edgar?CIK= — Filing list
        GET  /filing/<accession>        — Filing content
        GET  /api/xbrl/companyfacts/CIK<cik>.json — XBRL data
        GET  /status                    — Health check
    """
    app = Flask(__name__)

    @app.route("/")
    def home():
        return render_template_string("""
        <html>
        <head><title>Mock SEC EDGAR</title></head>
        <body>
            <h1>SEC EDGAR — Mock Environment</h1>
            <p>This is a synthetic EDGAR database for testing purposes.</p>
            <form action="/cgi-bin/browse-edgar" method="get">
                <label>Company Name:</label>
                <input type="text" name="company" id="company-search" />
                <input type="submit" value="Search" id="search-btn" />
            </form>
        </body>
        </html>
        """)

    @app.route("/cgi-bin/browse-edgar")
    def browse_edgar():
        company_query = request.args.get("company", "").lower()
        cik_query = request.args.get("CIK", "")
        form_type = request.args.get("type", "")

        # If CIK is provided, return filings for that company
        if cik_query:
            filings = MOCK_FILINGS.get(cik_query, [])
            if form_type:
                filings = [f for f in filings if f["form_type"] == form_type]

            filing_rows = ""
            for f in filings:
                filing_rows += f"""
                <tr>
                    <td>{f['form_type']}</td>
                    <td>{f['filing_date']}</td>
                    <td><a href="{f['url']}">{f['description']}</a></td>
                    <td>{f['accession']}</td>
                </tr>
                """

            return render_template_string("""
            <html><body>
            <h1>Filings for CIK {{ cik }}</h1>
            <table border="1" id="filing-table">
                <tr><th>Type</th><th>Date</th><th>Description</th><th>Accession</th></tr>
                {{ filing_rows | safe }}
            </table>
            </body></html>
            """, cik=cik_query, filing_rows=filing_rows)

        # Otherwise, search by company name
        results = [
            c for c in MOCK_COMPANIES
            if company_query in c["name"].lower()
        ]

        result_rows = ""
        for c in results:
            result_rows += f"""
            <tr>
                <td><a href="/cgi-bin/browse-edgar?CIK={c['cik']}">{c['name']}</a></td>
                <td>{c['cik']}</td>
                <td>{c['ticker']}</td>
                <td>{c['industry']}</td>
            </tr>
            """

        return render_template_string("""
        <html><body>
        <h1>EDGAR Company Search Results</h1>
        <table border="1" id="results-table">
            <tr><th>Company</th><th>CIK</th><th>Ticker</th><th>Industry</th></tr>
            {{ result_rows | safe }}
        </table>
        </body></html>
        """, result_rows=result_rows)

    @app.route("/filing/<accession>")
    def filing_detail(accession: str):
        # Return appropriate mock content based on the filing type
        if "000042" in accession:
            return MOCK_10K_CONTENT
        elif "000075" in accession:
            return MOCK_8K_CONTENT
        else:
            return render_template_string("""
            <html><body>
            <h1>Filing: {{ accession }}</h1>
            <p>Mock filing content for accession number {{ accession }}.</p>
            </body></html>
            """, accession=accession)

    @app.route("/api/xbrl/companyfacts/CIK<cik>.json")
    def xbrl_facts(cik: str):
        return jsonify({
            "cik": int(cik),
            "entityName": next(
                (c["name"] for c in MOCK_COMPANIES if c["cik"].lstrip("0") == cik.lstrip("0")),
                "Unknown"
            ),
            "facts": {
                "us-gaap": {
                    "Revenue": {
                        "units": {"USD": [
                            {"val": 2_500_000_000, "fy": 2024, "form": "10-K"},
                            {"val": 2_230_000_000, "fy": 2023, "form": "10-K"},
                        ]},
                    },
                    "NetIncomeLoss": {
                        "units": {"USD": [
                            {"val": 340_000_000, "fy": 2024, "form": "10-K"},
                            {"val": 290_000_000, "fy": 2023, "form": "10-K"},
                        ]},
                    },
                },
            },
        })

    @app.route("/status")
    def status():
        return jsonify({"status": "healthy", "environment": "mock", "timestamp": datetime.utcnow().isoformat()})

    return app


# =============================================================================
# Mock Corporate Intranet Application
# =============================================================================

def create_mock_intranet_app() -> Flask:
    """
    Create a Flask application simulating a corporate intranet with
    compliance dashboards and internal filing repositories.

    Routes:
        GET /                    — Intranet homepage
        GET /compliance/dashboard — Compliance status overview
        GET /compliance/reports   — Compliance report archive
        GET /compliance/alerts    — Active compliance alerts
    """
    app = Flask(__name__)

    @app.route("/")
    def home():
        return render_template_string("""
        <html><body>
        <h1>Acme Corp — Internal Compliance Portal</h1>
        <nav>
            <ul>
                <li><a href="/compliance/dashboard" id="nav-dashboard">Dashboard</a></li>
                <li><a href="/compliance/reports" id="nav-reports">Reports</a></li>
                <li><a href="/compliance/alerts" id="nav-alerts">Alerts</a></li>
            </ul>
        </nav>
        </body></html>
        """)

    @app.route("/compliance/dashboard")
    def dashboard():
        return render_template_string("""
        <html><body>
        <h1>Compliance Dashboard</h1>
        <div class="metrics">
            <div class="metric" id="metric-filings">
                <h3>Filings This Quarter</h3>
                <span class="value">7</span>
                <span class="status ok">All On Time</span>
            </div>
            <div class="metric" id="metric-risks">
                <h3>Active Risk Factors</h3>
                <span class="value">23</span>
                <span class="status warning">3 New</span>
            </div>
            <div class="metric" id="metric-alerts">
                <h3>Open Alerts</h3>
                <span class="value">2</span>
                <span class="status critical">1 Critical</span>
            </div>
        </div>
        <table id="recent-activities">
            <tr><th>Date</th><th>Activity</th><th>Status</th></tr>
            <tr><td>2024-08-14</td><td>10-Q Q2 Filed</td><td>Complete</td></tr>
            <tr><td>2024-06-01</td><td>8-K Officer Change</td><td>Complete</td></tr>
            <tr><td>2024-03-15</td><td>10-K Annual Filed</td><td>Complete</td></tr>
        </table>
        </body></html>
        """)

    @app.route("/compliance/reports")
    def reports():
        return jsonify({
            "reports": [
                {
                    "id": "RPT-2024-001",
                    "title": "Q2 2024 Compliance Review",
                    "date": "2024-08-20",
                    "status": "approved",
                    "risk_count": 23,
                    "flags": 2,
                },
                {
                    "id": "RPT-2024-002",
                    "title": "Annual Risk Assessment 2024",
                    "date": "2024-04-01",
                    "status": "approved",
                    "risk_count": 18,
                    "flags": 1,
                },
            ]
        })

    @app.route("/compliance/alerts")
    def alerts():
        return jsonify({
            "alerts": [
                {
                    "id": "ALT-001",
                    "severity": "CRITICAL",
                    "title": "CFO Transition — Enhanced Monitoring Required",
                    "description": "John Smith resigned as CFO effective June 15. Sarah Chen appointed as successor.",
                    "created_at": "2024-06-01",
                    "status": "open",
                },
                {
                    "id": "ALT-002",
                    "severity": "WARNING",
                    "title": "New EU Regulation Compliance Gap",
                    "description": "EU Digital Services Act requirements not yet fully implemented. Estimated cost: $15M.",
                    "created_at": "2024-07-15",
                    "status": "in_progress",
                },
            ]
        })

    return app


# =============================================================================
# Server Lifecycle Management
# =============================================================================

@dataclass
class MockServer:
    """Manages a Flask mock server running in a background thread."""
    app: Flask
    host: str = "127.0.0.1"
    port: int = 0
    _thread: Optional[threading.Thread] = field(default=None, repr=False)
    _running: bool = False

    def start(self) -> str:
        """Start the mock server and return its base URL."""
        from werkzeug.serving import make_server

        server = make_server(self.host, self.port, self.app)
        self.port = server.socket.getsockname()[1]  # Get assigned port

        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()
        self._running = True

        base_url = f"http://{self.host}:{self.port}"
        logger.info("Mock server started at %s", base_url)

        # Wait briefly for server to be ready
        time.sleep(0.2)
        return base_url

    def stop(self) -> None:
        """Stop the mock server."""
        self._running = False
        logger.info("Mock server stopped")


def start_mock_environment() -> dict[str, MockServer]:
    """
    Start both mock servers (EDGAR + Intranet) and return their details.

    Returns:
        Dictionary with 'edgar' and 'intranet' MockServer instances.
    """
    edgar_server = MockServer(app=create_mock_edgar_app())
    intranet_server = MockServer(app=create_mock_intranet_app())

    edgar_url = edgar_server.start()
    intranet_url = intranet_server.start()

    logger.info("Mock EDGAR: %s", edgar_url)
    logger.info("Mock Intranet: %s", intranet_url)

    return {
        "edgar": edgar_server,
        "intranet": intranet_server,
    }


def stop_mock_environment(servers: dict[str, MockServer]) -> None:
    """Stop all mock servers."""
    for name, server in servers.items():
        server.stop()
        logger.info("Stopped %s server", name)
