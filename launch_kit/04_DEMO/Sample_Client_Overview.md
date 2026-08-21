# Sample Client Overview — Acme Staffing Group

**Acme Staffing Group is entirely fictional.** All data in `client_intake/acme_staffing/` — every requisition, candidate, employee, invoice, rate card, and contract — was generated as sample data for demonstration and testing. It does not represent any real company, individual, or engagement.

## What Kind of Company It Represents

A mid-sized organization (~150 employees, per the sample headcount configuration) hiring across Engineering, Sales, Customer Success, Product, Marketing, and Support, with an active contingent workforce program spanning several staffing suppliers.

## What Data Was Supplied

The full intake package: 13 requisitions, associated candidates/applications/offers, 7 completed hires with HRIS employee and performance records, candidate experience survey responses, and a complete revenue-side export (billing history, rate cards, and active contracts) covering several supplier relationships.

## Reporting Context

A single-period snapshot analysis — the sample represents one intake covering roughly the trailing 90 days of recruiting activity and the corresponding billing period.

## Major Recruiting Findings

- **Time to Fill:** 47.9 days on average — above the alert threshold
- **Time to Hire:** 39.7 days on average
- **Offer Acceptance Rate:** 77.8% — below target
- **Fill Rate:** 63.6% — below target, driven partly by several cancelled requisitions in the period
- **First-Year Attrition:** 28.6%
- **An adverse-impact flag** on two demographic groups, correctly surfaced for HR/Legal review rather than acted on automatically

## Revenue Exposure

**$48,360.00** in total estimated exposure, spanning all five leak categories the engine checks: a potential classification-risk finding (the largest single item, at $43,680), off-contract spend, missed markup, stale rate card billing, and unbilled hours.

## Why This Sample Demonstrates the Full Workflow

It's the one dataset in the repository that exercises every part of the system at once: Tier 1 recruiting metrics, Tier 2 cross-system metrics (including the adverse-impact compliance flag), and all five revenue-leak checks — combined into a single consolidated report. It's also been used, unmodified, to validate the engine through every stage of this project, so the numbers above are exactly what running it produces, not a curated or idealized result.
