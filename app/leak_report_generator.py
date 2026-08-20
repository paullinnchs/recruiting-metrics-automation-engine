"""
leak_report_generator.py
------------------------
Turns the raw leak_detection_agent output into the actual client
deliverable: a prioritized, dollar-scored Markdown report (working copy),
PLUS a branded, client-ready .docx (PLS logo, navy/coral palette) built
automatically via report_docx_template.js — no manual formatting step.

Part of: recruiting-metrics-automation-engine
Author: Paul Linn Solutions (PLS)
"""

import json
import logging
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).parent.parent / "outputs"
APP_PATH = Path(__file__).parent

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"

CATEGORY_LABELS = {
    "missed_markup": "Missed / incorrect markup",
    "stale_rate_card": "Stale / expired rate card billing",
    "off_contract_spend": "Off-contract / maverick spend",
    "classification_risk": (
        "Potential classification risk requiring review"
    ),
    "hours_variance": "Duplicate / unbilled hours",
    "revenue_at_risk_fill": "Revenue-at-risk open fills",
}

SEVERITY_ICON = {
    "CRITICAL": "\U0001F534",
    "WARNING": "\U0001F7E1",
    "INFO": "\u26AA",
}


def load_latest_leak_report() -> dict:
    report_dir = OUTPUT_PATH / "reports"

    path = (
        report_dir
        / f"leak_report_{date.today().isoformat()}.json"
    )

    if not path.exists():
        log.warning(
            "No leak report found for today — "
            "run leak_detection_agent first."
        )
        return {}

    with open(path) as f:
        return json.load(f)


# ──────────────────────────────────────────────
# MARKDOWN WORKING COPY
# ──────────────────────────────────────────────

def build_plain_leak_report(
    report: dict,
    client_name: str = "Client",
) -> str:

    findings = report.get("findings", [])
    total = report.get("total_exposure", 0)
    by_cat = report.get("by_category", {})
    today = date.today().isoformat()

    summary_rows = "\n".join(
        (
            f"| {CATEGORY_LABELS.get(cat, cat)} "
            f"| {data['count']} "
            f"| ${data['dollar_impact']:,.2f} |"
        )
        for cat, data in sorted(
            by_cat.items(),
            key=lambda x: -x[1]["dollar_impact"],
        )
    ) or "| No findings this period | — | — |"

    top_findings = [
        f
        for f in findings
        if f["severity"] in ("CRITICAL", "WARNING")
    ][:15]

    finding_blocks = []

    for f in top_findings:
        icon = SEVERITY_ICON.get(
            f["severity"],
            "",
        )

        impact = f.get("dollar_impact")

        impact_str = (
            f"${impact:,.2f}"
            if impact is not None
            else "n/a — review required"
        )

        finding_blocks.append(
            f"### {icon} "
            f"{CATEGORY_LABELS.get(f['category'], f['category'])} "
            f"— {impact_str}\n\n"
            f"{f['description']}\n\n"
            f"**Recommended action:** "
            f"{f['recommendation']}\n"
        )

    findings_section = (
        "\n".join(finding_blocks)
        if finding_blocks
        else (
            "_No critical or warning-level findings "
            "this period._"
        )
    )

    return f"""# Workforce Revenue Leak Audit — {client_name}

*Generated {today} by Paul Linn Solutions — internal working copy*

---

## Executive summary

**Total estimated financial exposure flagged: ${total:,.2f}**

This total reflects estimated financial exposure surfaced by the audit. Some findings represent identifiable billing or revenue discrepancies, while classification-related findings are potential risk indicators requiring appropriate legal/compliance review.

| Finding category | Findings | Estimated $ impact |
|---|---|---|
{summary_rows}

---

## Prioritized findings

{findings_section}

---

### Important review note

Potential worker-classification findings are operational indicators only. They do not constitute legal advice or a legal determination of worker classification. Any such finding should be reviewed by the appropriate legal or compliance resource.

---

*Internal working copy — the branded .docx alongside this file is the client deliverable.*
"""


# ──────────────────────────────────────────────
# BRANDED .DOCX
# ──────────────────────────────────────────────

def build_branded_docx(
    report_json_path: Path,
    client_name: str,
    out_path: Path,
) -> bool:
    """
    Shells out to report_docx_template.js, which renders the same
    report JSON into a branded Workforce Revenue Leak Audit .docx.

    Returns True on success.
    """

    script = APP_PATH / "report_docx_template.js"

    try:
        result = subprocess.run(
            [
                "node",
                str(script),
                str(report_json_path),
                client_name,
                str(out_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            log.error(
                "Branded docx generation failed: "
                f"{result.stderr.strip()}"
            )
            return False

        log.info(result.stdout.strip())
        return True

    except FileNotFoundError:
        log.error(
            "Node.js not found — install Node to enable "
            "branded .docx generation."
        )
        return False

    except Exception as e:
        log.error(
            f"Branded docx generation error: {e}"
        )
        return False


def _find_libreoffice() -> str | None:
    """
    Locates the LibreOffice headless binary across platforms.
    """

    override = os.environ.get("LIBREOFFICE_PATH")

    if override and Path(override).exists():
        return override

    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]

    for c in candidates:
        if Path(c).exists():
            return c

    return (
        shutil.which("soffice")
        or shutil.which("soffice.exe")
    )


def convert_docx_to_pdf(
    docx_path: Path,
    out_dir: Path,
) -> Path | None:
    """
    Converts a .docx to .pdf via headless LibreOffice.

    Returns the resulting PDF path, or None if LibreOffice
    is unavailable or conversion fails.
    """

    soffice = _find_libreoffice()

    if not soffice:
        log.warning(
            "LibreOffice not found — PDF not generated. "
            "Install LibreOffice and ensure 'soffice' is on PATH, "
            "or set LIBREOFFICE_PATH. Falling back to .docx."
        )
        return None

    try:
        result = subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(docx_path),
            ],
            capture_output=True,
            text=True,
            timeout=90,
        )

        pdf_path = (
            out_dir
            / (docx_path.stem + ".pdf")
        )

        if (
            result.returncode != 0
            or not pdf_path.exists()
        ):
            log.error(
                f"PDF conversion failed: "
                f"{result.stderr.strip()}"
            )
            return None

        log.info(
            f"PDF written: {pdf_path}"
        )

        return pdf_path

    except Exception as e:
        log.error(
            f"PDF conversion error: {e}"
        )
        return None


# ──────────────────────────────────────────────
# OPTIONAL LLM EXECUTIVE NARRATIVE
# ──────────────────────────────────────────────

def generate_executive_narrative(
    report: dict,
    client_name: str = "Client",
) -> str:

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        log.error(
            "ANTHROPIC_API_KEY is not set — "
            "executive narrative generation unavailable."
        )
        return (
            "_Narrative generation unavailable — "
            "see the total exposure and findings table above._"
        )

    prompt = f"""
You are writing the executive-summary paragraph for a
Workforce Revenue Leak Audit for {client_name}.

Use only the findings data below.

Write 3-5 sentences in plain business language.
Be direct about the estimated financial exposure flagged
and the highest-priority operational action.

Do not use bullet points.

IMPORTANT:
If any finding involves worker classification, describe it
only as a potential risk or engagement pattern requiring
legal/compliance review.

Do not state that a worker or engagement has been
misclassified.

Do not provide a legal conclusion.

Do not instruct the client to reclassify a worker.

Do not describe estimated classification exposure as a
confirmed loss, penalty, back-pay obligation, or legal liability.

FINDINGS DATA:

{json.dumps(report, indent=2, default=str)[:6000]}
"""

    try:
        response = httpx.post(
            ANTHROPIC_API_URL,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": MODEL,
                "max_tokens": 400,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            },
            timeout=30,
        )

        response.raise_for_status()

        return response.json()["content"][0]["text"]

    except Exception as e:
        log.error(
            f"Executive narrative generation failed: {e}"
        )

        return (
            "_Narrative generation unavailable — "
            "see the total exposure and findings table above._"
        )


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def run(
    client_name: str = "Client",
    use_llm_narrative: bool = False,
):

    log.info(
        "Leak Report Generator starting"
    )

    report = load_latest_leak_report()

    if not report:
        return None, None, None

    out_dir = OUTPUT_PATH / "reports"

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    today = date.today().isoformat()

    slug = (
        client_name.lower()
        .replace(" ", "_")
    )

    # 1. Markdown working copy
    body = build_plain_leak_report(
        report,
        client_name,
    )

    md_path = (
        out_dir
        / (
            f"leak_workflow_sprint_working_copy_"
            f"{slug}_{today}.md"
        )
    )

    with open(
        md_path,
        "w",
        encoding="utf-8",
    ) as f:
        f.write(body)

    log.info(
        f"Working copy written: {md_path}"
    )

    # Optional executive narrative.
    # Preserved as an available function without changing the
    # existing report schema or DOCX workflow.
    if use_llm_narrative:
        narrative = generate_executive_narrative(
            report,
            client_name,
        )

        log.info(
            "Executive narrative generated."
        )

        narrative_path = (
            out_dir
            / (
                f"executive_narrative_"
                f"{slug}_{today}.md"
            )
        )

        with open(
            narrative_path,
            "w",
            encoding="utf-8",
        ) as f:
            f.write(narrative)

    # 2. Branded .docx
    report_json_path = (
        OUTPUT_PATH
        / "reports"
        / f"leak_report_{today}.json"
    )

    docx_path = (
        out_dir
        / (
            f"Workflow_Sprint_Report_"
            f"{slug}_{today}.docx"
        )
    )

    ok = build_branded_docx(
        report_json_path,
        client_name,
        docx_path,
    )

    if not ok:
        log.warning(
            "Falling back to Markdown only — "
            "branded .docx was not generated."
        )

        return body, None, None

    # 3. PDF
    pdf_path = convert_docx_to_pdf(
        docx_path,
        out_dir,
    )

    if not pdf_path:
        log.warning(
            "PDF conversion unavailable — the .docx "
            "above is still a valid deliverable."
        )

    return body, docx_path, pdf_path


if __name__ == "__main__":
    import sys

    client = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "Client"
    )

    run(
        client_name=client,
    )