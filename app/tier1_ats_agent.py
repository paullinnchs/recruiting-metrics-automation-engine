"""
tier1_ats_agent.py
------------------
Fully automatable recruiting metrics — ATS data only.

Computes metrics 1-5, 10-11, 14-16, 22 on a scheduled basis.
No human input required. Outputs reports and threshold alerts.

Part of: recruiting-metrics-automation-engine
Author:  Paul Linn Solutions (PLS)
"""

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests
import yaml
from dotenv import load_dotenv

from ats_connector import ATSConnector

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config"
OUTPUT_PATH = Path(__file__).parent.parent / "outputs"


def load_thresholds() -> dict:
    with open(CONFIG_PATH / "thresholds.yaml") as f:
        return yaml.safe_load(f)


def load_connections() -> dict:
    with open(CONFIG_PATH / "connections.yaml") as f:
        return yaml.safe_load(f)


# ──────────────────────────────────────────────
# METRIC CALCULATIONS
# ──────────────────────────────────────────────

def calc_time_to_fill(reqs: list[dict]) -> dict[str, Any]:
    """
    Metric 1: Time to Fill
    Days from req approval to offer accepted.
    """
    results = []
    for req in reqs:
        if req.get("status") == "filled" and req.get("approved_at") and req.get("offer_accepted_at"):
            days = (
                datetime.fromisoformat(req["offer_accepted_at"]) -
                datetime.fromisoformat(req["approved_at"])
            ).days
            results.append({"req_id": req["id"], "role": req["title"], "dept": req["department"], "days": days})

    avg = round(sum(r["days"] for r in results) / len(results), 1) if results else 0
    return {"metric": "time_to_fill", "average_days": avg, "by_req": results}


def calc_time_to_hire(candidates: list[dict]) -> dict[str, Any]:
    """
    Metric 2: Time to Hire
    Days from first contact/application to offer accepted.
    """
    results = []
    for c in candidates:
        if c.get("status") == "hired" and c.get("applied_at") and c.get("offer_accepted_at"):
            days = (
                datetime.fromisoformat(c["offer_accepted_at"]) -
                datetime.fromisoformat(c["applied_at"])
            ).days
            results.append({"candidate_id": c["id"], "role": c["role"], "days": days,
                            "stage_gaps": c.get("stage_gaps", [])})

    avg = round(sum(r["days"] for r in results) / len(results), 1) if results else 0
    bottleneck = _find_stage_bottleneck(results)
    return {"metric": "time_to_hire", "average_days": avg, "bottleneck_stage": bottleneck, "by_candidate": results}


def _find_stage_bottleneck(results: list[dict]) -> str | None:
    stage_totals: dict[str, list[int]] = {}
    for r in results:
        for gap in r.get("stage_gaps", []):
            stage_totals.setdefault(gap["stage"], []).append(gap["days"])
    if not stage_totals:
        return None
    return max(stage_totals, key=lambda s: sum(stage_totals[s]) / len(stage_totals[s]))


def calc_source_of_hire(hires: list[dict]) -> dict[str, Any]:
    """
    Metric 3: Source of Hire
    Which channel produced each hire.
    """
    source_counts: dict[str, int] = {}
    for h in hires:
        src = h.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    total = len(hires)
    breakdown = [
        {"source": s, "count": c, "pct": round(c / total * 100, 1)}
        for s, c in sorted(source_counts.items(), key=lambda x: -x[1])
    ]
    return {"metric": "source_of_hire", "total_hires": total, "breakdown": breakdown}


def calc_sourcing_channel_effectiveness(applications: list[dict]) -> dict[str, Any]:
    """
    Metric 4: Sourcing Channel Effectiveness
    Applications and conversion rate per channel.
    """
    channel_data: dict[str, dict] = {}
    for app in applications:
        src = app.get("source", "unknown")
        if src not in channel_data:
            channel_data[src] = {"applications": 0, "hires": 0}
        channel_data[src]["applications"] += 1
        if app.get("status") == "hired":
            channel_data[src]["hires"] += 1

    results = []
    for src, data in channel_data.items():
        conv = round(data["hires"] / data["applications"] * 100, 2) if data["applications"] else 0
        results.append({"source": src, **data, "conversion_pct": conv})

    return {"metric": "sourcing_channel_effectiveness", "channels": sorted(results, key=lambda x: -x["conversion_pct"])}


def calc_sourcing_channel_cost(ad_spend: dict[str, float], hires_by_source: dict[str, int]) -> dict[str, Any]:
    """
    Metric 5: Sourcing Channel Cost
    Ad spend / successful applicants per platform.
    """
    results = []
    for platform, spend in ad_spend.items():
        hires = hires_by_source.get(platform, 0)
        cph = round(spend / hires, 2) if hires else None
        results.append({"platform": platform, "spend": spend, "hires": hires, "cost_per_hire": cph})

    return {"metric": "sourcing_channel_cost", "by_platform": sorted(results, key=lambda x: x["cost_per_hire"] or 9999)}


def calc_applicants_per_opening(reqs: list[dict], applications: list[dict]) -> dict[str, Any]:
    """
    Metric 10: Applicants Per Opening
    """
    req_app_counts: dict[str, int] = {}
    for app in applications:
        rid = app.get("req_id")
        if rid:
            req_app_counts[rid] = req_app_counts.get(rid, 0) + 1

    results = []
    for req in reqs:
        count = req_app_counts.get(req["id"], 0)
        days_open = (date.today() - date.fromisoformat(req["approved_at"][:10])).days if req.get("approved_at") else 0
        results.append({"req_id": req["id"], "role": req["title"], "applicants": count, "days_open": days_open})

    avg = round(sum(r["applicants"] for r in results) / len(results), 1) if results else 0
    return {"metric": "applicants_per_opening", "average": avg, "by_req": results}


def calc_selection_ratio(reqs: list[dict], hires: list[dict], applications: list[dict]) -> dict[str, Any]:
    """
    Metric 11: Selection Ratio — Hires / Total applicants
    """
    total_apps = len(applications)
    total_hires = len(hires)
    ratio = round(total_hires / total_apps * 100, 2) if total_apps else 0
    return {"metric": "selection_ratio", "total_applicants": total_apps, "total_hires": total_hires, "ratio_pct": ratio}


def calc_offer_acceptance_rate(offers: list[dict]) -> dict[str, Any]:
    """
    Metric 14: Offer Acceptance Rate
    """
    extended = len(offers)
    accepted = sum(1 for o in offers if o.get("outcome") == "accepted")
    rate = round(accepted / extended * 100, 1) if extended else 0
    return {"metric": "offer_acceptance_rate", "offers_extended": extended, "accepted": accepted, "rate_pct": rate}


def calc_pct_open_positions(open_reqs: int, total_headcount: int) -> dict[str, Any]:
    """
    Metric 15: % of Open Positions (vacancy rate)
    """
    rate = round(open_reqs / total_headcount * 100, 1) if total_headcount else 0
    return {"metric": "pct_open_positions", "open_reqs": open_reqs, "total_headcount": total_headcount, "vacancy_rate_pct": rate}


def calc_application_completion_rate(sessions: list[dict]) -> dict[str, Any]:
    """
    Metric 16: Application Completion Rate
    Started vs. submitted applications.
    """
    started = len(sessions)
    completed = sum(1 for s in sessions if s.get("submitted"))
    rate = round(completed / started * 100, 1) if started else 0
    return {"metric": "application_completion_rate", "started": started, "completed": completed, "rate_pct": rate}


def calc_fill_rate(reqs: list[dict], window_days: int = 30) -> dict[str, Any]:
    """
    Metric 22: Fill Rate — % of reqs filled within target window
    """
    cutoff = date.today() - timedelta(days=window_days)
    closed = [r for r in reqs if r.get("closed_at") and
              date.fromisoformat(r["closed_at"][:10]) >= cutoff]
    filled = sum(1 for r in closed if r.get("close_reason") == "filled")
    rate = round(filled / len(closed) * 100, 1) if closed else 0
    return {"metric": "fill_rate", "closed_reqs": len(closed), "filled": filled, "fill_rate_pct": rate}


# ──────────────────────────────────────────────
# ALERTING
# ──────────────────────────────────────────────

def check_thresholds(results: dict, thresholds: dict) -> list[dict]:
    alerts = []

    def alert(metric, level, message, value):
        alerts.append({"metric": metric, "level": level, "message": message, "value": value,
                        "timestamp": datetime.utcnow().isoformat()})

    ttf = results.get("time_to_fill", {})
    if ttf:
        t = thresholds.get("time_to_fill", {})
        if ttf["average_days"] >= t.get("critical_days", 45):
            alert("time_to_fill", "CRITICAL", f"Avg TTF {ttf['average_days']} days exceeds critical threshold", ttf["average_days"])
        elif ttf["average_days"] >= t.get("warning_days", 30):
            alert("time_to_fill", "WARNING", f"Avg TTF {ttf['average_days']} days approaching threshold", ttf["average_days"])

    oar = results.get("offer_acceptance_rate", {})
    if oar:
        t = thresholds.get("offer_acceptance_rate", {})
        if oar["rate_pct"] <= t.get("critical_pct", 75):
            alert("offer_acceptance_rate", "CRITICAL", f"OAR {oar['rate_pct']}% — severe offer conversion issue", oar["rate_pct"])
        elif oar["rate_pct"] <= t.get("warning_pct", 85):
            alert("offer_acceptance_rate", "WARNING", f"OAR {oar['rate_pct']}% — dropping below target", oar["rate_pct"])

    fill = results.get("fill_rate", {})
    if fill:
        t = thresholds.get("fill_rate", {})
        if fill["fill_rate_pct"] < t.get("warning_pct", 70):
            alert("fill_rate", "WARNING", f"Fill rate {fill['fill_rate_pct']}% below target", fill["fill_rate_pct"])

    vacancy = results.get("pct_open_positions", {})
    if vacancy:
        t = thresholds.get("vacancy_rate", {})
        if vacancy["vacancy_rate_pct"] >= t.get("critical_pct", 15):
            alert("pct_open_positions", "CRITICAL", f"Vacancy rate {vacancy['vacancy_rate_pct']}% — org capacity at risk", vacancy["vacancy_rate_pct"])

    return alerts


# ──────────────────────────────────────────────
# REPORT WRITER
# ──────────────────────────────────────────────

def write_report(results: dict, alerts: list[dict]) -> Path:
    today = date.today().isoformat()
    report = {"generated_at": datetime.utcnow().isoformat(), "tier": 1, "metrics": results, "alerts": alerts}
    out_dir = OUTPUT_PATH / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"tier1_report_{today}.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log.info(f"Report written: {out_path}")
    return out_path


def write_alerts(alerts: list[dict]) -> None:
    if not alerts:
        return
    out_dir = OUTPUT_PATH / "alerts"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_path = out_dir / f"alerts_{today}.json"
    with open(out_path, "w") as f:
        json.dump(alerts, f, indent=2, default=str)
    log.info(f"{len(alerts)} alert(s) written: {out_path}")


# ──────────────────────────────────────────────
# SLACK NOTIFICATIONS
# ──────────────────────────────────────────────

# Translates each technical metric into business-readable language for
# non-technical stakeholders (recruiting managers, VP of Talent Acquisition,
# operational leaders). Each entry provides a plain-English metric name, the
# unit used to display the value, the business impact, and a recommended action.
METRIC_BUSINESS_CONTEXT: dict[str, dict[str, str]] = {
    "time_to_fill": {
        "label": "Time to Fill",
        "unit": "days",
        "impact": ("Roles are staying open longer than target, which can delay "
                   "hiring goals, increase recruiter workload, and slow revenue "
                   "or service delivery in affected teams."),
        "action": "Review aging requisitions and rebalance recruiter capacity.",
    },
    "time_to_hire": {
        "label": "Time to Hire",
        "unit": "days",
        "impact": ("Candidates are spending too long in the hiring process, "
                   "which increases the risk of drop-off and losing top talent "
                   "to faster competitors."),
        "action": "Identify the slowest interview stages and remove scheduling bottlenecks.",
    },
    "offer_acceptance_rate": {
        "label": "Offer Acceptance Rate",
        "unit": "%",
        "impact": ("Candidates are not accepting offers, which can delay hiring "
                   "goals and indicate compensation or candidate experience issues."),
        "action": "Review recent declined offers and identify patterns.",
    },
    "fill_rate": {
        "label": "Fill Rate",
        "unit": "%",
        "impact": ("Open positions are not being filled fast enough, which can "
                   "impact revenue targets, service delivery, and recruiter productivity."),
        "action": "Review aging requisitions and recruiter workload.",
    },
    "pct_open_positions": {
        "label": "Open Position (Vacancy) Rate",
        "unit": "%",
        "impact": ("A high share of roles are unfilled, putting organizational "
                   "capacity and delivery commitments at risk."),
        "action": "Prioritize critical and revenue-generating roles for immediate sourcing focus.",
    },
}


def _format_metric_value(value: Any, unit: str) -> str:
    """Render a metric value with its business unit (e.g. '0%', '38 days')."""
    if value is None:
        return "N/A"
    if unit == "%":
        return f"{value}%"
    if unit:
        return f"{value} {unit}"
    return str(value)


def _build_business_message(alerts: list[dict], total_metrics: int | None) -> str:
    """Translate threshold alerts into a leadership-readable Slack message."""
    # Surface the most severe alerts first.
    severity_rank = {"CRITICAL": 0, "WARNING": 1}
    ranked = sorted(alerts, key=lambda a: severity_rank.get(a.get("level", ""), 99))

    count = len(ranked)
    issue_word = "issue" if count == 1 else "issues"
    header = "*Recruiting Metrics Alert — Weekly Snapshot*"
    intro = f"*{count} {issue_word} need immediate attention.*"

    blocks = [header, "", intro, ""]
    for i, a in enumerate(ranked, start=1):
        ctx = METRIC_BUSINESS_CONTEXT.get(a.get("metric", ""), {})
        label = ctx.get("label") or a.get("metric", "Metric").replace("_", " ").title()
        value = _format_metric_value(a.get("value"), ctx.get("unit", ""))
        impact = ctx.get("impact") or a.get("message", "This metric crossed an alert threshold.")
        action = ctx.get("action") or "Review the underlying data and investigate root cause."

        blocks.append(f"*{i}. {label} = {value}*")
        blocks.append("*Business Impact:*")
        blocks.append(impact)
        blocks.append("*Recommended Action:*")
        blocks.append(action)
        blocks.append("")

    analyzed = total_metrics if total_metrics is not None else "Multiple"
    metric_word = "metric" if count == 1 else "metrics"
    blocks.append("*Summary:*")
    blocks.append(
        f"{analyzed} recruiting metrics were analyzed. {count} {metric_word} crossed "
        "alert thresholds requiring leadership review."
    )

    return "\n".join(blocks)


def notify_slack(alerts: list[dict], total_metrics: int | None = None) -> bool:
    """
    Post a business-readable summary of generated alerts to Slack.

    Translates technical metric alerts into leadership-friendly language
    (metric name, business impact, recommended action) so a non-technical
    stakeholder can immediately understand what they are looking at and why
    it matters.

    Reads SLACK_WEBHOOK_URL from the environment (.env). Fails safe: if the
    webhook is not configured or the request fails, logs a warning and returns
    False so the caller can continue uninterrupted. Never logs the webhook URL.
    """
    if not alerts:
        return False

    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        log.info("Slack webhook not configured (SLACK_WEBHOOK_URL unset) — skipping notification")
        return False

    text = _build_business_message(alerts, total_metrics)

    try:
        resp = requests.post(webhook_url, json={"text": text}, timeout=10)
        resp.raise_for_status()
        log.info(f"Slack notification sent ({len(alerts)} alert(s) summarized)")
        return True
    except requests.RequestException as e:
        # Avoid leaking the webhook URL, which may appear in the exception.
        log.warning(f"Slack notification failed ({type(e).__name__}) — continuing")
        return False


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def run():
    log.info("Tier 1 ATS Agent starting")
    thresholds = load_thresholds()
    connections = load_connections()

    ats = ATSConnector(connections["ats"])
    since = date.today() - timedelta(days=90)

    reqs = ats.get_requisitions(since=since)
    candidates = ats.get_candidates_all(since=since)
    hires = [c for c in candidates if c.get("status") == "hired"]
    applications = ats.get_applications(since=since)
    offers = ats.get_offers(since=since)
    sessions = ats.get_application_sessions(since=since)

    # Pull ad spend from config (or connector if available)
    ad_spend = connections.get("ad_spend_override", {})
    hires_by_source: dict[str, int] = {}
    for h in hires:
        src = h.get("source", "unknown")
        hires_by_source[src] = hires_by_source.get(src, 0) + 1

    results = {
        "time_to_fill":                calc_time_to_fill(reqs),
        "time_to_hire":                calc_time_to_hire(candidates),
        "source_of_hire":              calc_source_of_hire(hires),
        "sourcing_channel_effectiveness": calc_sourcing_channel_effectiveness(applications),
        "sourcing_channel_cost":       calc_sourcing_channel_cost(ad_spend, hires_by_source),
        "applicants_per_opening":      calc_applicants_per_opening(reqs, applications),
        "selection_ratio":             calc_selection_ratio(reqs, hires, applications),
        "offer_acceptance_rate":       calc_offer_acceptance_rate(offers),
        "pct_open_positions":          calc_pct_open_positions(
                                           open_reqs=len([r for r in reqs if r.get("status") == "open"]),
                                           total_headcount=connections.get("headcount_override", 500)
                                       ),
        "application_completion_rate": calc_application_completion_rate(sessions),
        "fill_rate":                   calc_fill_rate(reqs),
    }

    alerts = check_thresholds(results, thresholds)
    write_report(results, alerts)
    write_alerts(alerts)
    notify_slack(alerts, total_metrics=len(results))

    log.info(f"Tier 1 complete — {len(results)} metrics computed, {len(alerts)} alerts generated")
    return results, alerts


if __name__ == "__main__":
    run()
