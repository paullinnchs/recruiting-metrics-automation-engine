"""
hris_connector.py
-----------------
Generic HRIS adapter supporting Rippling, BambooHR, Workday HCM,
ADP Workforce Now, UKG Pro, and any REST-based HRIS.

Normalizes employee, termination, performance, headcount, and payroll
data into a common schema regardless of source platform.

Used by: tier2_crosssystem_agent.py
Metrics served: 6 (first-year attrition), 7 (quality of hire),
                12 (cost per hire), 15 (% open positions),
                18 (cost to OPL), 19 (time to productivity)

Part of: recruiting-metrics-automation-engine
Author:  Paul Linn Solutions (PLS)
"""

import logging
import os
from datetime import date
from typing import Any

import httpx

log = logging.getLogger(__name__)


class HRISConnector:
    """
    Generic HRIS connector. Dispatches to the correct adapter
    based on the 'platform' key in the connection config.

    Supported platforms: rippling, bamboohr, workday, adp, ukg, generic_rest

    Config shape:
        {
            "platform": "rippling",
            "base_url": "https://app.rippling.com/api/o/v1",
            "api_key": "${HRIS_API_KEY}",
            "subdomain": "acme"              # BambooHR only
        }
    """

    PLATFORM_ADAPTERS = {
        "rippling":    "_rippling_headers",
        "bamboohr":    "_bamboohr_headers",
        "workday":     "_workday_headers",
        "adp":         "_adp_headers",
        "ukg":         "_ukg_headers",
        "generic_rest": "_generic_headers",
    }

    def __init__(self, config: dict):
        self.config = config
        self.platform = config.get("platform", "generic_rest")
        self.base_url = config["base_url"].rstrip("/")
        self.client = httpx.Client(
            headers=self._build_headers(),
            timeout=30,
        )

    def _build_headers(self) -> dict:
        adapter = self.PLATFORM_ADAPTERS.get(self.platform, "_generic_headers")
        return getattr(self, adapter)()

    def _rippling_headers(self) -> dict:
        key = os.environ.get("HRIS_API_KEY", self.config.get("api_key", ""))
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _bamboohr_headers(self) -> dict:
        import base64
        key = os.environ.get("HRIS_API_KEY", self.config.get("api_key", ""))
        encoded = base64.b64encode(f"{key}:x".encode()).decode()
        return {"Authorization": f"Basic {encoded}", "Accept": "application/json"}

    def _workday_headers(self) -> dict:
        key = os.environ.get("HRIS_API_KEY", self.config.get("api_key", ""))
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _adp_headers(self) -> dict:
        key = os.environ.get("HRIS_API_KEY", self.config.get("api_key", ""))
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _ukg_headers(self) -> dict:
        key = os.environ.get("HRIS_API_KEY", self.config.get("api_key", ""))
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _generic_headers(self) -> dict:
        key = os.environ.get("HRIS_API_KEY", self.config.get("api_key", ""))
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    # ──────────────────────────────────────────────
    # COMMON INTERFACE
    # ──────────────────────────────────────────────

    def get_employees(self, since: date) -> list[dict]:
        """
        Returns all employee records modified since the given date,
        including active employees and terminated employees.

        Normalized schema:
        {
            "id": str,                        # internal HRIS employee ID
            "employee_id": str,               # joins to ATS hire record
            "first_name": str,
            "last_name": str,
            "title": str,
            "department": str,
            "location": str,
            "employment_type": str,           # "full_time" | "part_time" | "contractor"
            "hire_date": ISO str,
            "termination_date": ISO str | None,
            "termination_type": str | None,   # "voluntary" | "involuntary" | None
            "termination_reason": str | None,
            "manager_id": str | None,
            "status": str,                    # "active" | "terminated" | "on_leave"
        }
        """
        raw = self._paginate(self._employee_endpoint(), params={"updated_since": since.isoformat()})
        return [self._normalize_employee(e) for e in raw]

    def get_performance_ratings(self, since: date) -> list[dict]:
        """
        Returns first-year performance ratings for employees hired since the given date.
        Used by Metric 7: Quality of Hire.

        Normalized schema:
        {
            "id": str,
            "employee_id": str,               # joins to ATS hire record
            "review_period": str,             # "90_day" | "6_month" | "annual"
            "review_date": ISO str,
            "first_year_rating": float,       # numeric score (1.0–5.0 scale normalized)
            "rating_label": str,              # "exceeds" | "meets" | "below" | "unsatisfactory"
            "reviewer_id": str,
            "department": str,
        }
        """
        raw = self._paginate(self._performance_endpoint(), params={"review_date_after": since.isoformat()})
        return [self._normalize_performance(p) for p in raw]

    def get_headcount(self) -> dict[str, Any]:
        """
        Returns current headcount summary.
        Used by Metric 15: % of Open Positions.

        Normalized schema:
        {
            "total_active": int,
            "by_department": {"Engineering": 42, "Sales": 28, ...},
            "by_location": {"Remote": 80, "New York": 30, ...},
            "as_of": ISO str,
        }
        """
        try:
            resp = self.client.get(self._headcount_endpoint())
            resp.raise_for_status()
            raw = resp.json()
            return self._normalize_headcount(raw)
        except Exception as e:
            log.error(f"Headcount fetch failed: {e}")
            return {"total_active": 0, "by_department": {}, "by_location": {}, "as_of": date.today().isoformat()}

    def get_payroll_costs(self, since: date, until: date | None = None) -> list[dict]:
        """
        Returns payroll cost records for the given period.
        Used by Metric 12 (Cost per hire) and Metric 18 (Cost to OPL).

        Normalized schema:
        {
            "employee_id": str,
            "period_start": ISO str,
            "period_end": ISO str,
            "gross_pay": float,
            "employer_costs": float,          # benefits, taxes, etc.
            "total_cost": float,
            "department": str,
        }
        """
        params = {"start_date": since.isoformat()}
        if until:
            params["end_date"] = until.isoformat()
        raw = self._paginate(self._payroll_endpoint(), params=params)
        return [self._normalize_payroll(p) for p in raw]

    def get_onboarding_costs(self, since: date) -> list[dict]:
        """
        Returns onboarding program cost records.
        Used by Metric 18: Cost to OPL.

        Normalized schema:
        {
            "employee_id": str,
            "program_name": str,
            "cost": float,
            "completed_at": ISO str | None,
            "department": str,
        }
        """
        try:
            raw = self._paginate(self._onboarding_endpoint(), params={"since": since.isoformat()})
            return [self._normalize_onboarding(o) for o in raw]
        except Exception:
            log.warning("Onboarding cost data not available for this HRIS platform — use L&D system connector.")
            return []

    def get_productivity_milestones(self, since: date) -> list[dict]:
        """
        Returns productivity milestone records for new hires.
        Used by Metric 19: Time to Productivity.

        Normalized schema:
        {
            "employee_id": str,
            "milestone_name": str,            # e.g. "fully_ramped", "first_deal_closed"
            "milestone_date": ISO str | None,
            "confirmed_by": str | None,       # manager ID
            "hire_date": ISO str,
            "days_to_milestone": int | None,
            "department": str,
        }
        """
        try:
            raw = self._paginate(self._milestone_endpoint(), params={"since": since.isoformat()})
            return [self._normalize_milestone(m) for m in raw]
        except Exception:
            log.warning("Productivity milestone data not available — requires custom HRIS field configuration.")
            return []

    # ──────────────────────────────────────────────
    # PLATFORM-SPECIFIC ENDPOINTS
    # ──────────────────────────────────────────────

    def _employee_endpoint(self) -> str:
        endpoints = {
            "rippling":    f"{self.base_url}/employees",
            "bamboohr":    f"{self.base_url}/employees/directory",
            "workday":     f"{self.base_url}/workers",
            "adp":         f"{self.base_url}/hr/v2/workers",
            "ukg":         f"{self.base_url}/personnel/v1/employees",
            "generic_rest": f"{self.base_url}/employees",
        }
        return endpoints.get(self.platform, f"{self.base_url}/employees")

    def _performance_endpoint(self) -> str:
        endpoints = {
            "rippling":    f"{self.base_url}/performance/reviews",
            "bamboohr":    f"{self.base_url}/performance/reviews",
            "workday":     f"{self.base_url}/performanceManagement/performanceReviews",
            "adp":         f"{self.base_url}/talent/v2/performanceReviews",
            "ukg":         f"{self.base_url}/performance/v1/reviews",
            "generic_rest": f"{self.base_url}/performance_reviews",
        }
        return endpoints.get(self.platform, f"{self.base_url}/performance_reviews")

    def _headcount_endpoint(self) -> str:
        endpoints = {
            "rippling":    f"{self.base_url}/employees/headcount",
            "bamboohr":    f"{self.base_url}/employees/directory",
            "workday":     f"{self.base_url}/workers/headcount",
            "adp":         f"{self.base_url}/hr/v2/workers/summary",
            "ukg":         f"{self.base_url}/personnel/v1/headcount",
            "generic_rest": f"{self.base_url}/headcount",
        }
        return endpoints.get(self.platform, f"{self.base_url}/headcount")

    def _payroll_endpoint(self) -> str:
        endpoints = {
            "rippling":    f"{self.base_url}/payroll/pay_runs",
            "bamboohr":    f"{self.base_url}/payroll/employees/all/payStubs",
            "workday":     f"{self.base_url}/payroll/payrollResults",
            "adp":         f"{self.base_url}/payroll/v1/payData",
            "ukg":         f"{self.base_url}/payroll/v1/pay-statements",
            "generic_rest": f"{self.base_url}/payroll",
        }
        return endpoints.get(self.platform, f"{self.base_url}/payroll")

    def _onboarding_endpoint(self) -> str:
        endpoints = {
            "rippling":    f"{self.base_url}/onboarding/tasks",
            "bamboohr":    f"{self.base_url}/onboarding/tasks",
            "workday":     f"{self.base_url}/onboarding/onboardingActivities",
            "generic_rest": f"{self.base_url}/onboarding",
        }
        return endpoints.get(self.platform, f"{self.base_url}/onboarding")

    def _milestone_endpoint(self) -> str:
        # Most HRIS platforms don't have a native milestone endpoint.
        # This typically requires a custom field or integration with an LMS/enablement tool.
        return f"{self.base_url}/custom_fields/productivity_milestones"

    # ──────────────────────────────────────────────
    # NORMALIZATION
    # ──────────────────────────────────────────────

    def _normalize_employee(self, raw: dict) -> dict:
        if self.platform == "rippling":
            return {
                "id": str(raw.get("id", "")),
                "employee_id": str(raw.get("employeeNumber") or raw.get("id", "")),
                "first_name": raw.get("firstName"),
                "last_name": raw.get("lastName"),
                "title": raw.get("jobTitle"),
                "department": (raw.get("department") or {}).get("name"),
                "location": raw.get("workLocation"),
                "employment_type": _normalize_emp_type(raw.get("employmentType")),
                "hire_date": raw.get("startDate"),
                "termination_date": raw.get("endDate"),
                "termination_type": _normalize_term_type(raw.get("terminationType")),
                "termination_reason": raw.get("terminationReason"),
                "manager_id": str(raw.get("managerId")) if raw.get("managerId") else None,
                "status": "terminated" if raw.get("endDate") else "active",
            }

        if self.platform == "bamboohr":
            return {
                "id": str(raw.get("id", "")),
                "employee_id": str(raw.get("employeeNumber") or raw.get("id", "")),
                "first_name": raw.get("firstName"),
                "last_name": raw.get("lastName"),
                "title": raw.get("jobTitle"),
                "department": raw.get("department"),
                "location": raw.get("location"),
                "employment_type": _normalize_emp_type(raw.get("employmentHistoryStatus")),
                "hire_date": raw.get("hireDate"),
                "termination_date": raw.get("terminationDate"),
                "termination_type": _normalize_term_type(raw.get("terminationType")),
                "termination_reason": raw.get("terminationReason"),
                "manager_id": str(raw.get("supervisorId")) if raw.get("supervisorId") else None,
                "status": "terminated" if raw.get("terminationDate") else "active",
            }

        if self.platform == "workday":
            return {
                "id": str(raw.get("id", "")),
                "employee_id": str(raw.get("workerID") or raw.get("id", "")),
                "first_name": (raw.get("person") or {}).get("legalNameData", {}).get("firstNameData", {}).get("firstName"),
                "last_name": (raw.get("person") or {}).get("legalNameData", {}).get("lastNameData", {}).get("lastName"),
                "title": (raw.get("primaryJob") or {}).get("businessTitle"),
                "department": ((raw.get("primaryJob") or {}).get("organizationData") or [{}])[0].get("name"),
                "location": ((raw.get("primaryJob") or {}).get("locationData") or {}).get("locationName"),
                "employment_type": _normalize_emp_type((raw.get("primaryJob") or {}).get("workerTypeData", {}).get("workerType")),
                "hire_date": (raw.get("primaryJob") or {}).get("hireDate"),
                "termination_date": (raw.get("primaryJob") or {}).get("terminationDate"),
                "termination_type": _normalize_term_type((raw.get("primaryJob") or {}).get("terminationTypeData", {}).get("terminationType")),
                "termination_reason": (raw.get("primaryJob") or {}).get("terminationReasonData", {}).get("terminationReason"),
                "manager_id": str((raw.get("primaryJob") or {}).get("managerID")) if (raw.get("primaryJob") or {}).get("managerID") else None,
                "status": "terminated" if (raw.get("primaryJob") or {}).get("terminationDate") else "active",
            }

        # Generic / ADP / UKG fallback
        return {
            "id": str(raw.get("id", "")),
            "employee_id": str(raw.get("employee_id") or raw.get("employeeNumber") or raw.get("id", "")),
            "first_name": raw.get("first_name") or raw.get("firstName"),
            "last_name": raw.get("last_name") or raw.get("lastName"),
            "title": raw.get("title") or raw.get("jobTitle"),
            "department": raw.get("department"),
            "location": raw.get("location") or raw.get("workLocation"),
            "employment_type": _normalize_emp_type(raw.get("employment_type") or raw.get("employmentType")),
            "hire_date": raw.get("hire_date") or raw.get("hireDate") or raw.get("startDate"),
            "termination_date": raw.get("termination_date") or raw.get("terminationDate") or raw.get("endDate"),
            "termination_type": _normalize_term_type(raw.get("termination_type") or raw.get("terminationType")),
            "termination_reason": raw.get("termination_reason") or raw.get("terminationReason"),
            "manager_id": str(raw.get("manager_id") or raw.get("managerId")) if (raw.get("manager_id") or raw.get("managerId")) else None,
            "status": raw.get("status", "active").lower(),
        }

    def _normalize_performance(self, raw: dict) -> dict:
        if self.platform == "bamboohr":
            raw_rating = raw.get("rating")
            return {
                "id": str(raw.get("id", "")),
                "employee_id": str(raw.get("employeeId", "")),
                "review_period": raw.get("type", "annual").lower(),
                "review_date": raw.get("reviewedDate") or raw.get("completedDate"),
                "first_year_rating": _normalize_rating(raw_rating, scale=5.0),
                "rating_label": _rating_to_label(raw_rating),
                "reviewer_id": str(raw.get("reviewerId", "")),
                "department": raw.get("department", ""),
            }

        if self.platform == "rippling":
            raw_rating = raw.get("overallRating")
            return {
                "id": str(raw.get("id", "")),
                "employee_id": str(raw.get("employeeId", "")),
                "review_period": raw.get("reviewCycle", "annual").lower(),
                "review_date": raw.get("completedAt"),
                "first_year_rating": _normalize_rating(raw_rating, scale=5.0),
                "rating_label": _rating_to_label(raw_rating),
                "reviewer_id": str(raw.get("reviewerId", "")),
                "department": raw.get("department", ""),
            }

        # Generic fallback
        raw_rating = raw.get("rating") or raw.get("overall_rating") or raw.get("overallRating")
        return {
            "id": str(raw.get("id", "")),
            "employee_id": str(raw.get("employee_id") or raw.get("employeeId", "")),
            "review_period": raw.get("review_period") or raw.get("reviewCycle", "annual"),
            "review_date": raw.get("review_date") or raw.get("completedAt") or raw.get("reviewedDate"),
            "first_year_rating": _normalize_rating(raw_rating, scale=5.0),
            "rating_label": _rating_to_label(raw_rating),
            "reviewer_id": str(raw.get("reviewer_id") or raw.get("reviewerId", "")),
            "department": raw.get("department", ""),
        }

    def _normalize_headcount(self, raw: dict) -> dict:
        if self.platform == "bamboohr":
            employees = raw if isinstance(raw, list) else raw.get("employees", [])
            active = [e for e in employees if not e.get("terminationDate")]
            dept_counts: dict[str, int] = {}
            loc_counts: dict[str, int] = {}
            for e in active:
                d = e.get("department", "Unknown")
                l = e.get("location", "Unknown")
                dept_counts[d] = dept_counts.get(d, 0) + 1
                loc_counts[l] = loc_counts.get(l, 0) + 1
            return {
                "total_active": len(active),
                "by_department": dept_counts,
                "by_location": loc_counts,
                "as_of": date.today().isoformat(),
            }

        # Generic: if the endpoint returns a summary object
        return {
            "total_active": raw.get("total_active") or raw.get("totalActive") or raw.get("count", 0),
            "by_department": raw.get("by_department") or raw.get("byDepartment") or {},
            "by_location": raw.get("by_location") or raw.get("byLocation") or {},
            "as_of": raw.get("as_of") or raw.get("asOf") or date.today().isoformat(),
        }

    def _normalize_payroll(self, raw: dict) -> dict:
        gross = float(raw.get("gross_pay") or raw.get("grossPay") or raw.get("totalGross") or 0)
        employer = float(raw.get("employer_costs") or raw.get("employerCosts") or raw.get("totalEmployerCost") or 0)
        return {
            "employee_id": str(raw.get("employee_id") or raw.get("employeeId") or raw.get("workerId", "")),
            "period_start": raw.get("period_start") or raw.get("periodStart") or raw.get("payPeriodStart"),
            "period_end": raw.get("period_end") or raw.get("periodEnd") or raw.get("payPeriodEnd"),
            "gross_pay": gross,
            "employer_costs": employer,
            "total_cost": gross + employer,
            "department": raw.get("department", ""),
        }

    def _normalize_onboarding(self, raw: dict) -> dict:
        return {
            "employee_id": str(raw.get("employee_id") or raw.get("employeeId", "")),
            "program_name": raw.get("program_name") or raw.get("taskName") or raw.get("activityName", ""),
            "cost": float(raw.get("cost") or raw.get("programCost") or 0),
            "completed_at": raw.get("completed_at") or raw.get("completedAt"),
            "department": raw.get("department", ""),
        }

    def _normalize_milestone(self, raw: dict) -> dict:
        hire_date = raw.get("hire_date") or raw.get("hireDate")
        milestone_date = raw.get("milestone_date") or raw.get("milestoneDate") or raw.get("completedAt")
        days = None
        if hire_date and milestone_date:
            from datetime import datetime
            try:
                days = (datetime.fromisoformat(milestone_date) - datetime.fromisoformat(hire_date)).days
            except Exception:
                pass
        return {
            "employee_id": str(raw.get("employee_id") or raw.get("employeeId", "")),
            "milestone_name": raw.get("milestone_name") or raw.get("milestoneName") or raw.get("name", ""),
            "milestone_date": milestone_date,
            "confirmed_by": str(raw.get("confirmed_by") or raw.get("confirmedBy") or raw.get("managerId", "")) or None,
            "hire_date": hire_date,
            "days_to_milestone": days,
            "department": raw.get("department", ""),
        }

    # ──────────────────────────────────────────────
    # PAGINATION
    # ──────────────────────────────────────────────

    def _paginate(self, url: str, params: dict | None = None, max_pages: int = 50) -> list[dict]:
        results = []
        page = 1
        params = params or {}
        while page <= max_pages:
            try:
                resp = self.client.get(url, params={**params, "page": page, "per_page": 500})
                resp.raise_for_status()
                data = resp.json()
                items = data if isinstance(data, list) else data.get("results", data.get("data", data.get("employees", [])))
                if not items:
                    break
                results.extend(items)
                if len(items) < 500:
                    break
                page += 1
            except httpx.HTTPStatusError as e:
                log.error(f"HRIS API error {e.response.status_code} at {url}: {e}")
                break
            except Exception as e:
                log.error(f"Unexpected HRIS connector error: {e}")
                break
        log.info(f"HRIS: fetched {len(results)} records from {url}")
        return results

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def _normalize_emp_type(raw_value: str | None) -> str:
    """Map platform-specific employment type strings to a common set."""
    if not raw_value:
        return "full_time"
    val = raw_value.lower().replace("-", "_").replace(" ", "_")
    if any(k in val for k in ("full", "ft", "permanent", "regular")):
        return "full_time"
    if any(k in val for k in ("part", "pt")):
        return "part_time"
    if any(k in val for k in ("contract", "temp", "contingent", "freelance", "1099")):
        return "contractor"
    return val


def _normalize_term_type(raw_value: str | None) -> str | None:
    """Map platform-specific termination type strings to voluntary/involuntary."""
    if not raw_value:
        return None
    val = raw_value.lower()
    if any(k in val for k in ("involuntary", "termination", "laid_off", "layoff", "rif", "terminated", "fired")):
        return "involuntary"
    if any(k in val for k in ("voluntary", "resigned", "quit", "resignation")):
        return "voluntary"
    return val


def _normalize_rating(raw_rating: Any, scale: float = 5.0) -> float | None:
    """
    Normalize a performance rating to a 1.0–5.0 float.
    Handles numeric strings, label strings, and various scales.
    """
    if raw_rating is None:
        return None
    try:
        val = float(raw_rating)
        # If score appears to be on a 10-point scale, rescale
        if val > 5.0:
            val = val / 10.0 * 5.0
        return round(val, 2)
    except (ValueError, TypeError):
        pass
    # Handle text labels
    label_map = {
        "exceptional": 5.0, "outstanding": 5.0, "far_exceeds": 5.0,
        "exceeds": 4.0, "above": 4.0, "strong": 4.0,
        "meets": 3.0, "satisfactory": 3.0, "effective": 3.0,
        "below": 2.0, "needs_improvement": 2.0, "developing": 2.0,
        "unsatisfactory": 1.0, "poor": 1.0, "does_not_meet": 1.0,
    }
    key = str(raw_rating).lower().replace(" ", "_").replace("-", "_")
    return label_map.get(key)


def _rating_to_label(raw_rating: Any) -> str:
    """Convert a raw rating to a standard four-level label."""
    score = _normalize_rating(raw_rating)
    if score is None:
        return "unknown"
    if score >= 4.5:
        return "exceeds"
    if score >= 3.0:
        return "meets"
    if score >= 2.0:
        return "below"
    return "unsatisfactory"
