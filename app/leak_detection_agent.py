"""
leak_detection_agent.py
------------------------
Workforce Revenue Leak Workflow Sprint — detection engine.
"""

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from billing_connector import BillingConnector
from ats_connector import ATSConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config"
OUTPUT_PATH = Path(__file__).parent.parent / "outputs"


def load_config() -> tuple[dict, dict]:
    with open(CONFIG_PATH / "leak_rules.yaml") as f:
        rules = yaml.safe_load(f)
    with open(CONFIG_PATH / "connections.yaml") as f:
        connections = yaml.safe_load(f)
    return rules, connections


def _severity_for_amount(amount: float, bands: dict) -> str:
    if amount <= bands.get("info_max", 500):
        return "INFO"
    if amount <= bands.get("warning_max", 5000):
        return "WARNING"
    return "CRITICAL"


def _match_rate_card(record: dict, rate_cards: list[dict]) -> dict | None:
    for rc in rate_cards:
        if (rc.get("supplier_vendor") == record.get("supplier_vendor")
                and rc.get("role_title") == record.get("role_title")):
            return rc
    return None


def _match_contract(record: dict, contracts: list[dict]) -> dict | None:
    if record.get("contract_id"):
        for c in contracts:
            if c.get("contract_id") == record.get("contract_id"):
                return c
    for c in contracts:
        if c.get("supplier_vendor") == record.get("supplier_vendor"):
            return c
    return None


def check_missed_markup(billing: list[dict], rate_cards: list[dict], rules: dict) -> list[dict]:
    cfg = rules["markup_leak"]
    findings = []
    for r in billing:
        rc = _match_rate_card(r, rate_cards)
        if not rc or not rc.get("contracted_bill_rate"):
            continue
        variance_pct = round(
            (rc["contracted_bill_rate"] - r["bill_rate"]) / rc["contracted_bill_rate"] * 100, 2
        ) if rc["contracted_bill_rate"] else 0
        if variance_pct < cfg["min_variance_pct"]:
            continue
        dollar_impact = round((rc["contracted_bill_rate"] - r["bill_rate"]) * r["hours_invoiced"], 2)
        if dollar_impact < cfg["min_dollar_threshold"]:
            continue
        findings.append({
            "category": "missed_markup",
            "worker_id": r["worker_id"], "worker_name": r["worker_name"],
            "supplier_vendor": r["supplier_vendor"], "role_title": r["role_title"],
            "period": f"{r['period_start']} to {r['period_end']}",
            "contracted_bill_rate": rc["contracted_bill_rate"], "actual_bill_rate": r["bill_rate"],
            "variance_pct": variance_pct, "dollar_impact": dollar_impact,
            "description": (
                f"{r['worker_name'] or r['worker_id']} billed at ${r['bill_rate']}/hr vs. "
                f"contracted ${rc['contracted_bill_rate']}/hr ({variance_pct}% under) for "
                f"{r['hours_invoiced']} hours."
            ),
            "recommendation": "Correct the bill rate going forward and evaluate whether the variance is recoverable retroactively.",
        })
    return findings


def check_stale_rate_card_billing(billing: list[dict], rate_cards: list[dict], rules: dict) -> list[dict]:
    cfg = rules["stale_rate_card"]
    findings = []
    for r in billing:
        rc = _match_rate_card(r, rate_cards)
        if not rc or not rc.get("expiration_date") or not r.get("period_end"):
            continue
        expired = date.fromisoformat(rc["expiration_date"])
        billed = date.fromisoformat(r["period_end"])
        grace = timedelta(days=cfg["grace_period_days"])
        if billed <= expired + grace:
            continue
        dollar_impact = round(r["invoice_amount"] * (cfg["assumed_missed_escalation_pct"] / 100), 2)
        findings.append({
            "category": "stale_rate_card",
            "worker_id": r["worker_id"], "worker_name": r["worker_name"],
            "supplier_vendor": r["supplier_vendor"], "role_title": r["role_title"],
            "period": f"{r['period_start']} to {r['period_end']}",
            "rate_card_expired": rc["expiration_date"], "dollar_impact": dollar_impact,
            "description": (
                f"Billing continued {(billed - expired).days} days past rate card expiration "
                f"({rc['expiration_date']}) for {r['supplier_vendor']} / {r['role_title']} with no renegotiation on file."
            ),
            "recommendation": "Renegotiate and re-execute the rate card; back-bill the escalation if the master agreement allows it.",
        })
    return findings


def check_off_contract_spend(billing: list[dict], contracts: list[dict], rules: dict) -> list[dict]:
    cfg = rules["off_contract_spend"]
    findings = []
    for r in billing:
        contract = _match_contract(r, contracts)
        missing_contract = cfg["flag_missing_contract_id"] and not r.get("contract_id")
        unapproved = cfg["flag_unapproved_supplier"] and (
            not contract or not contract.get("approved_supplier") or not r.get("is_approved_supplier", True)
        )
        if not (missing_contract or unapproved):
            continue
        findings.append({
            "category": "off_contract_spend",
            "worker_id": r["worker_id"], "worker_name": r["worker_name"],
            "supplier_vendor": r["supplier_vendor"], "department": r.get("department"),
            "period": f"{r['period_start']} to {r['period_end']}",
            "dollar_impact": round(r["invoice_amount"], 2),
            "description": (
                f"${r['invoice_amount']:,.2f} billed to {r['supplier_vendor']} with "
                f"{'no contract on file' if missing_contract else 'no approved-supplier match'} "
                f"({r.get('department') or 'unknown department'})."
            ),
            "recommendation": "Route through the approved MSP/VMS channel or formalize a contract; verify the buying manager's authority.",
        })
    return findings


def check_classification_risk(billing: list[dict], contracts: list[dict], rules: dict) -> list[dict]:
    cfg = rules["classification_risk"]
    findings = []

    for c in contracts:
        if c.get("engagement_type") != "sow":
            continue
        if not (c.get("billing_cadence") == "hourly" and not c.get("deliverables_defined")):
            continue
        related = [r for r in billing if r.get("contract_id") == c["contract_id"]]
        if not related:
            continue
        annualized = round(sum(r["invoice_amount"] for r in related) * (52 / max(len(related), 1)), 2)
        exposure = round(annualized * cfg["exposure_multiplier_of_annualized_spend"], 2)
        findings.append({
            "category": "classification_risk", "subtype": "sow_in_name_only",
            "contract_id": c["contract_id"], "supplier_vendor": c["supplier_vendor"],
            "dollar_impact": exposure,
            "description": (
                f"Contract {c['contract_id']} with {c['supplier_vendor']} is classified as SOW but bills "
                f"hourly with no defined deliverables — functions as staff augmentation. Reclassification "
                f"exposure estimated on ${annualized:,.0f} annualized spend."
            ),
            "recommendation": "Rewrite the SOW with milestone-based deliverables, or reclassify to staff aug with proper markup/compliance treatment.",
        })

    by_worker: dict[str, list[dict]] = defaultdict(list)
    for r in billing:
        if r.get("worker_type") in ("1099", "corp_to_corp") and r.get("engagement_type") == "staff_aug":
            by_worker[r["worker_id"]].append(r)

    for worker_id, records in by_worker.items():
        if len(records) < cfg["min_consecutive_periods_staff_aug_1099"]:
            continue
        annualized = round(sum(r["invoice_amount"] for r in records) * (52 / max(len(records), 1)), 2)
        exposure = round(annualized * cfg["exposure_multiplier_of_annualized_spend"], 2)
        sample = records[0]
        findings.append({
            "category": "classification_risk", "subtype": "long_tenure_1099_staff_aug",
            "worker_id": worker_id, "worker_name": sample.get("worker_name"),
            "supplier_vendor": sample.get("supplier_vendor"), "dollar_impact": exposure,
            "description": (
                f"{sample.get('worker_name') or worker_id} has billed as a "
                f"{sample.get('worker_type')} staff-aug worker for {len(records)} consecutive periods — "
                f"a common trigger for worker classification audits. Estimated back-pay/penalty exposure "
                f"based on ${annualized:,.0f} annualized spend."
            ),
            "recommendation": "Have counsel review the engagement against ABC-test/IRS 20-factor criteria; consider moving to W-2 or EOR.",
        })

    return findings


def check_hours_variance(billing: list[dict], rules: dict) -> list[dict]:
    cfg = rules["hours_variance"]
    findings = []
    for r in billing:
        gap = round(r["hours_approved"] - r["hours_invoiced"], 2)
        if abs(gap) < cfg["min_hours_gap_flag"]:
            continue
        direction = "unbilled" if gap > 0 else "overbilled"
        dollar_impact = round(abs(gap) * r["bill_rate"], 2)
        findings.append({
            "category": "hours_variance", "subtype": direction,
            "worker_id": r["worker_id"], "worker_name": r["worker_name"],
            "period": f"{r['period_start']} to {r['period_end']}",
            "hours_approved": r["hours_approved"], "hours_invoiced": r["hours_invoiced"],
            "dollar_impact": dollar_impact,
            "description": (
                f"{abs(gap)} hours {direction} for {r['worker_name'] or r['worker_id']} "
                f"({r['hours_approved']} approved vs. {r['hours_invoiced']} invoiced)."
            ),
            "recommendation": (
                "Recover the unbilled hours on next invoice cycle." if direction == "unbilled"
                else "Issue a credit memo before the client catches the discrepancy themselves."
            ),
        })
    return findings


def score_findings(findings: list[dict], rules: dict) -> list[dict]:
    bands = rules["severity_dollar_bands"]
    for f in findings:
        if f.get("severity"):
            continue
        amount = f.get("dollar_impact") or 0
        f["severity"] = _severity_for_amount(amount, bands)
    return sorted(findings, key=lambda x: (x.get("dollar_impact") or 0), reverse=True)


def run(include_revenue_at_risk: bool = True) -> dict[str, Any]:
    log.info("Workforce Revenue Leak Workflow Sprint — detection run starting")
    rules, connections = load_config()

    billing_conn = BillingConnector(connections.get("billing", {"platform": "file_csv"}))
    billing = billing_conn.get_billing_records()
    rate_cards = billing_conn.get_rate_cards()
    contracts = billing_conn.get_contracts()

    findings: list[dict] = []
    findings += check_missed_markup(billing, rate_cards, rules)
    findings += check_stale_rate_card_billing(billing, rate_cards, rules)
    findings += check_off_contract_spend(billing, contracts, rules)
    findings += check_classification_risk(billing, contracts, rules)
    findings += check_hours_variance(billing, rules)

    findings = score_findings(findings, rules)
    total_exposure = round(sum(f.get("dollar_impact") or 0 for f in findings), 2)

    by_category: dict[str, dict] = defaultdict(lambda: {"count": 0, "dollar_impact": 0.0})
    for f in findings:
        by_category[f["category"]]["count"] += 1
        by_category[f["category"]]["dollar_impact"] += f.get("dollar_impact") or 0

    report = {
        "generated_at": datetime.now().isoformat(),
        "total_exposure": total_exposure,
        "finding_count": len(findings),
        "by_category": {k: {"count": v["count"], "dollar_impact": round(v["dollar_impact"], 2)}
                         for k, v in by_category.items()},
        "findings": findings,
    }

    out_dir = OUTPUT_PATH / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"leak_report_{date.today().isoformat()}.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log.info(f"Leak detection report written: {out_path} — total exposure ${total_exposure:,.2f}")
    return report


if __name__ == "__main__":
    run()
