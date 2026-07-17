"""
predictor.py
=============
Loads the trained Random Forest flood-risk classifier and the pre-engineered
ward feature table (terrain / drainage / census derived features), and
exposes a single entry point — predict_for_ward() — that:

  1. Pulls a ward's baseline engineered features (mean/min/max elevation,
     drainage density, population density, vulnerable population ratio,
     rainfall, etc.) from wards_with_predictions.geojson. These 18 features
     are exactly the ones the model was trained on (see feature_names.json).
  2. Optionally overrides the rainfall feature with a live reading (e.g.
     from Open-Meteo) to produce an up-to-the-minute prediction.
  3. Scales the feature vector with the fitted StandardScaler and runs it
     through the RandomForestClassifier to get a risk class (1/2/3) and
     class probabilities.
  4. Derives an "evacuation state" — the operational action a BBMP/ward
     office would take — from the risk class plus vulnerability signals
     (population density, drainage density, vulnerable population ratio).

This keeps the ML layer local/offline (no external calls needed to get a
risk number), matching the "local geospatial machine learning" part of the
spec. The LLM call (advisory.py) is a separate, optional layer on top.
"""

import json
import geopandas as gpd
import joblib
import numpy as np

MODEL_PATH = "data/flood_risk_model.pkl"
SCALER_PATH = "data/feature_scaler.pkl"
FEATURE_NAMES_PATH = "data/feature_names.json"
WARD_FILE = "data/wards_with_predictions.geojson"

RISK_LABELS = {1: "Low", 2: "Medium", 3: "High"}

# How strongly a live rainfall reading (mm in the last hour, from Open-Meteo)
# nudges the model's rainfall feature. The training data used a flat annual
# average (960mm) for every ward, so this is a deliberate, documented
# heuristic amplification to make live readings actually move the needle
# on an otherwise-static feature — not a scientifically calibrated figure.
LIVE_RAINFALL_AMPLIFIER = 150.0


class FloodRiskPredictor:
    def __init__(self):
        self.model = joblib.load(MODEL_PATH)
        self.scaler = joblib.load(SCALER_PATH)
        with open(FEATURE_NAMES_PATH) as f:
            self.feature_names = json.load(f)

        self.gdf = gpd.read_file(WARD_FILE)
        self.ward_col = "proposed_ward_name_en"
        # Precompute plain lat/lon centroids for the map + live rainfall API
        gdf_wgs84 = self.gdf.to_crs(epsg=4326) if self.gdf.crs else self.gdf
        self.gdf["centroid_lat"] = gdf_wgs84.geometry.centroid.y
        self.gdf["centroid_lon"] = gdf_wgs84.geometry.centroid.x

        # The model's own population_density/drainage_density features were
        # trained on an area computed directly from lat/lon geometry (degrees
        # squared), which is internally consistent for the model but produces
        # meaningless numbers if shown to a person. Compute real, human-
        # readable versions in a projected metric CRS purely for display.
        gdf_utm = gdf_wgs84.to_crs(gdf_wgs84.estimate_utm_crs())
        real_area_sqkm = (gdf_utm.geometry.area / 1_000_000).replace(0, 1e-6)
        self.gdf["display_area_sqkm"] = real_area_sqkm
        self.gdf["display_population_density"] = (
            self.gdf["population"].astype(float) / real_area_sqkm
        )
        self.gdf["display_drainage_density_km_per_sqkm"] = (
            self.gdf["total_drainage_m"].astype(float) / 1000.0 / real_area_sqkm
        )

    # -----------------------------------------------------------------
    def list_wards(self):
        return sorted(self.gdf[self.ward_col].dropna().unique().tolist())

    # -----------------------------------------------------------------
    def _find_row(self, ward_name):
        exact = self.gdf[self.gdf[self.ward_col].str.lower() == ward_name.lower()]
        if not exact.empty:
            return exact.iloc[0]
        match = self.gdf[
            self.gdf[self.ward_col].str.lower().str.contains(ward_name.lower(), na=False)
        ]
        if match.empty:
            raise ValueError(f"Ward '{ward_name}' not found.")
        return match.iloc[0]

    # -----------------------------------------------------------------
    def geojson_for_map(self):
        """Trimmed GeoJSON with just the fields the frontend needs to draw
        and initially color the map (baseline / no live-rain prediction)."""
        cols = [
            self.ward_col,
            "predicted_risk",
            "display_population_density",
            "display_drainage_density_km_per_sqkm",
            "vulnerable_pop_ratio",
            "avg_annual_rainfall",
            "centroid_lat",
            "centroid_lon",
            "geometry",
        ]
        return self.gdf[cols].to_json()

    # -----------------------------------------------------------------
    def predict_for_ward(self, ward_name, live_rainfall_mm=None):
        row = self._find_row(ward_name)

        feature_vector = []
        for name in self.feature_names:
            val = row.get(name, 0)
            feature_vector.append(float(val) if val is not None else 0.0)

        rainfall_idx = self.feature_names.index("avg_annual_rainfall")
        base_rainfall = feature_vector[rainfall_idx]

        effective_rainfall_mm_hr = 0.0
        if live_rainfall_mm is not None:
            effective_rainfall_mm_hr = float(live_rainfall_mm)
            feature_vector[rainfall_idx] = base_rainfall + (
                effective_rainfall_mm_hr * LIVE_RAINFALL_AMPLIFIER
            )

        X = np.array(feature_vector).reshape(1, -1)
        X_scaled = self.scaler.transform(X)

        pred_class = int(self.model.predict(X_scaled)[0])
        proba = self.model.predict_proba(X_scaled)[0]
        prob_by_class = {
            RISK_LABELS[c]: round(float(p), 3) for c, p in zip(self.model.classes_, proba)
        }
        risk_label = RISK_LABELS.get(pred_class, "Unknown")

        pop_density = float(row.get("display_population_density", 0) or 0)
        drainage_density = float(row.get("display_drainage_density_km_per_sqkm", 0) or 0)
        vulnerable_ratio = float(row.get("vulnerable_pop_ratio", 0) or 0)

        evacuation_state = self._evacuation_state(
            risk_label, pop_density, drainage_density, vulnerable_ratio
        )

        return {
            "ward_name": str(row[self.ward_col]),
            "predicted_flood_risk": risk_label,
            "risk_probabilities": prob_by_class,
            "evacuation_state": evacuation_state["state"],
            "evacuation_priority": evacuation_state["label"],
            "metrics": {
                "mean_elevation_m": round(float(row.get("mean_elevation", 0) or 0), 2),
                "population_density_per_sqkm": round(pop_density, 1),
                "drainage_density_km_per_sqkm": round(drainage_density, 3),
                "vulnerable_pop_ratio": round(vulnerable_ratio, 4),
                "population": int(row.get("population", 0) or 0),
                "baseline_avg_annual_rainfall_mm": round(base_rainfall, 1),
                "live_rainfall_mm_hr": round(effective_rainfall_mm_hr, 2),
            },
            "centroid": {
                "lat": float(row["centroid_lat"]),
                "lon": float(row["centroid_lon"]),
            },
        }

    # -----------------------------------------------------------------
    @staticmethod
    def _evacuation_state(risk_label, pop_density, drainage_density, vulnerable_ratio):
        """Translate risk class + local vulnerability context into an
        operational evacuation state, the kind of decision a ward disaster
        management officer actually needs to act on."""
        high_vulnerability = vulnerable_ratio > 0.15
        poor_drainage = drainage_density < 3.0
        dense = pop_density > 20000

        if risk_label == "High" and (high_vulnerability or poor_drainage):
            return {
                "state": "EVACUATE",
                "label": "🚨 Immediate evacuation — high risk compounded by vulnerable population/poor drainage.",
            }
        if risk_label == "High":
            return {
                "state": "EVACUATE",
                "label": "🚨 High risk — begin evacuation of low-lying areas now.",
            }
        if risk_label == "Medium" and dense:
            return {
                "state": "PREPARE",
                "label": "⚠️ Prepare & pre-position resources — dense ward at medium risk.",
            }
        if risk_label == "Medium":
            return {
                "state": "PREPARE",
                "label": "⚠️ Prepare — monitor conditions closely, alert residents.",
            }
        return {
            "state": "MONITOR",
            "label": "🟢 Monitor — no immediate action required.",
        }
