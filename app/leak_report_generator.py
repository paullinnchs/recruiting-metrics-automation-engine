"""
leak_report_generator.py
--------------------------
Turns the raw leak_detection_agent output into the actual client
deliverable: a prioritized, dollar-scored Markdown report (working copy),
PLUS a branded, client-ready .docx (PLS logo, navy/coral palette) built
automatically via report_docx_template.js — no manual formatting step.

Part of: recruiting-metrics-automation-engine
Author:  Paul Linn Solutions (PLS)
"""

import json
import logging
import subprocess
from datetime import date, datetime
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).parent.parent / "outputs"
APP_PATH = Path(__file__).parent
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"

CATEGORY_LABELS = {
    "missed_markup": "Missed / incorrect markup",
    "stale_rate_card": "Stale / expired rate card billing",
    "off_contract_spend": "Off-contract / maverick spend",
    "classification_risk": "Worker classification risk",
    "hours_variance": "Duplicate / unbilled hours",
    "revenue_at_risk_fill": "Revenue-at-risk open fills",
}

SEVERITY_ICON = {"CRITICAL": "\U0001F534", "WARNING": "\U0001F7E1", "INFO": "\u26AA"}


def load_latest_leak_report() -> dict:
    report_dir = OUTPUT_PATH / "reports"
    path = report_dir / f"leak_report_{date.today().isoformat()}.json"
    if not path.exists():
        log.warning("No leak report found for today — run leak_detection_agent first.")
        return {}
    with open(path) as f:
        return json.load(f)


# ──────────────────────────────────────────────
# MARKDOWN (WORKING COPY — internal, not for client delivery)
# ──────────────────────────────────────────────

def build_plain_leak_report(report: dict, client_name: str = "Client") -> str:
    findings = report.get("findings", [])
    total = report.get("total_exposure", 0)
    by_cat = report.get("by_category", {})
    today = date.today().isoformat()

    summary_rows = "\n".join(
        f"| {CATEGORY_LABELS.get(cat, cat)} | {data['count']} | ${data['dollar_impact']:,.2f} |"
        for cat, data in sorted(by_cat.items(), key=lambda x: -x[1]["dollar_impact"])
    ) or "| No findings this period | — | — |"

    top_findings = [f for f in findings if f["severity"] in ("CRITICAL", "WARNING")][:15]
    finding_blocks = []
    for f in top_findings:
        icon = SEVERITY_ICON.get(f["severity"], "")
        impact = f.get("dollar_impact")
        impact_str = f"${impact:,.2f}" if impact is not None else "n/a — escalation risk"
        finding_blocks.append(
            f"### {icon} {CATEGORY_LABELS.get(f['category'], f['category'])} — {impact_str}\n\n"
            f"{f['description']}\n\n"
            f"**Recommended action:** {f['recommendation']}\n"
        )
    findings_section = "\n".join(finding_blocks) if finding_blocks else "_No critical or warning-level findings this period._"

    return f"""# Workforce Revenue Leak Audit — {client_name}
*Generated {today} by the Workforce Revenue Leak Workflow Sprint (Paul Linn Solutions) — internal working copy*

---

## Executive summary

**Total identified revenue exposure: ${total:,.2f}**

| Leak category | Findings | Estimated $ impact |
|---|---|---|
{summary_rows}

---

## Prioritized findings

{findings_section}

---
*Internal working copy — the branded .docx alongside this file is the client deliverable.*
"""


# ──────────────────────────────────────────────
# BRANDED .DOCX (THE ACTUAL CLIENT DELIVERABLE)
# ──────────────────────────────────────────────

def build_branded_docx(report_json_path: Path, client_name: str, out_path: Path) -> bool:
    """
    Shells out to report_docx_template.js, which renders the same report
    JSON into a branded Workflow Sprint .docx (PLS logo, navy/coral, no
    purple). Returns True on success.
    """
    script = APP_PATH / "report_docx_template.js"
    try:
        result = subprocess.run(
            ["node", str(script), str(report_json_path), client_name, str(out_path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            log.error(f"Branded docx generation failed: {result.stderr.strip()}")
            return False
        log.info(result.stdout.strip())
        return True
    except FileNotFoundError:
        log.error("Node.js not found — install Node to enable branded .docx generation.")
        return False
    except Exception as e:
        log.error(f"Branded docx generation error: {e}")
        return False


# ──────────────────────────────────────────────
# LLM-WRITTEN EXECUTIVE NARRATIVE (OPTIONAL, feeds the .docx too if desired)
# ──────────────────────────────────────────────

def generate_executive_narrative(report: dict, client_name: str = "Client") -> str:
    prompt = f"""You are running a workforce revenue leak Workflow Sprint, writing the executive summary
paragraph for {client_name}. Use the findings data below. Write 3-5 sentences,
plain language, no jargon, direct about the dollar exposure and the single
highest-priority fix. Do not use bullet points — prose only.

FINDINGS DATA:
{json.dumps(report, indent=2, default=str)[:6000]}"""

    try:
        response = httpx.post(
            ANTHROPIC_API_URL,
            headers={"Content-Type": "application/json"},
            json={"model": MODEL, "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]
    except Exception as e:
        log.error(f"Executive narrative generation failed: {e}")
        return "_Narrative generation unavailable — see the total exposure and findings table above._"


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def run(client_name: str = "Client", use_llm_narrative: bool = False):
    log.info("Leak Report Generator starting")
    report = load_latest_leak_report()
    if not report:
        return None, None

    out_dir = OUTPUT_PATH / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    slug = client_name.lower().replace(" ", "_")

    # 1. Markdown working copy
    body = build_plain_leak_report(report, client_name)
    md_path = out_dir / f"leak_workflow_sprint_working_copy_{slug}_{today}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(body)
    log.info(f"Working copy written: {md_path}")

    # 2. Branded .docx — the actual client deliverable
    report_json_path = OUTPUT_PATH / "reports" / f"leak_report_{today}.json"
    docx_path = out_dir / f"Workflow_Sprint_Report_{slug}_{today}.docx"
    ok = build_branded_docx(report_json_path, client_name, docx_path)
    if not ok:
        log.warning("Falling back to Markdown only — branded .docx was not generated.")
        docx_path = None

    return body, docx_path


if __name__ == "__main__":
    import sys
    client = sys.argv[1] if len(sys.argv) > 1 else "Client"
    run(client_name=client)
