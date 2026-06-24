# Automation map — recruiting metrics

All 23 recruiting metrics from AIHR's framework, mapped to automation tier with rationale.

---

## Tier 1 — Fully automatable (ATS-only)

Agent runs end-to-end. No human input required.
Data source: ATS API only. Trigger: cron schedule.

| # | Metric | Formula | Why fully automatable |
|---|--------|---------|----------------------|
| 1 | Time to fill | Days(offer_accepted) − Days(req_approved) | Both timestamps in ATS. Pure calculation. |
| 2 | Time to hire | Days(offer_accepted) − Days(applied) | ATS stage timestamps. No external data. |
| 3 | Source of hire | Count hires by source field | ATS source field on every applicant record. |
| 4 | Sourcing channel effectiveness | Hires/Applications per channel | ATS + UTM params. GA4 optional enhancement. |
| 5 | Sourcing channel cost | Ad spend / hires per platform | Ad platform API + ATS source field. |
| 10 | Applicants per opening | Count(applications) per req | Direct ATS count. |
| 11 | Selection ratio | Hires / Total applicants | ATS hire count + application count. |
| 14 | Offer acceptance rate | Accepted offers / Extended offers | ATS offer stage outcome field. |
| 15 | % of open positions | Open reqs / Total headcount | ATS open reqs + HRIS headcount (read-only join). |
| 16 | Application completion rate | Submitted apps / Started sessions | ATS funnel data or GA4 event tracking. |
| 22 | Fill rate | Filled reqs / Total closed reqs | ATS req close status and reason. |

---

## Tier 2 — High automation (ATS + HRIS join, ~80%+ automated)

Agent joins data across systems. Human reviews anomalies and narratives.

| # | Metric | Data join | Human touchpoint | Why not fully automatable |
|---|--------|-----------|-----------------|--------------------------|
| 6 | First-year attrition | ATS hire + HRIS termination | Classify edge cases in managed/unmanaged | Termination type classification can be ambiguous |
| 7 | Quality of hire | ATS hire + HRIS performance rating | Validate perf data completeness before acting | Rating definitions vary by org; manager bias possible |
| 12 | Cost per hire | Finance/ERP spend + ATS hire count | Confirm spend category scope | Finance categories need human alignment each cycle |
| 13 | Candidate experience | Survey API + ATS stage events | Review open-text themes from LLM | LLM summarizes but human confirms action |
| 17 | Recruitment funnel effectiveness | ATS stage progression data | Interpret drop-off patterns in context | Context (new role, market conditions) requires judgment |
| 20 | Adverse impact | ATS demographic data + stage outcomes | Compliance review required before any action | Legal — cannot act on automated output without human sign-off |
| 21 | Recruiter performance | ATS + HRIS + survey join | Manager scorecard review | Performance data informs but does not replace manager conversation |

---

## Tier 3 — Partial automation (survey + LLM, ~50-70% automated)

Agent collects data and computes scores. LLM summarizes qualitative input.
Human interprets and decides.

| # | Metric | What agent does | What human does | Automation blocker |
|---|--------|----------------|-----------------|-------------------|
| 8 | Hiring manager satisfaction | Auto-sends survey; aggregates scores | Reviews narrative themes; acts on low scores | Survey response rates; qualitative nuance |
| 9 | Candidate job satisfaction | Auto-triggers pulse surveys (30/60/90 day) | Reviews LLM theme summary | New hire relationship sensitivity |
| 18 | Cost to OPL | Aggregates onboarding + salary costs | Defines OPL date; validates total | OPL definition is org-specific; milestone judgment |
| 19 | Time to productivity | Tracks predefined HRIS milestones | Confirms milestone was genuinely reached | Manager is the source of truth for readiness |
| 23 | Recruitment ROI | Aggregates cost inputs; pulls perf data | Defines productivity value; builds ROI narrative | Revenue-per-hire or productivity value has no universal formula |

---

## Adverse impact — special compliance note

Metric 20 (Adverse Impact) is technically automatable — the 4/5ths rule is a formula,
and demographic data can be pulled from the ATS. However:

- No automated output should trigger any personnel, process, or vendor decision
- All adverse impact findings must be reviewed by HR and Legal before communication
- The agent's role is detection and routing, not interpretation or action
- Demographic data handling must comply with applicable privacy law (EEOC, GDPR, etc.)

---

## Revenue-at-Risk integration point

The following metrics connect recruiting lag directly to business risk
and feed the `revenue-protection-engine` briefing:

- Time to fill (revenue roles) → pipeline coverage risk
- % of open positions (sales, CSM, delivery) → capacity risk
- First-year attrition → replacement cost + ramp cost
- Quality of hire → productivity loss per bad hire

When these metrics breach thresholds in revenue-generating departments,
the briefing agent escalates to the executive revenue risk briefing.
