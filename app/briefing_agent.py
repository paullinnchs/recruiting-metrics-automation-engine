"""
briefing_agent.py
-----------------
Executive TA briefing generator.

Aggregates outputs from Tier 1 and Tier 2 agents, summarizes
open-text survey data via LLM, and produces a weekly Markdown briefing
for TA leaders and a monthly executive summary.

Part of: recruiting-metrics-automation-engine
Author:  Paul Linn Solutions (PLS)
"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).parent.parent / "outputs"
CONFIG_PATH = Path(__file__).parent.parent / "config"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"


def load_latest_report(tier: int) -> dict:
    report_dir = OUTPUT_PATH / "reports"
    today = date.today().isoformat()
    path = report_dir / f"tier{tier}_report_{today}.json"
    if not path.exists():
        log.warning(f"No Tier {tier} report found for today. Using empty data.")
        return {}
    with open(path) as f:
        return json.load(f)


def load_alerts() -> list[dict]:
    alert_dir = OUTPUT_PATH / "alerts"
    today = date.today().isoformat()
    path = alert_dir / f"alerts_{today}.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


# ──────────────────────────────────────────────
# LLM CALLS
# ──────────────────────────────────────────────

def summarize_open_text(open_texts: list[str], context: str = "candidate experience") -> str:
    """
    Send open-text survey responses to Claude for theme extraction.
    Returns a concise Markdown summary of key themes.
    """
    if not open_texts:
        return "_No open-text responses available._"

    prompt = f"""You are analyzing open-text survey responses about {context} in a recruiting process.

Below are {len(open_texts)} responses. Extract the 3-5 most common themes.
For each theme: one-sentence label, frequency signal (most/some/few respondents), and one representative paraphrase.
Do not quote directly. Format as a simple bullet list. Be concise.

Responses:
{chr(10).join(f"- {t}" for t in open_texts[:50])}"""

    try:
        response = httpx.post(
            ANTHROPIC_API_URL,
            headers={"Content-Type": "application/json"},
            json={
                "model": MODEL,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]
    except Exception as e:
        log.error(f"LLM call failed: {e}")
        return "_Theme extraction unavailable — review raw responses._"


def generate_executive_briefing(metrics_summary: dict, alerts: list[dict],
                                 open_text_themes: str) -> str:
    """
    Generate a full executive TA briefing narrative via Claude.
    """
    prompt = f"""You are a talent acquisition analyst generating a weekly executive briefing for a TA leadership team.

Use the metrics data and alerts below to write a concise, business-oriented briefing.
Format: Markdown. Sections: Pipeline Health, Sourcing Performance, Candidate Experience, Recruiter Performance, Alerts & Actions.
Tone: direct, data-driven, no fluff. Flag risks clearly. Recommend 1-2 actions per section maximum.
Today's date: {date.today()}

METRICS DATA:
{json.dumps(metrics_summary, indent=2, default=str)}

ALERTS THIS PERIOD:
{json.dumps(alerts, indent=2, default=str)}

CANDIDATE EXPERIENCE THEMES (from open-text):
{open_text_themes}"""

    try:
        response = httpx.post(
            ANTHROPIC_API_URL,
            headers={"Content-Type": "application/json"},
            json={
                "model": MODEL,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=45,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]
    except Exception as e:
        log.error(f"Executive briefing generation failed: {e}")
        return "_Briefing generation failed — review raw metrics in report JSON._"


# ──────────────────────────────────────────────
# STRUCTURED WEEKLY REPORT
# ──────────────────────────────────────────────

def build_metric_snapshot(t1: dict, t2: dict) -> dict:
    """Pull key values out of tier reports into a flat summary dict."""
    m1 = t1.get("metrics", {})
    m2 = t2.get("metrics", {})

    return {
        "time_to_fill_avg_days":       m1.get("time_to_fill", {}).get("average_days"),
        "time_to_hire_avg_days":       m1.get("time_to_hire", {}).get("average_days"),
        "offer_acceptance_rate_pct":   m1.get("offer_acceptance_rate", {}).get("rate_pct"),
        "fill_rate_pct":               m1.get("fill_rate", {}).get("fill_rate_pct"),
        "vacancy_rate_pct":            m1.get("pct_open_positions", {}).get("vacancy_rate_pct"),
        "app_completion_rate_pct":     m1.get("application_completion_rate", {}).get("rate_pct"),
        "top_source_of_hire":          (m1.get("source_of_hire", {}).get("breakdown") or [{}])[0].get("source"),
        "quality_of_hire_success_ratio": m2.get("quality_of_hire", {}).get("success_ratio_pct"),
        "cost_per_hire":               m2.get("cost_per_hire", {}).get("cost_per_hire"),
        "first_year_attrition_pct":    m2.get("first_year_attrition", {}).get("rate_pct"),
        "cnps":                        m2.get("candidate_experience", {}).get("cnps"),
        "funnel_bottleneck":           m2.get("recruitment_funnel_effectiveness", {}).get("biggest_drop_stage"),
        "adverse_impact_flags":        m2.get("adverse_impact", {}).get("adverse_impact_flags", []),
    }


def build_plain_report(snapshot: dict, alerts: list[dict]) -> str:
    """Build a static Markdown report (no LLM) for fast weekly delivery."""
    today = date.today().isoformat()
    week_start = (date.today() - timedelta(days=7)).isoformat()

    def fmt(val, suffix=""):
        return f"{val}{suffix}" if val is not None else "—"

    alert_lines = "\n".join(
        f"  {'🔴' if a['level'] == 'CRITICAL' else '🟡'} **{a['metric'].replace('_', ' ').title()}**: {a['message']}"
        for a in alerts
    ) or "  ✅ No threshold breaches this period."

    return f"""# TA Metrics Briefing — Week of {week_start}
*Generated {today} by recruiting-metrics-automation-engine*

---

## Pipeline health

| Metric | Value |
|--------|-------|
| Avg time to fill | {fmt(snapshot['time_to_fill_avg_days'], ' days')} |
| Avg time to hire | {fmt(snapshot['time_to_hire_avg_days'], ' days')} |
| Fill rate (90 days) | {fmt(snapshot['fill_rate_pct'], '%')} |
| Vacancy rate | {fmt(snapshot['vacancy_rate_pct'], '%')} |
| Funnel bottleneck | {fmt(snapshot['funnel_bottleneck'])} |

## Sourcing performance

| Metric | Value |
|--------|-------|
| Top source of hire | {fmt(snapshot['top_source_of_hire'])} |
| Application completion rate | {fmt(snapshot['app_completion_rate_pct'], '%')} |
| Cost per hire | ${fmt(snapshot['cost_per_hire'])} |

## Offer & quality

| Metric | Value |
|--------|-------|
| Offer acceptance rate | {fmt(snapshot['offer_acceptance_rate_pct'], '%')} |
| Quality of hire (success ratio) | {fmt(snapshot['quality_of_hire_success_ratio'], '%')} |
| First-year attrition | {fmt(snapshot['first_year_attrition_pct'], '%')} |

## Candidate experience

| Metric | Value |
|--------|-------|
| Candidate NPS (cNPS) | {fmt(snapshot['cnps'])} |

## Alerts this period

{alert_lines}

## Compliance

{"⚠️  **Adverse impact flag(s):** " + ", ".join(snapshot['adverse_impact_flags']) + " — route to HR/Legal immediately." if snapshot['adverse_impact_flags'] else "✅ No adverse impact flags."}

---
*Powered by recruiting-metrics-automation-engine | Paul Linn Solutions*
"""


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def run(use_llm: bool = True):
    log.info("Briefing Agent starting")

    t1 = load_latest_report(1)
    t2 = load_latest_report(2)
    alerts = load_alerts()
    snapshot = build_metric_snapshot(t1, t2)

    # Extract open-text responses for LLM
    cx_data = t2.get("metrics", {}).get("candidate_experience", {})
    open_texts = cx_data.get("open_text_responses", [])

    if use_llm and open_texts:
        log.info(f"Sending {len(open_texts)} open-text responses to LLM for theme extraction")
        themes = summarize_open_text(open_texts)
        log.info("Generating executive briefing via LLM")
        briefing_body = generate_executive_briefing(snapshot, alerts, themes)
    else:
        themes = "_LLM disabled or no open-text data._"
        briefing_body = build_plain_report(snapshot, alerts)

    # Write outputs
    out_dir = OUTPUT_PATH / "briefings"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    md_path = out_dir / f"ta_briefing_{today}.md"
    with open(md_path, "w") as f:
        f.write(briefing_body)
    log.info(f"Briefing written: {md_path}")

    json_path = out_dir / f"ta_briefing_{today}.json"
    with open(json_path, "w") as f:
        json.dump({
            "generated_at": datetime.utcnow().isoformat(),
            "snapshot": snapshot,
            "alerts": alerts,
            "open_text_themes": themes,
        }, f, indent=2, default=str)
    log.info(f"Structured briefing JSON written: {json_path}")

    return briefing_body, snapshot


if __name__ == "__main__":
    run()
