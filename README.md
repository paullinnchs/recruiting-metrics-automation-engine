# Recruiting Metrics & Workforce Revenue Intelligence Engine

**A Paul Linn Solutions (PLS) system that turns one client intake into one consolidated executive report, covering both recruiting performance and contingent-workforce revenue exposure.**

```
One Client Intake  ->  Validation  ->  Recruiting Analysis + Revenue Analysis  ->  One Consolidated Report
```

Recruiting operations and contingent-workforce billing are usually analyzed separately, in separate spreadsheets, by separate people. This engine takes one client's data — recruiting/ATS records plus billing/contract records — validates what's actually usable, runs both analyses, and produces one branded report that answers: **what's happening in recruiting, where is revenue leaking, and what should happen next.**

---

## How It Works

1. A client's data is organized into one intake folder (`client_intake/<client_id>/`)
2. `app/main.py` validates the intake — which files are present, which analyses that supports
3. Recruiting Tier 1 and Tier 2 analysis runs on whatever recruiting data is present
4. The Workforce Revenue Leak Workflow Sprint runs on whatever revenue data is present
5. Results are combined into one consolidated `.docx` and `.pdf` — Executive Summary, Data Coverage, Recruiting Performance, Revenue Leakage, Priority Findings, Recommended Actions, and Methodology/legal notes

If part of the intake is missing, that section is clearly labeled **unavailable** in the report rather than estimated or guessed — the engine never fabricates a value it doesn't have real data for. Any analysis area with sufficient data still runs and reports normally.

---

## Run a Client Analysis

```bash
python app/main.py client_intake/<client_id>
```

Example, using the included sample client:

```bash
python app/main.py client_intake/acme_staffing
```

This produces `Consolidated_Client_Report_<client_id>_<date>.docx` and `.pdf` in `outputs/reports/` — the two client-facing deliverables. A Markdown/JSON working copy and the individual module JSON outputs are also written for internal traceability, but are not positioned as client deliverables.

Individual modules remain directly runnable for development/testing:

```bash
python app/tier1_ats_agent.py
python app/tier2_crosssystem_agent.py
python app/leak_detection_agent.py
python app/leak_report_generator.py "Client Name"
```

---

## Intake Requirements

Each client gets one intake folder:

```
client_intake/<client_id>/
    intake_manifest.json          {"client_id": ..., "client_name": ...}
    recruiting/
        requisitions.json         required — Tier 1
        candidates.json           required — Tier 1
        applications.json         required — Tier 1
        offers.json                required — Tier 1
        sessions.json              optional — enables application completion rate
        hris_employees.json       required — Tier 2 (in addition to Tier 1 files)
        hris_performance.json     required — Tier 2
        survey_responses.json    required — Tier 2
        recruiting_config.json    optional — headcount/spend/funnel overrides
    revenue/
        billing_data.csv           required — revenue analysis
        rate_cards.csv              required — revenue analysis
        contracts.csv                required — revenue analysis
```

**Recruiting data** — Tier 1 needs requisitions, candidates, applications, and offers at minimum; `sessions.json` is optional and only affects the application completion rate metric. Tier 2 needs everything Tier 1 needs, plus HRIS employee, HRIS performance, and survey data.

**Revenue/commercial data** — billing/invoice history, timesheets (embedded in the billing records), rate cards, and active contracts/SOWs. All three files are required for revenue analysis to run.

**Missing data behavior** — if any required file for an analysis area is absent, that area is skipped and clearly marked "Unavailable" in the Data Coverage section of the report, along with exactly which file(s) are missing. Every other analysis area that *does* have sufficient data still runs and is fully reported. Nothing is estimated in place of missing data.

The exact required fields within each file are determined by the existing connector/calculation logic in `app/tier1_ats_agent.py`, `app/tier2_crosssystem_agent.py`, and `app/leak_detection_agent.py` — see those files' docstrings for the normalized schema each expects.

---

## Recruiting Performance Analysis

### What it solves

Recruiting teams often spend significant time exporting ATS data, calculating KPIs, maintaining spreadsheets, and interpreting whether changes actually require attention. This layer calculates operational metrics, compares results against configurable thresholds, and produces alerts and executive-ready reporting.

### Example signals

- Time to Fill increasing beyond threshold
- Offer Acceptance Rate declining
- Fill Rate falling below target
- First-year attrition rising
- Adverse impact flags requiring compliance review

Each alert is designed to answer three questions: **What is happening? Why does it matter? What should we do next?**

---

## Revenue Leakage Analysis — Workforce Revenue Leak Workflow Sprint

### What it solves

Revenue and margin can quietly leak when billing records, approved hours, rate cards, supplier relationships, and contract terms do not line up. This analysis provides a repeatable diagnostic workflow using client-provided billing/contract data.

### What the engine checks

Five defined categories:

- **Missed / incorrect markup** — billed rates that fall below applicable contracted rates
- **Stale rate card billing** — billing associated with expired rate-card terms
- **Off-contract / maverick spend** — spend without an approved contract or supplier match
- **Potential worker classification risk requiring review** — engagement patterns that may warrant human legal/compliance review; the engine does not make a legal classification determination
- **Unbilled / duplicate hours** — approved hours not invoiced or invoiced hours that exceed approved hours

Findings involving worker classification are explicitly presented as **potential risk requiring review**, not as legal or compliance determinations. This language is preserved unchanged in every generated report.

---

## Recruiting Metric Tiers

### Tier 1 — ATS-driven metrics

Designed for metrics that can be calculated from structured recruiting data with configurable alert thresholds.

| Metric | Example trigger / threshold |
|---|---|
| Time to fill | Role open beyond benchmark |
| Time to hire | Stage duration exceeds threshold |
| Source of hire | On hire |
| Sourcing channel effectiveness | Conversion below threshold |
| Sourcing channel cost | Cost above configured threshold |
| Applicants per opening | Volume below expected level |
| Selection ratio | Scheduled calculation |
| Offer acceptance rate | Rate below threshold |
| % open positions | Vacancy rate above threshold |
| Application completion rate | Completion below threshold |
| Fill rate | Rate below target |

### Tier 2 — Cross-system metrics

Designed for metrics requiring data joins or additional validation.

| Metric | Typical data sources | Human touchpoint |
|---|---|---|
| First-year attrition | HRIS + ATS | Validate classification/data completeness |
| Quality of hire | Performance + ATS | Validate performance inputs |
| Cost per hire | Finance + ATS | Confirm spend categories |
| Candidate experience | Survey + ATS | Review qualitative themes |
| Funnel effectiveness | ATS stages | Interpret drop-off patterns |
| Adverse impact | ATS outcomes + applicable demographic data | Compliance review required |
| Recruiter performance | ATS + HRIS + survey | Manager review |

### Tier 3 — Human/LLM-assisted metrics

Used where qualitative information or business definitions require interpretation rather than deterministic calculation alone. Requires a live survey platform connection — not currently exercised by the sample intake.

| Metric | Automated component | Human role |
|---|---|---|
| Hiring manager satisfaction | Survey collection/scoring | Review narrative themes |
| Candidate job satisfaction | Pulse collection | Review summarized feedback |
| Cost to OPL | Cost aggregation | Validate OPL definition |
| Time to productivity | Milestone tracking | Confirm milestone completion |
| Recruitment ROI | Cost aggregation | Define/validate productivity value |

---

## Architecture

```text
recruiting-metrics-automation-engine/
│
├── app/
│   ├── main.py                        # single entry point: intake -> analysis -> consolidated report
│   ├── client_intake.py                # intake validation + recruiting data loading
│   ├── consolidated_report_generator.py
│   ├── consolidated_report_template.js # renders the one client-facing docx
│   │
│   ├── ats_connector.py
│   ├── billing_connector.py
│   ├── briefing_agent.py
│   ├── hris_connector.py
│   ├── leak_detection_agent.py
│   ├── leak_report_generator.py
│   ├── report_docx_template.js
│   ├── survey_connector.py
│   ├── tier1_ats_agent.py
│   └── tier2_crosssystem_agent.py
│
├── client_intake/
│   └── acme_staffing/                  # sample client intake
│       ├── intake_manifest.json
│       ├── recruiting/
│       └── revenue/
│
├── config/
│   ├── connections.yaml
│   ├── leak_rules.yaml
│   └── thresholds.yaml
│
├── sample_data/
├── outputs/
├── screenshots/
├── automation_map.md
├── requirements.txt
└── README.md
```

`main.py` and `consolidated_report_generator.py` are orchestration only — they call the existing `calc_`/`check_` functions in `tier1_ats_agent.py`, `tier2_crosssystem_agent.py`, and `leak_detection_agent.py` directly rather than reimplementing any calculation.

---

## Automation, AI, and Human Review

This project intentionally uses different execution methods for different types of work:

- **Deterministic automation** for calculations, comparisons, routing, thresholds, and repeatable data checks
- **LLM-assisted analysis** where qualitative interpretation or business-readable summarization adds value
- **Human review** where context, accountability, compliance, or material business judgment is required

The objective is not to use AI for every step. It is to use the simplest reliable method for each step in the workflow.

---

## Configurable Logic

`config/thresholds.yaml` controls recruiting KPI alert thresholds.

`config/leak_rules.yaml` controls Revenue Leak detection thresholds and severity logic.

`client_intake/<client_id>/recruiting/recruiting_config.json` (optional) overrides headcount, recruiting spend, ad spend, and funnel stages per client, falling back to system defaults in `main.py` if omitted.

These settings allow the engine to be configured for different operating environments without rewriting the core workflow.

---

## Data Sources and Connectors

The repository includes connector modules and a configurable adapter pattern for structured data sources (`ats_connector.py`, `hris_connector.py`, `survey_connector.py`, `billing_connector.py`). The current prototype operates against file-based client intake; the same connectors are designed to support live production integrations with ATS, HRIS, finance/billing, and survey platforms as required by an implementation.

Production integrations depend on the target platform's available API, authentication model, permissions, and customer environment.

---

## Outputs

**Client-facing deliverables** (from `python app/main.py <intake-folder>`):

- `Consolidated_Client_Report_<client>_<date>.docx`
- `Consolidated_Client_Report_<client>_<date>.pdf`

**Internal / traceability only** (not positioned as client deliverables):

- `consolidated_report_<client>_<date>.json` — full combined data
- `consolidated_working_copy_<client>_<date>.md` — internal working copy
- Individual Tier 1 / Tier 2 / revenue-leak JSON outputs, for debugging a specific analysis area

---

## Stack

- **Language:** Python 3.11+
- **Data processing:** pandas / polars
- **HTTP / integrations:** httpx
- **LLM layer:** Anthropic Claude API where qualitative analysis is appropriate
- **Configuration:** YAML / JSON
- **Alerting:** Slack webhook / structured output
- **Reporting:** Markdown, JSON, DOCX/PDF workflow
- **Scheduling / orchestration:** can be deployed with cron, GitHub Actions, n8n, or another production orchestration layer

---

## Local Setup

```bash
git clone https://github.com/paullinnchs/recruiting-metrics-automation-engine
cd recruiting-metrics-automation-engine
pip install -r requirements.txt
npm install docx
```

The consolidated and revenue-leak DOCX/PDF generation uses Node.js (the `docx` package) and LibreOffice (headless PDF conversion). Configuration is handled through the files under `config/`. Copy `.env.example` to `.env` and fill in values for whichever integrations you're actively using.

Run the sample client end to end:

```bash
python app/main.py client_intake/acme_staffing
```

Sample data is included for local testing; customer data should never be committed to the public repository.

---

## Portfolio Context

This repository demonstrates how Paul Linn Solutions approaches operational systems:

**defined business problem -> structured inputs -> repeatable analysis -> prioritized output -> human action where appropriate**

Related PLS work includes candidate screening/shortlisting and customer health intelligence workflows.

---

*Built by Paul Linn Solutions — practical workflow automation and operational intelligence for recruiting, workforce technology, and customer operations.*
