"""
main.py
--------
Single entry point for a full client analysis:

    python app/main.py <client-intake-folder>

Flow: client intake -> validation -> Tier 1 recruiting analysis
      + Tier 2 recruiting analysis + revenue-leak analysis
      -> one consolidated executive report (.docx / .pdf).

This file does not reimplement any calculation. It loads intake data into
the same normalized shapes the existing modules already expect, then calls
their existing calc_/check_ functions directly:

  - tier1_ats_agent.py   (recruiting Tier 1 metrics + calc_ functions)
  - tier2_crosssystem_agent.py (recruiting Tier 2 metrics + calc_ functions)
  - leak_detection_agent.py    (revenue-leak check_ functions)
  - leak_report_generator.py   (PDF conversion, reused as-is)

Individual modules remain directly runnable on their own for
development/testing — this file only adds the orchestration layer on top.

Part of: recruiting-metrics-automation-engine
Author:  Paul Linn Solutions (PLS)
"""

import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from client_intake import validate_intake, load_recruiting_data, build_billing_connector_config
from billing_connector import BillingConnector

import tier1_ats_agent as t1
import tier2_crosssystem_agent as t2
import leak_detection_agent as leak
import consolidated_report_generator as report_gen

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config"
OUTPUT_PATH = Path(__file__).parent.parent / "outputs"

DEFAULT_FUNNEL_STAGES = [
    "applied", "phone_screen", "hiring_manager_review",
    "interview", "final_round", "offer", "hired",
]
DEFAULT_HEADCOUNT = 500
DEFAULT_RECRUITING_SPEND = {
    "job_boards": 12000, "agency_fees": 45000,
    "recruiter_salaries": 78000, "tools_and_ats": 8000,
}
DEFAULT_AD_SPEND = {"linkedin": 4200, "indeed": 1800, "glassdoor": 600, "employee_referral": 0}


# ──────────────────────────────────────────────
# TIER 1
# ──────────────────────────────────────────────

def run_tier1(data: dict, thresholds: dict) -> tuple[dict, list[dict]]:
    reqs = data["reqs"]
    candidates = data["candidates"]
    applications = data["applications"]
    offers = data["offers"]
    sessions = data["sessions"]
    config = data.get("config") or {}

    hires = [c for c in candidates if c.get("status") == "hired"]
    hires_by_source: dict[str, int] = {}
    for h in hires:
        src = h.get("source", "unknown")
        hires_by_source[src] = hires_by_source.get(src, 0) + 1

    ad_spend = config.get("ad_spend_override", DEFAULT_AD_SPEND)
    headcount = config.get("headcount_override", DEFAULT_HEADCOUNT)

    results = {
        "time_to_fill": t1.calc_time_to_fill(reqs),
        "time_to_hire": t1.calc_time_to_hire(candidates),
        "source_of_hire": t1.calc_source_of_hire(hires),
        "sourcing_channel_effectiveness": t1.calc_sourcing_channel_effectiveness(applications),
        "sourcing_channel_cost": t1.calc_sourcing_channel_cost(ad_spend, hires_by_source),
        "applicants_per_opening": t1.calc_applicants_per_opening(reqs, applications),
        "selection_ratio": t1.calc_selection_ratio(reqs, hires, applications),
        "offer_acceptance_rate": t1.calc_offer_acceptance_rate(offers),
        "pct_open_positions": t1.calc_pct_open_positions(
            open_reqs=len([r for r in reqs if r.get("status") == "open"]),
            total_headcount=headcount,
        ),
        "application_completion_rate": t1.calc_application_completion_rate(sessions),
        "fill_rate": t1.calc_fill_rate(reqs),
    }
    alerts = t1.check_thresholds(results, thresholds)
    return results, alerts


# ──────────────────────────────────────────────
# TIER 2
# ──────────────────────────────────────────────

def run_tier2(data: dict) -> dict:
    reqs = data["reqs"]
    candidates = data["candidates"]
    hires = [c for c in candidates if c.get("status") == "hired"]
    hris_employees = data["hris_employees"]
    hris_perf = data["hris_performance"]
    survey_responses = data["survey_responses"]
    config = data.get("config") or {}

    finance_spend = config.get("recruiting_spend_override", DEFAULT_RECRUITING_SPEND)
    stages = config.get("funnel_stages", DEFAULT_FUNNEL_STAGES)

    period_start = date.today() - timedelta(days=90)
    period_end = date.today()

    return {
        "first_year_attrition": t2.calc_first_year_attrition(hris_employees, hires),
        "quality_of_hire": t2.calc_quality_of_hire(hris_perf, hires),
        "cost_per_hire": t2.calc_cost_per_hire(finance_spend, hires, period_start, period_end),
        "candidate_experience": t2.calc_candidate_experience(survey_responses),
        "recruitment_funnel_effectiveness": t2.calc_recruitment_funnel(candidates, stages),
        "adverse_impact": t2.calc_adverse_impact(candidates, []),
        "recruiter_performance": t2.calc_recruiter_performance(hires, reqs, survey_responses, hris_perf),
    }


# ──────────────────────────────────────────────
# REVENUE LEAK
# ──────────────────────────────────────────────

def run_revenue(intake_dir: str) -> dict:
    with open(CONFIG_PATH / "leak_rules.yaml") as f:
        rules = yaml.safe_load(f)

    billing_conn = BillingConnector(build_billing_connector_config(intake_dir))
    billing = billing_conn.get_billing_records()
    rate_cards = billing_conn.get_rate_cards()
    contracts = billing_conn.get_contracts()

    findings: list[dict] = []
    findings += leak.check_missed_markup(billing, rate_cards, rules)
    findings += leak.check_stale_rate_card_billing(billing, rate_cards, rules)
    findings += leak.check_off_contract_spend(billing, contracts, rules)
    findings += leak.check_classification_risk(billing, contracts, rules)
    findings += leak.check_hours_variance(billing, rules)
    findings = leak.score_findings(findings, rules)

    total_exposure = round(sum(f.get("dollar_impact") or 0 for f in findings), 2)
    by_category: dict[str, dict] = {}
    for f in findings:
        cat = f["category"]
        by_category.setdefault(cat, {"count": 0, "dollar_impact": 0.0})
        by_category[cat]["count"] += 1
        by_category[cat]["dollar_impact"] += f.get("dollar_impact") or 0
    for cat in by_category:
        by_category[cat]["dollar_impact"] = round(by_category[cat]["dollar_impact"], 2)

    return {
        "total_exposure": total_exposure,
        "finding_count": len(findings),
        "by_category": by_category,
        "findings": findings,
    }


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def run_client_analysis(intake_dir: str) -> dict:
    log.info(f"Client analysis starting — intake: {intake_dir}")

    validation = validate_intake(intake_dir)
    client_id = validation["client_id"]
    client_name = validation["client_name"]

    log.info(f"Client: {client_name} ({client_id})")
    log.info(f"  Recruiting Tier 1: {'available' if validation['recruiting_tier1']['available'] else 'UNAVAILABLE — missing ' + str(validation['recruiting_tier1']['missing'])}")
    log.info(f"  Recruiting Tier 2: {'available' if validation['recruiting_tier2']['available'] else 'UNAVAILABLE — missing ' + str(validation['recruiting_tier2']['missing'])}")
    log.info(f"  Revenue analysis:  {'available' if validation['revenue']['available'] else 'UNAVAILABLE — missing ' + str(validation['revenue']['missing'])}")

    recruiting_data = load_recruiting_data(intake_dir, validation)

    tier1_results, tier1_alerts = (None, [])
    tier2_results = None
    revenue_results = None

    if validation["recruiting_tier1"]["available"]:
        thresholds_path = CONFIG_PATH / "thresholds.yaml"
        with open(thresholds_path) as f:
            thresholds = yaml.safe_load(f)
        tier1_results, tier1_alerts = run_tier1(recruiting_data, thresholds)
        log.info(f"Tier 1 complete — {len(tier1_results)} metrics, {len(tier1_alerts)} alerts")

    if validation["recruiting_tier2"]["available"]:
        tier2_results = run_tier2(recruiting_data)
        log.info(f"Tier 2 complete — {len(tier2_results)} metrics")

    if validation["revenue"]["available"]:
        revenue_results = run_revenue(intake_dir)
        log.info(f"Revenue analysis complete — ${revenue_results['total_exposure']:,.2f} total exposure")

    consolidated = {
        "client_id": client_id,
        "client_name": client_name,
        "generated_at": datetime.now().isoformat(),
        "validation": validation,
        "recruiting": {
            "tier1_available": validation["recruiting_tier1"]["available"],
            "tier2_available": validation["recruiting_tier2"]["available"],
            "tier1": tier1_results,
            "tier1_alerts": tier1_alerts,
            "tier2": tier2_results,
        },
        "revenue": {
            "available": validation["revenue"]["available"],
            **(revenue_results or {}),
        },
    }

    out_dir = OUTPUT_PATH / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    slug = client_id.lower().replace(" ", "_")
    json_path = out_dir / f"consolidated_report_{slug}_{today}.json"
    with open(json_path, "w") as f:
        json.dump(consolidated, f, indent=2, default=str)
    log.info(f"Consolidated data written: {json_path}")

    docx_path, pdf_path = report_gen.generate(consolidated, json_path, out_dir, client_name, slug, today)

    log.info("Client analysis complete.")
    return {
        "consolidated": consolidated,
        "json_path": str(json_path),
        "docx_path": str(docx_path) if docx_path else None,
        "pdf_path": str(pdf_path) if pdf_path else None,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python app/main.py <client-intake-folder>")
        sys.exit(1)
    run_client_analysis(sys.argv[1])
