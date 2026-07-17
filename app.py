"""
app.py — Flood Relief Dashboard
================================
AI-driven Flask application combining:
  - A local Random Forest model trained on terrain (elevation), drainage,
    and census data to classify ward-level flood risk (Low/Medium/High).
  - Live rainfall ingestion (Open-Meteo) to nudge predictions in real time.
  - A cloud-hosted LLM (Anthropic Claude) that turns the technical output
    into a short, localized, actionable public safety advisory tied to an
    evacuation state (MONITOR / PREPARE / EVACUATE).
"""

import os
from flask import Flask, jsonify, render_template, request
import requests

from predictor import FloodRiskPredictor
from advisory import generate_advisory

app = Flask(__name__)
predictor = FloodRiskPredictor()

RAINFALL_API = "https://api.open-meteo.com/v1/forecast"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/wards")
def api_wards():
    """GeoJSON for the map, colored by baseline (no live-rain) prediction."""
    return app.response_class(predictor.geojson_for_map(), mimetype="application/json")


@app.route("/api/ward-names")
def api_ward_names():
    return jsonify(predictor.list_wards())


def _fetch_live_rainfall(lat, lon):
    """Latest hourly precipitation reading (mm) from Open-Meteo for a point."""
    try:
        r = requests.get(
            RAINFALL_API,
            params={"latitude": lat, "longitude": lon, "hourly": "precipitation", "timezone": "Asia/Kolkata"},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
        return float(data["hourly"]["precipitation"][-1])
    except Exception as e:
        print(f"[WARN] live rainfall fetch failed: {e}")
        return None


@app.route("/api/predict")
def api_predict():
    ward = request.args.get("ward", "")
    use_live_rain = request.args.get("use_live_rain", "1") in ("1", "true", "True")
    include_advisory = request.args.get("advisory", "1") in ("1", "true", "True")

    if not ward:
        return jsonify({"error": "ward parameter required"}), 400

    try:
        live_rainfall = None
        if use_live_rain:
            # need centroid first — do a cheap lookup via the predictor's row
            row = predictor._find_row(ward)
            live_rainfall = _fetch_live_rainfall(row["centroid_lat"], row["centroid_lon"])

        prediction = predictor.predict_for_ward(ward, live_rainfall_mm=live_rainfall)

        result = {"prediction": prediction}
        if include_advisory:
            result["advisory"] = generate_advisory(prediction["ward_name"], prediction)

        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        print(f"[ERROR] /api/predict failed: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
