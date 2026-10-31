import {
  AlertCircle,
  Cloud,
  Droplets,
  Eye,
  Info,
  LoaderCircle,
  MapPin,
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
import { environmentalService } from "../services/environmentalService";
import { adaptEvent } from "../services/eventAdapter";
import { eventService } from "../services/eventService";
import { visibilityService } from "../services/visibilityService";
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
        if (selected && adapted.some((e) => e.id === selected)) {
          setEventId(selected);
        } else if (adapted[0]) {
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

    saveObserverLocation({ latitude: lat, longitude: lon });
    setLoading(true);

    try {
      if (eventId) {
        const payload = {
          event_id: eventId,
          latitude: lat,
          longitude: lon,
          viewing_window_start: start,
          viewing_window_end: end,
          persist: false, // Avoid constraint conflicts if scoring returns unpersisted score
        };

        try {
          const result = await visibilityService.calculate(payload);
          setAssessment(result);
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
          <label>
            Latitude
            <input
              type="number"
              step="0.0001"
              min="-90"
              max="90"
              required
              value={latitude}
              onChange={(event) => setLatitude(event.target.value)}
              placeholder="e.g. 10.5276"
            />
          </label>

          <label>
            Longitude
            <input
              type="number"
              step="0.0001"
              min="-180"
              max="180"
              required
              value={longitude}
              onChange={(event) => setLongitude(event.target.value)}
              placeholder="e.g. 76.2144"
            />
          </label>

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
              {events.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {item.category} ({item.eventType})
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className="planner-hint">
          <MapPin size={14} />
          {selectedEvent ? (
            <span>
              Evaluating visibility for <strong>{selectedEvent.name}</strong> ({selectedEvent.category}).
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
            <div>
              <div className="eyebrow">VISIBILITY INTELLIGENCE ASSESSMENT</div>
              <h3>{assessment.quality_label || "Visibility Assessment"}</h3>
              <p className="muted-copy">
                Decision: <strong>{assessment.decision || "Evaluated"}</strong>
                {assessment.confidence ? ` · Confidence: ${assessment.confidence}` : ""}
                {assessment.status ? ` · Status: ${assessment.status}` : ""}
              </p>
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
