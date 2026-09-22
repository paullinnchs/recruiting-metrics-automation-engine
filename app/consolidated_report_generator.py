"""
consolidated_report_generator.py
----------------------------------
Turns the consolidated analysis dict (Tier 1 + Tier 2 recruiting +
revenue-leak findings) into:

  1. An internal Markdown working copy (not the client deliverable)
  2. ONE branded, client-ready .docx covering both analysis areas
  3. ONE .pdf, converted from that .docx

Reuses convert_docx_to_pdf() from leak_report_generator.py rather than
reimplementing PDF conversion. The Node template (consolidated_report_template.js)
is presentation-only, same pattern as report_docx_template.js — Python
remains the single source of truth for all figures.

Part of: recruiting-metrics-automation-engine
Author:  Paul Linn Solutions (PLS)
"""

import json
import logging
import subprocess
from pathlib import Path

from leak_report_generator import convert_docx_to_pdf, CATEGORY_LABELS as REVENUE_CATEGORY_LABELS
from tier1_ats_agent import METRIC_BUSINESS_CONTEXT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

APP_PATH = Path(__file__).parent

MAX_PRIORITY_ITEMS = 5
SEVERITY_RANK = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


# ──────────────────────────────────────────────
# PRIORITY FINDINGS (ranked across both analysis areas)
# ──────────────────────────────────────────────

def _severity_rank(severity: str) -> int:
    return SEVERITY_RANK.get(severity, 9)


def _highest_severity(values: list[str]) -> str:
    return sorted(values or ["INFO"], key=_severity_rank)[0]


def _normalize_action(action: str) -> str:
    return " ".join((action or "").strip().lower().split())


def _build_operations_priority_item(ops: dict) -> dict | None:
    exceptions = ops.get("exceptions", []) or []
    if not exceptions:
        return None

    grouped: dict[tuple[str, str], dict] = {}
    for ex in exceptions:
        key = (
            ex.get("exception_type", "operational_exception"),
            ex.get("recommended_action", "Review the underlying records and decide next action."),
        )
        grouped.setdefault(key, {
            "exception_type": key[0],
            "action": key[1],
            "count": 0,
            "severities": [],
        })
        grouped[key]["count"] += 1
        grouped[key]["severities"].append(ex.get("severity", "WARNING"))

    groups = sorted(
        grouped.values(),
        key=lambda g: (
            _severity_rank(_highest_severity(g["severities"])),
            -g["count"],
            g["exception_type"],
        ),
    )
    top_groups = groups[:3]
    severity = _highest_severity([s for g in groups for s in g["severities"]])
    type_count = len({ex.get("exception_type", "operational_exception") for ex in exceptions})
    top_types = ", ".join(
        f"{g['exception_type'].replace('_', ' ')} ({g['count']})"
        for g in top_groups
    )

    return {
        "area": "operations",
        "severity": severity,
        "label": "Recruiting Operations Exceptions",
        "detail": (
            f"{len(exceptions)} record-level operational exception(s) were detected across "
            f"{type_count} exception type(s). Highest-priority patterns: {top_types}. "
            "See Recruiting Operations Exceptions for record-level detail."
        ),
        "action": top_groups[0]["action"],
        "dollar_impact": None,
    }


def _build_revenue_priority_items(revenue: dict) -> list[dict]:
    grouped: dict[str, dict] = {}
    for finding in revenue.get("findings") or []:
        if finding.get("severity") not in ("CRITICAL", "WARNING"):
            continue
        category = finding.get("category", "revenue_risk")
        grouped.setdefault(category, {
            "category": category,
            "count": 0,
            "dollar_impact": 0,
            "severities": [],
            "descriptions": [],
            "actions": [],
        })
        grouped[category]["count"] += 1
        grouped[category]["dollar_impact"] += finding.get("dollar_impact") or 0
        grouped[category]["severities"].append(finding.get("severity", "WARNING"))
        if finding.get("description"):
            grouped[category]["descriptions"].append(finding["description"])
        if finding.get("recommendation"):
            grouped[category]["actions"].append(finding["recommendation"])

    items = []
    for category, group in grouped.items():
        detail = (
            f"{group['count']} revenue/commercial finding(s) in this category with "
            f"${group['dollar_impact']:,.2f} in estimated exposure."
        )
        if group["descriptions"]:
            detail += f" Example: {group['descriptions'][0]}"
        items.append({
            "area": "revenue",
            "severity": _highest_severity(group["severities"]),
            "label": REVENUE_CATEGORY_LABELS.get(category, category),
            "detail": detail,
            "action": group["actions"][0] if group["actions"] else "",
            "dollar_impact": round(group["dollar_impact"], 2),
        })
    return items


def _dedupe_actions(items: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for item in items:
        action_key = _normalize_action(item.get("action", ""))
        if action_key and action_key in seen:
            item = dict(item)
            item["action"] = ""
        elif action_key:
            seen.add(action_key)
        deduped.append(item)
    return deduped


def build_priority_items(consolidated: dict) -> list[dict]:
    items = []

    recruiting = consolidated.get("recruiting", {})
    ops = recruiting.get("operational_exceptions") or {}
    ops_item = _build_operations_priority_item(ops)
    if ops_item:
        items.append(ops_item)

    for a in recruiting.get("tier1_alerts", []) or []:
        ctx = METRIC_BUSINESS_CONTEXT.get(a.get("metric", ""), {})
        items.append({
            "area": "recruiting",
            "severity": a.get("level", "WARNING"),
            "label": ctx.get("label") or a.get("metric", "").replace("_", " ").title(),
            "detail": ctx.get("impact") or a.get("message", ""),
            "action": ctx.get("action") or "Review the underlying data and investigate root cause.",
            "dollar_impact": None,
        })

    tier2 = recruiting.get("tier2") or {}
    ai = tier2.get("adverse_impact") or {}
    if ai.get("compliance_review_required"):
        items.append({
            "area": "recruiting",
            "severity": "CRITICAL",
            "label": "Adverse Impact Flag",
            "detail": (f"Selection-rate disparity flagged for group(s): "
                       f"{', '.join(ai.get('adverse_impact_flags', []))}. Requires HR/Legal review "
                       f"before any related action."),
            "action": "Route to HR/Legal for compliance review before any personnel decision is made.",
            "dollar_impact": None,
        })

    revenue = consolidated.get("revenue", {})
    items.extend(_build_revenue_priority_items(revenue))

    items.sort(key=lambda x: (_severity_rank(x["severity"]), -(x["dollar_impact"] or 0)))
    return _dedupe_actions(items[:MAX_PRIORITY_ITEMS])


# ──────────────────────────────────────────────
# DATA COVERAGE SUMMARY
# ──────────────────────────────────────────────

def build_coverage_summary(consolidated: dict) -> dict:
    v = consolidated["validation"]
    return {
        "tier1": {"available": v["recruiting_tier1"]["available"], "missing": v["recruiting_tier1"]["missing"]},
        "tier2": {"available": v["recruiting_tier2"]["available"], "missing": v["recruiting_tier2"]["missing"]},
        "revenue": {"available": v["revenue"]["available"], "missing": v["revenue"]["missing"]},
    }


# ──────────────────────────────────────────────
# MARKDOWN WORKING COPY (internal only)
# ──────────────────────────────────────────────

def build_working_copy_markdown(consolidated: dict, priority_items: list[dict]) -> str:
    client_name = consolidated["client_name"]
    today = consolidated["generated_at"][:10]
    coverage = build_coverage_summary(consolidated)
    recruiting = consolidated["recruiting"]
    revenue = consolidated["revenue"]

    lines = [
        f"# Consolidated Client Analysis — {client_name}",
        f"*Generated {today} — internal working copy*",
        "",
        "## Data Coverage",
        f"- Recruiting Tier 1: {'available' if coverage['tier1']['available'] else 'UNAVAILABLE — missing ' + ', '.join(coverage['tier1']['missing'])}",
        f"- Recruiting Tier 2: {'available' if coverage['tier2']['available'] else 'UNAVAILABLE — missing ' + ', '.join(coverage['tier2']['missing'])}",
        f"- Revenue analysis: {'available' if coverage['revenue']['available'] else 'UNAVAILABLE — missing ' + ', '.join(coverage['revenue']['missing'])}",
        "",
        "## Priority Findings",
    ]
    if priority_items:
        for it in priority_items:
            impact = f" — ${it['dollar_impact']:,.2f}" if it.get("dollar_impact") else ""
            lines.append(f"- [{it['severity']}] ({it['area']}) {it['label']}{impact}: {it['detail']}")
    else:
        lines.append("- No critical or warning-level findings across either analysis area.")

    lines.append("")
    lines.append("## Recruiting Performance")
    if recruiting["tier1_available"]:
        lines.append(f"Tier 1 metrics computed: {len(recruiting['tier1'])}. Alerts: {len(recruiting['tier1_alerts'])}.")
    else:
        lines.append("Tier 1 recruiting analysis unavailable — required intake files missing.")
    if recruiting["tier2_available"]:
        lines.append(f"Tier 2 metrics computed: {len(recruiting['tier2'])}.")
    else:
        lines.append("Tier 2 recruiting analysis unavailable — required intake files missing.")

    ops = recruiting.get("operational_exceptions") or {}
    lines.append("")
    lines.append("## Recruiting Operations Exceptions")
    if ops:
        lines.append(f"Operational exceptions generated: {ops.get('exception_count', 0)}.")
        for ex in (ops.get("exceptions") or [])[:20]:
            target = ex.get("req_id") or ex.get("candidate_id") or ex.get("recruiter_id") or "overall"
            lines.append(
                f"- [{ex.get('severity')}] {ex.get('exception_type')} ({target}): "
                f"{ex.get('observed_evidence')} Action: {ex.get('recommended_action')}"
            )
        for skipped in ops.get("not_evaluated") or []:
            lines.append(f"- [not evaluated] {skipped.get('exception_type')}: {skipped.get('reason')}")
    else:
        lines.append("Operational exception analysis unavailable - Tier 1 recruiting intake was not available.")

    lines.append("")
    lines.append("## Revenue Leakage / Commercial Risk")
    if revenue.get("available"):
        lines.append(f"Total estimated financial exposure flagged: ${revenue.get('total_exposure', 0):,.2f}")
        lines.append(f"Findings: {revenue.get('finding_count', 0)}")
    else:
        lines.append("Revenue analysis unavailable — required intake files missing.")

    lines.append("")
    lines.append("*Internal working copy — the branded .docx/.pdf alongside this file is the client deliverable.*")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# BRANDED DOCX (via Node template)
# ──────────────────────────────────────────────

def build_branded_docx(json_path: Path, client_name: str, out_path: Path) -> bool:
    script = APP_PATH / "consolidated_report_template.js"
    try:
        result = subprocess.run(
            ["node", str(script), str(json_path), client_name, str(out_path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            log.error(f"Consolidated docx generation failed: {result.stderr.strip()}")
            return False
        log.info(result.stdout.strip())
        return True
    except FileNotFoundError:
        log.error("Node.js not found — install Node to enable consolidated .docx generation.")
        return False
    except Exception as e:
        log.error(f"Consolidated docx generation error: {e}")
        return False


# ──────────────────────────────────────────────
# MAIN ENTRY POINT (called from main.py)
# ──────────────────────────────────────────────

def generate(consolidated: dict, json_path: Path, out_dir: Path, client_name: str, slug: str, today: str):
    priority_items = build_priority_items(consolidated)

    # Embed priority items into a render-ready JSON payload for the Node template,
    # so the Node side only renders — all ranking/labeling logic stays in Python.
    render_payload = dict(consolidated)
    render_payload["priority_items"] = priority_items
    render_json_path = out_dir / f"consolidated_render_{slug}_{today}.json"
    with open(render_json_path, "w") as f:
        json.dump(render_payload, f, indent=2, default=str)

    # 1. Markdown working copy
    md_body = build_working_copy_markdown(consolidated, priority_items)
    md_path = out_dir / f"consolidated_working_copy_{slug}_{today}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_body)
    log.info(f"Working copy written: {md_path}")

    # 2. Branded .docx
    docx_path = out_dir / f"Consolidated_Client_Report_{slug}_{today}.docx"
    ok = build_branded_docx(render_json_path, client_name, docx_path)
    if not ok:
        log.warning("Falling back to Markdown only — consolidated .docx was not generated.")
        return None, None

    # 3. PDF (reuses the existing conversion helper)
    pdf_path = convert_docx_to_pdf(docx_path, out_dir)
    if not pdf_path:
        log.warning("PDF conversion unavailable — the .docx above is still a valid deliverable.")

    return docx_path, pdf_path
