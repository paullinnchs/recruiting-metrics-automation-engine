# Recruiting Metrics & Workforce Revenue Intelligence Engine

**A Paul Linn Solutions (PLS) workflow automation prototype for recruiting operations and contingent workforce revenue intelligence.**

This repository contains two related operational modules:

1. **Workforce Revenue Leak Audit** — analyzes workforce billing, timesheets, rate cards, and contracts/SOWs to surface potential revenue leakage and prioritize findings by estimated financial exposure.
2. **Recruiting Metrics Intelligence** — calculates recruiting KPIs, evaluates configurable thresholds, and turns operational signals into business-readable alerts and reporting.

The goal is straightforward: take operational data that normally lives across spreadsheets and systems, standardize it, run repeatable checks, and produce clear findings that tell an operator **what is happening, why it matters, and what should happen next**.

---

## Module 1 — Workforce Revenue Leak Audit

### What it solves

Revenue and margin can quietly leak when billing records, approved hours, rate cards, supplier relationships, and contract terms do not line up. Manually comparing those sources is time-consuming and easy to defer.

The Revenue Leak module provides a repeatable diagnostic workflow using client-provided data.

### Standard inputs

- Billing / invoice history
- Timesheets for the same period
- Rate cards
- Active contracts / SOWs
- Optional ATS export of open requisitions for additional revenue-risk context

### What the engine checks

The current module evaluates five defined categories:

- **Missed / incorrect markup** — billed rates that fall below applicable contracted rates
- **Stale rate card billing** — billing associated with expired rate-card terms
- **Off-contract / maverick spend** — spend without an approved contract or supplier match
- **Potential worker classification risk requiring review** — engagement patterns that may warrant human legal/compliance review; the engine does not make a legal classification determination
- **Unbilled / duplicate hours** — approved hours not invoiced or invoiced hours that exceed approved hours

### Workflow

```text
Client files
    ↓
Data normalization and validation
    ↓
Configurable revenue-leak rules
    ↓
Leak detection engine
    ↓
Prioritized findings + estimated financial exposure
    ↓
Human validation
    ↓
Branded client report + recommended next actions
```

### Output

The audit produces a prioritized report containing:

- Total estimated financial exposure identified
- Findings by leak category
- Estimated dollar impact by finding
- Severity / prioritization
- Supporting explanation
- Recommended operational next action

Findings involving worker classification are explicitly presented as **potential risk requiring review**, not as legal or compliance determinations.

### Core files

- `app/billing_connector.py` — loads and normalizes billing, timesheet, rate-card, and contract data
- `app/leak_detection_agent.py` — executes the defined revenue-leak checks
- `app/leak_report_generator.py` — generates the working report and branded output
- `app/report_docx_template.js` — branded DOCX report generation
- `config/leak_rules.yaml` — configurable detection thresholds
- `config/connections.yaml` — source/file connection configuration

---

## Module 2 — Recruiting Metrics Intelligence

### What it solves

Recruiting teams often spend significant time exporting ATS data, calculating KPIs, maintaining spreadsheets, and interpreting whether changes actually require attention.

This module demonstrates a repeatable recruiting-intelligence layer that calculates operational metrics, compares results against configurable thresholds, and produces alerts and executive-ready reporting.

### Example signals

- Time to Fill increasing beyond threshold
- Time to Hire increasing
- Offer Acceptance Rate declining
- Fill Rate falling below target
- Application Completion Rate declining
- Recruiter workload imbalance
- Sourcing performance deterioration

### Example business output

> **Recruiting Metrics Alert — Weekly Snapshot**
>
> **2 issues need attention.**
>
> **Offer Acceptance Rate below threshold**  
> **Business Impact:** Hiring goals may be delayed and recent declined offers may indicate compensation, process, or candidate-experience issues.  
> **Recommended Action:** Review declined offers and identify recurring patterns.
>
> **Fill Rate below target**  
> **Business Impact:** Open positions are not being filled at the expected rate, potentially affecting revenue, service delivery, and recruiter capacity.  
> **Recommended Action:** Review aging requisitions, funnel conversion, and recruiter workload.

Each alert is designed to answer three questions: **What is happening? Why does it matter? What should we do next?**

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

Used where qualitative information or business definitions require interpretation rather than deterministic calculation alone.

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

These settings allow the engine to be configured for different operating environments without rewriting the core workflow.

---

## Data Sources and Connectors

The repository includes connector modules and a configurable adapter pattern for structured data sources. The current prototype can operate against configured/sample data and is designed to support production integrations with ATS, HRIS, finance/billing, survey, and other operational systems as required by an implementation.

Production integrations depend on the target platform's available API, authentication model, permissions, and customer environment.

---

## Outputs

Depending on the module and configuration, outputs can include:

- Revenue Leak findings and estimated exposure
- Branded Workforce Revenue Leak report
- Recruiting metric reports
- Threshold alerts
- Business-readable recommendations
- Markdown / JSON output for downstream reporting
- Optional Slack notifications

---

## Stack

- **Language:** Python 3.11+
- **Data processing:** pandas / polars
- **HTTP / integrations:** httpx
- **LLM layer:** Anthropic Claude API where qualitative analysis is appropriate
- **Configuration:** YAML
- **Alerting:** Slack webhook / structured output
- **Reporting:** Markdown, JSON, DOCX/PDF workflow
- **Scheduling / orchestration:** can be deployed with cron, GitHub Actions, n8n, or another production orchestration layer

---

## Local Setup

```bash
git clone https://github.com/paullinnchs/recruiting-metrics-automation-engine
cd recruiting-metrics-automation-engine
pip install -r requirements.txt
```

The branded Revenue Leak DOCX report generator also uses Node.js and the `docx` package:

```bash
npm install docx
```

Configuration is handled through the files under `config/`. Sample data is included for local testing; customer data should never be committed to the public repository.

---

## Portfolio Context

This repository demonstrates how Paul Linn Solutions approaches operational systems:

**defined business problem → structured inputs → repeatable analysis → prioritized output → human action where appropriate**

Related PLS work includes candidate screening/shortlisting and customer health intelligence workflows.

---

*Built by Paul Linn Solutions — practical workflow automation and operational intelligence for recruiting, workforce technology, and customer operations.*