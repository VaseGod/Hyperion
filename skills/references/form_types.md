---
title: SEC Form Types Reference
summary: >
  Taxonomy of SEC filing form types with filing requirements, key extraction
  targets, and typical content structure.
tags:
  - sec
  - forms
  - taxonomy
---

# SEC Form Types — Filing Taxonomy

Reference document for the most commonly analyzed SEC filing types.

## Annual & Periodic Reports

### 10-K — Annual Report

**Filing Frequency:** Annual, within 60 days of fiscal year end (large accelerated filers)
**Filed By:** Public companies registered under the Securities Exchange Act
**Key Sections:**
- Part I: Business (Items 1-4)
- Part II: Financial Information (Items 5-9A)
- Part III: Directors and Officers (Items 10-14)
- Part IV: Exhibits and Financial Statement Schedules (Item 15)

**Primary Extraction Targets:**
- Item 1A: Risk Factors
- Item 7: Management's Discussion and Analysis
- Item 8: Financial Statements and Supplementary Data

**Amendments:** Filed as `10-K/A`. Always compare with original filing.

### 10-Q — Quarterly Report

**Filing Frequency:** Quarterly (Q1, Q2, Q3 only — Q4 covered by 10-K)
**Filed By:** Public companies
**Key Sections:**
- Part I: Financial Information (Items 1-4)
- Part II: Other Information (Items 1-6)

**Primary Extraction Targets:**
- Item 1: Condensed Financial Statements
- Item 2: MD&A (condensed version)
- Item 1A: Risk Factor Updates (changes from 10-K only)

**Note:** 10-Q filings are unaudited. Financial data should be flagged accordingly.

## Current Reports

### 8-K — Current Report

**Filing Frequency:** Within 4 business days of the triggering event
**Filed By:** Public companies when material events occur

**Triggering Events:**
| Item | Event Category |
|------|---------------|
| 1.01 | Entry into Material Agreement |
| 1.02 | Termination of Material Agreement |
| 2.01 | Completion of Acquisition or Disposition |
| 2.02 | Results of Operations and Financial Condition |
| 2.05 | Costs Associated with Exit or Disposal Activities |
| 2.06 | Material Impairments |
| 3.01 | Notice of Delisting |
| 4.01 | Changes in Certifying Accountant |
| 4.02 | Non-Reliance on Previously Issued Financial Statements |
| 5.02 | Departure/Appointment of Directors or Officers |
| 5.03 | Amendments to Articles of Incorporation or Bylaws |
| 7.01 | Regulation FD Disclosure |
| 8.01 | Other Events |
| 9.01 | Financial Statements and Exhibits |

**Critical 8-K Items for Compliance:**
- Item 4.02 triggers immediate red flag
- Item 5.02 requires tracking in officer change log
- Item 2.06 requires financial impact assessment

## Proxy & Registration Statements

### DEF 14A — Definitive Proxy Statement

**Filed By:** Companies soliciting shareholder votes
**Key Extraction Targets:**
- Executive compensation tables (Summary Compensation Table)
- Board of Directors composition
- Shareholder proposals
- Related party transactions
- Say-on-Pay voting results

### S-1 — Registration Statement (IPO)

**Filed By:** Companies registering securities for the first time
**Key Extraction Targets:**
- Complete business description
- Use of proceeds
- Risk factors (comprehensive initial set)
- Capitalization table
- Dilution analysis
- Management team backgrounds

## EDGAR Search Parameters

### CIK Lookup
- URL: `https://www.sec.gov/cgi-bin/browse-edgar?company={name}&CIK=&type=&dateb=&owner=include&count=40&search_text=&action=getcompany`
- The CIK is the primary identifier for all SEC filings

### Filing Search
- Base URL: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={form_type}&dateb=&owner=include&count=10`
- Replace `{cik}` with the company's CIK number
- Replace `{form_type}` with the desired form (e.g., `10-K`, `10-Q`, `8-K`)

### XBRL Data Access
- Interactive viewer: `https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik}&type={form_type}`
- XBRL JSON API: `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json`
  - CIK must be zero-padded to 10 digits

### Full-Text Search (EDGAR EFTS)
- URL: `https://efts.sec.gov/LATEST/search-index?q={query}&dateRange=custom&startdt={start}&enddt={end}&forms={form_type}`
