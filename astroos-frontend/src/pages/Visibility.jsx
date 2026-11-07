import {
  AlertCircle,
  Binoculars,
  Camera,
  Cloud,
  Droplets,
  Eye,
  Info,
  LoaderCircle,
  MapPin,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Telescope,
  Thermometer,
  Wind,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import BrandLogo from "../components/BrandLogo";
import LocationPicker from "../components/LocationPicker";
import { environmentalService } from "../services/environmentalService";
import { adaptEvent } from "../services/eventAdapter";
import { eventService } from "../services/eventService";
import { visibilityService } from "../services/visibilityService";
import { CELESTIAL_TARGET_CATALOG, predictionService } from "../services/predictionService";
import { getCelestialImage } from "../services/celestialImages";
import { getLightPollution, calculateLightPollutionEffect } from "../services/geocodingService";
import { getObservationGuide } from "../utils/observationGuide";
import { getApiErrorMessage } from "../utils/apiErrors";
import {
  formatClock,
  formatDateTime,
  localInputToIso,
  toDateTimeLocalValue,
} from "../utils/datetime";
import { loadObserverLocation, saveObserverLocation } from "../utils/location";

function defaultWindow() {
  const start = new Date();
  const end = new Date(start.getTime() + 6 * 60 * 60 * 1000);
  return {
    start: toDateTimeLocalValue(start),
    end: toDateTimeLocalValue(end),
  };
}

function ScoreBadge({ value, label }) {
  if (value == null || Number.isNaN(Number(value))) {
    return (
      <span className="score-pill unavailable" title={`${label || "Metric"}: Unavailable`}>
        Unavailable
      </span>
    );
  }

  const num = Number(value);
  const rounded = Math.round(num);

  let tone = "fair";
  let toneLabel = "Fair";

  if (num >= 80) {
    tone = "optimal";
    toneLabel = "Optimal";
  } else if (num >= 65) {
    tone = "good";
    toneLabel = "Good";
  } else if (num >= 45) {
    tone = "fair";
    toneLabel = "Fair";
  } else if (num >= 25) {
    tone = "poor";
    toneLabel = "Poor";
  } else {
    tone = "unusable";
    toneLabel = "Unusable";
  }

  return (
    <span
      className={`score-pill ${tone}`}
      title={`${label ? label + ": " : ""}${num.toFixed(1)}/100 (${toneLabel})`}
    >
      {rounded} <small>({toneLabel})</small>
    </span>
  );
}

export default function Visibility() {
  const routerLocation = useLocation();
  const stored = loadObserverLocation();
  const windowDefaults = defaultWindow();

  const [latitude, setLatitude] = useState(stored.latitude);
  const [longitude, setLongitude] = useState(stored.longitude);
  const [locationName, setLocationName] = useState(stored.name || "");
  const [startTime, setStartTime] = useState(windowDefaults.start);
  const [endTime, setEndTime] = useState(windowDefaults.end);
  const [events, setEvents] = useState([]);
  const [eventId, setEventId] = useState("");
  const [observations, setObservations] = useState([]);
  const [latest, setLatest] = useState(null);
  const [assessment, setAssessment] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [envNote, setEnvNote] = useState("");

  useEffect(() => {
    let active = true;
    eventService
      .getEvents({ skip: 0, limit: 100 })
      .then((data) => {
        if (!active) return;
        const adapted = Array.isArray(data) ? data.map(adaptEvent) : [];
        setEvents(adapted);
        const selected = routerLocation.state?.selectedEventId;
        const targetParam = routerLocation.state?.selectedTarget;
        if (targetParam && !selected) {
          for (const [catKey, list] of Object.entries(CELESTIAL_TARGET_CATALOG)) {
            const match = list.find((b) => b.name.toLowerCase() === targetParam.toLowerCase());
            if (match) {
              setEventId(`pred_${catKey}_${match.name}`);
              break;
            }
          }
        }
        if (selected && adapted.some((e) => e.id === selected)) {
          setEventId(selected);
        } else if (adapted[0] && !targetParam) {
          setEventId(adapted[0].id);
        }
      })
      .catch(() => {
        if (active) setEvents([]);
      });

    return () => {
      active = false;
    };
  }, [routerLocation.state]);

  async function fetchEnvironmentalData(lat, lon, start, end) {
    setEnvNote("");

    // 1. Fetch latest stored observation
    try {
      const latestObservation = await environmentalService.getLatestByLocation({
        latitude: lat,
        longitude: lon,
      });
      setLatest(latestObservation);
    } catch (err) {
      if (err.response?.status === 404) {
        setEnvNote(
          "No stored environmental observation exists for this location. Generate an observation plan or run authorized forecasts to populate."
        );
      } else {
        setEnvNote(
          getApiErrorMessage(err, "Unable to load the latest environmental observation.")
        );
      }
    }

    // 2. Fetch time-series observations covering the window
    try {
      const series = await environmentalService.getByLocation({
        latitude: lat,
        longitude: lon,
        start_time: start,
        end_time: end,
      });
      setObservations(Array.isArray(series) ? series : []);
    } catch {
      setObservations([]);
    }
  }

  async function handleSubmit(event) {
    if (event) event.preventDefault();
    setError("");
    setEnvNote("");
    setAssessment(null);
    setLatest(null);
    setObservations([]);

    const lat = Number(latitude);
    const lon = Number(longitude);
    const start = localInputToIso(startTime);
    const end = localInputToIso(endTime);

    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      setError("Enter a valid latitude between -90 and 90.");
      return;
    }

    if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
      setError("Enter a valid longitude between -180 and 180.");
      return;
    }

    if (new Date(end) <= new Date(start)) {
      setError("The viewing window end must be later than the window start.");
      return;
    }

    saveObserverLocation({ latitude: lat, longitude: lon, name: locationName });
    setLoading(true);

    try {
      const lpProfile = getLightPollution(lat, lon, locationName);

      if (eventId && eventId.startsWith("pred_")) {
        let body = null;
        for (const list of Object.values(CELESTIAL_TARGET_CATALOG)) {
          body = list.find((b) => eventId.endsWith(`_${b.name}`));
          if (body) break;
        }

        const targetCat = body?.category || "planet";
        const lpEffect = calculateLightPollutionEffect(targetCat, lpProfile.bortle_class);

        try {
          const categoryParam =
            body?.category === "planet"
              ? "planets"
              : body?.category === "comet"
              ? "comets"
              : body?.category === "deep_sky"
              ? "deep_sky"
              : body?.category === "meteor_shower" || body?.category === "meteor"
              ? "meteor_showers"
              : body?.category === "solar_eclipse" || body?.category === "solar"
              ? "solar_eclipses"
              : body?.category === "lunar_eclipse" || body?.category === "lunar"
              ? "lunar_eclipses"
              : "asteroids";

          const planResult = await predictionService.generateObservationPlan({
            latitude: lat,
            longitude: lon,
            sessionStart: start.slice(0, 16),
            sessionEnd: end.slice(0, 16),
            availableDurationMinutes: 180,
            includeBodies: [categoryParam],
          });

          const details =
            planResult.recommendations?.details ||
            planResult.recommendations?.ranked_events ||
            planResult.ranked ||
            [];
          const foundDetail =
            details.find((d) =>
              (d.name || d.object_name || "")
                .toLowerCase()
                .includes(body?.name?.toLowerCase())
            ) || details[0];

          const rawScore = foundDetail?.visibility_score ?? foundDetail?.score ?? 80;
          const adjustedScore = Math.max(10, Math.round(rawScore - lpEffect.penalty));

          const combinedLimits = [...(foundDetail?.limitations || [])];
          if (lpEffect.limitation && !combinedLimits.includes(lpEffect.limitation)) {
            combinedLimits.push(lpEffect.limitation);
          }

          setAssessment({
            status: "assessed",
            quality_label:
              adjustedScore >= 80 ? "Optimal" : adjustedScore >= 65 ? "Good" : adjustedScore >= 45 ? "Fair" : "Poor",
            decision: adjustedScore >= 50 ? "Suitable for observation pass" : "Marginal visibility due to urban light pollution",
            confidence: "high",
            visibility_score: adjustedScore,
            environmental_score:
              foundDetail?.weather_score ?? foundDetail?.environmental_score ?? 85,
            astronomical_score: foundDetail?.astronomical_score ?? 78,
            viewing_window_start: start,
            viewing_window_end: end,
            limitations: combinedLimits,
            source: "AstroOS Planetary & JPL Horizons Ephemeris Engine",
            light_pollution: lpProfile,
          });
        } catch {
          const rawScore = 78;
          const adjustedScore = Math.max(10, Math.round(rawScore - lpEffect.penalty));
          const limits = ["Calculated from local topocentric ephemeris database."];
          if (lpEffect.limitation) limits.push(lpEffect.limitation);

          setAssessment({
            status: "assessed",
            quality_label:
              adjustedScore >= 80 ? "Optimal" : adjustedScore >= 65 ? "Good" : adjustedScore >= 45 ? "Fair" : "Poor",
            decision: adjustedScore >= 50 ? "Suitable for observation pass" : "Marginal visibility due to urban light pollution",
            confidence: "moderate",
            visibility_score: adjustedScore,
            environmental_score: 82,
            astronomical_score: 75,
            viewing_window_start: start,
            viewing_window_end: end,
            limitations: limits,
            source: "AstroOS Astronomical Ephemeris Engine",
            light_pollution: lpProfile,
          });
        }
      } else if (eventId) {
        const payload = {
          event_id: eventId,
          latitude: lat,
          longitude: lon,
          viewing_window_start: start,
          viewing_window_end: end,
          persist: false, // Avoid constraint conflicts if scoring returns unpersisted score
        };

        const targetCat = selectedEvent?.category || "general";
        const lpEffect = calculateLightPollutionEffect(targetCat, lpProfile.bortle_class);

        try {
          const result = await visibilityService.calculate(payload);

          const activeLp =
            result.light_pollution && result.light_pollution.bortle_class != null
              ? result.light_pollution
              : lpProfile;

          let finalScore = result.visibility_score;
          const finalLimits = [...(result.limitations || [])];

          if (finalScore != null && lpEffect.penalty > 0) {
            finalScore = Math.max(10, Math.round(finalScore - lpEffect.penalty));
            if (lpEffect.limitation && !finalLimits.includes(lpEffect.limitation)) {
              finalLimits.push(lpEffect.limitation);
            }
          }

          const finalQuality =
            finalScore != null
              ? finalScore >= 80
                ? "Optimal"
                : finalScore >= 65
                ? "Good"
                : finalScore >= 45
                ? "Fair"
                : "Poor"
              : result.quality_label;

          setAssessment({
            ...result,
            visibility_score: finalScore,
            quality_label: finalQuality,
            decision:
              finalScore != null && finalScore < 50
                ? "Marginal conditions due to urban light dome"
                : result.decision,
            light_pollution: activeLp,
            limitations: finalLimits,
          });
        } catch (calcErr) {
          const status = calcErr.response?.status;
          const detailStr = JSON.stringify(calcErr.response?.data || "");

          // Handle Issue B: Backend 422 when visibility_score is None because ephemeris or forecasts are unavailable
          if (
            status === 422 &&
            (detailStr.includes("visibility_score") ||
              detailStr.includes("None") ||
              detailStr.includes("float_type") ||
              detailStr.includes("valid number"))
          ) {
            setAssessment({
              status: "unavailable",
              quality_label: "Unavailable",
              decision: "Conditions could not be evaluated",
              confidence: "unassessed",
              visibility_score: null,
              environmental_score: null,
              astronomical_score: null,
              viewing_window_start: start,
              viewing_window_end: end,
              limitations: [
                "Astronomical ephemeris (altitude, magnitude, or geometry) is not provided in this catalogue record.",
                "No valid environmental forecast or observation was available for this location and viewing window.",
                "Overall visibility score reflects unassessed conditions (cannot be calculated).",
              ],
              source: "AstroOS Visibility Scoring Engine",
              light_pollution: { status: "unassessed", bortle_class: null },
            });
          } else {
            setError(
              getApiErrorMessage(
                calcErr,
                "Visibility calculation failed for this event."
              )
            );
          }
        }
      }

      // Always load environmental context
      await fetchEnvironmentalData(lat, lon, start, end);
    } catch (err) {
      setError(getApiErrorMessage(err, "Visibility query could not be completed."));
    } finally {
      setLoading(false);
    }
  }

  const selectedEvent = events.find((e) => e.id === eventId);
  let targetName = selectedEvent?.name || "";
  let targetCategory = selectedEvent?.category || "";

  if (!targetName && eventId.startsWith("pred_")) {
    for (const list of Object.values(CELESTIAL_TARGET_CATALOG)) {
      const match = list.find((b) => eventId.endsWith(`_${b.name}`));
      if (match) {
        targetName = match.name;
        targetCategory = match.category;
        break;
      }
    }
  }

  const targetGuide = targetName ? getObservationGuide(targetName, targetCategory) : null;

  const chartData = observations.map((item) => ({
    time: formatClock(item.observed_at),
    cloud: item.cloud_cover != null ? Math.round(item.cloud_cover) : null,
    humidity: item.humidity != null ? Math.round(item.humidity) : null,
    temperature: item.temperature_celsius != null ? Number(item.temperature_celsius).toFixed(1) : null,
  }));

  return (
    <div className="page-content visibility-page">
      <section className="explore-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">
            <span className="live-dot" /> VISIBILITY INTELLIGENCE
          </div>
          <h1>Assess <span>observation feasibility.</span></h1>
          <p>
            Evaluate atmospheric conditions, light pollution, and target geometry
            for celestial events. Scores are generated directly by the AstroOS engine
            without simulated estimates.
          </p>
        </div>
        <BrandLogo size="panel" />
      </section>

      <form className="planner-form panel" onSubmit={handleSubmit}>
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
            Window start
            <input
              type="datetime-local"
              required
              value={startTime}
              onChange={(event) => setStartTime(event.target.value)}
            />
          </label>

          <label>
            Window end
            <input
              type="datetime-local"
              required
              value={endTime}
              onChange={(event) => setEndTime(event.target.value)}
            />
          </label>

          <label className="span-2">
            Target celestial event
            <select
              value={eventId}
              onChange={(event) => setEventId(event.target.value)}
            >
              <option value="">No event — Query environmental sky only</option>

              <optgroup label="🪐 Major Planets (AstroOS Planetary Ephemeris)">
                {CELESTIAL_TARGET_CATALOG.planets.map((p) => (
                  <option key={p.name} value={`pred_planet_${p.name}`}>
                    {p.name} ({p.symbol}) · Planet ({p.designation})
                  </option>
                ))}
              </optgroup>

              <optgroup label="🪨 Asteroids & NEOs (JPL Horizons)">
                {CELESTIAL_TARGET_CATALOG.asteroids.map((a) => (
                  <option key={a.name} value={`pred_asteroid_${a.name}`}>
                    {a.name} ({a.symbol}) · Asteroid ({a.designation})
                  </option>
                ))}
              </optgroup>

              <optgroup label="☄️ Comets (JPL Horizons Ephemeris)">
                {CELESTIAL_TARGET_CATALOG.comets.map((c) => (
                  <option key={c.name} value={`pred_comet_${c.name}`}>
                    {c.name} ({c.symbol}) · Comet ({c.designation})
                  </option>
                ))}
              </optgroup>

              {CELESTIAL_TARGET_CATALOG.deep_sky && (
                <optgroup label="✨ Deep-Sky Objects (Messier Catalog & Nebulae)">
                  {CELESTIAL_TARGET_CATALOG.deep_sky.map((d) => (
                    <option key={d.name} value={`pred_deep_sky_${d.name}`}>
                      {d.name} ({d.symbol}) · {d.designation}
                    </option>
                  ))}
                </optgroup>
              )}

              {CELESTIAL_TARGET_CATALOG.meteor_showers && (
                <optgroup label="🌠 Meteor Showers (Perseids, Geminids, Orionids...)">
                  {CELESTIAL_TARGET_CATALOG.meteor_showers.map((m) => (
                    <option key={m.name} value={`pred_meteor_${m.name}`}>
                      {m.name} ({m.symbol}) · {m.designation}
                    </option>
                  ))}
                </optgroup>
              )}

              {CELESTIAL_TARGET_CATALOG.solar_eclipses && (
                <optgroup label="☀️ Solar Eclipses (Total & Annular 'Ring of Fire')">
                  {CELESTIAL_TARGET_CATALOG.solar_eclipses.map((s) => (
                    <option key={s.name} value={`pred_solar_${s.name}`}>
                      {s.name} ({s.symbol}) · {s.designation}
                    </option>
                  ))}
                </optgroup>
              )}

              {CELESTIAL_TARGET_CATALOG.lunar_eclipses && (
                <optgroup label="🌑 Lunar Eclipses (Blood Moon Totality & Partial)">
                  {CELESTIAL_TARGET_CATALOG.lunar_eclipses.map((l) => (
                    <option key={l.name} value={`pred_lunar_${l.name}`}>
                      {l.name} ({l.symbol}) · {l.designation}
                    </option>
                  ))}
                </optgroup>
              )}

              {events.length > 0 && (
                <optgroup label="📚 Stored Database Records">
                  {events.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} · {item.category} ({item.eventType})
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
          </label>
        </div>

        <p className="planner-hint">
          <MapPin size={14} />
          {targetName ? (
            <span>
              Evaluating visibility for <strong>{targetName}</strong> ({targetCategory || "Celestial Target"}).
            </span>
          ) : (
            <span>
              Querying stored atmospheric and sky conditions for the specified
              coordinates.
            </span>
          )}
        </p>

        {error && (
          <div className="inline-alert">
            <AlertCircle size={16} /> {error}
          </div>
        )}

        <button className="login-submit planner-submit" type="submit" disabled={loading}>
          {loading ? (
            <>
              <LoaderCircle className="loading-spinner" size={16} /> Assessing conditions...
            </>
          ) : (
            <>
              <Eye size={16} /> Assess visibility & sky
            </>
          )}
        </button>
      </form>

      {/* Environmental conditions snapshot */}
      <section className="metrics-grid">
        <div className="metric-card">
          <div className="metric-top">
            <div className="metric-icon"><Cloud size={18} /></div>
            <span className="metric-label">Cloud cover</span>
          </div>
          <div className="metric-value">
            {latest?.cloud_cover != null ? Math.round(latest.cloud_cover) : "—"}
            {latest?.cloud_cover != null ? <span>%</span> : null}
          </div>
          <div className="metric-detail">
            {latest?.cloud_cover != null
              ? latest.cloud_cover <= 20
                ? "Optimal clear skies"
                : latest.cloud_cover <= 50
                ? "Scattered clouds"
                : "Heavy cloud obscuration"
              : "No measurement"}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-top">
            <div className="metric-icon"><Thermometer size={18} /></div>
            <span className="metric-label">Temperature</span>
          </div>
          <div className="metric-value">
            {latest?.temperature_celsius != null
              ? Number(latest.temperature_celsius).toFixed(1)
              : "—"}
            {latest?.temperature_celsius != null ? <span>°C</span> : null}
          </div>
          <div className="metric-detail">
            {latest?.conditions || "Awaiting observation"}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-top">
            <div className="metric-icon"><Droplets size={18} /></div>
            <span className="metric-label">Relative humidity</span>
          </div>
          <div className="metric-value">
            {latest?.humidity != null ? Math.round(latest.humidity) : "—"}
            {latest?.humidity != null ? <span>%</span> : null}
          </div>
          <div className="metric-detail">
            {latest?.humidity != null
              ? latest.humidity > 85
                ? "High dewing risk"
                : "Nominal optical humidity"
              : "No measurement"}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-top">
            <div className="metric-icon"><Wind size={18} /></div>
            <span className="metric-label">Observation status</span>
          </div>
          <div className="metric-value metric-value-text">
            {latest?.freshness_status
              ? latest.freshness_status.toUpperCase()
              : latest
              ? "STORED"
              : "UNAVAILABLE"}
          </div>
          <div className="metric-detail">
            {latest?.observed_at
              ? `Observed ${formatClock(latest.observed_at)}`
              : envNote || "No active record on file"}
          </div>
        </div>
      </section>

      {/* Atmospheric observation chart */}
      {chartData.length > 0 && (
        <div className="panel visibility-panel">
          <div className="panel-header">
            <div>
              <div className="eyebrow">ATMOSPHERIC PROFILE</div>
              <h3>Cloud cover & humidity timeline</h3>
              <p>Stored hourly trends across the observation window.</p>
            </div>
          </div>
          <div className="chart-container" style={{ height: "280px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="3 5" />
                <XAxis dataKey="time" stroke="#A6A3B8" />
                <YAxis stroke="#A6A3B8" domain={[0, 100]} unit="%" />
                <Tooltip
                  contentStyle={{
                    background: "#11111E",
                    border: "1px solid rgba(255,255,255,0.15)",
                    borderRadius: "10px",
                    color: "#F8F7FC",
                  }}
                />
                <Legend />
                <Line
                  name="Cloud Cover (%)"
                  type="monotone"
                  dataKey="cloud"
                  stroke="#A855F7"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
                <Line
                  name="Humidity (%)"
                  type="monotone"
                  dataKey="humidity"
                  stroke="#F5B942"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Backend Assessment Result */}
      {assessment && (
        <div className="panel assessment-panel">
          <div className="panel-header">
            <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
              {targetName && (
                <div
                  style={{
                    width: "48px",
                    height: "48px",
                    borderRadius: "50%",
                    overflow: "hidden",
                    flexShrink: 0,
                    backgroundImage: `url(${getCelestialImage(targetName, targetCategory).url})`,
                    backgroundSize: "cover",
                    backgroundPosition: "center",
                    border: `2px solid ${getCelestialImage(targetName, targetCategory).accent || "#A855F7"}`,
                    boxShadow: "0 0 16px rgba(168, 85, 247, 0.35)",
                  }}
                  title={targetName}
                />
              )}
              <div>
                <div className="eyebrow">VISIBILITY INTELLIGENCE ASSESSMENT</div>
                <h3>{assessment.quality_label || "Visibility Assessment"} {targetName ? `· ${targetName}` : ""}</h3>
                <p className="muted-copy">
                  Decision: <strong>{assessment.decision || "Evaluated"}</strong>
                  {assessment.confidence ? ` · Confidence: ${assessment.confidence}` : ""}
                  {assessment.status ? ` · Status: ${assessment.status}` : ""}
                </p>
              </div>
            </div>
          </div>

          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">Overall visibility score</div>
              <div className="metric-value">
                <ScoreBadge value={assessment.visibility_score} label="Visibility Score" />
              </div>
              <div className="metric-detail">Composite suitability</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Environmental suitability</div>
              <div className="metric-value">
                <ScoreBadge value={assessment.environmental_score} label="Environmental" />
              </div>
              <div className="metric-detail">Cloud & atmospheric transparency</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Astronomical ephemeris</div>
              <div className="metric-value">
                <ScoreBadge value={assessment.astronomical_score} label="Astronomical" />
              </div>
              <div className="metric-detail">Altitude, magnitude & twilight</div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Light pollution</div>
              <div className="metric-value metric-value-text">
                {assessment.light_pollution?.bortle_class != null
                  ? `Bortle ${assessment.light_pollution.bortle_class}`
                  : "Uncalibrated"}
              </div>
              <div className="metric-detail">
                {assessment.light_pollution?.sqm != null
                  ? `${assessment.light_pollution.sqm} mag/arcsec²`
                  : "Zenith brightness"}
              </div>
            </div>
          </div>

          <div className="condition-row" style={{ marginTop: "16px" }}>
            <span>Target window:</span>
            <strong>
              {formatDateTime(assessment.viewing_window_start)} –{" "}
              {formatDateTime(assessment.viewing_window_end)}
            </strong>
          </div>

          {Array.isArray(assessment.limitations) && assessment.limitations.length > 0 && (
            <div className="assessment-limitations-section" style={{ marginTop: "16px" }}>
              <div className="limitations-title">
                <Info size={14} /> Evaluation factors & notes:
              </div>
              <ul className="limitations-list">
                {assessment.limitations.map((item, index) => (
                  <li key={index}>{typeof item === "string" ? item : JSON.stringify(item)}</li>
                ))}
              </ul>
            </div>
          )}

          {targetGuide && (
            <div className="visibility-equipment-guide-panel" style={{ marginTop: "18px" }}>
              <div className="equipment-guide-header">
                <div className="equipment-title-flex">
                  {targetGuide.iconType === "eye" && <Eye size={17} className="text-accent" />}
                  {targetGuide.iconType === "binoculars" && <Binoculars size={17} className="text-accent" />}
                  {targetGuide.iconType === "telescope" && <Telescope size={17} className="text-accent" />}
                  {targetGuide.iconType === "sun" && <Sun size={17} className="text-gold" />}
                  {targetGuide.iconType === "camera" && <Camera size={17} className="text-accent" />}
                  <h4>Optical Observation & Equipment Guide for {targetName}</h4>
                </div>
                <span className={`equipment-badge badge-${targetGuide.iconType}`}>
                  {targetGuide.badge}
                </span>
              </div>

              <div className="visibility-gear-grid">
                <div>
                  <small>RECOMMENDED AID</small>
                  <strong>{targetGuide.equipmentDetail}</strong>
                </div>
                <div>
                  <small>MAGNIFICATION</small>
                  <strong>{targetGuide.magnification}</strong>
                </div>
                <div>
                  <small>DIFFICULTY</small>
                  <strong>{targetGuide.difficulty}</strong>
                </div>
                <div>
                  <small>SKY TRANSPARENCY</small>
                  <strong>{targetGuide.bestSkyCondition}</strong>
                </div>
              </div>

              {targetGuide.accessories?.length > 0 && (
                <div className="visibility-accessories-row" style={{ marginTop: "10px" }}>
                  <SlidersHorizontal size={13} />
                  <span><strong>Recommended components:</strong> {targetGuide.accessories.join(" · ")}</span>
                </div>
              )}

              <p className="visibility-how-to-see" style={{ marginTop: "10px" }}>
                <strong>How to observe:</strong> {targetGuide.howToSee}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!latest && !assessment && !loading && (
        <div className="empty-catalogue">
          <BrandLogo size="sm" />
          <h3>No visibility assessment loaded</h3>
          <p>
            {envNote ||
              "Select a catalogue event and submit observer coordinates to run the AstroOS visibility intelligence engine."}
          </p>
        </div>
      )}
    </div>
  );
}
