# Sample Intake README

The canonical demo/test intake lives at:

```
client_intake/acme_staffing/
```

This file is not a copy of that data — it's a pointer explaining how it maps to the real intake requirements documented in `01_CLIENT_INTAKE/Data_Requirements.md`. The sample data itself remains the single source of truth; nothing here duplicates it.

## Structure

```
client_intake/acme_staffing/
    intake_manifest.json
    recruiting/
        requisitions.json
        candidates.json
        applications.json
        offers.json
        sessions.json
        hris_employees.json
        hris_performance.json
        survey_responses.json
        recruiting_config.json
    revenue/
        billing_data.csv
        rate_cards.csv
        contracts.csv
```

This is a **complete** intake — every required and optional file is present, which is why running it produces a full report with nothing marked "Unavailable." It's the reference example for what a fully complete intake package looks like.

## How It Maps to Real Requirements

Every filename, field name, and format in this sample intake matches `Data_Requirements.md` exactly — it was built directly against the same connector code that will process a real client's data. If you're ever unsure what a real client export should look like, opening the corresponding sample file is a legitimate way to check the expected shape, in addition to reading the field reference.

## Using It

- **For a demo:** see `04_DEMO/Demo_Guide.md` — run it as-is.
- **For testing a code change:** run `python app/main.py client_intake/acme_staffing` and compare the output against `05_SAMPLE/SAMPLE_REPORT_README.md`'s expected results.
- **For testing missing-data handling:** temporarily move a file or folder out (e.g., move `revenue/` aside), run the engine, confirm the report correctly marks that section unavailable, then move it back. Do not delete or permanently modify anything in `client_intake/acme_staffing/` to test this — always restore it afterward, since it's the canonical reference intake.
