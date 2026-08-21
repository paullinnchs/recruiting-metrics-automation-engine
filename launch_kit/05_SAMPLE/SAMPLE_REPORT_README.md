# Sample Report README

## How To Generate It

```bash
python app/main.py client_intake/acme_staffing
```

## Expected Client-Facing Filenames

Report filenames include the execution date, so the exact filename depends on when you run it:

```
Consolidated_Client_Report_acme_staffing_YYYY-MM-DD.docx
Consolidated_Client_Report_acme_staffing_YYYY-MM-DD.pdf
```

`YYYY-MM-DD` is your machine's local date at the time you run it — not a fixed value.

## Where They're Generated

```
outputs/reports/
```

Alongside the two client-facing files, you'll also see internal-only outputs (`consolidated_report_*.json`, `consolidated_working_copy_*.md`, and individual Tier 1/Tier 2/revenue JSON files) — see `03_CLIENT_DELIVERY/Delivery_Process.md` for which files are and aren't client deliverables.

## Expected Sections

The consolidated report contains, in order:
1. Executive Summary
2. Data Coverage
3. Recruiting Performance (Tier 1 snapshot + alerts, Tier 2 quality/retention)
4. Revenue Leakage / Commercial Risk — Workforce Revenue Leak Workflow Sprint
5. Priority Findings
6. Recommended Actions
7. Methodology / Important Notes (includes the legal-safety/classification disclaimer)

## Key Expected Sample Results

Verified against an actual run of this repository:

| Metric | Value |
|---|---|
| Time to Fill | **47.9 days** |
| Time to Hire | **39.7 days** |
| Offer Acceptance Rate | 77.8% |
| Fill Rate | 63.6% |
| First-Year Attrition | 28.6% |
| Revenue Exposure | **$48,360.00** |

If a future run produces materially different numbers without an intentional change to `client_intake/acme_staffing/` or the calculation logic, treat that as a signal something changed unexpectedly and investigate before delivering any report based on it.
