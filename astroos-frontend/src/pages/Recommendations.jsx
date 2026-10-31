import { useEffect, useState } from "react";
import {
  AlertCircle,
  CalendarDays,
  CheckCircle2,
  Clock,
  Database,
  Info,
  LoaderCircle,
  Sparkles,
  Telescope,
  XCircle,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import BrandLogo from "../components/BrandLogo";
import { eventService } from "../services/eventService";
import { parseObservationPlan } from "../services/observationPlanService";
import { recommendationService } from "../services/recommendationService";
import { getApiErrorMessage } from "../utils/apiErrors";
import {
  formatClock,
  formatDateTime,
  localInputToIso,
  toDateTimeLocalValue,
} from "../utils/datetime";
import { loadObserverLocation, saveObserverLocation } from "../utils/location";

const GOAL_OPTIONS = [
  { value: "general_observation", label: "General Observation" },
  { value: "deep_sky", label: "Deep-Sky Objects" },
  { value: "planetary", label: "Planetary Observation" },
  { value: "meteor_shower", label: "Meteor Showers" },
  { value: "astrophotography", label: "Astrophotography" },
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
  let statusText = "Fair";

  if (num >= 80) {
    tone = "optimal";
    statusText = "Optimal";
  } else if (num >= 65) {
    tone = "good";
    statusText = "Good";
  } else if (num >= 45) {
    tone = "fair";
    statusText = "Fair";
  } else if (num >= 25) {
    tone = "poor";
    statusText = "Poor";
  } else {
    tone = "unusable";
    statusText = "Unusable";
  }

  return (
    <span
      className={`score-pill ${tone}`}
      title={`${label ? label + ": " : ""}${num.toFixed(1)}/100 (${statusText})`}
    >
      {rounded}
    </span>
  );
}

export default function Recommendations() {
  const navigate = useNavigate();
  const stored = loadObserverLocation();
  const windowDefaults = defaultWindow();

  const [latitude, setLatitude] = useState(stored.latitude);
  const [longitude, setLongitude] = useState(stored.longitude);
  const [startTime, setStartTime] = useState(windowDefaults.start);
  const [endTime, setEndTime] = useState(windowDefaults.end);
  const [duration, setDuration] = useState(120);
  const [goal, setGoal] = useState("general_observation");
  const [category, setCategory] = useState("");
  const [availableCategories, setAvailableCategories] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState(null);

  // Discover categories from currently stored events
  useEffect(() => {
    eventService
      .getEvents({ skip: 0, limit: 100 })
      .then((data) => {
        if (Array.isArray(data)) {
          const cats = [...new Set(data.map((d) => d.category))].filter(Boolean);
          setAvailableCategories(cats);
        }
      })
      .catch(() => {});
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setResult(null);
    setExpandedId(null);

    const lat = Number(latitude);
    const lon = Number(longitude);
    const startIso = localInputToIso(startTime);
    const endIso = localInputToIso(endTime);
    const durationNum = Number(duration);

    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      setError("Please enter a valid latitude between -90 and 90.");
      return;
    }
    if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
      setError("Please enter a valid longitude between -180 and 180.");
      return;
    }
    if (!startIso || !endIso || new Date(endIso) <= new Date(startIso)) {
      setError("End time must be later than the start time.");
      return;
    }

    saveObserverLocation({ latitude: lat, longitude: lon });
    setLoading(true);

    try {
      const data = await recommendationService.fromDatabase({
        location: { latitude: lat, longitude: lon },
        start_time: startIso,
        end_time: endIso,
        available_duration_minutes: durationNum,
        observation_goal: goal,
        category: category || null,
      });

      setResult(parseObservationPlan(data));
    } catch (err) {
      setError(
        getApiErrorMessage(
          err,
          "Catalog recommendations could not be generated from database records."
        )
      );
    } finally {
      setLoading(false);
    }
  }

  const ranked = result?.ranked || [];
  const schedule = result?.schedule || [];
  const skipped = result?.skipped || [];

  return (
    <div className="page-content recommendations-page">
      <section className="explore-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">
            <span className="live-dot" /> DATABASE RECOMMENDATIONS
          </div>
          <h1>Rank stored <span>catalogue events.</span></h1>
          <p>
            Query and score celestial events stored in the AstroOS database.
            The intelligence engine evaluates local visibility, weather conditions,
            and preference weights to rank suitable targets.
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
              onChange={(e) => setLatitude(e.target.value)}
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
              onChange={(e) => setLongitude(e.target.value)}
              placeholder="e.g. 76.2144"
            />
          </label>

          <label>
            Start time
            <input
              type="datetime-local"
              required
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
            />
          </label>

          <label>
            End time
            <input
              type="datetime-local"
              required
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
            />
          </label>

          <label>
            Available duration (minutes)
            <input
              type="number"
              min="1"
              max="1440"
              required
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
            />
          </label>

          <label>
            Observation goal
            <select value={goal} onChange={(e) => setGoal(e.target.value)}>
              {GOAL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <label className="span-2">
            Category filter
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All Categories (Evaluate entire database)</option>
              {availableCategories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className="planner-hint">
          <Database size={14} />
          <span>
            This query evaluates records in the AstroOS events database. To discover
            live targets outside stored records, use the Observation Planner.
          </span>
        </p>

        {error && (
          <div className="inline-alert">
            <AlertCircle size={16} /> {error}
          </div>
        )}

        <button className="login-submit planner-submit" type="submit" disabled={loading}>
          {loading ? (
            <>
              <LoaderCircle className="loading-spinner" size={16} /> Ranking catalogue...
            </>
          ) : (
            <>
              <Sparkles size={16} /> Rank database catalogue
            </>
          )}
        </button>
      </form>

      {result && (
        <section className="planner-results">
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-top">
                <div className="metric-icon"><Database size={18} /></div>
                <span className="metric-label">Database records</span>
              </div>
              <div className="metric-value">{result.eventCount}</div>
              <div className="metric-detail">Stored in database</div>
            </div>

            <div className="metric-card">
              <div className="metric-top">
                <div className="metric-icon"><Sparkles size={18} /></div>
                <span className="metric-label">Ranked opportunities</span>
              </div>
              <div className="metric-value">{ranked.length}</div>
              <div className="metric-detail">Assessed for this session</div>
            </div>

            <div className="metric-card">
              <div className="metric-top">
                <div className="metric-icon"><CalendarDays size={18} /></div>
                <span className="metric-label">Scheduled targets</span>
              </div>
              <div className="metric-value">{schedule.length}</div>
              <div className="metric-detail">Fit session constraints</div>
            </div>

            <div className="metric-card">
              <div className="metric-top">
                <div className="metric-icon"><Clock size={18} /></div>
                <span className="metric-label">Session status</span>
              </div>
              <div className="metric-value metric-value-text">
                {result.status ? result.status.toUpperCase() : "COMPLETE"}
              </div>
              <div className="metric-detail">
                {result.dataQuality?.data_mode
                  ? `Mode: ${result.dataQuality.data_mode}`
                  : "Database evaluation"}
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <div>
                <div className="eyebrow">RANKED CATALOGUE TARGETS</div>
                <h3>Recommended observation opportunities</h3>
                <p>
                  Rankings reflect composite evaluation of astronomical ephemeris,
                  environmental conditions, and target suitability.
                </p>
              </div>
            </div>

            {ranked.length === 0 ? (
              <div className="empty-inline">
                <BrandLogo size="sm" />
                <p>
                  {result.eventCount === 0 || result.status === "empty"
                    ? "The database recommendation engine found no stored celestial events overlapping this observation window. Try widening the window or use the Observation Planner to fetch live JPL targets."
                    : "No catalogue events met the criteria for this session window."}
                </p>
                <button
                  className="secondary-action"
                  style={{ marginTop: "12px" }}
                  onClick={() => navigate("/planner")}
                >
                  <Telescope size={15} /> Switch to Observation Planner
                </button>
              </div>
            ) : (
              <div className="result-table">
                {ranked.map((item, index) => {
                  const id = item.event_id || item.id || `rec-${index}`;
                  const isExpanded = expandedId === id;
                  const breakdown = item.score_breakdown || {};

                  return (
                    <div key={id} className="result-item-container">
                      <article
                        className="result-row"
                        onClick={() => setExpandedId(isExpanded ? null : id)}
                        style={{ cursor: "pointer" }}
                      >
                        <div className="result-rank">#{item.rank ?? index + 1}</div>

                        <div className="result-info">
                          <strong>{item.name || item.object_name}</strong>
                          <span>{item.category || item.event_type || "Celestial target"}</span>
                        </div>

                        <div>
                          <small>Window</small>
                          <strong>
                            {item.window_start || item.start_time
                              ? formatClock(item.window_start || item.start_time)
                              : "Session"}
                          </strong>
                        </div>

                        <div>
                          <small>Composite score</small>
                          <ScoreBadge
                            value={item.recommendation_score}
                            label="Recommendation Score"
                          />
                        </div>

                        <div>
                          <small>Visibility weight</small>
                          <span className="text-muted">
                            {breakdown.visibility != null
                              ? `${Math.round(breakdown.visibility * 100)}%`
                              : "—"}
                          </span>
                        </div>

                        <div>
                          <small>Weather weight</small>
                          <span className="text-muted">
                            {breakdown.weather != null
                              ? `${Math.round(breakdown.weather * 100)}%`
                              : "—"}
                          </span>
                        </div>

                        <div>
                          <small>Preference weight</small>
                          <span className="text-muted">
                            {breakdown.preference != null
                              ? `${Math.round(breakdown.preference * 100)}%`
                              : "—"}
                          </span>
                        </div>
                      </article>

                      {isExpanded && (
                        <div className="result-expanded-details">
                          <div className="limitations-title">
                            <Info size={14} /> Score breakdown & factors:
                          </div>
                          <ul className="limitations-list">
                            <li>
                              Recommendation score:{" "}
                              <strong>{item.recommendation_score?.toFixed(1) ?? "Unavailable"}</strong>/100
                            </li>
                            {item.explanation && <li>{item.explanation}</li>}
                            {item.duration_minutes && (
                              <li>Required duration: {item.duration_minutes} minutes</li>
                            )}
                          </ul>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {schedule.length > 0 && (
            <div className="panel schedule-panel">
              <div className="panel-header">
                <div>
                  <div className="eyebrow">OPTIMIZED SCHEDULE</div>
                  <h3>Suggested observation timeline</h3>
                </div>
              </div>

              <div className="result-table">
                {schedule.map((item, index) => (
                  <article className="result-row" key={item.event_id || `rec-sched-${index}`}>
                    <div className="result-rank">
                      <CheckCircle2 size={16} className="text-emerald" />
                    </div>
                    <div>
                      <strong>{item.name}</strong>
                      <span>{item.explanation || "Scheduled target"}</span>
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
                      <ScoreBadge value={item.recommendation_score} label="Score" />
                    </div>
                  </article>
                ))}
              </div>
            </div>
          )}

          {skipped.length > 0 && (
            <div className="panel skipped-panel">
              <div className="panel-header">
                <div>
                  <div className="eyebrow">UNSCHEDULED CANDIDATES</div>
                  <h3>Excluded catalogue records</h3>
                </div>
              </div>

              <ul className="skipped-list">
                {skipped.map((item, index) => (
                  <li key={item.event_id || item.name || `rec-skip-${index}`}>
                    <div className="skipped-item-header">
                      <XCircle size={15} className="text-muted" />
                      <strong>{item.name || "Target"}</strong>
                    </div>
                    <span>
                      {item.reason ||
                        item.explanation ||
                        "Could not be scheduled within session duration or window constraints."}
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
