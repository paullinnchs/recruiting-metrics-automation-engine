# Demo Guide

For demonstrating the prototype to staffing-company owners, recruiting leaders, workforce leaders, HR Tech leaders, prospective consulting clients, or potential partners/employers.

Uses the existing `acme_staffing` sample intake — no client data required, and nothing needs to be set up beyond the standard environment (`Run_Instructions.md`).

Keep the demo focused on business value, not code. You don't need to open or explain any source file during the demo itself.

---

## Step 1 — Show the Intake

Open `client_intake/acme_staffing/` in a file browser. Show the two subfolders — `recruiting/` and `revenue/` — and explain plainly: *this represents the kind of exports a real client would send us. Nothing more complicated than what you already pull out of your own ATS and billing systems.*

Don't dwell on individual field names here — the point is that it's ordinary operational data, not something exotic to prepare.

## Step 2 — Run the Engine

In a terminal:

```bash
python app/main.py client_intake/acme_staffing
```

Let it run in front of them — it completes in a few seconds. Narrate what's happening as it prints:

- "It's checking what data is actually available..."
- "Now it's running the recruiting analysis..."
- "Now the revenue analysis..."
- "And now it's building the one combined report."

## Step 3 — Show Validation

Point to the console output showing Tier 1 / Tier 2 / Revenue each marked "available." Explain: *if any of these were missing, it would say so right here, and the report would clearly show that section as unavailable instead of guessing.* This is a good moment to mention that the same engine handles a partial intake gracefully — it doesn't need perfect data to be useful.

## Step 4 — Show Recruiting Intelligence

Open the generated report and walk to the Recruiting Performance section. Highlight metrics that land the point:

- Time to Fill and Time to Hire — and that they're tracked as two distinct things
- Offer Acceptance Rate and Fill Rate, each flagged against a threshold rather than shown as a raw number
- First-Year Attrition and Quality of Hire, from the deeper Tier 2 layer

## Step 5 — Show Revenue Exposure

Move to the Revenue Leakage section. Point to the headline number:

**$48,360 in revenue exposure identified**, broken into specific categories — missed markup, stale rate cards, off-contract spend, a classification-risk flag, and unbilled hours.

## Step 6 — Show Consolidated Report

Zoom out to the whole document. Emphasize: *this is one report, generated from one intake, in one run — not two teams producing two separate spreadsheets that someone then has to reconcile by hand.* Close on the Priority Findings section, which ranks issues from both analysis areas together, and the Recommended Actions that follow directly from them.
