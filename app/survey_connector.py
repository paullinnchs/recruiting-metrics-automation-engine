"""
survey_connector.py
-------------------
Generic survey adapter supporting Typeform, Qualtrics, SurveyMonkey,
Google Forms (via Sheets API), and any REST-based survey platform.

Handles survey triggering, response retrieval, and NPS/score normalization
for candidate experience, hiring manager satisfaction, and new hire pulse surveys.

Used by: tier2_crosssystem_agent.py, tier3_survey_agent.py
Metrics served: 8 (hiring manager satisfaction), 9 (candidate job satisfaction),
                13 (candidate experience / cNPS)

Part of: recruiting-metrics-automation-engine
Author:  Paul Linn Solutions (PLS)
"""

import logging
import os
from datetime import date, datetime
from typing import Any

import httpx

log = logging.getLogger(__name__)

# Survey type identifiers — used to route to the correct form/survey ID
SURVEY_TYPE_CANDIDATE_EXPERIENCE = "candidate_experience"
SURVEY_TYPE_HM_SATISFACTION = "hiring_manager_satisfaction"
SURVEY_TYPE_NEW_HIRE_PULSE = "candidate_job_satisfaction"


class SurveyConnector:
    """
    Generic survey connector. Dispatches to the correct adapter
    based on the 'platform' key in the connection config.

    Supported platforms: typeform, qualtrics, surveymonkey, google_forms, generic_rest

    Config shape:
        {
            "platform": "typeform",
            "base_url": "https://api.typeform.com",
            "api_key": "${SURVEY_API_KEY}",
            "form_ids": {
                "candidate_experience": "abc123",
                "hiring_manager_satisfaction": "def456",
                "candidate_job_satisfaction": "ghi789"
            }
        }
    """

    PLATFORM_ADAPTERS = {
        "typeform":      "_typeform_headers",
        "qualtrics":     "_qualtrics_headers",
        "surveymonkey":  "_surveymonkey_headers",
        "google_forms":  "_google_forms_headers",
        "generic_rest":  "_generic_headers",
    }

    def __init__(self, config: dict):
        self.config = config
        self.platform = config.get("platform", "generic_rest")
        self.base_url = config["base_url"].rstrip("/")
        self.form_ids = config.get("form_ids", {})
        self.client = httpx.Client(
            headers=self._build_headers(),
            timeout=30,
        )

    def _build_headers(self) -> dict:
        adapter = self.PLATFORM_ADAPTERS.get(self.platform, "_generic_headers")
        return getattr(self, adapter)()

    def _typeform_headers(self) -> dict:
        key = os.environ.get("SURVEY_API_KEY", self.config.get("api_key", ""))
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _qualtrics_headers(self) -> dict:
        key = os.environ.get("SURVEY_API_KEY", self.config.get("api_key", ""))
        return {"X-API-TOKEN": key, "Content-Type": "application/json"}

    def _surveymonkey_headers(self) -> dict:
        key = os.environ.get("SURVEY_API_KEY", self.config.get("api_key", ""))
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _google_forms_headers(self) -> dict:
        key = os.environ.get("SURVEY_API_KEY", self.config.get("api_key", ""))
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _generic_headers(self) -> dict:
        key = os.environ.get("SURVEY_API_KEY", self.config.get("api_key", ""))
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    # ──────────────────────────────────────────────
    # COMMON INTERFACE
    # ──────────────────────────────────────────────

    def get_responses(self, since: date,
                      survey_type: str = SURVEY_TYPE_CANDIDATE_EXPERIENCE) -> list[dict]:
        """
        Returns normalized survey responses for the given survey type and date range.

        survey_type options:
            "candidate_experience"         — post-process survey (all candidates)
            "hiring_manager_satisfaction"  — sent to HM on offer accept
            "candidate_job_satisfaction"   — 30/60/90 day new hire pulse

        Normalized schema:
        {
            "response_id": str,
            "survey_type": str,
            "respondent_id": str,             # candidate_id, employee_id, or HM employee_id
            "recruiter_id": str | None,
            "req_id": str | None,
            "submitted_at": ISO str,
            "nps": int | None,                # 0–10 NPS score
            "process_rating": float | None,   # 1.0–5.0
            "communication_rating": float | None,
            "overall_rating": float | None,
            "open_text": str | None,          # free-text response
            "pulse_day": int | None,          # 30 | 60 | 90 for new hire pulse surveys
            "would_recommend": bool | None,
        }
        """
        form_id = self.form_ids.get(survey_type)
        if not form_id:
            log.warning(f"No form_id configured for survey_type '{survey_type}'. Check connections.yaml.")
            return []

        raw = self._paginate(
            self._response_endpoint(form_id),
            params={"since": since.isoformat(), "form_id": form_id}
        )
        return [self._normalize_response(r, survey_type=survey_type) for r in raw]

    def get_all_survey_responses(self, since: date) -> dict[str, list[dict]]:
        """
        Convenience method — fetches all three survey types and returns them keyed by type.

        Returns:
        {
            "candidate_experience": [...],
            "hiring_manager_satisfaction": [...],
            "candidate_job_satisfaction": [...],
        }
        """
        return {
            SURVEY_TYPE_CANDIDATE_EXPERIENCE: self.get_responses(since, SURVEY_TYPE_CANDIDATE_EXPERIENCE),
            SURVEY_TYPE_HM_SATISFACTION:      self.get_responses(since, SURVEY_TYPE_HM_SATISFACTION),
            SURVEY_TYPE_NEW_HIRE_PULSE:       self.get_responses(since, SURVEY_TYPE_NEW_HIRE_PULSE),
        }

    def trigger_survey(self, survey_type: str, recipient_email: str,
                       metadata: dict | None = None) -> bool:
        """
        Sends a survey invite to the given recipient email.
        Triggered by ATS/HRIS webhook events (offer accepted, stage completed, hire date + N days).

        metadata is passed as hidden fields to pre-populate respondent context:
            {"candidate_id": "...", "req_id": "...", "recruiter_id": "...", "pulse_day": 30}

        Returns True on success, False on failure.
        """
        form_id = self.form_ids.get(survey_type)
        if not form_id:
            log.warning(f"Cannot trigger survey — no form_id for '{survey_type}'.")
            return False

        try:
            endpoint = self._trigger_endpoint(form_id)
            payload = self._build_trigger_payload(
                form_id=form_id,
                email=recipient_email,
                metadata=metadata or {},
            )
            resp = self.client.post(endpoint, json=payload)
            resp.raise_for_status()
            log.info(f"Survey triggered: {survey_type} → {recipient_email}")
            return True
        except httpx.HTTPStatusError as e:
            log.error(f"Survey trigger failed ({e.response.status_code}): {e}")
            return False
        except Exception as e:
            log.error(f"Survey trigger error: {e}")
            return False

    # ──────────────────────────────────────────────
    # PLATFORM-SPECIFIC ENDPOINTS
    # ──────────────────────────────────────────────

    def _response_endpoint(self, form_id: str) -> str:
        endpoints = {
            "typeform":     f"{self.base_url}/forms/{form_id}/responses",
            "qualtrics":    f"{self.base_url}/API/v3/surveys/{form_id}/responses",
            "surveymonkey": f"{self.base_url}/surveys/{form_id}/responses/bulk",
            "google_forms": f"{self.base_url}/forms/{form_id}/responses",
            "generic_rest": f"{self.base_url}/surveys/{form_id}/responses",
        }
        return endpoints.get(self.platform, f"{self.base_url}/surveys/{form_id}/responses")

    def _trigger_endpoint(self, form_id: str) -> str:
        endpoints = {
            "typeform":     f"{self.base_url}/forms/{form_id}/webhooks",
            "qualtrics":    f"{self.base_url}/API/v3/distributions",
            "surveymonkey": f"{self.base_url}/collectors",
            "generic_rest": f"{self.base_url}/surveys/{form_id}/send",
        }
        return endpoints.get(self.platform, f"{self.base_url}/surveys/{form_id}/send")

    def _build_trigger_payload(self, form_id: str, email: str, metadata: dict) -> dict:
        """Builds a platform-appropriate trigger payload."""
        if self.platform == "typeform":
            return {
                "messages": [{"email": email}],
                "hidden": metadata,
            }

        if self.platform == "qualtrics":
            return {
                "surveyId": form_id,
                "method": "Email",
                "message": {"libraryId": "UR_SYSTEM", "messageId": "MS_DEFAULT"},
                "recipients": {"mailingListId": None, "contactId": None,
                               "email": email, "embeddedData": metadata},
                "header": {"fromEmail": "noreply@yourcompany.com",
                           "replyToEmail": "noreply@yourcompany.com",
                           "fromName": "People Team", "subject": "Quick survey from us"},
                "sendDate": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

        if self.platform == "surveymonkey":
            return {
                "type": "email",
                "survey_id": form_id,
                "messages": [{"subject": "Quick survey from us",
                              "body": "Please take a moment to complete this survey.",
                              "recipients": [{"email": email,
                                              "custom_variables": metadata}]}],
            }

        # Generic fallback
        return {"form_id": form_id, "email": email, "metadata": metadata}

    # ──────────────────────────────────────────────
    # NORMALIZATION
    # ──────────────────────────────────────────────

    def _normalize_response(self, raw: dict, survey_type: str = "") -> dict:
        if self.platform == "typeform":
            return self._normalize_typeform(raw, survey_type)
        if self.platform == "qualtrics":
            return self._normalize_qualtrics(raw, survey_type)
        if self.platform == "surveymonkey":
            return self._normalize_surveymonkey(raw, survey_type)
        return self._normalize_generic(raw, survey_type)

    def _normalize_typeform(self, raw: dict, survey_type: str) -> dict:
        answers = {a.get("field", {}).get("ref", ""): a for a in raw.get("answers", [])}
        hidden = raw.get("hidden", {})

        nps_answer = answers.get("nps_score") or answers.get("nps")
        process_answer = answers.get("process_rating") or answers.get("process")
        comm_answer = answers.get("communication_rating") or answers.get("communication")
        text_answer = answers.get("open_feedback") or answers.get("open_text") or answers.get("comments")

        return {
            "response_id": raw.get("response_id") or raw.get("token", ""),
            "survey_type": survey_type,
            "respondent_id": hidden.get("candidate_id") or hidden.get("employee_id", ""),
            "recruiter_id": hidden.get("recruiter_id"),
            "req_id": hidden.get("req_id"),
            "submitted_at": raw.get("submitted_at") or raw.get("landed_at"),
            "nps": _extract_number(nps_answer),
            "process_rating": _extract_rating(process_answer),
            "communication_rating": _extract_rating(comm_answer),
            "overall_rating": _extract_rating(answers.get("overall_rating")),
            "open_text": _extract_text(text_answer),
            "pulse_day": _safe_int(hidden.get("pulse_day")),
            "would_recommend": _extract_boolean(answers.get("would_recommend")),
        }

    def _normalize_qualtrics(self, raw: dict, survey_type: str) -> dict:
        values = raw.get("values", {})
        embedded = raw.get("embeddedData", {})

        return {
            "response_id": raw.get("responseId", ""),
            "survey_type": survey_type,
            "respondent_id": embedded.get("candidate_id") or embedded.get("employee_id", ""),
            "recruiter_id": embedded.get("recruiter_id"),
            "req_id": embedded.get("req_id"),
            "submitted_at": raw.get("recordedDate") or raw.get("endDate"),
            "nps": _safe_int(values.get("QID_NPS") or values.get("nps")),
            "process_rating": _extract_qualtrics_rating(values, "process"),
            "communication_rating": _extract_qualtrics_rating(values, "communication"),
            "overall_rating": _extract_qualtrics_rating(values, "overall"),
            "open_text": values.get("QID_OpenText") or values.get("open_feedback"),
            "pulse_day": _safe_int(embedded.get("pulse_day")),
            "would_recommend": _safe_int(values.get("QID_Recommend", 0)) >= 4 if values.get("QID_Recommend") else None,
        }

    def _normalize_surveymonkey(self, raw: dict, survey_type: str) -> dict:
        pages = raw.get("pages", [])
        all_answers = {}
        for page in pages:
            for question in page.get("questions", []):
                qid = question.get("id", "")
                answers = question.get("answers", [])
                if answers:
                    all_answers[qid] = answers[0]
        metadata = raw.get("metadata", {})

        return {
            "response_id": raw.get("id", ""),
            "survey_type": survey_type,
            "respondent_id": metadata.get("candidate_id") or metadata.get("employee_id", ""),
            "recruiter_id": metadata.get("recruiter_id"),
            "req_id": metadata.get("req_id"),
            "submitted_at": raw.get("date_modified") or raw.get("date_created"),
            "nps": _safe_int((all_answers.get("nps_question") or {}).get("text")),
            "process_rating": _safe_float((all_answers.get("process_q") or {}).get("text")),
            "communication_rating": _safe_float((all_answers.get("comm_q") or {}).get("text")),
            "overall_rating": _safe_float((all_answers.get("overall_q") or {}).get("text")),
            "open_text": (all_answers.get("open_q") or {}).get("text"),
            "pulse_day": _safe_int(metadata.get("pulse_day")),
            "would_recommend": None,
        }

    def _normalize_generic(self, raw: dict, survey_type: str) -> dict:
        return {
            "response_id": str(raw.get("id") or raw.get("response_id", "")),
            "survey_type": survey_type,
            "respondent_id": str(raw.get("respondent_id") or raw.get("candidate_id") or raw.get("employee_id", "")),
            "recruiter_id": str(raw.get("recruiter_id", "")) or None,
            "req_id": str(raw.get("req_id", "")) or None,
            "submitted_at": raw.get("submitted_at") or raw.get("created_at"),
            "nps": _safe_int(raw.get("nps")),
            "process_rating": _safe_float(raw.get("process_rating")),
            "communication_rating": _safe_float(raw.get("communication_rating")),
            "overall_rating": _safe_float(raw.get("overall_rating")),
            "open_text": raw.get("open_text") or raw.get("comments"),
            "pulse_day": _safe_int(raw.get("pulse_day")),
            "would_recommend": raw.get("would_recommend"),
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
                resp = self.client.get(url, params={**params, "page": page, "page_size": 500})
                resp.raise_for_status()
                data = resp.json()

                # Platform-specific response unwrapping
                if self.platform == "typeform":
                    items = data.get("items", [])
                    total_items = data.get("total_items", 0)
                elif self.platform == "qualtrics":
                    items = data.get("result", {}).get("elements", [])
                    total_items = data.get("result", {}).get("nextPage") and 999 or 0
                elif self.platform == "surveymonkey":
                    items = data.get("data", [])
                    total_items = data.get("total", 0)
                else:
                    items = data if isinstance(data, list) else data.get("results", data.get("data", []))
                    total_items = len(items)

                if not items:
                    break
                results.extend(items)
                if len(items) < 500:
                    break
                page += 1
            except httpx.HTTPStatusError as e:
                log.error(f"Survey API error {e.response.status_code} at {url}: {e}")
                break
            except Exception as e:
                log.error(f"Unexpected survey connector error: {e}")
                break
        log.info(f"Survey: fetched {len(results)} responses from {url}")
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

def _safe_int(val: Any) -> int | None:
    try:
        return int(float(str(val))) if val is not None else None
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> float | None:
    try:
        return round(float(str(val)), 2) if val is not None else None
    except (ValueError, TypeError):
        return None


def _extract_number(answer_block: dict | None) -> int | None:
    """Extract a numeric value from a Typeform answer block."""
    if not answer_block:
        return None
    return _safe_int(answer_block.get("number") or answer_block.get("choice", {}).get("label"))


def _extract_rating(answer_block: dict | None) -> float | None:
    """Extract a 1-5 rating from a Typeform answer block (opinion scale or rating)."""
    if not answer_block:
        return None
    raw = answer_block.get("number") or answer_block.get("rating")
    return _safe_float(raw)


def _extract_text(answer_block: dict | None) -> str | None:
    """Extract free text from a Typeform answer block."""
    if not answer_block:
        return None
    return answer_block.get("text") or answer_block.get("email")


def _extract_boolean(answer_block: dict | None) -> bool | None:
    """Extract a yes/no boolean from a Typeform answer block."""
    if not answer_block:
        return None
    val = answer_block.get("boolean")
    if val is not None:
        return bool(val)
    label = (answer_block.get("choice") or {}).get("label", "").lower()
    if label in ("yes", "true", "1"):
        return True
    if label in ("no", "false", "0"):
        return False
    return None


def _extract_qualtrics_rating(values: dict, key_prefix: str) -> float | None:
    """Look for common Qualtrics QID naming patterns for a given question type."""
    for key in values:
        if key_prefix.lower() in key.lower():
            return _safe_float(values[key])
    return None
