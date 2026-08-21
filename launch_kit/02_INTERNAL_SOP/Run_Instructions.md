# Run Instructions

Concise technical cheat sheet. Not a developer manual — see `README.md` for architecture detail if you need it.

---

## Environment Setup (one-time, per machine)

```bash
git clone https://github.com/paullinnchs/recruiting-metrics-automation-engine
cd recruiting-metrics-automation-engine

python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash
pip install -r requirements.txt

npm install docx                    # required for branded DOCX generation
```

Also required on the machine (not installed via pip/npm):
- **Node.js** — runs the branded report templates
- **LibreOffice** — headless PDF conversion. Must be on PATH as `soffice`, or set `LIBREOFFICE_PATH` in `.env`

Copy `.env.example` to `.env` and fill in values for whichever integrations you're actively using — a file-based intake run doesn't need live ATS/HRIS/survey credentials at all.

## Activation (every new terminal session)

```bash
source .venv/Scripts/activate
```

## Client Intake Placement

```
client_intake/<client_id>/
    intake_manifest.json
    recruiting/
        requisitions.json
        candidates.json
        applications.json
        offers.json
        sessions.json            (optional)
        hris_employees.json
        hris_performance.json
        survey_responses.json
        recruiting_config.json   (optional)
    revenue/
        billing_data.csv
        rate_cards.csv
        contracts.csv
```

## Execution

```bash
python app/main.py client_intake/<client_id>
```

Example, using the included sample:

```bash
python app/main.py client_intake/acme_staffing
```

## Outputs

Everything lands in `outputs/reports/`:

**Client-facing (deliver these):**
- `Consolidated_Client_Report_<client_id>_<date>.docx`
- `Consolidated_Client_Report_<client_id>_<date>.pdf`

**Internal only (do not deliver):**
- `consolidated_report_<client_id>_<date>.json`
- `consolidated_working_copy_<client_id>_<date>.md`
- Individual `tier1_report_*`, `tier2_report_*`, `leak_report_*` JSON files (debugging/traceability only)

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ModuleNotFoundError` on any `import` | Virtual environment not activated, or `pip install -r requirements.txt` not run |
| "Node.js not found" in the log | Node isn't installed, or isn't on PATH |
| "LibreOffice not found — PDF not generated" | LibreOffice isn't installed, or `LIBREOFFICE_PATH` isn't set correctly. The `.docx` is still generated and usable |
| A section shows "Unavailable" in the report | Expected behavior — a required file for that analysis area is missing from the intake folder. Check the console log for exactly which file |
| Report filename date looks off by one day | Check the machine's local timezone setting — the engine uses the system's local date, not UTC |
