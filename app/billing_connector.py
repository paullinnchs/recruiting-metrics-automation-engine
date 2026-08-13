"""
billing_connector.py
---------------------
Billing / VMS / timesheet adapter for the Workforce Revenue Leak Workflow Sprint.
"""

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


class BillingConnector:
    FILE_PLATFORMS = {"file_csv", "file_excel"}
    API_PLATFORMS = {"sap_fieldglass", "beeline", "bullhorn", "generic_rest"}

    def __init__(self, config: dict):
        self.config = config
        self.platform = config.get("platform", "file_csv")
        self.client = None
        if self.platform in self.API_PLATFORMS:
            import httpx
            import os
            key = os.environ.get("VMS_API_KEY", config.get("api_key", ""))
            self.base_url = config.get("base_url", "").rstrip("/")
            self.client = httpx.Client(
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=30,
            )

    def get_billing_records(self, since: date | None = None) -> list[dict]:
        if self.platform in self.FILE_PLATFORMS:
            raw = self._read_file(self.config.get("billing_path") or self.config.get("timesheet_path"))
        else:
            raw = self._paginate("/billing_records", params=self._since_param(since))
        records = [self._normalize_billing_record(r) for r in raw]
        if since:
            records = [r for r in records if r["period_end"] and r["period_end"] >= since.isoformat()]
        return records

    def get_rate_cards(self) -> list[dict]:
        if self.platform in self.FILE_PLATFORMS:
            raw = self._read_file(self.config.get("rate_card_path"))
        else:
            raw = self._paginate("/rate_cards")
        return [self._normalize_rate_card(r) for r in raw]

    def get_contracts(self) -> list[dict]:
        if self.platform in self.FILE_PLATFORMS:
            raw = self._read_file(self.config.get("contracts_path"))
        else:
            raw = self._paginate("/contracts")
        return [self._normalize_contract(r) for r in raw]

    def _read_file(self, path: str | None) -> list[dict]:
        if not path:
            return []
        p = Path(path)
        if not p.exists():
            log.warning(f"Billing connector: file not found at {path} — skipping.")
            return []
        try:
            if self.platform == "file_excel" or p.suffix in (".xlsx", ".xls"):
                df = pd.read_excel(p)
            else:
                df = pd.read_csv(p)
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            return df.to_dict(orient="records")
        except Exception as e:
            log.error(f"Failed to read billing file {path}: {e}")
            return []

    def _since_param(self, since: date | None) -> dict:
        return {"since": since.isoformat()} if since else {}

    def _paginate(self, endpoint: str, params: dict | None = None, max_pages: int = 50) -> list[dict]:
        if not self.client:
            return []
        import httpx
        results = []
        page = 1
        params = params or {}
        url = f"{self.base_url}{endpoint}"
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
                log.error(f"Billing/VMS API error {e.response.status_code} at {url}: {e}")
                break
            except Exception as e:
                log.error(f"Unexpected billing connector error: {e}")
                break
        return results

    @staticmethod
    def _to_float(val, default: float = 0.0) -> float:
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_bool(val, default: bool = False) -> bool:
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.strip().lower() in ("true", "yes", "1", "y")
        return default

    def _normalize_billing_record(self, raw: dict) -> dict:
        return {
            "id": str(raw.get("id") or raw.get("invoice_line_id") or raw.get("record_id", "")),
            "worker_id": str(raw.get("worker_id") or raw.get("contractor_id", "")),
            "worker_name": raw.get("worker_name") or raw.get("contractor_name"),
            "worker_type": (raw.get("worker_type") or raw.get("classification") or "unknown").strip().lower(),
            "engagement_type": (raw.get("engagement_type") or raw.get("engagement") or "unspecified").strip().lower(),
            "supplier_vendor": raw.get("supplier_vendor") or raw.get("vendor") or raw.get("supplier"),
            "department": raw.get("department") or raw.get("cost_center"),
            "role_title": raw.get("role_title") or raw.get("job_title") or raw.get("role"),
            "contract_id": str(raw.get("contract_id")) if raw.get("contract_id") else None,
            "period_start": self._parse_date(raw.get("period_start") or raw.get("week_start")),
            "period_end": self._parse_date(raw.get("period_end") or raw.get("week_end") or raw.get("invoice_date")),
            "hours_submitted": self._to_float(raw.get("hours_submitted")),
            "hours_approved": self._to_float(raw.get("hours_approved")),
            "hours_invoiced": self._to_float(raw.get("hours_invoiced") or raw.get("hours_billed")),
            "pay_rate": self._to_float(raw.get("pay_rate")),
            "bill_rate": self._to_float(raw.get("bill_rate")),
            "invoice_amount": self._to_float(raw.get("invoice_amount") or raw.get("amount_billed")),
            "is_approved_supplier": self._to_bool(raw.get("is_approved_supplier"), default=True),
        }

    def _normalize_rate_card(self, raw: dict) -> dict:
        return {
            "supplier_vendor": raw.get("supplier_vendor") or raw.get("vendor") or raw.get("supplier"),
            "role_title": raw.get("role_title") or raw.get("job_title") or raw.get("role"),
            "contracted_bill_rate": self._to_float(raw.get("contracted_bill_rate") or raw.get("bill_rate")),
            "contracted_markup_pct": (
                self._to_float(raw["contracted_markup_pct"])
                if raw.get("contracted_markup_pct") not in (None, "")
                else None
            ),
            "effective_date": self._parse_date(raw.get("effective_date")),
            "expiration_date": self._parse_date(raw.get("expiration_date")),
        }

    def _normalize_contract(self, raw: dict) -> dict:
        return {
            "contract_id": str(raw.get("contract_id") or raw.get("id", "")),
            "supplier_vendor": raw.get("supplier_vendor") or raw.get("vendor") or raw.get("supplier"),
            "engagement_type": (raw.get("engagement_type") or "unspecified").strip().lower(),
            "approved_supplier": self._to_bool(raw.get("approved_supplier"), default=True),
            "billing_cadence": (raw.get("billing_cadence") or "unspecified").strip().lower(),
            "deliverables_defined": self._to_bool(raw.get("deliverables_defined"), default=False),
        }

    @staticmethod
    def _parse_date(val) -> str | None:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        if isinstance(val, (date, datetime)):
            return val.isoformat()
        try:
            return pd.to_datetime(val).date().isoformat()
        except Exception:
            return None

    def close(self):
        if self.client:
            self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
