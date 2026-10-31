import {
  AlertCircle,
  Cloud,
  Droplets,
  Eye,
  LoaderCircle,
  Thermometer,
  Wind,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  CartesianGrid,
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
import { formatClock, formatDateTime, localInputToIso, toDateTimeLocalValue } from "../utils/datetime";
import { loadObserverLocation, saveObserverLocation } from "../utils/location";

function defaultWindow() {
  const start = new Date();
  const end = new Date(start.getTime() + 6 * 60 * 60 * 1000);
  return {
    start: toDateTimeLocalValue(start),
    end: toDateTimeLocalValue(end),
  };
}

export default function Visibility() {
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
    eventService
      .getEvents({ skip: 0, limit: 100 })
      .then((data) => {
        const adapted = Array.isArray(data) ? data.map(adaptEvent) : [];
        setEvents(adapted);
        if (adapted[0]) setEventId(adapted[0].id);
      })
      .catch(() => setEvents([]));
  }, []);

  async function loadEnvironment() {
    const lat = Number(latitude);
    const lon = Number(longitude);
    saveObserverLocation({ latitude: lat, longitude: lon });
    setEnvNote("");
    setLatest(null);
    setObservations([]);

    try {
      const latestObservation = await environmentalService.getLatestByLocation({
        latitude: lat,
        longitude: lon,
      });
      setLatest(latestObservation);
    } catch (err) {
      if (err.response?.status === 404) {
        setEnvNote("No stored environmental observation exists for this location.");
      } else {
        setEnvNote(getApiErrorMessage(err, "Unable to load the latest observation."));
      }
    }

    try {
      const series = await environmentalService.getByLocation({
        latitude: lat,
        longitude: lon,
        start_time: localInputToIso(startTime),
        end_time: localInputToIso(endTime),
      });
      setObservations(Array.isArray(series) ? series : []);
    } catch (err) {
      if (!err.response || err.response.status !== 404) {
        setError(getApiErrorMessage(err, "Unable to load environmental observations."));
      }
    }
  }


async function handleSubmit(event) {
  event.preventDefault();
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
    setError("The viewing window end must be after its start.");
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
        persist: true,
      };

      const result = await visibilityService.calculate(payload);
      setAssessment(result);
    }

    // Reload environmental observations after the backend
    // has had an opportunity to fetch and persist forecasts.
    try {
      const latestObservation =
        await environmentalService.getLatestByLocation({
          latitude: lat,
          longitude: lon,
        });

      setLatest(latestObservation);
    } catch (err) {
      if (err.response?.status === 404) {
        setEnvNote("No stored environmental observation exists for this location.");
      } else {
        setEnvNote(
          getApiErrorMessage(err, "Unable to load the latest observation.")
        );
      }
    }

    try {
      const series = await environmentalService.getByLocation({
        latitude: lat,
        longitude: lon,
        start_time: start,
        end_time: end,
      });

      setObservations(Array.isArray(series) ? series : []);
    } catch (err) {
      setError(
        getApiErrorMessage(
          err,
          "Unable to load environmental observations."
        )
      );
    }
  } catch (err) {
    setError(
      getApiErrorMessage(err, "Visibility assessment failed.")
    );
  } finally {
    setLoading(false);
  }
}


  const chartData = observations.map((item) => ({
    time: formatClock(item.observed_at),
    cloud: item.cloud_cover,
    humidity: item.humidity,
    temperature: item.temperature_celsius,
  }));

  return (
    <div className="page-content">
      <section className="explore-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">
            <span className="live-dot" /> VISIBILITY INTELLIGENCE
          </div>
          <h1>Assess <span>observation feasibility.</span></h1>
          <p>
            Query stored environmental observations and calculate a visibility
            assessment for a catalogue event. Scores come from the backend only.
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
              required
              value={latitude}
              onChange={(event) => setLatitude(event.target.value)}
            />
          </label>
          <label>
            Longitude
            <input
              type="number"
              step="0.0001"
              required
              value={longitude}
              onChange={(event) => setLongitude(event.target.value)}
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
            Catalogue event
            <select value={eventId} onChange={(event) => setEventId(event.target.value)}>
              <option value="">No event — environment only</option>
              {events.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {item.category}
                </option>
              ))}
            </select>
          </label>
        </div>

        {error && (
          <div className="inline-alert">
            <AlertCircle size={16} /> {error}
          </div>
        )}

        <button className="login-submit planner-submit" disabled={loading}>
          {loading ? (
            <>
              <LoaderCircle className="loading-spinner" size={16} /> Assessing...
            </>
          ) : (
            <>
              <Eye size={16} /> Assess visibility
            </>
          )}
        </button>
      </form>

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
        </div>
        <div className="metric-card">
          <div className="metric-top">
            <div className="metric-icon"><Droplets size={18} /></div>
            <span className="metric-label">Humidity</span>
          </div>
          <div className="metric-value">
            {latest?.humidity != null ? Math.round(latest.humidity) : "—"}
            {latest?.humidity != null ? <span>%</span> : null}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-top">
            <div className="metric-icon"><Wind size={18} /></div>
            <span className="metric-label">Conditions</span>
          </div>
          <div className="metric-value metric-value-text">
            {latest?.conditions || "Unavailable"}
          </div>
          <div className="metric-detail">
            {latest?.freshness_status || envNote || "Stored observation"}
          </div>
        </div>
      </section>

      {chartData.length > 0 && (
        <div className="panel visibility-panel">
          <div className="panel-header">
            <div>
              <div className="eyebrow">STORED OBSERVATIONS</div>
              <h3>Cloud and humidity over the selected window</h3>
            </div>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="3 5" />
                <XAxis dataKey="time" stroke="#A6A3B8" />
                <YAxis stroke="#A6A3B8" />
                <Tooltip
                  contentStyle={{
                    background: "#11111E",
                    border: "1px solid rgba(255,255,255,0.09)",
                    borderRadius: "10px",
                    color: "#F8F7FC",
                  }}
                />
                <Line type="monotone" dataKey="cloud" stroke="#A855F7" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="humidity" stroke="#F5B942" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {assessment && (
        <div className="panel">
          <div className="eyebrow">BACKEND ASSESSMENT</div>
          <h3>{assessment.quality_label || "Visibility assessment"}</h3>
          <p className="muted-copy">
            Status: {assessment.status} · Decision: {assessment.decision} · Confidence: {assessment.confidence}
          </p>
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">Visibility score</div>
              <div className="metric-value">{assessment.visibility_score ?? "—"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Environmental</div>
              <div className="metric-value">{assessment.environmental_score ?? "—"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Astronomical</div>
              <div className="metric-value">{assessment.astronomical_score ?? "—"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Window</div>
              <div className="metric-detail">
                {formatDateTime(assessment.viewing_window_start)} – {formatDateTime(assessment.viewing_window_end)}
              </div>
            </div>
          </div>
          {Array.isArray(assessment.limitations) && assessment.limitations.length > 0 && (
            <ul className="skipped-list">
              {assessment.limitations.map((item, index) => (
                <li key={index}>{typeof item === "string" ? item : JSON.stringify(item)}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {!latest && !assessment && !loading && (
        <div className="empty-catalogue">
          <BrandLogo size="sm" />
          <h3>No visibility data yet</h3>
          <p>
            {envNote ||
              "Submit a location and window to query stored environmental observations. Forecast persistence is performed by the observation planner and authorized backend services."}
          </p>
        </div>
      )}
    </div>
  );
}
