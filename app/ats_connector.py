"""
ats_connector.py
----------------
Generic ATS adapter supporting Greenhouse, Lever, Workday Recruiting,
iCIMS, Jobvite, and any REST-based ATS.

Normalizes data into a common schema regardless of source platform.

Part of: recruiting-metrics-automation-engine
Author:  Paul Linn Solutions (PLS)
"""

import logging
from datetime import date
from typing import Any

import httpx

log = logging.getLogger(__name__)


class ATSConnector:
    """
    Generic ATS connector. Dispatches to the correct adapter
    based on the 'platform' key in the connection config.

    Supported platforms: greenhouse, lever, workday, icims, jobvite, generic_rest

    Config shape:
        {
            "platform": "greenhouse",
            "base_url": "https://harvest.greenhouse.io/v1",
            "api_key": "${ATS_API_KEY}",          # resolved from env
            "org_id": "acme-corp"                  # platform-specific
        }
    """

    PLATFORM_ADAPTERS = {
        "greenhouse": "_greenhouse_headers",
        "lever":      "_lever_headers",
        "workday":    "_workday_headers",
        "icims":      "_icims_headers",
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

    def _greenhouse_headers(self) -> dict:
        import base64, os
        key = os.environ.get("ATS_API_KEY", self.config.get("api_key", ""))
        encoded = base64.b64encode(f"{key}:".encode()).decode()
        return {"Authorization": f"Basic {encoded}", "Content-Type": "application/json"}

    def _lever_headers(self) -> dict:
        import os
        key = os.environ.get("ATS_API_KEY", self.config.get("api_key", ""))
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _workday_headers(self) -> dict:
        import os
        key = os.environ.get("ATS_API_KEY", self.config.get("api_key", ""))
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _icims_headers(self) -> dict:
        import os
        key = os.environ.get("ATS_API_KEY", self.config.get("api_key", ""))
        return {"Authorization": f"Basic {key}", "Content-Type": "application/json"}

    def _generic_headers(self) -> dict:
        import os
        key = os.environ.get("ATS_API_KEY", self.config.get("api_key", ""))
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    # ──────────────────────────────────────────────
    # COMMON INTERFACE (platform adapters normalize to this schema)
    # ──────────────────────────────────────────────

    def get_requisitions(self, since: date) -> list[dict]:
        """
        Returns normalized requisition records.

        Normalized schema:
        {
            "id": str,
            "title": str,
            "department": str,
            "location": str,
            "status": "open" | "filled" | "cancelled",
            "approved_at": ISO str,
            "closed_at": ISO str | None,
            "close_reason": "filled" | "cancelled" | None,
            "offer_accepted_at": ISO str | None,
            "recruiter_id": str,
            "hiring_manager_id": str,
        }
        """
        raw = self._paginate(self._req_endpoint(), params={"created_after": since.isoformat()})
        return [self._normalize_req(r) for r in raw]

    def get_candidates_all(self, since: date) -> list[dict]:
        """
        Returns normalized candidate records with stage history.

        Normalized schema:
        {
            "id": str,
            "req_id": str,
            "role": str,
            "department": str,
            "source": str,
            "status": "active" | "hired" | "rejected" | "withdrawn",
            "applied_at": ISO str,
            "hire_date": ISO str | None,
            "offer_accepted_at": ISO str | None,
            "furthest_stage": str,
            "stage_gaps": [{"stage": str, "days": int}],
            "employee_id": str | None,
            "recruiter_id": str,
            "demographic_group": str | None,
            "days_to_hire": int | None,
        }
        """
        raw = self._paginate(self._candidate_endpoint(), params={"created_after": since.isoformat()})
        return [self._normalize_candidate(c) for c in raw]

    def get_applications(self, since: date) -> list[dict]:
        """
        Returns normalized application records (one per candidate per req).
        """
        raw = self._paginate(self._application_endpoint(), params={"created_after": since.isoformat()})
        return [self._normalize_application(a) for a in raw]

    def get_offers(self, since: date) -> list[dict]:
        """
        Returns normalized offer records.

        Normalized schema:
        {
            "id": str,
            "candidate_id": str,
            "req_id": str,
            "extended_at": ISO str,
            "outcome": "accepted" | "declined" | "pending",
            "decline_reason": str | None,
            "recruiter_id": str,
        }
        """
        raw = self._paginate(self._offer_endpoint(), params={"created_after": since.isoformat()})
        return [self._normalize_offer(o) for o in raw]

    def get_application_sessions(self, since: date) -> list[dict]:
        """
        Returns application funnel session data (started vs. submitted).
        Note: not all ATS platforms expose this — falls back to empty list.
        """
        try:
            raw = self._paginate(self._session_endpoint(), params={"since": since.isoformat()})
            return [{"session_id": s.get("id"), "req_id": s.get("job_id"),
                     "submitted": s.get("completed", False)} for s in raw]
        except Exception:
            log.warning("Application session data not available for this ATS platform.")
            return []

    # ──────────────────────────────────────────────
    # PLATFORM-SPECIFIC ENDPOINTS
    # Override these in a subclass for your ATS
    # ──────────────────────────────────────────────

    def _req_endpoint(self) -> str:
        endpoints = {
            "greenhouse": f"{self.base_url}/jobs",
            "lever":      f"{self.base_url}/postings",
            "workday":    f"{self.base_url}/workers/jobRequisitions",
            "generic_rest": f"{self.base_url}/requisitions",
        }
        return endpoints.get(self.platform, f"{self.base_url}/requisitions")

    def _candidate_endpoint(self) -> str:
        endpoints = {
            "greenhouse": f"{self.base_url}/candidates",
            "lever":      f"{self.base_url}/opportunities",
            "workday":    f"{self.base_url}/staffing/candidates",
            "generic_rest": f"{self.base_url}/candidates",
        }
        return endpoints.get(self.platform, f"{self.base_url}/candidates")

    def _application_endpoint(self) -> str:
        endpoints = {
            "greenhouse": f"{self.base_url}/applications",
            "lever":      f"{self.base_url}/applications",
            "generic_rest": f"{self.base_url}/applications",
        }
        return endpoints.get(self.platform, f"{self.base_url}/applications")

    def _offer_endpoint(self) -> str:
        endpoints = {
            "greenhouse": f"{self.base_url}/offers",
            "lever":      f"{self.base_url}/offers",
            "generic_rest": f"{self.base_url}/offers",
        }
        return endpoints.get(self.platform, f"{self.base_url}/offers")

    def _session_endpoint(self) -> str:
        return f"{self.base_url}/application_sessions"

    # ──────────────────────────────────────────────
    # NORMALIZATION (platform-specific field mapping)
    # Extend these methods when adding a new ATS
    # ──────────────────────────────────────────────

    def _normalize_req(self, raw: dict) -> dict:
        if self.platform == "greenhouse":
            return {
                "id": str(raw.get("id")),
                "title": raw.get("name"),
                "department": (raw.get("departments") or [{}])[0].get("name"),
                "location": (raw.get("offices") or [{}])[0].get("name"),
                "status": raw.get("status", "open").lower(),
                "approved_at": raw.get("opened_at"),
                "closed_at": raw.get("closed_at"),
                "close_reason": "filled" if raw.get("status") == "closed" else None,
                "offer_accepted_at": None,
                "recruiter_id": str((raw.get("hiring_team", {}).get("recruiters") or [{}])[0].get("id")),
                "hiring_manager_id": str((raw.get("hiring_team", {}).get("hiring_managers") or [{}])[0].get("id")),
            }
        # Generic fallback
        return {
            "id": str(raw.get("id", "")),
            "title": raw.get("title") or raw.get("name"),
            "department": raw.get("department"),
            "location": raw.get("location"),
            "status": raw.get("status", "open"),
            "approved_at": raw.get("approved_at") or raw.get("created_at"),
            "closed_at": raw.get("closed_at"),
            "close_reason": raw.get("close_reason"),
            "offer_accepted_at": raw.get("offer_accepted_at"),
            "recruiter_id": str(raw.get("recruiter_id", "")),
            "hiring_manager_id": str(raw.get("hiring_manager_id", "")),
        }

    def _normalize_candidate(self, raw: dict) -> dict:
        return {
            "id": str(raw.get("id", "")),
            "req_id": str(raw.get("job_id") or raw.get("req_id", "")),
            "role": raw.get("role") or raw.get("job_title"),
            "department": raw.get("department"),
            "source": raw.get("source") or (raw.get("sourced_from") or {}).get("name"),
            "status": raw.get("status", "active").lower(),
            "applied_at": raw.get("applied_at") or raw.get("created_at"),
            "hire_date": raw.get("hire_date"),
            "offer_accepted_at": raw.get("offer_accepted_at"),
            "furthest_stage": raw.get("current_stage") or raw.get("stage"),
            "stage_gaps": raw.get("stage_gaps", []),
            "employee_id": str(raw.get("employee_id")) if raw.get("employee_id") else None,
            "recruiter_id": str(raw.get("recruiter_id", "")),
            "demographic_group": raw.get("demographic_group") or raw.get("eeoc_group"),
            "days_to_hire": raw.get("days_to_hire"),
        }

    def _normalize_application(self, raw: dict) -> dict:
        return {
            "id": str(raw.get("id", "")),
            "req_id": str(raw.get("job_id") or raw.get("req_id", "")),
            "candidate_id": str(raw.get("candidate_id", "")),
            "source": raw.get("source"),
            "status": raw.get("status", "active").lower(),
            "applied_at": raw.get("applied_at") or raw.get("created_at"),
        }

    def _normalize_offer(self, raw: dict) -> dict:
        return {
            "id": str(raw.get("id", "")),
            "candidate_id": str(raw.get("candidate_id", "")),
            "req_id": str(raw.get("job_id") or raw.get("req_id", "")),
            "extended_at": raw.get("sent_at") or raw.get("created_at"),
            "outcome": raw.get("status", "pending").lower(),
            "decline_reason": raw.get("reject_reason"),
            "recruiter_id": str(raw.get("recruiter_id", "")),
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
                items = data if isinstance(data, list) else data.get("results", data.get("data", []))
                if not items:
                    break
                results.extend(items)
                if len(items) < 500:
                    break
                page += 1
            except httpx.HTTPStatusError as e:
                log.error(f"ATS API error {e.response.status_code} at {url}: {e}")
                break
            except Exception as e:
                log.error(f"Unexpected ATS connector error: {e}")
                break
        log.info(f"ATS: fetched {len(results)} records from {url}")
        return results

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
