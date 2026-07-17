"""
advisory.py
============
Calls a cloud-hosted LLM (Anthropic's Claude, via the standard Messages API)
to translate a ward's technical flood-risk metrics into a short, localized,
actionable public safety advisory — the part of the spec that turns numbers
like "drainage_density: 0.42, population_density: 21000" into something a
resident or ward officer can actually act on.

Design choices:
- Stateless HTTP call via `requests` (no SDK dependency required).
- API key read from the ANTHROPIC_API_KEY environment variable. Never
  hardcode a key in source.
- If no key is configured, or the call fails/times out, we fall back to a
  deterministic templated advisory so the dashboard keeps working end to
  end for a demo/offline setting — it just loses the "instantly localized
  by an LLM" polish.
- A tiny in-memory cache avoids re-calling the API for the same
  (ward, risk, evacuation_state) combination within a session.
"""

import os
import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-5"  # override with ANTHROPIC_MODEL env var if desired

_cache = {}


def _fallback_advisory(ward_name, prediction):
    """Deterministic, template-based advisory used when no LLM is available."""
    risk = prediction["predicted_flood_risk"]
    state = prediction["evacuation_state"]
    m = prediction["metrics"]

    if state == "EVACUATE":
        return (
            f"{ward_name} is at HIGH flood risk right now. Residents in low-lying streets "
            f"and near drains should move to higher ground or a designated relief center "
            f"immediately. Avoid underpasses and flooded roads — do not attempt to drive or "
            f"walk through moving water. Keep emergency contacts and essential documents ready."
        )
    if state == "PREPARE":
        return (
            f"{ward_name} is at MEDIUM flood risk. Drainage density here is "
            f"{'below' if m['drainage_density_km_per_sqkm'] < 3 else 'around'} normal levels, so clear "
            f"blocked drains near your home if it's safe to do so. Keep an eye on rising water "
            f"near low-lying areas, move vehicles and valuables to higher floors, and stay "
            f"tuned to BBMP alerts over the next few hours."
        )
    return (
        f"{ward_name} currently shows LOW flood risk. No immediate action is needed, but it's "
        f"a good time to check that drains near your home aren't blocked ahead of the next "
        f"heavy spell, especially given local rainfall patterns."
    )


def generate_advisory(ward_name, prediction):
    """Return a short localized advisory string for this ward's current prediction."""
    cache_key = (
        ward_name,
        prediction["predicted_flood_risk"],
        prediction["evacuation_state"],
        prediction["metrics"]["live_rainfall_mm_hr"],
    )
    if cache_key in _cache:
        return {"advisory": _cache[cache_key], "source": "llm-cached"}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        text = _fallback_advisory(ward_name, prediction)
        return {"advisory": text, "source": "fallback-no-api-key"}

    m = prediction["metrics"]
    prompt = (
        "You are a public-safety communications assistant for the BBMP (Bengaluru's civic body) "
        "flood monitoring desk. Translate the following technical flood-risk assessment for one "
        "city ward into a short, plain-language, actionable public advisory (3-4 sentences, no "
        "markdown, no headers). Be specific to the numbers given, not generic. Mention the "
        "concrete action residents/ward officials should take right now given the evacuation "
        "state.\n\n"
        f"Ward: {ward_name}\n"
        f"Predicted flood risk: {prediction['predicted_flood_risk']}\n"
        f"Evacuation state: {prediction['evacuation_state']}\n"
        f"Mean elevation: {m['mean_elevation_m']} m\n"
        f"Population density: {m['population_density_per_sqkm']} people/km2\n"
        f"Drainage density: {m['drainage_density_km_per_sqkm']} km of drains per km2\n"
        f"Vulnerable population ratio (SC/ST): {m['vulnerable_pop_ratio']}\n"
        f"Population: {m['population']}\n"
        f"Live rainfall reading: {m['live_rainfall_mm_hr']} mm/hr\n"
    )

    try:
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": os.environ.get("ANTHROPIC_MODEL", ANTHROPIC_MODEL),
                "max_tokens": 250,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        text = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        ).strip()
        if not text:
            raise ValueError("Empty response from LLM")
        _cache[cache_key] = text
        return {"advisory": text, "source": "llm"}
    except Exception as e:
        text = _fallback_advisory(ward_name, prediction)
        return {"advisory": text, "source": f"fallback-error:{e}"}
