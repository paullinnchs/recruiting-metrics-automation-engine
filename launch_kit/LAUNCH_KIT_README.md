# Launch Kit — Recruiting Metrics Automation Engine

This kit makes the existing engine operationally usable: easy to explain, demonstrate, hand off, and deliver to a real client. It documents and packages what the engine already does — it does not add any new functionality.

**Operating model:** One Client Intake -> Validation -> Recruiting Performance + Revenue Leak Analysis -> One Consolidated Executive Report.

This is a navigation document — each linked file is the actual source of truth for its topic; nothing below duplicates their content.

---

## Where To Go

### Setting up a new client? Start here.
- **`01_CLIENT_INTAKE/Client_Intake_Instructions.md`** — client-facing, plain language: what to send us
- **`01_CLIENT_INTAKE/Data_Requirements.md`** — internal, field-level: the exact technical requirements
- **`01_CLIENT_INTAKE/Intake_Checklist.md`** — practical pre-validation checklist

### Running an analysis? Go here.
- **`02_INTERNAL_SOP/Operator_SOP.md`** — the full process, end to end, including what to do when data is incomplete
- **`02_INTERNAL_SOP/Run_Instructions.md`** — the concise technical cheat sheet (setup, execution, troubleshooting)
- **`02_INTERNAL_SOP/QA_Checklist.md`** — the final gate before anything goes to a client

### Explaining this to a client? Go here.
- **`03_CLIENT_DELIVERY/Client_Service_Overview.md`** — client-facing plain-English explanation of the service
- **`03_CLIENT_DELIVERY/What_To_Expect.md`** — client-facing walkthrough of the engagement lifecycle
- **`03_CLIENT_DELIVERY/Delivery_Process.md`** — internal delivery process and file conventions

### Demoing this to someone? Go here.
- **`04_DEMO/Demo_Guide.md`** — step-by-step demo sequence using the sample client
- **`04_DEMO/Demo_Talk_Track.md`** — a natural spoken explanation you can actually use
- **`04_DEMO/Sample_Client_Overview.md`** — background on the fictional sample client and its findings

### Working with the sample data? Go here.
- **`05_SAMPLE/SAMPLE_INTAKE_README.md`** — how the sample intake maps to real intake requirements
- **`05_SAMPLE/SAMPLE_REPORT_README.md`** — how to generate the sample report and what to expect

---

## Terminology (used consistently throughout this kit)

- **Recruiting Metrics Automation Engine** — the overall system/repository
- **Workforce Revenue Leak Workflow Sprint** — the revenue/commercial analysis component

"Audit" is not used anywhere in this kit's client-facing material, and the legal-safety/classification-risk disclaimer established in the engine's report templates is preserved unchanged wherever referenced.

## Branding

Client-facing materials in this kit are Markdown source documents. The actual formatted client deliverable — the consolidated `.docx`/`.pdf` — carries the established PLS branding (logo, navy/coral color treatment, typography) already built into `app/consolidated_report_template.js` and `app/report_docx_template.js`. This kit does not introduce any new branding, template, or visual design — see those two files for the approved visual reference if producing any additional formatted client-facing artifact in the future.
