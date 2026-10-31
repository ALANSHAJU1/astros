import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  AlertCircle,
  CalendarDays,
  LoaderCircle,
  MapPin,
  Telescope,
} from "lucide-react";

import BrandLogo from "../components/BrandLogo";
import { eventService } from "../services/eventService";
import { adaptEvent } from "../services/eventAdapter";
import { observationPlanService } from "../services/observationPlanService";
import { getApiErrorMessage } from "../utils/apiErrors";
import {
  formatDateTime,
  localInputToIso,
  minutesBetween,
  toDateTimeLocalValue,
} from "../utils/datetime";
import {
  loadObserverLocation,
  saveObserverLocation,
} from "../utils/location";

function defaultWindow() {
  const start = new Date();
  start.setMinutes(0, 0, 0);
  start.setHours(19, 0, 0, 0);
  const end = new Date(start);
  end.setHours(22, 0, 0, 0);
  return {
    start: toDateTimeLocalValue(start),
    end: toDateTimeLocalValue(end),
  };
}

function scoreValue(item, keys) {
  for (const key of keys) {
    const value = item?.[key];
    if (value != null && value !== "") return Number(value);
  }
  return null;
}

function RankBadge({ value }) {
  if (value == null || Number.isNaN(value)) {
    return <span className="score-pill muted">Unavailable</span>;
  }
  const rounded = Math.round(value);
  const tone = rounded >= 75 ? "good" : rounded >= 50 ? "fair" : "poor";
  return <span className={`score-pill ${tone}`}>{rounded}</span>;
}

export default function Planner() {
  const routerLocation = useLocation();
  const storedLocation = loadObserverLocation();
  const windowDefaults = defaultWindow();

  const [latitude, setLatitude] = useState(storedLocation.latitude);
  const [longitude, setLongitude] = useState(storedLocation.longitude);
  const [sessionStart, setSessionStart] = useState(windowDefaults.start);
  const [sessionEnd, setSessionEnd] = useState(windowDefaults.end);
  const [duration, setDuration] = useState(120);
  const [selectedEventId, setSelectedEventId] = useState("");
  const [catalogue, setCatalogue] = useState([]);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    eventService
      .getEvents({ skip: 0, limit: 100 })
      .then((data) => setCatalogue(Array.isArray(data) ? data.map(adaptEvent) : []))
      .catch(() => setCatalogue([]));
  }, []);

  useEffect(() => {
    const targetName = routerLocation.state?.selectedTarget;
    if (!targetName || catalogue.length === 0) return;
    const match = catalogue.find(
      (event) => event.name.toLowerCase() === String(targetName).toLowerCase()
    );
    if (match) setSelectedEventId(match.id);
  }, [routerLocation.state, catalogue]);

  const selectedEvent = useMemo(
    () => catalogue.find((event) => event.id === selectedEventId),
    [catalogue, selectedEventId]
  );

  async function handleGenerate(event) {
    event.preventDefault();
    setError("");
    setPlan(null);
    setLoading(true);

    const lat = Number(latitude);
    const lon = Number(longitude);
    saveObserverLocation({ latitude: lat, longitude: lon });

    const payload = {
      session: {
        latitude: lat,
        longitude: lon,
        session_start: localInputToIso(sessionStart),
        session_end: localInputToIso(sessionEnd),
        available_duration_minutes: Number(duration) || undefined,
      },
      events: [],
    };

    if (selectedEvent) {
      payload.events = [
        {
          event_id: selectedEvent.id,
          name: selectedEvent.name,
          category: selectedEvent.category,
          event_type: selectedEvent.eventType,
          window_start: selectedEvent.startTime || localInputToIso(sessionStart),
          window_end: selectedEvent.endTime || localInputToIso(sessionEnd),
          latitude: selectedEvent.latitude ?? lat,
          longitude: selectedEvent.longitude ?? lon,
        },
      ];
    }

    try {
      const result = await observationPlanService.generate(payload);
      setPlan(result);
    } catch (err) {
      setError(getApiErrorMessage(err, "Unable to generate an observation plan."));
    } finally {
      setLoading(false);
    }
  }

  const ranked = plan?.ranked || [];
  const schedule = plan?.schedule || [];
  const skipped = plan?.skipped || [];
  const details = plan?.details || [];

  return (
    <div className="page-content planner-page">
      <section className="explore-hero planner-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">
            <span className="live-dot" /> OBSERVATION PLANNING
          </div>
          <h1>Plan the <span>night sky.</span></h1>
          <p>
            Submit observer coordinates and a session window. AstroOS evaluates
            live astronomical targets and returns ranked observation opportunities.
          </p>
        </div>
        <BrandLogo size="panel" />
      </section>

      <form className="planner-form panel" onSubmit={handleGenerate}>
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
            />
          </label>
          <label>
            Session start
            <input
              type="datetime-local"
              required
              value={sessionStart}
              onChange={(event) => setSessionStart(event.target.value)}
            />
          </label>
          <label>
            Session end
            <input
              type="datetime-local"
              required
              value={sessionEnd}
              onChange={(event) => setSessionEnd(event.target.value)}
            />
          </label>
          <label>
            Available duration (minutes)
            <input
              type="number"
              min="1"
              max="1440"
              value={duration}
              onChange={(event) => setDuration(event.target.value)}
            />
          </label>
          <label>
            Catalogue event (optional)
            <select
              value={selectedEventId}
              onChange={(event) => setSelectedEventId(event.target.value)}
            >
              <option value="">Discover live targets automatically</option>
              {catalogue.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {item.category}
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className="planner-hint">
          <MapPin size={14} />
          Leave event selection empty to let the backend discover solar-system and
          catalogue targets for this location and window.
        </p>

        {error && (
          <div className="inline-alert">
            <AlertCircle size={16} /> {error}
          </div>
        )}

        <button className="login-submit planner-submit" type="submit" disabled={loading}>
          {loading ? (
            <>
              <LoaderCircle className="loading-spinner" size={16} /> Generating plan...
            </>
          ) : (
            <>
              <Telescope size={16} /> Generate observation plan
            </>
          )}
        </button>
      </form>

      {plan && (
        <section className="planner-results">
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">Targets evaluated</div>
              <div className="metric-value">{plan.eventCount}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Ranked</div>
              <div className="metric-value">{ranked.length}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Scheduled</div>
              <div className="metric-value">{schedule.length}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Unsuitable / skipped</div>
              <div className="metric-value">{skipped.length}</div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <div>
                <div className="eyebrow">RECOMMENDED TARGETS</div>
                <h3>Ranked observation opportunities</h3>
              </div>
            </div>
            {(ranked.length ? ranked : details).length === 0 ? (
              <div className="empty-inline">
                <BrandLogo size="sm" />
                <p>The engine returned no ranked targets for this session.</p>
              </div>
            ) : (
              <div className="result-table">
                {(ranked.length ? ranked : details).map((item, index) => {
                  const name = item.name || item.object_name || "Unnamed target";
                  const rank = item.rank ?? index + 1;
                  const visibility = scoreValue(item, [
                    "visibility_score",
                    "recommendation_score",
                    "astronomical_score",
                  ]);
                  const weather = scoreValue(item, [
                    "weather_score",
                    "environmental_score",
                  ]);
                  const start = item.window_start || item.start_time || item.scheduled_start;
                  const end = item.window_end || item.end_time || item.scheduled_end;
                  const durationMinutes =
                    item.duration_minutes ||
                    item.required_duration_minutes ||
                    minutesBetween(start, end);
                  const status = item.assessment_status || item.quality_label || item.decision;

                  return (
                    <article className="result-row" key={item.event_id || item.id || name + rank}>
                      <div className="result-rank">#{rank}</div>
                      <div>
                        <strong>{name}</strong>
                        <span>
                          {item.event_type || item.category || "Celestial target"}
                          {status ? ` · ${status}` : ""}
                        </span>
                      </div>
                      <div>
                        <small>Window</small>
                        <strong>
                          {formatDateTime(start)}
                          {end ? ` – ${formatDateTime(end)}` : ""}
                        </strong>
                      </div>
                      <div>
                        <small>Duration</small>
                        <strong>{durationMinutes != null ? `${durationMinutes} min` : "—"}</strong>
                      </div>
                      <div>
                        <small>Visibility</small>
                        <RankBadge value={visibility} />
                      </div>
                      <div>
                        <small>Environment</small>
                        <RankBadge value={weather} />
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </div>

          {schedule.length > 0 && (
            <div className="panel">
              <div className="eyebrow">SCHEDULE</div>
              <h3>Recommended observation windows</h3>
              <div className="result-table">
                {schedule.map((item, index) => (
                  <article className="result-row" key={item.event_id || index}>
                    <div className="result-rank">
                      <CalendarDays size={16} />
                    </div>
                    <div>
                      <strong>{item.name}</strong>
                      <span>{item.explanation || "Scheduled by AstroOS"}</span>
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
                    <RankBadge value={scoreValue(item, ["recommendation_score", "visibility_score"])} />
                  </article>
                ))}
              </div>
            </div>
          )}

          {skipped.length > 0 && (
            <div className="panel">
              <div className="eyebrow">UNSUITABLE OPPORTUNITIES</div>
              <h3>Skipped or unavailable targets</h3>
              <ul className="skipped-list">
                {skipped.map((item, index) => (
                  <li key={item.event_id || item.name || index}>
                    <strong>{item.name || "Unnamed target"}</strong>
                    <span>
                      {item.reason ||
                        item.explanation ||
                        item.rejection_reason ||
                        "Not scheduled for this session."}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
