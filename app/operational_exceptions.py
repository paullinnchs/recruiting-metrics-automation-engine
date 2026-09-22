"""
operational_exceptions.py
-------------------------
Deterministic V1 recruiting operations exception analysis.

This module does not change Tier 1/Tier 2 KPI calculations. It inspects the
same intake records plus optional activity events, then emits prioritized
record-level exceptions for human review.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.fromisoformat(value[:10]).date()


def _days_since(value: str | None, as_of: date) -> int | None:
    parsed = _parse_date(value)
    return (as_of - parsed).days if parsed else None


def _severity(days_or_pct: float, warning: float, critical: float, lower_is_worse: bool = False) -> str:
    if lower_is_worse:
        return "CRITICAL" if days_or_pct <= critical else "WARNING"
    return "CRITICAL" if days_or_pct >= critical else "WARNING"


def _exception(
    exception_type: str,
    severity: str,
    evidence: str,
    rule: str,
    significance: str,
    action: str,
    req_id: str | None = None,
    candidate_id: str | None = None,
    recruiter_id: str | None = None,
    affected_role: str | None = None,
) -> dict[str, Any]:
    return {
        "exception_type": exception_type,
        "severity": severity,
        "req_id": req_id,
        "candidate_id": candidate_id,
        "recruiter_id": recruiter_id,
        "affected_role": affected_role,
        "observed_evidence": evidence,
        "threshold_rule": rule,
        "business_significance": significance,
        "recommended_action": action,
    }


def _not_evaluated(exception_type: str, reason: str, required_data: list[str]) -> dict[str, Any]:
    return {
        "exception_type": exception_type,
        "status": "not_evaluated",
        "reason": reason,
        "required_data": required_data,
    }


def analyze(data: dict, thresholds: dict, as_of: date | None = None) -> dict[str, Any]:
    as_of = as_of or date.today()
    cfg = thresholds.get("operational_exceptions", {})

    reqs = data.get("reqs") or []
    candidates = data.get("candidates") or []
    applications = data.get("applications") or []
    offers = data.get("offers") or []
    activities = data.get("activities") or []
    stages = (data.get("config") or {}).get("funnel_stages") or [
        "applied", "phone_screen", "hiring_manager_review", "interview", "final_round", "offer", "hired"
    ]

    exceptions: list[dict[str, Any]] = []
    not_evaluated: list[dict[str, Any]] = []

    req_by_id = {r.get("id"): r for r in reqs if r.get("id")}
    apps_by_req: dict[str, list[dict]] = {}
    candidates_by_req: dict[str, list[dict]] = {}
    offers_by_req: dict[str, list[dict]] = {}
    activities_by_req: dict[str, list[dict]] = {}
    activities_by_candidate: dict[str, list[dict]] = {}

    for app in applications:
        apps_by_req.setdefault(app.get("req_id"), []).append(app)
    for cand in candidates:
        candidates_by_req.setdefault(cand.get("req_id"), []).append(cand)
    for offer in offers:
        offers_by_req.setdefault(offer.get("req_id"), []).append(offer)
    for activity in activities:
        activities_by_req.setdefault(activity.get("req_id"), []).append(activity)
        if activity.get("candidate_id"):
            activities_by_candidate.setdefault(activity.get("candidate_id"), []).append(activity)

    # 1. Aging requisitions
    aging_cfg = cfg.get("aging_requisitions", {})
    if not reqs or not any(r.get("approved_at") for r in reqs):
        not_evaluated.append(_not_evaluated("aging_requisition", "No requisition approval dates available.", ["requisitions.approved_at"]))
    else:
        warn = aging_cfg.get("warning_days_open", 30)
        crit = aging_cfg.get("critical_days_open", 45)
        for req in reqs:
            if req.get("status") != "open":
                continue
            days_open = _days_since(req.get("approved_at"), as_of)
            if days_open is not None and days_open >= warn:
                exceptions.append(_exception(
                    "aging_requisition",
                    _severity(days_open, warn, crit),
                    f"{req['id']} has been open {days_open} days since approval on {req.get('approved_at')}.",
                    f"Open requisition age >= {warn} days warning / >= {crit} days critical.",
                    "Extended vacancy can delay delivery and increases the risk of stale candidate pipelines.",
                    "Confirm role priority, unblock hiring-manager decisions, and reset the sourcing plan.",
                    req_id=req["id"],
                    recruiter_id=req.get("recruiter_id"),
                    affected_role=req.get("title"),
                ))

    # 2. Low candidate flow
    flow_cfg = cfg.get("low_candidate_flow", {})
    if not reqs or applications is None:
        not_evaluated.append(_not_evaluated("low_candidate_flow", "Requisition or application data unavailable.", ["requisitions", "applications"]))
    else:
        min_apps = flow_cfg.get("min_applications", 5)
        after_days = flow_cfg.get("after_days_open", 14)
        for req in reqs:
            if req.get("status") != "open":
                continue
            days_open = _days_since(req.get("approved_at"), as_of)
            app_count = len(apps_by_req.get(req.get("id"), []))
            if days_open is not None and days_open >= after_days and app_count < min_apps:
                exceptions.append(_exception(
                    "low_candidate_flow",
                    "WARNING",
                    f"{req['id']} has {app_count} applications after {days_open} days open.",
                    f"Applications < {min_apps} after {after_days} days open.",
                    "Low top-of-funnel flow can make the hiring plan miss target dates before interview activity begins.",
                    "Review sourcing channels, job-post reach, and referral/agency support for this requisition.",
                    req_id=req["id"],
                    recruiter_id=req.get("recruiter_id"),
                    affected_role=req.get("title"),
                ))

    # 3. Stalled candidates
    stalled_cfg = cfg.get("stalled_candidates", {})
    active_candidates = [c for c in candidates if c.get("status") == "active"]
    if active_candidates and not any(c.get("current_stage_entered_at") for c in active_candidates):
        not_evaluated.append(_not_evaluated("stalled_candidate", "Active candidates do not include current_stage_entered_at.", ["candidates.current_stage", "candidates.current_stage_entered_at"]))
    else:
        warn = stalled_cfg.get("warning_days_in_stage", 10)
        crit = stalled_cfg.get("critical_days_in_stage", 21)
        for cand in active_candidates:
            days = _days_since(cand.get("current_stage_entered_at"), as_of)
            if days is not None and days >= warn:
                req = req_by_id.get(cand.get("req_id"), {})
                exceptions.append(_exception(
                    "stalled_candidate",
                    _severity(days, warn, crit),
                    f"{cand['id']} has been in {cand.get('current_stage') or cand.get('furthest_stage')} for {days} days.",
                    f"Active candidate stage age >= {warn} days warning / >= {crit} days critical.",
                    "Candidate delay increases drop-off risk and can mask hiring-manager or scheduling bottlenecks.",
                    "Confirm candidate disposition or schedule the next step within the next hiring sync.",
                    req_id=cand.get("req_id"),
                    candidate_id=cand["id"],
                    recruiter_id=cand.get("recruiter_id"),
                    affected_role=req.get("title") or cand.get("role"),
                ))

    # 4. Weak funnel conversion
    funnel_cfg = cfg.get("weak_funnel_conversion", {})
    min_conversion = funnel_cfg.get("min_stage_conversion_pct", 35)
    min_prior = funnel_cfg.get("min_prior_stage_count", 5)
    if not candidates or not stages:
        not_evaluated.append(_not_evaluated("weak_funnel_conversion", "Candidate funnel data unavailable.", ["candidates.furthest_stage", "recruiting_config.funnel_stages"]))
    else:
        stage_counts = {stage: 0 for stage in stages}
        for cand in candidates:
            reached = cand.get("furthest_stage")
            if reached in stage_counts:
                for stage in stages:
                    stage_counts[stage] += 1
                    if stage == reached:
                        break
        previous_stage = None
        previous_count = None
        for stage in stages:
            count = stage_counts[stage]
            if previous_count and previous_count >= min_prior:
                conversion = round(count / previous_count * 100, 1)
                if conversion < min_conversion:
                    exceptions.append(_exception(
                        "weak_funnel_conversion",
                        "WARNING",
                        f"{previous_stage} -> {stage} conversion is {conversion}% ({count}/{previous_count}).",
                        f"Stage conversion < {min_conversion}% with at least {min_prior} candidates in prior stage.",
                        "A sharp conversion drop points to a process, screening, or hiring-manager calibration issue.",
                        "Review rejected/withdrawn records at the drop-off stage and recalibrate screening criteria.",
                    ))
            previous_stage = stage
            previous_count = count

    # 5. Offer acceptance exception
    offer_cfg = cfg.get("offer_acceptance_exception", {})
    if not offers:
        not_evaluated.append(_not_evaluated("offer_acceptance_exception", "No offer records available.", ["offers"]))
    else:
        warn = offer_cfg.get("warning_pct", 85)
        crit = offer_cfg.get("critical_pct", 75)
        min_offers = offer_cfg.get("min_offers", 2)
        for req_id, req_offers in offers_by_req.items():
            if len(req_offers) < min_offers:
                continue
            accepted = sum(1 for o in req_offers if o.get("outcome") == "accepted")
            rate = round(accepted / len(req_offers) * 100, 1)
            if rate <= warn:
                req = req_by_id.get(req_id, {})
                reasons = sorted({o.get("decline_reason") for o in req_offers if o.get("decline_reason")})
                exceptions.append(_exception(
                    "offer_acceptance_exception",
                    _severity(rate, warn, crit, lower_is_worse=True),
                    f"{req_id} offer acceptance is {rate}% ({accepted}/{len(req_offers)} accepted); decline reasons: {', '.join(reasons) or 'not supplied'}.",
                    f"Offer acceptance <= {warn}% warning / <= {crit}% critical with at least {min_offers} offers.",
                    "Declined offers consume late-stage pipeline capacity and may indicate compensation or role-positioning issues.",
                    "Review declined-offer feedback and confirm compensation/range competitiveness before extending more offers.",
                    req_id=req_id,
                    recruiter_id=req.get("recruiter_id"),
                    affected_role=req.get("title"),
                ))

    # 6. Recruiter workload concentration
    workload_cfg = cfg.get("recruiter_workload_concentration", {})
    open_reqs = [r for r in reqs if r.get("status") == "open"]
    if not open_reqs:
        not_evaluated.append(_not_evaluated("recruiter_workload_concentration", "No open requisitions available to evaluate.", ["requisitions.status", "requisitions.recruiter_id"]))
    else:
        min_open = workload_cfg.get("min_open_reqs", 3)
        warn_share = workload_cfg.get("warning_share_pct", 50)
        crit_share = workload_cfg.get("critical_share_pct", 65)
        if len(open_reqs) >= min_open:
            by_recruiter: dict[str, int] = {}
            for req in open_reqs:
                by_recruiter[req.get("recruiter_id", "unknown")] = by_recruiter.get(req.get("recruiter_id", "unknown"), 0) + 1
            rec_id, count = max(by_recruiter.items(), key=lambda item: item[1])
            share = round(count / len(open_reqs) * 100, 1)
            if share >= warn_share:
                exceptions.append(_exception(
                    "recruiter_workload_concentration",
                    _severity(share, warn_share, crit_share),
                    f"{rec_id} owns {count}/{len(open_reqs)} open requisitions ({share}%).",
                    f"Open req ownership share >= {warn_share}% warning / >= {crit_share}% critical when at least {min_open} reqs are open.",
                    "Concentrated workload creates execution risk and can worsen aging, low-flow, and candidate-stall patterns.",
                    "Review recruiter capacity and rebalance ownership or sourcing support for active requisitions.",
                    recruiter_id=rec_id,
                ))

    # 7. High-priority requisitions lacking activity
    high_cfg = cfg.get("high_priority_lacking_activity", {})
    if not any(r.get("priority") for r in reqs):
        not_evaluated.append(_not_evaluated("high_priority_lacking_activity", "No requisition priority field supplied.", ["requisitions.priority", "activities"]))
    elif not activities:
        not_evaluated.append(_not_evaluated("high_priority_lacking_activity", "Activity events unavailable.", ["activities.occurred_at", "activities.req_id"]))
    else:
        inactive_days = high_cfg.get("max_days_since_activity", 7)
        high_values = set(high_cfg.get("priority_values", ["high", "critical"]))
        for req in reqs:
            if req.get("status") != "open" or str(req.get("priority", "")).lower() not in high_values:
                continue
            req_activities = activities_by_req.get(req.get("id"), [])
            last_activity = max((_parse_date(a.get("occurred_at")) for a in req_activities if a.get("occurred_at")), default=None)
            days = (as_of - last_activity).days if last_activity else None
            if days is None or days > inactive_days:
                evidence = f"{req['id']} is {req.get('priority')} priority with no activity events." if days is None else f"{req['id']} is {req.get('priority')} priority; last activity was {days} days ago."
                exceptions.append(_exception(
                    "high_priority_requisition_lacking_activity",
                    "CRITICAL",
                    evidence,
                    f"High/critical open requisition has no activity within {inactive_days} days.",
                    "A priority role without recent activity is an execution risk against the hiring plan.",
                    "Confirm active ownership and schedule immediate sourcing or hiring-manager follow-up.",
                    req_id=req["id"],
                    recruiter_id=req.get("recruiter_id"),
                    affected_role=req.get("title"),
                ))

    # 8. Activity without progression
    activity_cfg = cfg.get("activity_without_progression", {})
    if not activities:
        not_evaluated.append(_not_evaluated("activity_without_progression", "Activity events unavailable.", ["activities.event_type", "activities.occurred_at"]))
    else:
        min_events = activity_cfg.get("min_activity_events", 3)
        window_days = activity_cfg.get("window_days", 14)
        non_progression = set(activity_cfg.get("non_progression_event_types", ["note", "email", "call", "task"]))
        progression = set(activity_cfg.get("progression_event_types", ["stage_change", "interview", "offer"]))
        cutoff = as_of.toordinal() - window_days
        for cand in active_candidates:
            cand_activities = activities_by_candidate.get(cand.get("id"), [])
            recent_non_progress = [
                a for a in cand_activities
                if a.get("event_type") in non_progression and _parse_date(a.get("occurred_at")) and _parse_date(a.get("occurred_at")).toordinal() >= cutoff
            ]
            recent_progress = [
                a for a in cand_activities
                if a.get("event_type") in progression and _parse_date(a.get("occurred_at")) and _parse_date(a.get("occurred_at")).toordinal() >= cutoff
            ]
            if len(recent_non_progress) >= min_events and not recent_progress:
                req = req_by_id.get(cand.get("req_id"), {})
                exceptions.append(_exception(
                    "activity_without_progression",
                    "WARNING",
                    f"{cand['id']} has {len(recent_non_progress)} non-progression activities in the last {window_days} days and no progression event.",
                    f">= {min_events} activity events in {window_days} days with no stage_change/interview/offer event.",
                    "Repeated touches without pipeline movement can signal unclear ownership, candidate indecision, or blocked next steps.",
                    "Decide the next stage or disposition the candidate so activity turns into pipeline movement.",
                    req_id=cand.get("req_id"),
                    candidate_id=cand["id"],
                    recruiter_id=cand.get("recruiter_id"),
                    affected_role=req.get("title") or cand.get("role"),
                ))

    severity_rank = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    exceptions.sort(key=lambda x: (severity_rank.get(x.get("severity"), 9), x.get("exception_type", "")))

    return {
        "available": bool(reqs and candidates and applications and offers),
        "as_of": as_of.isoformat(),
        "exceptions": exceptions,
        "exception_count": len(exceptions),
        "not_evaluated": not_evaluated,
    }
