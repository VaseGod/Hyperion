---
title: Regulation S-K Reference
summary: >
  Key items from SEC Regulation S-K governing non-financial disclosure
  requirements in registration statements and periodic reports.
tags:
  - regulation
  - disclosure
  - sec
---

# Regulation S-K — Key Disclosure Items

This reference covers the Regulation S-K items most relevant to automated
compliance analysis of 10-K and 10-Q filings.

## Subpart 100 — Business

### Item 101: Description of Business

**Requirement:** Describe the general development of the business, its
segments, and the narrative description of the business during the most
recent fiscal year.

**Key Elements to Extract:**
- Principal products or services
- Distribution methods
- Status of new products or segments
- Competitive conditions
- Number of employees
- Environmental compliance costs
- Revenue breakdown by segment

**Compliance Check:** Ensure all material business segments are individually
described. A segment contributing >10% of revenue must be separately disclosed.

### Item 102: Description of Properties

**Requirement:** Describe the location and general character of principal
physical properties.

**Key Elements:**
- Material properties owned or leased
- Lease expiration dates for significant properties
- Capacity utilization information

### Item 103: Legal Proceedings

**Requirement:** Describe any material pending legal proceedings.

**Key Elements:**
- Nature of proceeding
- Date instituted
- Parties involved
- Relief sought
- Estimated financial exposure (if quantifiable)

**Compliance Check:** Proceedings involving governmental authorities regarding
environmental regulations must be disclosed if sanctions could exceed $300,000.

## Subpart 300 — Financial Information

### Item 303: Management's Discussion and Analysis (MD&A)

**Requirement:** Provide a narrative explanation of the financial statements
that enables investors to see the company through management's eyes.

**Key Elements to Extract:**
1. **Liquidity** — Known trends, demands, events that will materially affect
   the company's liquidity
2. **Capital Resources** — Material commitments for capital expenditures,
   expected sources of funds
3. **Results of Operations** — Revenue and expense analysis for each reported
   period, unusual or infrequent events
4. **Off-Balance Sheet Arrangements** — Any transactions with unconsolidated
   entities that may have material effects
5. **Critical Accounting Estimates** — Estimates requiring significant judgment

**Compliance Checks:**
- MD&A must cover at least 3 fiscal years for 10-K filings
- Known trends or uncertainties that will materially impact revenue must be disclosed
- Companies must discuss the impact of inflation if material

### Item 305: Quantitative and Qualitative Disclosures About Market Risk

**Requirement:** Provide quantitative and qualitative information about
the company's exposure to market risk.

**Key Elements:**
- Interest rate risk exposure
- Foreign currency risk
- Commodity price risk
- Sensitivity analysis or Value-at-Risk disclosures

## Subpart 500 — Registration Statement and Prospectus Provisions

### Item 503: Prospectus Summary and Risk Factors

**Requirement:** Where appropriate, provide a summary of the key aspects
of the offering. Provide a discussion of the most significant factors that
make the offering speculative or risky.

**Risk Factor Requirements:**
- Each risk factor must be **specific** to the issuer or the offering
- Generic risks that could apply to any company are insufficient
- Risk factors should be ordered by significance
- Each factor should include a clear heading summarizing the risk
- Quantitative context should be provided where possible

**Compliance Checks:**
- Risk factors must not be presented as an exhaustive list
- Mitigating factors may be discussed but must not undermine the risk description
- New risks identified since the prior filing should be clearly distinguishable

## Cross-Reference Matrix

| Filing Type | Required Items | Frequency |
|-------------|---------------|-----------|
| 10-K | 101, 102, 103, 303, 305, 503 | Annual |
| 10-Q | 303, 305 (condensed) | Quarterly |
| 8-K | Varies by event type | Event-driven |
| S-1 | All items (initial registration) | One-time |
