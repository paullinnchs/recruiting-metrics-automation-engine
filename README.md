# recruiting-metrics-automation-engine

**Part of the [AI Operator Lab](https://github.com/paullinnchs) portfolio by Paul Linn Solutions (PLS)**

---

An agentic workflow system that automates the collection, calculation, alerting, and reporting of the 23 core recruiting metrics. Designed for talent acquisition teams and HR operators who want to move from manual spreadsheet tracking to a fully automated, always-on intelligence layer across their recruiting function.

This engine connects to your ATS, HRIS, survey tools, and ad platforms — computes metrics on a schedule — and delivers alerts, dashboards, and briefings without a human touching a spreadsheet.

---

## What this solves

Most TA teams track recruiting metrics manually: exporting ATS reports, pasting into Excel, building pivot tables. It takes hours, happens infrequently, and produces stale data. This engine replaces that loop with:

- **Always-on data collection** via API connectors to ATS, HRIS, and ad platforms
- **Automated calculation** of all 23 AIHR-standard recruiting metrics
- **Proactive alerting** when metrics cross defined thresholds
- **Auto-generated briefings** delivered on a schedule to TA leaders and HMs
- **An executive Revenue-at-Risk layer** that connects recruiting lag to business cost

---

## Architecture

```
recruiting-metrics-automation-engine/
│
├── app/                                  # Core workflow automation and connector logic
│   ├── tier1_ats_agent.py               # Fully automatable ATS-only recruiting metrics
│   ├── tier2_crosssystem_agent.py       # Cross-system metrics requiring ATS + HRIS data joins
│   ├── briefing_agent.py                # Executive briefing and reporting intelligence layer
│   ├── ats_connector.py                 # Connector for ATS API integrations (Greenhouse, Lever, iCIMS)
│   ├── hris_connector.py                # Connector for HRIS platforms (Workday, BambooHR, Rippling)
│   └── survey_connector.py              # Survey integrations for candidate and hiring manager feedback
│
├── config/                              # Configurable system logic and API connection settings
│   ├── thresholds.yaml                 # Alert thresholds for KPI monitoring and anomaly detection
│   └── connections.yaml               # API endpoints and connection configuration (no secrets stored)
│
├── sample_data/                         # Mock ATS and recruiting data for local testing and development
│   └── sample_ats_data.json           # Sample candidate, requisition, and pipeline data
│
├── automation_map.md                    # Workflow automation architecture and metric mapping framework
├── .env.example                        # Public environment variable template (safe for GitHub)
├── .gitignore                          # Prevents sensitive files from being committed
├── requirements.txt                    # Python dependencies required for project execution
└── README.md                           # Project overview, architecture, setup instructions, and business case
```

---

## Metric tiers

### Tier 1 — Fully automatable (ATS-only)
Agent queries ATS API on schedule. No human input required.

| # | Metric | Trigger | Alert condition |
|---|--------|---------|-----------------|
| 1 | Time to fill | Daily | Role open > benchmark days |
| 2 | Time to hire | Daily | Stage gap > 5 days |
| 3 | Source of hire | On hire | — |
| 4 | Sourcing channel effectiveness | Weekly | Conversion < 2% |
| 5 | Sourcing channel cost | Weekly | CPH > $X threshold |
| 10 | Applicants per opening | Daily | < 10 applicants after 7 days |
| 11 | Selection ratio | Weekly | — |
| 14 | Offer acceptance rate | On offer outcome | OAR drops below 80% |
| 15 | % open positions | Daily | Vacancy rate > 10% |
| 16 | Application completion rate | Weekly | Completion < 60% |
| 22 | Fill rate | Weekly | Fill rate < target % |

### Tier 2 — High automation (ATS + HRIS join)
Agent joins data across systems. Results auto-published. Human reviews anomalies.

| # | Metric | Systems joined | Human touchpoint |
|---|--------|---------------|-----------------|
| 6 | First-year attrition | HRIS + ATS | Review managed vs. unmanaged classification |
| 7 | Quality of hire | HRIS perf + ATS | Validate perf data completeness |
| 12 | Cost per hire | Finance/ERP + ATS | Confirm spend categories |
| 13 | Candidate experience | Survey + ATS | Review open-text themes |
| 17 | Recruitment funnel effectiveness | ATS stages | Interpret drop-off patterns |
| 20 | Adverse impact | ATS demographics + outcomes | Compliance review required |
| 21 | Recruiter performance | ATS + HRIS + survey | Manager scorecard review |

### Tier 3 — Partial automation (survey + LLM layer)
Agent collects and computes. LLM summarizes qualitative data. Human interprets.

| # | Metric | Automation limit | What human does |
|---|--------|-----------------|-----------------|
| 8 | Hiring manager satisfaction | Survey auto-sent + scored | Reviews narrative themes |
| 9 | Candidate job satisfaction | 30/60/90 day pulse auto-sent | Reviews LLM summary |
| 18 | Cost to OPL | Cost aggregation automated | Validates OPL date definition |
| 19 | Time to productivity | Milestone tracking automated | Confirms milestone completion |
| 23 | Recruitment ROI | Cost inputs automated | Defines productivity value |

---

## Agent behaviors

### `tier1_ats_agent.py`
- Runs on cron (daily or weekly depending on metric)
- Queries ATS REST API for raw stage/status data
- Computes all Tier 1 metrics
- Writes results to `outputs/reports/`
- Publishes threshold alerts to `outputs/alerts/`
- Optionally posts to Slack webhook

### `tier2_crosssystem_agent.py`
- Pulls from ATS + HRIS connectors
- Joins on employee ID
- Computes Tier 2 metrics
- Flags anomalies (statistical outliers, adverse impact triggers)
- Generates structured JSON output for dashboard consumption

### `tier3_survey_agent.py`
- Triggers surveys via Typeform/Qualtrics API on ATS events (hire, stage complete)
- Collects responses
- Sends open-text responses to LLM for theme extraction
- Computes NPS / satisfaction scores
- Produces human-review summary in Markdown

### `briefing_agent.py`
- Runs weekly (Fridays, configurable)
- Aggregates outputs from all three tier agents
- Generates an executive TA briefing:
  - Pipeline health snapshot
  - Metric alerts this week
  - Top funnel bottlenecks
  - Recruiter performance summary
  - Sourcing channel ROI
- Output: Markdown briefing + JSON payload

---

## Configurable thresholds (`config/thresholds.yaml`)

```yaml
time_to_fill:
  warning_days: 30
  critical_days: 45

time_to_hire:
  warning_days: 20
  critical_days: 30

offer_acceptance_rate:
  warning_pct: 85
  critical_pct: 75

application_completion_rate:
  warning_pct: 65
  critical_pct: 50

fill_rate:
  target_pct: 80
  warning_pct: 70

vacancy_rate:
  warning_pct: 10
  critical_pct: 15

first_year_attrition:
  warning_pct: 15
  critical_pct: 25
```

All thresholds are overridable per department, role type, or seniority band.

---

## Connectors

The engine uses a generic adapter pattern. Each connector implements the same interface:

```python
class BaseConnector:
    def authenticate(self) -> bool: ...
    def get_requisitions(self, since: date) -> list[dict]: ...
    def get_candidates(self, req_id: str) -> list[dict]: ...
    def get_hires(self, since: date) -> list[dict]: ...
    def get_stage_history(self, candidate_id: str) -> list[dict]: ...
```

Supported ATS platforms: Greenhouse, Lever, Workday Recruiting, iCIMS, Jobvite, generic REST (configurable)

Supported HRIS platforms: Rippling, BambooHR, Workday HCM, ADP (via API), generic REST

---

## Outputs

### Weekly TA Report (auto-generated Markdown)
```
Week of [DATE] — Recruiting Metrics Summary

PIPELINE HEALTH
  Open reqs:           47
  Avg time to fill:    28 days  ⚠ (benchmark: 25)
  Fill rate (MTD):     73%      ⚠ (target: 80%)

SOURCING
  Top channel:         LinkedIn (42% of hires)
  Lowest CPH:          Employee referral ($1,240)
  Highest CPH:         Agency ($8,900)  ⚠

CANDIDATE FLOW
  Applications this week:  312
  Offer acceptance rate:   88%  ✓
  Avg time to hire:        19 days  ✓

ALERTS THIS WEEK
  🔴 Engineering reqs: avg 38 days TTF (critical threshold)
  🟡 Sales funnel: phone screen → offer conversion dropped to 12%
  🟡 Indeed completion rate: 51% (below 65% warning)
```

### Executive Briefing (monthly)
Narrative summary with sourcing ROI, QoH trends, recruiter performance, and cost analysis. Formatted for async consumption by CPO, CHRO, or VP TA.

---

## Revenue-at-Risk integration

This engine is designed to connect to the broader [`revenue-protection-engine`](https://github.com/paullinnchs/revenue-protection-engine) — the flagship repo in this portfolio. Open headcount is a revenue risk event. When `% open positions` or `time to fill` breach thresholds in a revenue-generating role (sales, CSM, delivery), the briefing agent escalates to the executive revenue risk briefing.

---

## Stack

- **Language**: Python 3.11+
- **Scheduling**: cron / GitHub Actions / n8n
- **HTTP**: `httpx` (async-first)
- **Data processing**: `pandas`, `polars`
- **LLM layer**: Anthropic Claude API (open-text summarization, briefing generation)
- **Alerting**: Slack webhook, email (SMTP)
- **Storage**: SQLite (local) or PostgreSQL (production)
- **Dashboard**: Outputs JSON consumable by Looker, Tableau, or Retool

---

## Setup

See [`docs/setup_guide.md`](docs/setup_guide.md) for full configuration walkthrough.

Quick start:

```bash
git clone https://github.com/paullinnchs/recruiting-metrics-automation-engine
cd recruiting-metrics-automation-engine
pip install -r requirements.txt
cp config/connections.yaml.example config/connections.yaml
# Add your API credentials to connections.yaml
python agents/tier1_ats_agent.py --run-now
```

---

## Portfolio context

This repo is part of the **AI Operator Lab** — a cross-domain portfolio spanning customer success and talent acquisition, unified by a revenue-protection framework. Related repos:

- [`revenue-protection-engine`](https://github.com/paullinnchs/revenue-protection-engine) — flagship cross-domain engine
- [`candidate-ranking-agent`](https://github.com/paullinnchs/candidate-ranking-agent) — AI-powered candidate scoring
- [`offer-to-start-agent`](https://github.com/paullinnchs/offer-to-start-agent) — falloff risk monitoring
- [`renewal-risk-engine`](https://github.com/paullinnchs/renewal-risk-engine) — CS counterpart to this repo

---

*Built by Paul Linn Solutions — operational workflow automation focused on recruiting, workforce technology, and revenue-critical business systems.
