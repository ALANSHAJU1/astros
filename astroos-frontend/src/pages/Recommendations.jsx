import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  AlertCircle,
  ArrowRight,
  Binoculars,
  Calendar,
  CalendarDays,
  Camera,
  CheckCircle2,
  Clock,
  Cloud,
  Compass,
  Droplets,
  Eye,
  Info,
  Layers,
  LoaderCircle,
  MapPin,
  RefreshCw,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Telescope,
  Thermometer,
  Wind,
} from "lucide-react";

import BrandLogo from "../components/BrandLogo";
import LocationPicker from "../components/LocationPicker";
import api from "../services/api";
import { formatEventDate } from "../services/eventAdapter";
import {
  CELESTIAL_TARGET_CATALOG,
  predictionService,
  toISOWithOffset,
} from "../services/predictionService";
import {
  getLightPollution,
  calculateLightPollutionEffect,
} from "../services/geocodingService";
import { getCelestialImage } from "../services/celestialImages";
import { getObservationGuide } from "../utils/observationGuide";
import {
  formatClock,
  formatDateTime,
  localInputToIso,
  minutesBetween,
  toDateTimeLocalValue,
} from "../utils/datetime";
import {
  loadObserverLocation,
  saveObserverLocation,
} from "../utils/location";

const GOAL_OPTIONS = [
  { value: "general_observation", label: "🌌 General Stargazing & Overview" },
  { value: "planetary", label: "🪐 Planetary Belts, Rings & Moons" },
  { value: "deep_sky", label: "✨ Deep-Sky Nebulae, Star Clusters & Galaxies" },
  { value: "meteor_shower", label: "🌠 Meteor Showers & Transient Streaks" },
  { value: "astrophotography", label: "📷 High-Contrast Digital Imaging" },
];

const CATEGORY_FILTER_OPTIONS = [
  "All Objects",
  "Planets",
  "Deep Sky",
  "Moon",
  "Meteor Showers",
  "Comets",
  "Asteroids",
  "Solar Eclipses",
  "Lunar Eclipses",
];

function defaultWindow() {
  const start = new Date();
  start.setMinutes(0, 0, 0);
  start.setHours(19, 0, 0, 0);
  const end = new Date(start);
  end.setHours(23, 0, 0, 0);
  return {
    start: toDateTimeLocalValue(start),
    end: toDateTimeLocalValue(end),
  };
}

function RecScorePill({ score, label }) {
  const s = Math.round(score || 0);
  let tone = "fair";
  let txt = "Fair";
  if (s >= 80) {
    tone = "optimal";
    txt = "Optimal";
  } else if (s >= 65) {
    tone = "good";
    txt = "Good";
  } else if (s >= 45) {
    tone = "fair";
    txt = "Fair";
  } else {
    tone = "poor";
    txt = "Poor";
  }

  return (
    <div
      className={`event-score-box ${tone}`}
      title={`${label || "Overall Recommendation"}: ${s}/100 (${txt})`}
    >
      <strong>{s}</strong>
      <span>/100</span>
      <small>{txt}</small>
    </div>
  );
}

function normalizeRecommendationResult(data, scope, activeLp) {
  if (!data) return null;

  // 1. Determine ranked list
  let rawRanked = [];
  if (Array.isArray(data.ranked_events) && data.ranked_events.length > 0) {
    rawRanked = data.ranked_events;
  } else if (Array.isArray(data.ranked) && data.ranked.length > 0) {
    rawRanked = data.ranked;
  } else if (Array.isArray(data.recommendations?.ranked_events)) {
    rawRanked = data.recommendations.ranked_events;
  } else if (Array.isArray(data.details)) {
    rawRanked = data.details;
  }

  // 2. Lookup map for enriched details (multi-key indexing for robust resolution)
  const detailsMap = new Map();
  if (Array.isArray(data.details)) {
    for (const d of data.details) {
      if (d.event_id) detailsMap.set(String(d.event_id), d);
      if (d.id) detailsMap.set(String(d.id), d);
      if (d.name) {
        detailsMap.set(String(d.name), d);
        detailsMap.set(String(d.name).toLowerCase(), d);
      }
    }
  }

  const rankedItems = rawRanked.map((item, idx) => {
    const key = String(item.event_id || item.id || item.name || idx);
    const detail =
      detailsMap.get(String(item.event_id)) ||
      detailsMap.get(String(item.id)) ||
      detailsMap.get(String(item.name)) ||
      detailsMap.get(String(item.name || "").toLowerCase()) ||
      detailsMap.get(key) ||
      {};

    const name = item.name || detail.name || detail.object_name || "Celestial Target";
    const rawCat =
      item.category || detail.category || item.event_type || detail.event_type || "";
    let category = "Deep Sky";
    const lower = String(rawCat).toLowerCase();
    if (lower.includes("planet")) category = "Planets";
    else if (lower.includes("comet")) category = "Comets";
    else if (lower.includes("asteroid") || lower.includes("neo")) category = "Asteroids";
    else if (lower.includes("moon") || lower.includes("lunar")) category = "Moon";
    else if (lower.includes("meteor")) category = "Meteor Showers";
    else if (lower.includes("eclipse")) category = "Eclipses";
    else if (
      lower.includes("deep") ||
      lower.includes("dso") ||
      lower.includes("messier") ||
      lower.includes("galaxy") ||
      lower.includes("nebula") ||
      lower.includes("cluster")
    ) {
      category = "Deep Sky";
    }

    const score =
      item.recommendation_score ??
      detail.recommendation_score ??
      item.score ??
      detail.visibility_score ??
      75;

    const visScore =
      item.visibility_score ??
      detail.visibility_score ??
      detail.astronomical_score ??
      null;

    const weatherScore =
      item.weather_score ??
      detail.weather_score ??
      detail.environmental_score ??
      null;

    const prefScore =
      item.preference_score ??
      detail.preference_score ??
      null;

    const apparentMag =
      item.apparent_magnitude ??
      detail.apparent_magnitude ??
      item.additional_data?.apparent_magnitude ??
      detail.additional_data?.apparent_magnitude ??
      null;

    const altitude =
      item.target_altitude_deg ??
      item.peak_elevation_deg ??
      detail.target_altitude_deg ??
      detail.peak_elevation_deg ??
      item.additional_data?.target_altitude_deg ??
      item.additional_data?.peak_elevation_deg ??
      detail.additional_data?.target_altitude_deg ??
      detail.additional_data?.peak_elevation_deg ??
      null;

    const guide = getObservationGuide(
      name,
      category,
      apparentMag
    );

    const windowStart =
      item.window_start ||
      detail.window_start ||
      item.scheduled_start ||
      detail.start_time;

    const windowEnd =
      item.window_end ||
      detail.window_end ||
      item.scheduled_end ||
      detail.end_time;

    const durationMinutes =
      item.duration_minutes ||
      detail.duration_minutes ||
      detail.required_duration_minutes ||
      20;

    // Light Pollution Impact Analysis for observer's site
    const bortle = activeLp?.bortle_class || 5;
    const lpEffect = calculateLightPollutionEffect(category, bortle, apparentMag);

    let lpNotice = null;
    if (bortle >= 6) {
      if (category === "Planets") {
        lpNotice = {
          tone: "favorable",
          label: `Bortle ${bortle} Penetration`,
          text: `High surface brightness (${apparentMag != null ? apparentMag + " mag" : "radiant"}) readily cuts through city light dome and skyglow.`,
        };
      } else if (category === "Moon") {
        lpNotice = {
          tone: "favorable",
          label: `Bortle ${bortle} Immune`,
          text: `Brilliant lunar radiance unaffected by artificial city lighting.`,
        };
      } else if (category === "Deep Sky") {
        lpNotice = {
          tone: "caution",
          label: `Bortle ${bortle} Skyglow Impact`,
          text: `Urban light dome washes out faint diffuse nebulosity; contrast filters or dark sky sites recommended.`,
        };
      } else if (category === "Meteor Showers") {
        lpNotice = {
          tone: "severe",
          label: `Bortle ${bortle} Skyglow Obscuration`,
          text: `City skyglow masks faint meteors; only brightest fireballs visible.`,
        };
      } else {
        lpNotice = {
          tone: "caution",
          label: `Bortle ${bortle} Urban Site`,
          text: `Requires telescopic aperture to punch through urban skyglow.`,
        };
      }
    } else {
      lpNotice = {
        tone: "optimal",
        label: `Bortle ${bortle} Dark Sky`,
        text: `Dark celestial backdrop ideal for high-contrast viewing.`,
      };
    }

    const limitations = [
      ...(Array.isArray(item.limitations) ? item.limitations : []),
      ...(Array.isArray(detail.limitations) ? detail.limitations : []),
    ];
    if (lpEffect.limitation && !limitations.some((l) => l.includes(`Bortle ${bortle}`))) {
      limitations.push(lpEffect.limitation);
    }

    return {
      id: key,
      rank: item.rank ?? idx + 1,
      name,
      category,
      eventType: item.event_type || detail.event_type || category,
      score: Math.round(score),
      visibilityScore: visScore != null ? Math.round(visScore) : null,
      weatherScore: weatherScore != null ? Math.round(weatherScore) : null,
      preferenceScore: prefScore != null ? Math.round(prefScore) : null,
      apparentMagnitude: apparentMag != null ? Number(apparentMag) : null,
      altitude: altitude != null ? Math.round(Number(altitude)) : null,
      lpNotice,
      bortleClass: bortle,
      qualityLabel:
        item.quality_label ||
        detail.quality_label ||
        (score >= 80 ? "Optimal" : score >= 60 ? "Good" : score >= 40 ? "Fair" : "Poor"),
      explanation:
        item.explanation ||
        detail.explanation ||
        (score >= 80
          ? `High observation value: favorable topocentric elevation and clear atmospheric transparency during peak session pass.`
          : `Observing pass ranked by AstroOS multi-criteria recommendation engine based on current sky mechanics.`),
      windowStart,
      windowEnd,
      durationMinutes,
      limitations,
      observationGuide: guide,
    };
  });

  const schedule =
    data.schedule ||
    data.recommendation?.schedule ||
    data.recommendations?.schedule ||
    [];

  const summary =
    data.recommendation?.summary ||
    data.recommendations?.summary ||
    data.summary ||
    {};

  const environmentalContext =
    data.environmental_context ||
    data.recommendation?.environmental_context ||
    null;

  return {
    rankedItems,
    schedule,
    summary,
    environmentalContext,
    databaseEventsFound: data.database_events_found ?? rankedItems.length,
    scope,
  };
}

export default function Recommendations() {
  const routerLocation = useLocation();
  const navigate = useNavigate();
  const storedLocation = loadObserverLocation();
  const windowDefaults = defaultWindow();

  // Mode: "unified" (Recommended: Live Discovery & Ephemerides) or "database" (Stored Records)
  const [scope, setScope] = useState("unified");

  // Session parameters
  const [latitude, setLatitude] = useState(storedLocation.latitude);
  const [longitude, setLongitude] = useState(storedLocation.longitude);
  const [locationName, setLocationName] = useState(storedLocation.name || "");
  const [startTime, setStartTime] = useState(windowDefaults.start);
  const [endTime, setEndTime] = useState(windowDefaults.end);
  const [duration, setDuration] = useState(180);
  const [goal, setGoal] = useState("general_observation");
  const [categoryFilter, setCategoryFilter] = useState("All Objects");

  // Advanced recommendation weighting preferences
  const [showWeights, setShowWeights] = useState(false);
  const [visibilityWeight, setVisibilityWeight] = useState(0.5);
  const [weatherWeight, setWeatherWeight] = useState(0.3);
  const [preferenceWeight, setPreferenceWeight] = useState(0.2);

  // Results & UI state
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");
  const [expandedTarget, setExpandedTarget] = useState(null);
  const [activeResultCategory, setActiveResultCategory] = useState("All Objects");

  const activeLp = useMemo(
    () => getLightPollution(latitude, longitude, locationName),
    [latitude, longitude, locationName]
  );

  // Auto-fill target passed from other views
  useEffect(() => {
    if (routerLocation.state?.selectedTarget) {
      setGoal("planetary");
    }
    if (routerLocation.state?.category) {
      setCategoryFilter(routerLocation.state.category);
    }
  }, [routerLocation.state]);

  const executeRecommendation = useCallback(
    async (targetScope = scope) => {
      setLoading(true);
      setError("");
      setResults(null);
      setExpandedTarget(null);

      const lat = Number(latitude);
      const lon = Number(longitude);
      const startIso = localInputToIso(startTime);
      const endIso = localInputToIso(endTime);
      const durationNum = Number(duration);

      if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
        setError("Please enter a valid observer latitude between -90 and 90.");
        setLoading(false);
        return;
      }
      if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
        setError("Please enter a valid observer longitude between -180 and 180.");
        setLoading(false);
        return;
      }
      if (!startIso || !endIso || new Date(endIso) <= new Date(startIso)) {
        setError("Observation session end must be later than the start time.");
        setLoading(false);
        return;
      }

      saveObserverLocation({ latitude: lat, longitude: lon, name: locationName });

      try {
        if (targetScope === "database") {
          // Query database recommendations endpoint
          const payload = {
            location: {
              latitude: lat,
              longitude: lon,
              name: "Observer Site",
              timezone: "Asia/Kolkata",
            },
            start_time: startIso,
            end_time: endIso,
            available_duration_minutes: durationNum,
            observation_goal: goal,
            preferences: {
              weights: {
                visibility: Number(visibilityWeight),
                weather: Number(weatherWeight),
                preference: Number(preferenceWeight),
              },
            },
            category:
              categoryFilter !== "All Objects"
                ? categoryFilter.toLowerCase().replace(/\s+/g, "_")
                : null,
          };

          const response = await api.post(
            "/api/v1/recommendations/from-database",
            payload
          );
          const normalized = normalizeRecommendationResult(response.data, "database", activeLp);
          setResults(normalized);
        } else {
          // Unified Astronomical Catalog: Major Planets, Asteroids, Comets & Deep-Sky Discovery
          const planResponse = await predictionService.generateObservationPlan({
            latitude: lat,
            longitude: lon,
            sessionStart: startTime,
            sessionEnd: endTime,
            availableDurationMinutes: durationNum,
            includeBodies: [
              "planets",
              "asteroids",
              "comets",
              "deep_sky",
              "meteor_showers",
              "solar_eclipses",
              "lunar_eclipses",
            ],
            observationGoal: goal,
          });

          const normalized = normalizeRecommendationResult(planResponse, "unified", activeLp);
          setResults(normalized);
        }
      } catch (err) {
        const detail = err.response?.data?.detail || err.message;
        setError(
          typeof detail === "string"
            ? detail
            : "Could not generate catalog recommendations. Check your session timings and backend connection."
        );
      } finally {
        setLoading(false);
      }
    },
    [
      scope,
      latitude,
      longitude,
      locationName,
      activeLp,
      startTime,
      endTime,
      duration,
      goal,
      categoryFilter,
      visibilityWeight,
      weatherWeight,
      preferenceWeight,
    ]
  );

  // Auto-run recommendations on first load
  useEffect(() => {
    executeRecommendation("unified");
  }, []);

  // Filter returned results by category pill
  const filteredRankedItems = useMemo(() => {
    if (!results?.rankedItems) return [];
    if (activeResultCategory === "All Objects") return results.rankedItems;

    return results.rankedItems.filter(
      (item) => item.category.toLowerCase() === activeResultCategory.toLowerCase()
    );
  }, [results, activeResultCategory]);

  const topItem = results?.rankedItems?.[0];
  const env = results?.environmentalContext;

  return (
    <div className="page-content recommendations-page">
      {/* Hero Header */}
      <section className="explore-hero planner-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">
            <span className="live-dot" /> MULTI-CRITERIA SCORING & CATALOG RECOMMENDATION ENGINE
          </div>

          <h1>Catalog <span>recommendations.</span></h1>

          <p>
            Ranked astronomical opportunities tailored to your observing goals, local coordinates,
            and live atmospheric transparency. Evaluates solar-system bodies, deep-sky highlights,
            and database records using AstroOS multi-criteria intelligence.
          </p>
        </div>

        <BrandLogo size="panel" />
      </section>

      {/* Scope Selector: Unified Astronomical Catalog vs Stored Database */}
      <section className="panel planner-config-panel">
        <div className="panel-header">
          <div>
            <div className="eyebrow">CATALOG RECOMMENDATION SCOPE</div>
            <h3>Configure observation parameters & goals</h3>
          </div>
          <span className="panel-tag">ASTROOS INTELLIGENCE</span>
        </div>

        <div className="rec-scope-selector" role="radiogroup" aria-label="Recommendation Source Scope">
          <button
            type="button"
            className={`rec-scope-btn ${scope === "unified" ? "active" : ""}`}
            onClick={() => setScope("unified")}
          >
            <strong>
              <Sparkles size={14} className="text-accent" /> Unified Astronomical Catalog
            </strong>
            <span>
              Live ephemeris & discovery for major planets, comets, asteroids, Messier deep-sky objects, and eclipses.
            </span>
          </button>

          <button
            type="button"
            className={`rec-scope-btn ${scope === "database" ? "active" : ""}`}
            onClick={() => setScope("database")}
          >
            <strong>
              <Layers size={14} className="text-gold" /> Stored Database Records
            </strong>
            <span>
              Evaluates records stored in the AstroOS celestial_events database matching your session window.
            </span>
          </button>
        </div>

        {/* Query Form */}
        <form
          className="planner-form"
          onSubmit={(e) => {
            e.preventDefault();
            executeRecommendation(scope);
          }}
        >
          <div className="planner-grid">
            <LocationPicker
              latitude={latitude}
              longitude={longitude}
              locationName={locationName}
              onChange={({ latitude: newLat, longitude: newLon, name }) => {
                setLatitude(newLat);
                setLongitude(newLon);
                if (name) setLocationName(name);
              }}
            />

            <label>
              Session start
              <input
                type="datetime-local"
                required
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
              />
            </label>

            <label>
              Session end
              <input
                type="datetime-local"
                required
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
              />
            </label>

            <label>
              Available duration (min)
              <input
                type="number"
                min="15"
                max="1440"
                required
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
              />
            </label>

            <label>
              Observing goal
              <select value={goal} onChange={(e) => setGoal(e.target.value)}>
                {GOAL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="span-2">
              Focus category
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
              >
                {CATEGORY_FILTER_OPTIONS.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {/* Advanced Weighting Preferences Toggle */}
          <div style={{ marginTop: "12px" }}>
            <button
              type="button"
              className="rec-weights-toggle-btn"
              onClick={() => setShowWeights(!showWeights)}
            >
              <SlidersHorizontal size={14} />
              <span>
                {showWeights
                  ? "Hide Advanced Recommendation Weights"
                  : "Customize Recommendation Weights (Visibility · Weather · Goal)"}
              </span>
            </button>

            {showWeights && (
              <div className="rec-weights-panel">
                <div className="rec-weight-row">
                  <div className="rec-weight-label">
                    <span>Astronomical Visibility Weight</span>
                    <small>Prioritizes elevation altitude, dark culmination, and apparent brightness</small>
                  </div>
                  <div className="rec-weight-slider-group">
                    <input
                      type="range"
                      min="0.1"
                      max="1.0"
                      step="0.05"
                      value={visibilityWeight}
                      onChange={(e) => setVisibilityWeight(e.target.value)}
                    />
                    <span className="rec-weight-val">
                      {Math.round(visibilityWeight * 100)}%
                    </span>
                  </div>
                </div>

                <div className="rec-weight-row">
                  <div className="rec-weight-label">
                    <span>Atmospheric Weather Weight</span>
                    <small>Penalizes cloud obscuration, relative humidity, and wind scintillation</small>
                  </div>
                  <div className="rec-weight-slider-group">
                    <input
                      type="range"
                      min="0.1"
                      max="1.0"
                      step="0.05"
                      value={weatherWeight}
                      onChange={(e) => setWeatherWeight(e.target.value)}
                    />
                    <span className="rec-weight-val">
                      {Math.round(weatherWeight * 100)}%
                    </span>
                  </div>
                </div>

                <div className="rec-weight-row">
                  <div className="rec-weight-label">
                    <span>Observing Goal Alignment</span>
                    <small>Weights celestial objects matching your chosen observing objective</small>
                  </div>
                  <div className="rec-weight-slider-group">
                    <input
                      type="range"
                      min="0.1"
                      max="1.0"
                      step="0.05"
                      value={preferenceWeight}
                      onChange={(e) => setPreferenceWeight(e.target.value)}
                    />
                    <span className="rec-weight-val">
                      {Math.round(preferenceWeight * 100)}%
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="inline-alert" style={{ marginTop: "14px" }}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            className="login-submit planner-submit"
            style={{ marginTop: "16px" }}
            disabled={loading}
          >
            {loading ? (
              <>
                <LoaderCircle className="loading-spinner" size={16} />
                <span>Computing catalog recommendations...</span>
              </>
            ) : (
              <>
                <Sparkles size={16} />
                <span>Compute Catalog Recommendations</span>
              </>
            )}
          </button>
        </form>
      </section>

      {/* Summary KPI Overview Cards */}
      {results && (
        <section className="metrics-grid">
          <div className="metric-card">
            <div className="metric-top">
              <div className="metric-icon"><Telescope size={18} /></div>
              <span className="metric-label">Evaluated targets</span>
            </div>
            <div className="metric-value">{results.rankedItems.length}</div>
            <div className="metric-detail">Assessed candidates</div>
          </div>

          <div className="metric-card">
            <div className="metric-top">
              <div className="metric-icon"><Sparkles size={18} /></div>
              <span className="metric-label">Top recommendation</span>
            </div>
            <div className="metric-value" style={{ color: "#fef08a" }}>
              {topItem ? `${topItem.score}` : "—"}
              {topItem && <span style={{ fontSize: "14px", color: "var(--muted)" }}>/100</span>}
            </div>
            <div className="metric-detail">{topItem?.name || "None in window"}</div>
          </div>

          <div className="metric-card">
            <div className="metric-top">
              <div className="metric-icon"><Clock size={18} /></div>
              <span className="metric-label">Scheduled time</span>
            </div>
            <div className="metric-value">
              {results.schedule.reduce((acc, s) => acc + (s.duration_minutes || 0), 0)}
              <span> min</span>
            </div>
            <div className="metric-detail">of {duration} min allocated</div>
          </div>

          <div className="metric-card">
            <div className="metric-top">
              <div className="metric-icon"><Cloud size={18} /></div>
              <span className="metric-label">Sky transparency</span>
            </div>
            <div className="metric-value metric-value-text">
              {env?.cloud_cover != null ? `${Math.round(env.cloud_cover)}%` : "NOMINAL"}
            </div>
            <div className="metric-detail">
              {env?.bortle_class
                ? `Bortle Class ${env.bortle_class}`
                : `Bortle ${activeLp.bortle_class} (${activeLp.classification.split("(")[0].trim()})`}
            </div>
          </div>
        </section>
      )}

      {/* Results Section */}
      {results && (
        <section className="panel" style={{ marginTop: "20px" }}>
          <div className="panel-header">
            <div>
              <div className="eyebrow">RECOMMENDED OPPORTUNITIES</div>
              <h3>Ranked catalog recommendations</h3>
              <p>
                Scores represent composite evaluation of topocentric elevation, optical contrast,
                and atmospheric weather.
              </p>
            </div>

            {/* Category Filter Pills for Results */}
            <div className="result-category-filter" role="group">
              {["All Objects", "Planets", "Deep Sky", "Moon", "Comets", "Asteroids", "Meteor Showers", "Solar Eclipses", "Lunar Eclipses"].map(
                (cat) => (
                  <button
                    key={cat}
                    type="button"
                    className={`category-chip ${
                      activeResultCategory.toLowerCase() === cat.toLowerCase()
                        ? "selected"
                        : ""
                    }`}
                    onClick={() => setActiveResultCategory(cat)}
                  >
                    {cat}
                  </button>
                )
              )}
            </div>
          </div>

          {/* Empty State with Intelligent Fallback */}
          {filteredRankedItems.length === 0 ? (
            <div className="empty-catalogue" style={{ minHeight: "200px" }}>
              <Telescope size={32} />
              <h3>No matching recommendations for this selection</h3>
              <p>
                {scope === "database"
                  ? "No stored records in the database match your chosen window and category."
                  : "Targets may be below the horizon or obscured during the selected hours."}
              </p>

              {scope === "database" && (
                <div className="rec-fallback-banner">
                  <div className="rec-fallback-content">
                    <Sparkles size={20} />
                    <div>
                      <h4>Switch to Unified Astronomical Catalog</h4>
                      <p>
                        The Unified Catalog automatically evaluates live ephemerides for Jupiter,
                        Saturn, Mars, meteor showers, comets, asteroids, and deep-sky Messier targets for tonight.
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="primary-action"
                    onClick={() => {
                      setScope("unified");
                      executeRecommendation("unified");
                    }}
                  >
                    <Sparkles size={14} /> Recommend from Unified Catalog
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              {activeLp.bortle_class >= 6 && (
                <div className="urban-intelligence-banner" style={{ marginBottom: "16px" }}>
                  <div className="urban-banner-icon">
                    <Sparkles size={20} className="text-gold" />
                  </div>
                  <div className="urban-banner-body">
                    <h4>Urban Observing Intelligence · {activeLp.zone || "Urban Sector"} (Bortle {activeLp.bortle_class})</h4>
                    <p>
                      In high light-pollution regions, <strong>Solar System Planets (Jupiter, Mars, Saturn, Venus)</strong> and the <strong>Moon</strong> deliver optimal visibility scores because their extreme surface brightness (e.g. Jupiter at -2.8 mag, Mars at -1.2 mag) penetrates city light domes without loss of planetary detail. Conversely, faint diffuse nebulae, distant galaxies, and meteor showers suffer background skyglow wash-out and receive adjusted contrast feasibility ratings.
                    </p>
                  </div>
                </div>
              )}

              <div className="ranked-events-grid">
                {filteredRankedItems.map((item) => {
                  const guide = item.observationGuide;
                  const isExpanded = expandedTarget === item.id;

                  return (
                    <article className="ranked-event-card" key={item.id}>
                      {/* Header: Rank + Name + Category + Score */}
                      <div className="event-card-header">
                        <div className="event-rank-pill">#{item.rank}</div>
                        <div className="event-title-group">
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <div
                              style={{
                                width: "28px",
                                height: "28px",
                                borderRadius: "50%",
                                overflow: "hidden",
                                flexShrink: 0,
                                backgroundImage: `url(${getCelestialImage(item.name, item.category).url})`,
                                backgroundSize: "cover",
                                backgroundPosition: "center",
                                border: `1px solid ${getCelestialImage(item.name, item.category).accent || "rgba(255,255,255,0.2)"}`,
                              }}
                              title={item.name}
                            />
                            <h4>{item.name}</h4>
                          </div>
                          <div style={{ display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" }}>
                            <span className="event-category-badge">{item.category}</span>
                            <span
                              className={`equipment-badge badge-${guide?.iconType}`}
                              title={`Recommended Optical Aid: ${guide?.equipmentDetail}`}
                            >
                              {guide?.iconType === "eye" && <Eye size={10} />}
                              {guide?.iconType === "binoculars" && <Binoculars size={10} />}
                              {guide?.iconType === "telescope" && <Telescope size={10} />}
                              {guide?.iconType === "sun" && <Sun size={10} />}
                              {guide?.iconType === "camera" && <Camera size={10} />}
                              <span>{guide?.badge}</span>
                            </span>
                            {item.lpNotice && (
                              <span className={`rec-lp-tag tag-${item.lpNotice.tone}`} title={item.lpNotice.text}>
                                <Sparkles size={10} />
                                <span>{item.lpNotice.label}</span>
                              </span>
                            )}
                          </div>
                        </div>

                        <RecScorePill score={item.score} label="Overall Score" />
                      </div>

                      {/* Score Breakdown Pills */}
                      <div className="rec-score-breakdown">
                        {item.visibilityScore != null && (
                          <div className="breakdown-pill">
                            <Telescope size={12} className="text-accent" />
                            <span>Visibility:</span>
                            <strong>{item.visibilityScore}/100</strong>
                          </div>
                        )}
                        {item.weatherScore != null && (
                          <div className="breakdown-pill">
                            <Cloud size={12} className="text-gold" />
                            <span>Weather:</span>
                            <strong>{item.weatherScore}/100</strong>
                          </div>
                        )}
                        {item.apparentMagnitude != null && (
                          <div className="breakdown-pill">
                            <Eye size={12} className="text-accent" />
                            <span>Mag:</span>
                            <strong>{item.apparentMagnitude > 0 ? `+${item.apparentMagnitude}` : item.apparentMagnitude}</strong>
                          </div>
                        )}
                        {item.altitude != null && (
                          <div className="breakdown-pill">
                            <Compass size={12} className="text-gold" />
                            <span>Alt:</span>
                            <strong>{item.altitude}°</strong>
                          </div>
                        )}
                        {item.preferenceScore != null && (
                          <div className="breakdown-pill">
                            <Sparkles size={12} className="text-accent" />
                            <span>Goal Fit:</span>
                            <strong>{item.preferenceScore}/100</strong>
                          </div>
                        )}
                        <div className="breakdown-pill" style={{ marginLeft: "auto" }}>
                          <Clock size={12} />
                          <span>Pass:</span>
                          <strong>{item.durationMinutes} min</strong>
                        </div>
                      </div>

                      {/* Recommendation Engine Explanation */}
                      {item.explanation && (
                        <div className="rec-explanation-card">
                          <div className="rec-explanation-header">
                            <Sparkles size={12} />
                            <span>Recommendation Engine Analysis</span>
                          </div>
                          <p>{item.explanation}</p>
                          {item.lpNotice && (
                            <div className={`rec-lp-explanation ${item.lpNotice.tone}`} style={{ marginTop: "8px", display: "flex", gap: "6px", alignItems: "center" }}>
                              <Info size={13} style={{ flexShrink: 0 }} />
                              <span><strong>Site Skyglow ({item.bortleClass ? `Bortle ${item.bortleClass}` : "Urban"}):</strong> {item.lpNotice.text}</span>
                            </div>
                          )}
                        </div>
                      )}

                    {/* Optical Equipment Details */}
                    {guide && (
                      <div className="visibility-equipment-guide-panel" style={{ marginTop: "10px" }}>
                        <div className="visibility-gear-grid">
                          <div>
                            <small>RECOMMENDED AID</small>
                            <strong>{guide.equipmentDetail}</strong>
                          </div>
                          <div>
                            <small>MAGNIFICATION</small>
                            <strong>{guide.magnification}</strong>
                          </div>
                          <div>
                            <small>DIFFICULTY</small>
                            <strong>{guide.difficulty}</strong>
                          </div>
                          <div>
                            <small>IDEAL SKY</small>
                            <strong>{guide.bestSkyCondition}</strong>
                          </div>
                        </div>

                        {guide.accessories?.length > 0 && (
                          <div className="visibility-accessories-row" style={{ marginTop: "8px" }}>
                            <SlidersHorizontal size={13} />
                            <span>
                              <strong>Recommended components:</strong>{" "}
                              {guide.accessories.join(" · ")}
                            </span>
                          </div>
                        )}

                        <p className="visibility-how-to-see" style={{ marginTop: "8px" }}>
                          <strong>How to Observe:</strong> {guide.howToSee}
                        </p>
                      </div>
                    )}

                    {/* Limitations / Notes */}
                    {item.limitations?.length > 0 && (
                      <div className="limitations-box" style={{ marginTop: "8px" }}>
                        <div className="limitations-title">
                          <Info size={13} /> Evaluation factors & notes:
                        </div>
                        <ul className="limitations-list">
                          {item.limitations.map((lim, i) => (
                            <li key={i}>{lim}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Action Shortcuts */}
                    <div className="rec-card-actions">
                      <button
                        type="button"
                        className="rec-action-chip primary"
                        onClick={() =>
                          navigate("/planner", {
                            state: { selectedTarget: item.name },
                          })
                        }
                      >
                        <CalendarDays size={13} /> Plan Session
                      </button>

                      <button
                        type="button"
                        className="rec-action-chip"
                        onClick={() =>
                          navigate("/visibility", {
                            state: {
                              selectedTarget: item.name,
                              selectedEventId: item.id,
                            },
                          })
                        }
                      >
                        <Eye size={13} /> Assess Visibility
                      </button>

                      <button
                        type="button"
                        className="rec-action-chip"
                        onClick={() =>
                          navigate("/explore", {
                            state: { search: item.name },
                          })
                        }
                      >
                        <Compass size={13} /> Explore Target
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
            </>
          )}
        </section>
      )}

      {/* Session Observation Schedule Panel */}
      {results?.schedule?.length > 0 && (
        <section className="panel schedule-panel" style={{ marginTop: "20px" }}>
          <div className="panel-header">
            <div>
              <div className="eyebrow">OPTIMIZED TIMELINE</div>
              <h3>Recommended observation session timeline</h3>
              <p>Chronologically ordered schedule maximizing observation value within session constraints.</p>
            </div>
          </div>

          <div className="result-table">
            {results.schedule.map((item, index) => {
              const schedGuide = getObservationGuide(item.name, item.category);
              return (
                <article className="result-row" key={item.event_id || `sched-${index}`}>
                  <div className="result-rank">
                    <CheckCircle2 size={16} className="text-emerald" />
                  </div>
                  <div>
                    <strong>{item.name}</strong>
                    <span>{item.explanation || "Scheduled by AstroOS optimizer"}</span>
                    <span
                      className={`equipment-badge badge-${schedGuide.iconType}`}
                      style={{ marginTop: "4px", width: "fit-content" }}
                    >
                      {schedGuide.iconType === "eye" && <Eye size={10} />}
                      {schedGuide.iconType === "binoculars" && <Binoculars size={10} />}
                      {schedGuide.iconType === "telescope" && <Telescope size={10} />}
                      {schedGuide.iconType === "sun" && <Sun size={10} />}
                      {schedGuide.iconType === "camera" && <Camera size={10} />}
                      <span>{schedGuide.badge}</span>
                    </span>
                  </div>
                  <div>
                    <small>Start</small>
                    <strong>{formatDateTime(item.scheduled_start)}</strong>
                  </div>
                  <div>
                    <small>End</small>
                    <strong>{formatDateTime(item.scheduled_end)}</strong>
                  </div>
                  <div>
                    <small>Duration</small>
                    <strong>{item.duration_minutes ?? "—"} min</strong>
                  </div>
                  <div>
                    <small>Score</small>
                    <RecScorePill score={item.recommendation_score} label="Score" />
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
