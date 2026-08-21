# Operator SOP — Recruiting Metrics Automation Engine

**Internal.** Full process: client sends files -> intake preparation -> validation -> engine execution -> QA -> client delivery.

---

## 1. Client Sends Files

Client sends recruiting and/or revenue exports per `01_CLIENT_INTAKE/Client_Intake_Instructions.md`, however they naturally deliver them (email, shared drive, etc.).

## 2. Intake Preparation

1. Create the client's intake folder:
   ```
   client_intake/<client_id>/
       recruiting/
       revenue/
   ```
2. Create `client_intake/<client_id>/intake_manifest.json`:
   ```json
   { "client_id": "<client_id>", "client_name": "<Client Display Name>" }
   ```
3. Convert/rename the client's raw exports into the exact filenames `Data_Requirements.md` specifies (`requisitions.json`, `billing_data.csv`, etc.) and place them in the correct subfolder.
4. Work through `Intake_Checklist.md` before moving on.

## 3. Validation

Validation happens automatically the moment you run the engine — there's no separate manual validation step. `app/main.py` calls `app/client_intake.py`'s `validate_intake()` first thing, and logs exactly what it found:

```
Recruiting Tier 1: available / UNAVAILABLE — missing [...]
Recruiting Tier 2: available / UNAVAILABLE — missing [...]
Revenue analysis:  available / UNAVAILABLE — missing [...]
```

Read this output before assuming a full report is coming.

## 4. Engine Execution

```bash
python app/main.py client_intake/<client_id>
```

See `Run_Instructions.md` for environment setup if this is a fresh machine.

## 5. QA

Run through `QA_Checklist.md` against the generated report before sending anything to the client. Do not skip this step even for a client you've run before.

## 6. Client Delivery

Deliver the two client-facing files only:
- `Consolidated_Client_Report_<client_id>_<date>.docx`
- `Consolidated_Client_Report_<client_id>_<date>.pdf`

See `03_CLIENT_DELIVERY/Delivery_Process.md` for the delivery convention.

---

## What To Do In Each Scenario

**All data present.** Proceed normally — full report, all three analysis areas populated.

**Tier 1 data present, Tier 2 incomplete.** Run it anyway. The report will show Tier 1 fully and mark Tier 2 "Unavailable" with the exact missing files. This is a legitimate partial deliverable — confirm with the client whether they want to send the missing Tier 2 files before final delivery, or proceed with a Tier 1 + revenue report.

**Revenue data incomplete.** Same principle — the engine still runs recruiting analysis in full. All three revenue files (`billing_data.csv`, `rate_cards.csv`, `contracts.csv`) are required together; there's no partial revenue analysis.

**Required fields are missing** (file present, but key columns blank). The engine does not hard-fail on this — affected individual records are typically skipped from that calculation rather than the whole metric erroring. Check the specific metric in question against `Data_Requirements.md` if a number looks unexpectedly low or zero, then go back to the client for a corrected export if needed.

**File formatting is incorrect** (wrong file type, unreadable CSV, malformed JSON). The relevant connector will log a warning and return no records for that file rather than crashing the whole run — you'll see it in the console output and in the report's Data Coverage section as effectively empty. Fix the file and re-run.

**The engine reports a section unavailable.** This is expected, correct behavior, not a bug — it means a required file for that section wasn't found. Don't try to force it; either get the missing file from the client or deliver the partial report with that section clearly marked unavailable, per client agreement.

**Report generation fails** (DOCX/PDF step errors out). Check that Node.js and the `docx` npm package are installed (`npm install docx` from the repo root) and that LibreOffice is installed and discoverable (`soffice` on PATH, or `LIBREOFFICE_PATH` set in `.env`). The pipeline degrades gracefully — if PDF conversion fails, you'll still have a working `.docx`; if DOCX generation itself fails, you still have the internal Markdown working copy to fall back on temporarily, but do not deliver that to a client — fix the environment issue first.

---

## Escalation

If something happens outside the scenarios above, don't guess — check the actual console output from the run (it's designed to be readable), and consult `Data_Requirements.md` and the relevant module docstring before improvising a fix.
