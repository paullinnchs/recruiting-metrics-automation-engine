# Intake Checklist

Run through this before handing an intake off to `app/main.py`. Not verbose — just the practical gate.

- [ ] `intake_manifest.json` created with correct `client_id` and `client_name`
- [ ] Recruiting data received (or explicitly confirmed as not available for this engagement)
- [ ] Commercial/revenue data received (or explicitly confirmed as not available)
- [ ] Reporting period confirmed with the client — what date range does the data actually cover?
- [ ] Required Tier 1 files present: `requisitions.json`, `candidates.json`, `applications.json`, `offers.json`
- [ ] Required Tier 2 files present (if in scope): `hris_employees.json`, `hris_performance.json`, `survey_responses.json`
- [ ] Required revenue files present (if in scope): `billing_data.csv`, `rate_cards.csv`, `contracts.csv`
- [ ] Spot-checked required fields are actually populated, not just present as empty columns
- [ ] File formats correct — CSV for revenue, JSON for recruiting (see `Data_Requirements.md` for exceptions)
- [ ] Cross-file identifiers align:
  - [ ] Hired candidates' `employee_id` matches `hris_employees.json`'s `id`
  - [ ] `supplier_vendor` and `role_title` spelled identically across `billing_data.csv`, `rate_cards.csv`, and `contracts.csv`
- [ ] Any missing optional data documented (e.g., "client does not track `sessions.json`")
- [ ] Files placed under `client_intake/<client_id>/recruiting/` and `client_intake/<client_id>/revenue/` correctly
- [ ] Intake ready — proceed to `python app/main.py client_intake/<client_id>` per `Run_Instructions.md`
