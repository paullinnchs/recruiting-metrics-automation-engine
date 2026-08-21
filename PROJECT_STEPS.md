# Recruiting Metrics Automation Engine — Project Tracker

## Current Status

- Git initialized and active — 11 commits on `main`, up to date with `origin/main`
- Two functional modules in place: Recruiting Metrics Intelligence (Tier 1/2/3) and the Workforce Revenue Leak Workflow Sprint module
- `.venv` (Python) and `node_modules` (Node) both set up locally; dependencies installed from `requirements.txt` and `package.json`
- `.env` exists locally with real values for active integrations; `.env.example` documents every environment variable the app currently references
- Sample data in place for both modules (`sample_data/`) and exercised in validation runs
- Tier 1 (`tier1_ats_agent.py`), Tier 2 (`tier2_crosssystem_agent.py`), and the revenue-leak engine (`leak_detection_agent.py` + `leak_report_generator.py`) all run successfully against sample/config data
- Branded client-facing DOCX/PDF generation (via `report_docx_template.js` + LibreOffice) confirmed working end-to-end

## Known Gaps / Next Steps

- Tier 3 (survey-driven) metrics require a live survey platform connection (Typeform/Qualtrics/etc.) — not yet exercised against real data
- Full README repositioning around the one-intake -> recruiting analysis + revenue analysis -> one consolidated report architecture is planned as a follow-up pass, separate from the technical fixes tracked here
- Production ATS/HRIS/survey credentials are not yet configured — current runs use sample/config-driven data only

## Reference - One-Time Setup (for a fresh clone)

```bash
git clone https://github.com/paullinnchs/recruiting-metrics-automation-engine
cd recruiting-metrics-automation-engine

python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash
pip install -r requirements.txt

npm install docx                    # for branded DOCX generation
```

Copy `.env.example` to `.env` and fill in real values for whichever integrations you're actively using -- not every variable is required for every module (e.g., the revenue-leak module only needs `VMS_API_KEY` if reading from a live billing API instead of file exports).

Run any module directly, e.g.:

```bash
python app/tier1_ats_agent.py
python app/tier2_crosssystem_agent.py
python app/leak_detection_agent.py
python app/leak_report_generator.py "Client Name"
```
