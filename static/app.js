const RISK_COLOR = { Low: "#3FA796", Medium: "#E8A33D", High: "#E4572E" };

const map = L.map("map", { zoomControl: true }).setView([12.97, 77.59], 11);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

let geoLayer = null;
let wardLayers = {};

const panelEmpty = document.querySelector(".panel-empty-state");
const panelLoaded = document.querySelector(".panel-loaded");
const panelLoading = document.querySelector(".panel-loading");
const liveRainToggle = document.getElementById("live-rain-toggle");
const wardSearch = document.getElementById("ward-search");
const wardList = document.getElementById("ward-list");

function showState(which) {
  panelEmpty.hidden = which !== "empty";
  panelLoaded.hidden = which !== "loaded";
  panelLoading.hidden = which !== "loading";
}

// ---------------------------------------------------------------
// Load ward boundaries, colored by baseline model prediction
// ---------------------------------------------------------------
fetch("/api/wards")
  .then((r) => r.json())
  .then((data) => {
    geoLayer = L.geoJSON(data, {
      style: (feature) => ({
        color: "#2A3639",
        weight: 1,
        fillColor: RISK_COLOR[feature.properties.predicted_risk] || "#3FA796",
        fillOpacity: 0.45,
      }),
      onEachFeature: (feature, layer) => {
        const name = feature.properties.proposed_ward_name_en || "Unnamed";
        wardLayers[name] = layer;
        layer.on("mouseover", () => layer.setStyle({ fillOpacity: 0.7 }));
        layer.on("mouseout", () => layer.setStyle({ fillOpacity: 0.45 }));
        layer.on("click", () => selectWard(name));
      },
    }).addTo(map);
    map.fitBounds(geoLayer.getBounds());
  })
  .catch((err) => console.error("Failed to load wards:", err));

fetch("/api/ward-names")
  .then((r) => r.json())
  .then((names) => {
    wardList.innerHTML = names.map((n) => `<option value="${n}"></option>`).join("");
  });

wardSearch.addEventListener("change", () => {
  const name = wardSearch.value.trim();
  if (name) selectWard(name);
});

// ---------------------------------------------------------------
// Ward selection -> fetch prediction + advisory, render panel
// ---------------------------------------------------------------
function selectWard(name) {
  showState("loading");

  const layer = wardLayers[name];
  if (layer) {
    map.fitBounds(layer.getBounds(), { maxZoom: 14 });
  }

  const useLiveRain = liveRainToggle.checked ? "1" : "0";
  fetch(`/api/predict?ward=${encodeURIComponent(name)}&use_live_rain=${useLiveRain}&advisory=1`)
    .then((r) => r.json())
    .then((data) => {
      if (data.error) {
        alert(data.error);
        showState("empty");
        return;
      }
      renderPanel(data.prediction, data.advisory);
      showState("loaded");
    })
    .catch((err) => {
      console.error(err);
      showState("empty");
    });
}

function renderPanel(pred, advisory) {
  document.getElementById("ward-eyebrow").textContent = "WARD";
  document.getElementById("ward-name").textContent = pred.ward_name;
  document.getElementById("risk-value").textContent = pred.predicted_flood_risk;
  document.getElementById("risk-value").style.color = RISK_COLOR[pred.predicted_flood_risk] || "";

  document.getElementById("rain-value").textContent = `${pred.metrics.live_rainfall_mm_hr} mm/hr`;
  document.getElementById("drain-value").textContent = `${pred.metrics.drainage_density_km_per_sqkm} km/km²`;
  document.getElementById("pop-value").textContent = `${Math.round(pred.metrics.population_density_per_sqkm).toLocaleString()}/km²`;
  document.getElementById("elev-value").textContent = `${pred.metrics.mean_elevation_m} m`;
  document.getElementById("vuln-value").textContent = pred.metrics.vulnerable_pop_ratio;

  const banner = document.getElementById("evac-banner");
  banner.className = `state-banner state-${pred.evacuation_state}`;
  document.getElementById("evac-label").textContent = pred.evacuation_priority;

  const probBars = document.getElementById("prob-bars");
  probBars.innerHTML = Object.entries(pred.risk_probabilities)
    .map(
      ([label, p]) => `
      <div class="prob-row">
        <span class="prob-label">${label}</span>
        <span class="prob-track"><span class="prob-fill" style="width:${p * 100}%;background:${RISK_COLOR[label]}"></span></span>
        <span class="prob-pct">${Math.round(p * 100)}%</span>
      </div>`
    )
    .join("");

  document.getElementById("advisory-text").textContent = advisory.advisory;
  const sourceEl = document.getElementById("advisory-source");
  sourceEl.textContent = advisory.source.startsWith("llm") ? "· generated live" : "· offline template";
}
