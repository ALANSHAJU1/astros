import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  ArrowRight,
  CalendarDays,
  Cloud,
  Compass,
  Droplets,
  Eye,
  LoaderCircle,
  Sparkles,
  Telescope,
  Thermometer,
} from "lucide-react";

import BrandLogo from "../components/BrandLogo";
import { useAuth } from "../context/AuthContext";
import { eventService } from "../services/eventService";
import { adaptEvent, formatEventDate } from "../services/eventAdapter";
import { environmentalService } from "../services/environmentalService";
import { CELESTIAL_TARGET_CATALOG } from "../services/predictionService";
import { getCelestialImage } from "../services/celestialImages";
import { getApiErrorMessage } from "../utils/apiErrors";
import { loadObserverLocation } from "../utils/location";

function MetricCard({ icon: Icon, label, value, unit, detail }) {
  return (
    <div className="metric-card">
      <div className="metric-top">
        <div className="metric-icon"><Icon size={19} /></div>
        <span className="metric-label">{label}</span>
      </div>
      <div className="metric-value">
        {value}
        {unit ? <span>{unit}</span> : null}
      </div>
      <div className="metric-detail">{detail}</div>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const location = useMemo(() => loadObserverLocation(), []);

  const [events, setEvents] = useState([]);
  const [environment, setEnvironment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [envNote, setEnvNote] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");
      setEnvNote("");

      try {
        const data = await eventService.getEvents({ skip: 0, limit: 100 });
        if (!cancelled) {
          setEvents(Array.isArray(data) ? data.map(adaptEvent).filter(Boolean) : []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(getApiErrorMessage(err, "Unable to load celestial events."));
        }
      }

      try {
        const latest = await environmentalService.getLatestByLocation(location);
        if (!cancelled) setEnvironment(latest);
      } catch (err) {
        if (!cancelled) {
          if (err.response?.status === 404) {
            setEnvNote(
              "No stored environmental observation exists for the saved observer location. Generate a plan to populate forecast records."
            );
          } else {
            setEnvNote(
              getApiErrorMessage(
                err,
                "Environmental observations are unavailable for this location."
              )
            );
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [location]);

  // Display opportunities: prioritizes database events, falling back to predicted planetary targets
  const displayEvents = useMemo(() => {
    if (events.length > 0) return events.slice(0, 6);

    // Fallback: predictable planets, deep sky objects, asteroids & comets
    const fallback = [
      ...CELESTIAL_TARGET_CATALOG.planets.slice(0, 3),
      ...(CELESTIAL_TARGET_CATALOG.deep_sky ? CELESTIAL_TARGET_CATALOG.deep_sky.slice(0, 2) : []),
      ...CELESTIAL_TARGET_CATALOG.asteroids.slice(0, 1),
      ...CELESTIAL_TARGET_CATALOG.comets.slice(0, 1),
    ].map((b) =>
      adaptEvent({
        id: `pred-${b.name.toLowerCase()}`,
        name: b.name,
        category: b.category,
        designation: b.designation,
        start_time: new Date().toISOString(),
        is_predicted: true,
        score: 88,
        description: b.description,
        additional_data: {
          symbol: b.symbol,
          apparent_magnitude: b.apparent_magnitude,
        },
      })
    ).filter(Boolean);

    return fallback;
  }, [events]);

  const categories = useMemo(
    () => new Set((events.length ? events : displayEvents).map((event) => event.category)).size,
    [events, displayEvents]
  );

  const greeting = user?.full_name || user?.email || "Observer";

  return (
    <div className="page-content dashboard-page">
      <section className="welcome-section">
        <div>
          <div className="eyebrow">
            <span className="live-dot" /> CELESTIAL INTELLIGENCE SYSTEM
          </div>
          <h1>
            Welcome back, <span>{greeting}.</span>
          </h1>
          <p>
            Explore celestial events, predict visible passes for planets, comets, and asteroids,
            inspect atmospheric conditions, and calculate optimal viewing sessions.
          </p>
          <div className="welcome-actions">
            <button className="primary-action" onClick={() => navigate("/explore")}>
              <Compass size={16} /> Explore Cosmos
            </button>
            <button className="secondary-action" onClick={() => navigate("/planner")}>
              <Telescope size={16} /> Observation Planner
            </button>
          </div>
        </div>
        <div className="welcome-logo">
          <BrandLogo size="panel" />
        </div>
      </section>

      <section className="section-heading">
        <div>
          <div className="eyebrow">CATALOGUE & PREDICTIONS OVERVIEW</div>
          <h2>At a glance</h2>
        </div>
        {loading && (
          <span className="demo-label">
            <LoaderCircle className="loading-spinner" size={12} /> LOADING
          </span>
        )}
      </section>

      {error && (
        <div className="inline-alert">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      <section className="metrics-grid">
        <MetricCard
          icon={CalendarDays}
          label="Available targets"
          value={events.length || displayEvents.length}
          detail={events.length ? "Database & Ephemeris" : "Predicted celestial bodies"}
        />
        <MetricCard
          icon={Compass}
          label="Categories"
          value={categories}
          detail="Planets, Deep Sky, Comets, Asteroids"
        />
        <MetricCard
          icon={Thermometer}
          label="Temperature"
          value={
            (environment?.temperature_celsius ?? environment?.temperature) != null
              ? Math.round(environment.temperature_celsius ?? environment.temperature)
              : "—"
          }
          unit={
            (environment?.temperature_celsius ?? environment?.temperature) != null
              ? "°C"
              : ""
          }
          detail={
            environment
              ? `Cloud: ${Math.round(environment.cloud_cover ?? environment.cloud_coverage ?? 0)}%`
              : "Open-Meteo forecast"
          }
        />
        <MetricCard
          icon={Eye}
          label="Observer location"
          value={location.name ? location.name.split(",")[0] : `${location.latitude.toFixed(2)}°`}
          detail={`${location.latitude.toFixed(2)}°, ${location.longitude.toFixed(2)}°`}
        />
      </section>

      <section className="dashboard-grid">
        <div className="panel opportunities-panel">
          <div className="panel-header">
            <div>
              <div className="eyebrow">CELESTIAL TARGETS</div>
              <h3>Observation opportunities</h3>
              <p>Predicted planetary and catalogue bodies ready for observation planning.</p>
            </div>
            <button className="text-button" onClick={() => navigate("/explore")}>
              View all <ArrowRight size={15} />
            </button>
          </div>

          <div className="opportunity-list">
            {displayEvents.map((item) => (
              <div
                className="opportunity-row"
                key={item.id}
                onClick={() =>
                  navigate("/planner", { state: { selectedTarget: item.name } })
                }
                style={{ cursor: "pointer" }}
                title="Click to plan observation session for this target"
              >
                <div
                  className="target-symbol"
                  style={{
                    position: "relative",
                    overflow: "hidden",
                    backgroundImage: `url(${getCelestialImage(item.name, item.category).url})`,
                    backgroundSize: "cover",
                    backgroundPosition: "center",
                    border: `1px solid ${getCelestialImage(item.name, item.category).accent || "#29424d"}`,
                  }}
                  title={item.name}
                >
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      background: "rgba(5, 5, 11, 0.45)",
                    }}
                  />
                  <span style={{ position: "relative", zIndex: 1, textShadow: "0 2px 4px rgba(0,0,0,0.8)" }}>
                    {item.additionalData?.symbol || (item.category === "Planets" ? "🪐" : item.category === "Comets" ? "☄️" : item.category === "Asteroids" ? "🪨" : item.category === "Meteor Showers" ? "🌠" : item.category === "Solar Eclipses" ? "☀️" : item.category === "Lunar Eclipses" ? "🌑" : "✦")}
                  </span>
                </div>
                <div className="target-info">
                  <strong>{item.name}</strong>
                  <span>{item.designation}</span>
                </div>
                <div className="target-type">
                  <span>{item.category}</span>
                  {item.observationGuide && (
                    <span
                      className={`equipment-badge badge-${item.observationGuide.iconType}`}
                      style={{ fontSize: "0.68rem", padding: "1px 6px", marginTop: "2px" }}
                    >
                      {item.observationGuide.badge}
                    </span>
                  )}
                </div>
                <div className="target-time">
                  {item.isPredicted ? (
                    <span style={{ color: "#fef08a" }}>PREDICTED PASS</span>
                  ) : (
                    formatEventDate(item.startTime)
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel conditions-panel">
          <div className="panel-header">
            <div>
              <div className="eyebrow">ENVIRONMENTAL CONDITIONS</div>
              <h3>Stored sky snapshot</h3>
            </div>
            <Droplets size={21} className="sun-icon" />
          </div>

          {environment ? (
            <>
              <div className="condition-status">
                <div className="condition-status-icon"><Cloud size={25} /></div>
                <div>
                  <strong>{environment.conditions || "Observation on file"}</strong>
                  <span>
                    {environment.freshness_status
                      ? `Freshness: ${environment.freshness_status.toUpperCase()}`
                      : "Latest stored observation"}
                  </span>
                </div>
              </div>
              <div className="condition-row">
                <span>Humidity</span>
                <strong>
                  {environment.humidity != null ? `${Math.round(environment.humidity)}%` : "Unavailable"}
                </strong>
              </div>
              <div className="condition-row">
                <span>Observed at</span>
                <strong>{formatEventDate(environment.observed_at)}</strong>
              </div>
              <div className="condition-row">
                <span>Location</span>
                <strong>
                  {environment.latitude?.toFixed(4)}, {environment.longitude?.toFixed(4)}
                </strong>
              </div>
            </>
          ) : (
            <div className="condition-note">
              {envNote ||
                "No stored environmental observation exists for this location. Generate an observation plan to fetch and persist fresh Open-Meteo forecasts."}
            </div>
          )}

          <div style={{ display: "flex", gap: "10px", marginTop: "16px" }}>
            <button
              className="secondary-action"
              style={{ flex: 1, justifyContent: "center" }}
              onClick={() => navigate("/visibility")}
            >
              <Eye size={15} /> Visibility Intelligence
            </button>
            <button
              className="primary-action"
              style={{ flex: 1, justifyContent: "center" }}
              onClick={() => navigate("/planner")}
            >
              <Telescope size={15} /> Observation Planner
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
