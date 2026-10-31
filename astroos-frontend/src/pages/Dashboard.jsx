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
  Telescope,
  Thermometer,
} from "lucide-react";

import BrandLogo from "../components/BrandLogo";
import { useAuth } from "../context/AuthContext";
import { eventService } from "../services/eventService";
import { adaptEvent, formatEventDate } from "../services/eventAdapter";
import { environmentalService } from "../services/environmentalService";
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
          setEvents(Array.isArray(data) ? data.map(adaptEvent) : []);
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
              "No stored environmental observation exists for the saved observer location yet. Generate a plan or query Visibility Intelligence after a forecast has been persisted."
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

  const upcoming = useMemo(() => {
    const now = Date.now();
    return [...events]
      .filter((event) => {
        if (!event.startTime) return true;
        return new Date(event.startTime).getTime() >= now - 6 * 60 * 60 * 1000;
      })
      .slice(0, 6);
  }, [events]);

  const categories = new Set(events.map((event) => event.category)).size;
  const greeting = user?.full_name || user?.email || "Observer";

  return (
    <div className="page-content">
      <section className="welcome-section">
        <div>
          <div className="eyebrow">
            <span className="live-dot" /> CELESTIAL INTELLIGENCE SYSTEM
          </div>
          <h1>
            Welcome back, <span>{greeting}.</span>
          </h1>
          <p>
            Review catalogue events, inspect stored sky conditions, and open the
            observation planner when you are ready to generate a live session.
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
          <div className="eyebrow">CATALOGUE OVERVIEW</div>
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
          label="Catalogue events"
          value={String(events.length).padStart(2, "0")}
          detail="Records returned by GET /api/v1/events"
        />
        <MetricCard
          icon={Eye}
          label="Event categories"
          value={String(categories).padStart(2, "0")}
          detail="Distinct categories in the loaded catalogue"
        />
        <MetricCard
          icon={Cloud}
          label="Cloud cover"
          value={environment?.cloud_cover != null ? Math.round(environment.cloud_cover) : "—"}
          unit={environment?.cloud_cover != null ? "%" : ""}
          detail={environment ? `Source: ${environment.source || "stored observation"}` : "No stored observation"}
        />
        <MetricCard
          icon={Thermometer}
          label="Temperature"
          value={
            environment?.temperature_celsius != null
              ? Number(environment.temperature_celsius).toFixed(1)
              : "—"
          }
          unit={environment?.temperature_celsius != null ? "°C" : ""}
          detail={environment?.conditions || "Awaiting environmental data"}
        />
      </section>

      <section className="dashboard-grid">
        <div className="panel opportunities-panel">
          <div className="panel-header opportunities-header">
            <div>
              <div className="eyebrow">UPCOMING CATALOGUE EVENTS</div>
              <h3>Observation opportunities</h3>
              <p>These are stored celestial events, not generated recommendation scores.</p>
            </div>
            <button className="text-button" onClick={() => navigate("/explore")}>
              Open catalogue <ArrowRight size={16} />
            </button>
          </div>

          {upcoming.length === 0 ? (
            <div className="empty-inline">
              <BrandLogo size="sm" />
              <p>
                {events.length === 0
                  ? "The event catalogue is empty. Use Observation Planner to discover live targets from astronomy services."
                  : "No upcoming events were found in the loaded catalogue window."}
              </p>
            </div>
          ) : (
            <div className="opportunity-list">
              {upcoming.map((item) => (
                <div className="opportunity-row" key={item.id}>
                  <div className="target-symbol">{item.category.slice(0, 3)}</div>
                  <div className="target-info">
                    <strong>{item.name}</strong>
                    <span>{item.eventType}</span>
                  </div>
                  <div className="target-type">{item.category}</div>
                  <div className="target-time">{formatEventDate(item.startTime)}</div>
                </div>
              ))}
            </div>
          )}
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
                      ? `Freshness: ${environment.freshness_status}`
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
                  {environment.latitude?.toFixed(3)}, {environment.longitude?.toFixed(3)}
                </strong>
              </div>
            </>
          ) : (
            <div className="condition-note">{envNote || "No environmental data loaded."}</div>
          )}

          <button className="secondary-action" onClick={() => navigate("/visibility")}>
            Open visibility intelligence
          </button>
        </div>
      </section>
    </div>
  );
}
