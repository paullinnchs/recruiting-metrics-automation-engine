"""
client_intake.py
-----------------
Validates and loads a single client's intake folder, feeding the existing
Tier 1 / Tier 2 recruiting calc functions and the existing revenue-leak
check functions. Does not reimplement any calculation — it only reads
files into the same normalized shapes those functions already consume.

Expected intake structure:

    <intake_dir>/
        intake_manifest.json        (client_id, client_name)
        recruiting/
            requisitions.json       required for Tier 1
            candidates.json         required for Tier 1
            applications.json       required for Tier 1
            offers.json             required for Tier 1
            sessions.json           optional (application completion rate only)
            hris_employees.json     required for Tier 2 (in addition to Tier 1 files)
            hris_performance.json   required for Tier 2
            survey_responses.json   required for Tier 2
            recruiting_config.json  optional (headcount/spend/funnel overrides)
        revenue/
            billing_data.csv        required for revenue analysis
            rate_cards.csv          required for revenue analysis
            contracts.csv           required for revenue analysis

Part of: recruiting-metrics-automation-engine
Author:  Paul Linn Solutions (PLS)
"""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

TIER1_REQUIRED = ["requisitions.json", "candidates.json", "applications.json", "offers.json"]
TIER1_OPTIONAL = ["sessions.json", "recruiting_config.json"]
TIER2_REQUIRED_ADDITIONAL = ["hris_employees.json", "hris_performance.json", "survey_responses.json"]
REVENUE_REQUIRED = ["billing_data.csv", "rate_cards.csv", "contracts.csv"]


def _check_files(folder: Path, filenames: list[str]) -> tuple[list[str], list[str]]:
    present, missing = [], []
    for name in filenames:
        (present if (folder / name).exists() else missing).append(name)
    return present, missing


def validate_intake(intake_dir: str | Path) -> dict:
    """
    Inspects the intake folder and returns exactly what's present, what's
    missing, and which analysis areas can run. Never fabricates data —
    this is a presence check only, run before any calculation.
    """
    intake_dir = Path(intake_dir)
    recruiting_dir = intake_dir / "recruiting"
    revenue_dir = intake_dir / "revenue"

    manifest_path = intake_dir / "intake_manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
        client_id = manifest.get("client_id", intake_dir.name)
        client_name = manifest.get("client_name", client_id)
    else:
        client_id = intake_dir.name
        client_name = intake_dir.name
        log.warning(f"No intake_manifest.json found — using folder name '{client_id}' as client identifier.")

    t1_present, t1_missing = _check_files(recruiting_dir, TIER1_REQUIRED)
    t1_opt_present, _ = _check_files(recruiting_dir, TIER1_OPTIONAL)
    t2_present, t2_missing = _check_files(recruiting_dir, TIER2_REQUIRED_ADDITIONAL)
    rev_present, rev_missing = _check_files(revenue_dir, REVENUE_REQUIRED)

    tier1_available = len(t1_missing) == 0
    tier2_available = tier1_available and len(t2_missing) == 0
    revenue_available = len(rev_missing) == 0

    return {
        "client_id": client_id,
        "client_name": client_name,
        "intake_dir": str(intake_dir),
        "recruiting_tier1": {
            "available": tier1_available,
            "present": t1_present + t1_opt_present,
            "missing": t1_missing,
            "has_sessions": "sessions.json" in t1_opt_present,
        },
        "recruiting_tier2": {
            "available": tier2_available,
            "present": t2_present,
            "missing": (t1_missing if not tier1_available else []) + t2_missing,
        },
        "revenue": {
            "available": revenue_available,
            "present": rev_present,
            "missing": rev_missing,
        },
    }


def _load_json(path: Path) -> list | dict:
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def load_recruiting_data(intake_dir: str | Path, validation: dict) -> dict:
    """
    Loads recruiting-side intake files into the exact normalized shapes
    tier1_ats_agent.py and tier2_crosssystem_agent.py's calc_ functions
    already expect. Only loads what validate_intake() confirmed is present;
    returns empty lists for anything missing rather than guessing.
    """
    recruiting_dir = Path(intake_dir) / "recruiting"
    data = {
        "reqs": [], "candidates": [], "applications": [], "offers": [], "sessions": [],
        "hris_employees": [], "hris_performance": [], "survey_responses": [],
        "config": {},
    }

    if validation["recruiting_tier1"]["available"]:
        data["reqs"] = _load_json(recruiting_dir / "requisitions.json")
        data["candidates"] = _load_json(recruiting_dir / "candidates.json")
        data["applications"] = _load_json(recruiting_dir / "applications.json")
        data["offers"] = _load_json(recruiting_dir / "offers.json")
        if validation["recruiting_tier1"]["has_sessions"]:
            data["sessions"] = _load_json(recruiting_dir / "sessions.json")

    if validation["recruiting_tier2"]["available"]:
        data["hris_employees"] = _load_json(recruiting_dir / "hris_employees.json")
        data["hris_performance"] = _load_json(recruiting_dir / "hris_performance.json")
        data["survey_responses"] = _load_json(recruiting_dir / "survey_responses.json")

    config_path = recruiting_dir / "recruiting_config.json"
    if config_path.exists():
        data["config"] = _load_json(config_path)

    return data


def build_billing_connector_config(intake_dir: str | Path) -> dict:
    """
    Returns a BillingConnector-compatible config dict pointing at this
    intake's revenue files. BillingConnector itself is unchanged — it
    already supports file_csv, this just points it at the intake folder
    instead of the global sample_data/ path.
    """
    revenue_dir = Path(intake_dir) / "revenue"
    return {
        "platform": "file_csv",
        "billing_path": str(revenue_dir / "billing_data.csv"),
        "rate_card_path": str(revenue_dir / "rate_cards.csv"),
        "contracts_path": str(revenue_dir / "contracts.csv"),
    }
