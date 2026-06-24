"""
tier2_crosssystem_agent.py
--------------------------
High-automation recruiting metrics requiring ATS + HRIS data joins.

Computes metrics 6, 7, 12, 13, 17, 20, 21.
Results auto-published. Anomalies flagged for human review.

Part of: recruiting-metrics-automation-engine
Author:  Paul Linn Solutions (PLS)
"""

import json
import logging
import statistics
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from connectors.ats_connector import ATSConnector
from connectors.hris_connector import HRISConnector
from connectors.survey_connector import SurveyConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config"
OUTPUT_PATH = Path(__file__).parent.parent / "outputs"


def load_config() -> tuple[dict, dict]:
    with open(CONFIG_PATH / "thresholds.yaml") as f:
        thresholds = yaml.safe_load(f)
    with open(CONFIG_PATH / "connections.yaml") as f:
        connections = yaml.safe_load(f)
    return thresholds, connections


# ──────────────────────────────────────────────
# METRIC CALCULATIONS
# ──────────────────────────────────────────────

def calc_first_year_attrition(hris_employees: list[dict], ats_hires: list[dict]) -> dict[str, Any]:
    """
    Metric 6: First-Year Attrition
    Join HRIS terminations to ATS hire records, filter tenure < 365 days.
    """
    hire_map = {h["employee_id"]: h for h in ats_hires if h.get("employee_id")}

    first_year_exits = []
    for emp in hris_employees:
        if not emp.get("termination_date"):
            continue
        term = datetime.fromisoformat(emp["termination_date"])
        hire = datetime.fromisoformat(emp["hire_date"])
        tenure_days = (term - hire).days
        if tenure_days <= 365:
            ats_record = hire_map.get(emp["id"], {})
            first_year_exits.append({
                "employee_id": emp["id"],
                "tenure_days": tenure_days,
                "attrition_type": "managed" if emp.get("termination_type") == "involuntary" else "unmanaged",
                "source_channel": ats_record.get("source"),
                "role": emp.get("title"),
                "department": emp.get("department"),
            })

    total_hires = len(ats_hires)
    rate = round(len(first_year_exits) / total_hires * 100, 1) if total_hires else 0
    managed = sum(1 for e in first_year_exits if e["attrition_type"] == "managed")
    unmanaged = len(first_year_exits) - managed

    return {
        "metric": "first_year_attrition",
        "total_hires_in_period": total_hires,
        "first_year_exits": len(first_year_exits),
        "rate_pct": rate,
        "managed_count": managed,
        "unmanaged_count": unmanaged,
        "by_exit": first_year_exits,
    }


def calc_quality_of_hire(hris_perf: list[dict], ats_hires: list[dict]) -> dict[str, Any]:
    """
    Metric 7: Quality of Hire
    First-year performance rating joined to ATS hire source.
    """
    hire_map = {h["employee_id"]: h for h in ats_hires if h.get("employee_id")}
    perf_map = {p["employee_id"]: p for p in hris_perf}

    results = []
    for emp_id, perf in perf_map.items():
        if emp_id not in hire_map:
            continue
        ats = hire_map[emp_id]
        rating = perf.get("first_year_rating")
        if rating is None:
            continue
        results.append({
            "employee_id": emp_id,
            "rating": rating,
            "meets_expectations": rating >= 3,
            "source_channel": ats.get("source"),
            "role": ats.get("role"),
            "department": ats.get("department"),
        })

    if not results:
        return {"metric": "quality_of_hire", "error": "insufficient data"}

    avg_rating = round(statistics.mean(r["rating"] for r in results), 2)
    success_count = sum(1 for r in results if r["meets_expectations"])
    success_ratio = round(success_count / len(results) * 100, 1)

    # QoH by source channel
    by_source: dict[str, list[float]] = {}
    for r in results:
        src = r["source_channel"] or "unknown"
        by_source.setdefault(src, []).append(r["rating"])
    source_qoh = [
        {"source": s, "avg_rating": round(statistics.mean(ratings), 2), "n": len(ratings)}
        for s, ratings in sorted(by_source.items(), key=lambda x: -statistics.mean(x[1]))
    ]

    return {
        "metric": "quality_of_hire",
        "avg_first_year_rating": avg_rating,
        "success_ratio_pct": success_ratio,
        "total_evaluated": len(results),
        "by_source_channel": source_qoh,
    }


def calc_cost_per_hire(finance_spend: dict, ats_hires: list[dict],
                       period_start: date, period_end: date) -> dict[str, Any]:
    """
    Metric 12: Cost Per Hire
    Total recruiting spend / number of hires in period.
    """
    hires_in_period = [
        h for h in ats_hires
        if h.get("hire_date") and
        period_start <= date.fromisoformat(h["hire_date"][:10]) <= period_end
    ]
    total_spend = sum(finance_spend.values())
    total_hires = len(hires_in_period)
    cph = round(total_spend / total_hires, 2) if total_hires else 0

    return {
        "metric": "cost_per_hire",
        "period": f"{period_start} to {period_end}",
        "total_spend": total_spend,
        "spend_breakdown": finance_spend,
        "total_hires": total_hires,
        "cost_per_hire": cph,
    }


def calc_candidate_experience(survey_responses: list[dict]) -> dict[str, Any]:
    """
    Metric 13: Candidate Experience (cNPS + structured scores)
    """
    if not survey_responses:
        return {"metric": "candidate_experience", "error": "no survey data"}

    nps_scores = [r["nps"] for r in survey_responses if r.get("nps") is not None]
    promoters = sum(1 for s in nps_scores if s >= 9)
    detractors = sum(1 for s in nps_scores if s <= 6)
    cnps = round((promoters - detractors) / len(nps_scores) * 100, 1) if nps_scores else 0

    process_scores = [r["process_rating"] for r in survey_responses if r.get("process_rating")]
    comm_scores = [r["communication_rating"] for r in survey_responses if r.get("communication_rating")]

    open_texts = [r["open_text"] for r in survey_responses if r.get("open_text")]

    return {
        "metric": "candidate_experience",
        "response_count": len(survey_responses),
        "cnps": cnps,
        "avg_process_rating": round(statistics.mean(process_scores), 2) if process_scores else None,
        "avg_communication_rating": round(statistics.mean(comm_scores), 2) if comm_scores else None,
        "open_text_responses": open_texts,
        "note": "Send open_text_responses to briefing_agent for LLM theme extraction",
    }


def calc_recruitment_funnel(candidates: list[dict], stages: list[str]) -> dict[str, Any]:
    """
    Metric 17: Recruitment Funnel Effectiveness
    Conversion % at each stage.
    """
    stage_counts: dict[str, int] = {s: 0 for s in stages}
    for c in candidates:
        reached = c.get("furthest_stage")
        if reached in stage_counts:
            for stage in stages:
                stage_counts[stage] += 1
                if stage == reached:
                    break

    funnel = []
    prev = None
    for stage in stages:
        count = stage_counts[stage]
        conv = round(count / prev * 100, 1) if prev else 100.0
        funnel.append({"stage": stage, "count": count, "conversion_from_prev_pct": conv})
        prev = count

    # Identify biggest drop
    biggest_drop = min(
        [f for f in funnel if f["conversion_from_prev_pct"] < 100],
        key=lambda x: x["conversion_from_prev_pct"],
        default=None
    )

    return {
        "metric": "recruitment_funnel_effectiveness",
        "stages": funnel,
        "biggest_drop_stage": biggest_drop["stage"] if biggest_drop else None,
    }


def calc_adverse_impact(candidates: list[dict], protected_groups: list[str]) -> dict[str, Any]:
    """
    Metric 20: Adverse Impact
    Applies the 4/5ths (80%) rule across protected classes.
    """
    group_data: dict[str, dict] = {}
    for c in candidates:
        group = c.get("demographic_group", "unknown")
        if group not in group_data:
            group_data[group] = {"total": 0, "selected": 0}
        group_data[group]["total"] += 1
        if c.get("status") == "hired":
            group_data[group]["selected"] += 1

    selection_rates = {
        g: round(d["selected"] / d["total"] * 100, 2)
        for g, d in group_data.items() if d["total"] > 0
    }

    if not selection_rates:
        return {"metric": "adverse_impact", "error": "insufficient demographic data"}

    highest_rate_group = max(selection_rates, key=selection_rates.get)
    highest_rate = selection_rates[highest_rate_group]

    impact_ratios = []
    flags = []
    for group, rate in selection_rates.items():
        if group == highest_rate_group:
            continue
        ratio = round(rate / highest_rate, 3) if highest_rate else 0
        adverse = ratio < 0.8
        impact_ratios.append({"group": group, "selection_rate_pct": rate, "impact_ratio": ratio, "adverse_impact_flag": adverse})
        if adverse:
            flags.append(group)

    return {
        "metric": "adverse_impact",
        "reference_group": highest_rate_group,
        "reference_selection_rate_pct": highest_rate,
        "group_analysis": impact_ratios,
        "adverse_impact_flags": flags,
        "compliance_review_required": len(flags) > 0,
        "note": "Results flagged for adverse impact must be reviewed by HR/Legal before action.",
    }


def calc_recruiter_performance(ats_hires: list[dict], ats_reqs: list[dict],
                               survey_responses: list[dict], hris_perf: list[dict]) -> dict[str, Any]:
    """
    Metric 21: Recruiter Performance Metrics
    Aggregated scorecard per recruiter.
    """
    recruiters: dict[str, dict] = {}

    for req in ats_reqs:
        rec = req.get("recruiter_id", "unknown")
        if rec not in recruiters:
            recruiters[rec] = {"reqs": 0, "fills": 0, "tth_days": [], "cnps_scores": [], "qoh_ratings": []}
        recruiters[rec]["reqs"] += 1
        if req.get("status") == "filled":
            recruiters[rec]["fills"] += 1

    for h in ats_hires:
        rec = h.get("recruiter_id", "unknown")
        if rec in recruiters and h.get("days_to_hire"):
            recruiters[rec]["tth_days"].append(h["days_to_hire"])

    for sr in survey_responses:
        rec = sr.get("recruiter_id", "unknown")
        if rec in recruiters and sr.get("nps") is not None:
            recruiters[rec]["cnps_scores"].append(sr["nps"])

    scorecards = []
    for rec_id, data in recruiters.items():
        scorecards.append({
            "recruiter_id": rec_id,
            "reqs_owned": data["reqs"],
            "reqs_filled": data["fills"],
            "fill_rate_pct": round(data["fills"] / data["reqs"] * 100, 1) if data["reqs"] else 0,
            "avg_tth_days": round(statistics.mean(data["tth_days"]), 1) if data["tth_days"] else None,
            "cnps": round(statistics.mean(data["cnps_scores"]), 1) if data["cnps_scores"] else None,
        })

    return {
        "metric": "recruiter_performance",
        "scorecards": sorted(scorecards, key=lambda x: -x["fill_rate_pct"]),
        "note": "Route to hiring manager for narrative review before sharing with recruiter",
    }


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def run():
    log.info("Tier 2 Cross-System Agent starting")
    thresholds, connections = load_config()

    ats = ATSConnector(connections["ats"])
    hris = HRISConnector(connections["hris"])
    survey = SurveyConnector(connections["survey"])

    since = date.today() - timedelta(days=90)
    period_start = date.today() - timedelta(days=90)
    period_end = date.today()

    reqs = ats.get_requisitions(since=since)
    candidates = ats.get_candidates_all(since=since)
    hires = [c for c in candidates if c.get("status") == "hired"]
    hris_employees = hris.get_employees(since=since)
    hris_perf = hris.get_performance_ratings(since=since)
    survey_responses = survey.get_responses(since=since)
    finance_spend = connections.get("recruiting_spend_override", {
        "job_boards": 12000,
        "agency_fees": 45000,
        "recruiter_salaries": 78000,
        "tools_and_ats": 8000,
    })

    stages = connections.get("funnel_stages", [
        "applied", "phone_screen", "hiring_manager_review",
        "interview", "final_round", "offer", "hired"
    ])

    results = {
        "first_year_attrition":          calc_first_year_attrition(hris_employees, hires),
        "quality_of_hire":               calc_quality_of_hire(hris_perf, hires),
        "cost_per_hire":                 calc_cost_per_hire(finance_spend, hires, period_start, period_end),
        "candidate_experience":          calc_candidate_experience(survey_responses),
        "recruitment_funnel_effectiveness": calc_recruitment_funnel(candidates, stages),
        "adverse_impact":                calc_adverse_impact(candidates, []),
        "recruiter_performance":         calc_recruiter_performance(hires, reqs, survey_responses, hris_perf),
    }

    out_dir = OUTPUT_PATH / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_path = out_dir / f"tier2_report_{today}.json"
    with open(out_path, "w") as f:
        json.dump({"generated_at": datetime.utcnow().isoformat(), "tier": 2, "metrics": results},
                  f, indent=2, default=str)

    # Surface compliance flag
    ai = results.get("adverse_impact", {})
    if ai.get("compliance_review_required"):
        log.warning(f"ADVERSE IMPACT FLAG: groups {ai['adverse_impact_flags']} — route to HR/Legal")

    log.info(f"Tier 2 complete — {len(results)} metrics computed")
    return results


if __name__ == "__main__":
    run()
