# QA Checklist — Pre-Delivery Gate

Run through every item before sending a report to a client. This is the final gate — nothing skips it.

## Identity & Period
- [ ] Correct client name appears throughout the report (title page and body)
- [ ] Reporting period matches what was agreed with the client

## Data Coverage
- [ ] Data Coverage section accurately shows Tier 1 status (Available / Unavailable + missing files)
- [ ] Data Coverage section accurately shows Tier 2 status
- [ ] Data Coverage section accurately shows revenue-analysis status
- [ ] Any "Unavailable" section is genuinely unavailable due to missing intake data — not a run error mistaken for a data gap

## Numbers
- [ ] Recruiting metrics look plausible for this client (no impossible values — negative days, >100% rates, etc.)
- [ ] Revenue exposure total is the sum of its own category breakdown (spot-check the math)
- [ ] Priority Findings are actually traceable back to the underlying data — not summarized in a way that overstates or misrepresents a finding
- [ ] Recommended Actions are tied to an actual finding in the report, not generic filler

## Language & Terminology
- [ ] No internal-only notes, debug text, or placeholder content anywhere in the client-facing document
- [ ] The word **"Audit"** does not appear anywhere in the client-facing document
- [ ] The legal-safety / classification-risk disclaimer is present and unedited
- [ ] Revenue section is labeled **Workforce Revenue Leak Workflow Sprint**, not any other name

## Format
- [ ] `.docx` file generated successfully
- [ ] `.pdf` file generated successfully
- [ ] Opened and visually inspected — logo present, correct colors, tables render cleanly, no page-break awkwardness
- [ ] Approved branding preserved (PLS logo, navy/coral color scheme) — no substitute or placeholder styling

## Security
- [ ] No credentials, API keys, tokens, or `.env` contents appear anywhere in the delivered files
