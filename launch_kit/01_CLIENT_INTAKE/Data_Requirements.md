# Data Requirements — Field-Level Reference

Internal/technical reference. This is the authoritative source when preparing a real client's export — every field below is taken directly from the current connector and analysis code, not assumed.

All files live under `client_intake/<client_id>/`, split into `recruiting/` and `revenue/`. A single `intake_manifest.json` at the intake root ties everything to one client:

```json
{ "client_id": "acme_staffing", "client_name": "Acme Staffing Group" }
```

`client_id` is the shared identifier — every file under that intake folder is treated as belonging to that one client. There is no per-row client identifier requirement; the folder itself is the boundary.

---

## Recruiting Data (`recruiting/`)

### `requisitions.json` — required for Tier 1

| Field | Definition | Format |
|---|---|---|
| `id` | Requisition ID | string |
| `title` | Job title | string |
| `department` | Department | string |
| `location` | Location | string |
| `status` | `"open"` \| `"filled"` \| `"cancelled"` | string |
| `approved_at` | Date the req was approved | ISO date string |
| `closed_at` | Date the req closed (filled or cancelled) | ISO date string, or `null` if still open |
| `close_reason` | `"filled"` \| `"cancelled"` \| `null` | string or null |
| `offer_accepted_at` | Date the accepted offer was signed | ISO date string, or `null` |
| `recruiter_id` | Owning recruiter | string |
| `hiring_manager_id` | Hiring manager | string |

**Used by:** Time to Fill, Fill Rate, % Open Positions, Applicants per Opening.
**If missing entirely:** Tier 1 does not run at all — this file is required.

### `candidates.json` — required for Tier 1

| Field | Definition | Format |
|---|---|---|
| `id` | Candidate ID | string |
| `req_id` | Links to `requisitions.json` | string |
| `role` | Role applied for | string |
| `department` | Department | string |
| `source` | Sourcing channel | string |
| `status` | `"active"` \| `"hired"` \| `"rejected"` \| `"withdrawn"` | string |
| `applied_at` | Application date | ISO date string |
| `hire_date` | Hire date, if hired | ISO date string or `null` |
| `offer_accepted_at` | Offer acceptance date, if hired | ISO date string or `null` |
| `furthest_stage` | Furthest pipeline stage reached | string |
| `stage_gaps` | List of `{"stage": str, "days": int}` | array |
| `employee_id` | **Shared identifier into HRIS data** — required on every hired candidate for Tier 2 to join correctly | string or `null` |
| `recruiter_id` | Owning recruiter | string |
| `demographic_group` | Used only for the adverse-impact calculation | string or `null` |
| `days_to_hire` | Days from application to offer acceptance | integer or `null` |

**Used by:** Time to Hire, Source of Hire, Selection Ratio, Recruitment Funnel, Adverse Impact, and — via `employee_id` — every Tier 2 metric.
**Critical dependency:** `employee_id` on hired candidates must exactly match the `id` field in `hris_employees.json` and the `employee_id` field in `hris_performance.json`. If these don't align, Tier 2 will run but will silently show zero matches rather than error — always spot-check this join during intake QA.

### `applications.json` — required for Tier 1

| Field | Definition | Format |
|---|---|---|
| `id` | Application ID | string |
| `req_id` | Links to requisition | string |
| `candidate_id` | Links to candidate | string |
| `source` | Sourcing channel | string |
| `status` | Application status | string |
| `applied_at` | Application date | ISO date string |

**Used by:** Applicants per Opening, Sourcing Channel Effectiveness, Selection Ratio.

### `offers.json` — required for Tier 1

| Field | Definition | Format |
|---|---|---|
| `id` | Offer ID | string |
| `candidate_id` | Links to candidate | string |
| `req_id` | Links to requisition | string |
| `extended_at` | Date offer was extended | ISO date string |
| `outcome` | `"accepted"` \| `"declined"` \| `"pending"` | string |
| `decline_reason` | Reason if declined | string or `null` |
| `recruiter_id` | Owning recruiter | string |

**Used by:** Offer Acceptance Rate.

### `sessions.json` — optional

| Field | Definition | Format |
|---|---|---|
| `session_id` | Session ID | string |
| `req_id` | Linked requisition | string |
| `submitted` | Whether the application was completed | boolean |

**Used by:** Application Completion Rate only. Nothing else depends on this file — safe to omit if not readily available.

### `hris_employees.json` — required for Tier 2 (in addition to all Tier 1 files)

| Field | Definition | Format |
|---|---|---|
| `id` | HRIS internal employee ID — **must match `employee_id` on hired candidates** | string |
| `employee_id` | Employee number | string |
| `first_name`, `last_name` | Name | string |
| `title` | Job title | string |
| `department` | Department | string |
| `location` | Location | string |
| `employment_type` | `"full_time"` \| `"part_time"` \| `"contractor"` | string |
| `hire_date` | Hire date | ISO date string |
| `termination_date` | Termination date, if applicable | ISO date string or `null` |
| `termination_type` | `"voluntary"` \| `"involuntary"` \| `null` | string or null |
| `termination_reason` | Free text | string or `null` |
| `manager_id` | Manager | string or `null` |
| `status` | `"active"` \| `"terminated"` \| `"on_leave"` | string |

**Used by:** First-Year Attrition.

### `hris_performance.json` — required for Tier 2

| Field | Definition | Format |
|---|---|---|
| `id` | Review record ID | string |
| `employee_id` | **Must match candidate's `employee_id`** | string |
| `review_period` | `"90_day"` \| `"6_month"` \| `"annual"` | string |
| `review_date` | Review date | ISO date string |
| `first_year_rating` | Numeric rating (1.0–5.0 scale) | float |
| `rating_label` | `"exceeds"` \| `"meets"` \| `"below"` \| `"unsatisfactory"` | string |
| `reviewer_id` | Reviewer | string |
| `department` | Department | string |

**Used by:** Quality of Hire.
**If missing/insufficient:** Quality of Hire reports as unavailable due to insufficient data rather than a fabricated ratio — this is handled gracefully by the existing calculation, not something the intake layer needs to guard against separately.

### `survey_responses.json` — required for Tier 2

| Field | Definition | Format |
|---|---|---|
| `response_id` | Response ID | string |
| `survey_type` | e.g. `"candidate_experience"` | string |
| `respondent_id` | Candidate/employee ID | string |
| `recruiter_id` | Linked recruiter | string or `null` |
| `req_id` | Linked requisition | string or `null` |
| `submitted_at` | Submission date | ISO date string |
| `nps` | 0–10 NPS score | integer or `null` |
| `process_rating`, `communication_rating`, `overall_rating` | 1.0–5.0 scale | float or `null` |
| `open_text` | Free-text comment | string or `null` |
| `pulse_day` | 30/60/90-day pulse marker | integer or `null` |
| `would_recommend` | Boolean | boolean or `null` |

**Used by:** Candidate Experience (cNPS).

### `recruiting_config.json` — optional

Overrides for `headcount_override`, `recruiting_spend_override`, `ad_spend_override`, `funnel_stages`. If omitted, system defaults are used (see `app/main.py`). Affects % Open Positions, Cost per Hire, Sourcing Channel Cost, and Recruitment Funnel accuracy — not their availability.

---

## Revenue / Commercial Data (`revenue/`)

All three files below are **required** — revenue analysis does not run partially.

### `billing_data.csv` — required

| Field | Definition | Format |
|---|---|---|
| `id` | Billing/invoice line ID | string |
| `worker_id` | Worker/contractor ID | string |
| `worker_name` | Name | string |
| `worker_type` | e.g. `w2`, `1099`, `corp_to_corp` | string |
| `engagement_type` | e.g. `staff_aug`, `sow` | string |
| `supplier_vendor` | Supplier name — **must match `rate_cards.csv` and `contracts.csv` exactly** for cross-checks to work | string |
| `department` | Cost center / department | string |
| `role_title` | Role — **must match `rate_cards.csv`** | string |
| `contract_id` | Links to `contracts.csv` | string or blank |
| `period_start`, `period_end` | Billing period | date |
| `hours_submitted`, `hours_approved`, `hours_invoiced` | Hours | numeric |
| `pay_rate`, `bill_rate` | Rates | numeric |
| `invoice_amount` | Total billed | numeric |
| `is_approved_supplier` | true/false | boolean |

**Used by:** all five revenue-leak checks (missed markup, stale rate card, off-contract spend, classification risk, hours variance).

### `rate_cards.csv` — required

| Field | Definition |
|---|---|
| `supplier_vendor` | **Must match billing data exactly** (case-sensitive string match — this is the single most common intake error) |
| `role_title` | **Must match billing data exactly** |
| `contracted_bill_rate` | Agreed bill rate |
| `contracted_markup_pct` | Agreed markup, if tracked |
| `effective_date`, `expiration_date` | Rate card validity window |

**Used by:** Missed Markup, Stale Rate Card Billing.

### `contracts.csv` — required

| Field | Definition |
|---|---|
| `contract_id` | Links to billing data |
| `supplier_vendor` | Supplier |
| `engagement_type` | `staff_aug` or `sow` |
| `approved_supplier` | true/false |
| `billing_cadence` | `hourly` or `milestone` |
| `deliverables_defined` | true/false — drives the classification-risk check |

**Used by:** Off-Contract Spend, Classification Risk.

---

## Blank / Null Handling

Every connector treats blank or missing optional fields as `null`/`None` and continues rather than erroring. Required *files* being absent is what gates an entire analysis area off — a required *field* being blank within a present file typically causes that specific record to be skipped from the relevant calculation, not a hard failure. If you're unsure whether a specific blank field will silently degrade a result, check the calculation function in question (`tier1_ats_agent.py`, `tier2_crosssystem_agent.py`, `leak_detection_agent.py`) before assuming.

## What Cannot Be Calculated If a File Is Missing

| Missing file | Directly disables |
|---|---|
| Any Tier 1 recruiting file | All of Tier 1, and therefore all of Tier 2 (Tier 2 depends on Tier 1 running) |
| `hris_employees.json` or `hris_performance.json` or `survey_responses.json` | Tier 2 entirely |
| `sessions.json` | Application Completion Rate only |
| Any revenue file | Revenue analysis entirely (no partial revenue analysis) |

This mapping is enforced by `app/client_intake.py` (`validate_intake()`), not by convention — it's the actual gating logic the engine runs.
