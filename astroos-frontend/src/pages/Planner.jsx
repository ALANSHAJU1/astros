import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  AlertCircle,
  CalendarDays,
  CheckCircle2,
  Clock,
  Info,
  LoaderCircle,
  MapPin,
  Sparkles,
  Telescope,
  XCircle,
} from "lucide-react";

import BrandLogo from "../components/BrandLogo";
import { eventService } from "../services/eventService";
import { adaptEvent } from "../services/eventAdapter";
import { observationPlanService } from "../services/observationPlanService";
import { getApiErrorMessage } from "../utils/apiErrors";
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
  { value: "general", label: "General Stargazing" },
  { value: "deep_sky", label: "Deep-Sky Objects (Nebulae & Galaxies)" },
  { value: "planetary", label: "Planetary & Lunar" },
  { value: "meteor_shower", label: "Meteor Showers & Transients" },
  { value: "astrophotography", label: "Astrophotography High-Contrast" },
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

function ScorePill({ value, label }) {
  if (value == null || Number.isNaN(Number(value))) {
    return (
      <span className="score-pill unavailable" title={`${label || "Score"}: Unavailable from provider`}>
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

export default function Planner() {
  const routerLocation = useLocation();
  const storedLocation = loadObserverLocation();
  const windowDefaults = defaultWindow();

  const [latitude, setLatitude] = useState(storedLocation.latitude);
  const [longitude, setLongitude] = useState(storedLocation.longitude);
  const [sessionStart, setSessionStart] = useState(windowDefaults.start);
  const [sessionEnd, setSessionEnd] = useState(windowDefaults.end);
  const [duration, setDuration] = useState(180);
  const [goal, setGoal] = useState("general");
  const [selectedEventId, setSelectedEventId] = useState("");
  const [catalogue, setCatalogue] = useState([]);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedTarget, setExpandedTarget] = useState(null);

  useEffect(() => {
    let active = true;
    eventService
      .getEvents({ skip: 0, limit: 100 })
      .then((data) => {
        if (!active) return;
        const adapted = Array.isArray(data) ? data.map(adaptEvent) : [];
        setCatalogue(adapted);

        const targetName = routerLocation.state?.selectedTarget;
        if (targetName && adapted.length > 0) {
          const match = adapted.find(
            (event) => event.name.toLowerCase() === String(targetName).toLowerCase()
          );
          if (match) setSelectedEventId(match.id);
        }
      })
      .catch(() => {
        if (active) setCatalogue([]);
      });

    return () => {
      active = false;
    };
  }, [routerLocation.state]);

  const selectedEvent = useMemo(
    () => catalogue.find((event) => event.id === selectedEventId),
    [catalogue, selectedEventId]
  );

  async function handleGenerate(event) {
    event.preventDefault();
    setError("");
    setPlan(null);
    setExpandedTarget(null);

    const lat = Number(latitude);
    const lon = Number(longitude);
    const startIso = localInputToIso(sessionStart);
    const endIso = localInputToIso(sessionEnd);
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
      setError("Session end time must be later than the session start time.");
      return;
    }
    if (!durationNum || durationNum <= 0 || durationNum > 1440) {
      setError("Available duration must be between 1 and 1440 minutes (24 hours).");
      return;
    }

    saveObserverLocation({ latitude: lat, longitude: lon });
    setLoading(true);

    const payload = {
      session: {
        latitude: lat,
        longitude: lon,
        session_start: startIso,
        session_end: endIso,
        available_duration_minutes: durationNum,
        observation_goal: goal,
      },
      events: selectedEvent
        ? [
            {
              event_id: selectedEvent.id,
              name: selectedEvent.name,
              category: selectedEvent.category,
              event_type: selectedEvent.eventType,
              window_start: startIso,
              window_end: endIso,
              latitude: selectedEvent.latitude ?? lat,
              longitude: selectedEvent.longitude ?? lon,
            },
          ]
        : [],
    };

    try {
      const result = await observationPlanService.generate(payload);
      setPlan(result);
    } catch (err) {
      setError(
        getApiErrorMessage(
          err,
          "Unable to generate an observation plan. Check coordinates and session dates."
        )
      );
    } finally {
      setLoading(false);
    }
  }

  // Merge ranked list with enriched event details to ensure all columns render accurately
  const rankedItems = useMemo(() => {
    if (!plan) return [];

    const detailsMap = new Map();
    for (const d of plan.details || []) {
      const key = String(d.event_id || d.id || d.name);
      detailsMap.set(key, d);
    }

    const sourceList =
      Array.isArray(plan.ranked) && plan.ranked.length > 0
        ? plan.ranked
        : Array.isArray(plan.details)
        ? plan.details
        : [];

    return sourceList.map((item, idx) => {
      const key = String(item.event_id || item.id || item.name);
      const detail = detailsMap.get(key) || {};

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

      const durationMins =
        item.duration_minutes ||
        detail.duration_minutes ||
        detail.required_duration_minutes ||
        minutesBetween(windowStart, windowEnd);

      return {
        ...detail,
        ...item,
        key: key || `target-${idx}`,
        rank: item.rank ?? idx + 1,
        name: item.name || detail.name || detail.object_name || "Celestial target",
        category: detail.category || item.category || "General target",
        eventType: detail.event_type || item.event_type || "Observation",
        recommendationScore:
          item.recommendation_score ?? detail.recommendation_score ?? null,
        visibilityScore:
          detail.visibility_score ?? item.visibility_score ?? null,
        weatherScore:
          detail.weather_score ??
          detail.environmental_score ??
          item.weather_score ??
          null,
        astronomicalScore:
          detail.astronomical_score ?? item.astronomical_score ?? null,
        windowStart,
        windowEnd,
        durationMinutes: durationMins,
        qualityLabel:
          detail.quality_label || item.quality_label || detail.status || null,
        assessmentStatus:
          detail.assessment_status || item.assessment_status || null,
        limitations:
          Array.isArray(detail.limitations) && detail.limitations.length > 0
            ? detail.limitations
            : Array.isArray(item.limitations)
            ? item.limitations
            : [],
        scoreBreakdown: item.score_breakdown || detail.score_breakdown || null,
      };
    });
  }, [plan]);

  const schedule = plan?.schedule || [];
  const skipped = plan?.skipped || [];
  const summary = plan?.summary || {};

  return (
    <div className="page-content planner-page">
      <section className="explore-hero planner-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">
            <span className="live-dot" /> OBSERVATION PLANNING
          </div>
          <h1>Plan the <span>night sky.</span></h1>
          <p>
            Configure your observing coordinates, session window, and goals.
            AstroOS analyzes ephemeris geometry and environmental conditions to
            produce an optimized observation plan.
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
              required
              value={duration}
              onChange={(event) => setDuration(event.target.value)}
            />
          </label>

          <label>
            Observation goal
            <select value={goal} onChange={(event) => setGoal(event.target.value)}>
              {GOAL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <label className="span-2">
            Target selection
            <select
              value={selectedEventId}
              onChange={(event) => setSelectedEventId(event.target.value)}
            >
              <option value="">
                Discover live targets automatically (JPL Horizons & Catalogues)
              </option>
              {catalogue.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {item.category} ({item.eventType})
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className="planner-hint">
          <MapPin size={14} />
          {selectedEventId ? (
            <span>
              Evaluating specific target <strong>{selectedEvent?.name}</strong> for
              the selected observation session.
            </span>
          ) : (
            <span>
              Automatic discovery evaluates solar-system bodies, visible planets,
              and catalogued deep-sky objects visible from your location.
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
              <LoaderCircle className="loading-spinner" size={16} /> Generating observation plan...
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
              <div className="metric-top">
                <div className="metric-icon"><Telescope size={18} /></div>
                <span className="metric-label">Evaluated targets</span>
              </div>
              <div className="metric-value">{plan.eventCount}</div>
              <div className="metric-detail">Discovered & analyzed</div>
            </div>

            <div className="metric-card">
              <div className="metric-top">
                <div className="metric-icon"><Sparkles size={18} /></div>
                <span className="metric-label">Ranked targets</span>
              </div>
              <div className="metric-value">{rankedItems.length}</div>
              <div className="metric-detail">Assessed for suitability</div>
            </div>

            <div className="metric-card">
              <div className="metric-top">
                <div className="metric-icon"><CalendarDays size={18} /></div>
                <span className="metric-label">Scheduled</span>
              </div>
              <div className="metric-value">{schedule.length}</div>
              <div className="metric-detail">Fit in available time</div>
            </div>

            <div className="metric-card">
              <div className="metric-top">
                <div className="metric-icon"><Clock size={18} /></div>
                <span className="metric-label">Scheduled time</span>
              </div>
              <div className="metric-value">
                {summary.scheduled_duration_minutes ??
                  summary.total_scheduled_minutes ??
                  schedule.reduce((acc, s) => acc + (s.duration_minutes || 0), 0)}
                <span> min</span>
              </div>
              <div className="metric-detail">
                {summary.remaining_duration_minutes != null
                  ? `${summary.remaining_duration_minutes} min remaining`
                  : `of ${duration} min session`}
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <div>
                <div className="eyebrow">RANKED OPPORTUNITIES</div>
                <h3>Astronomical targets ranked by intelligence</h3>
                <p>
                  Scores reflect composite weighting of visibility conditions,
                  environmental forecasts, and observer preference.
                </p>
              </div>
            </div>

            {rankedItems.length === 0 ? (
              <div className="empty-inline">
                <BrandLogo size="sm" />
                <p>The intelligence engine evaluated this session but found no suitable targets.</p>
              </div>
            ) : (
              <div className="result-table">
                {rankedItems.map((item) => {
                  const isExpanded = expandedTarget === item.key;
                  return (
                    <div key={item.key} className="result-item-container">
                      <article
                        className="result-row"
                        onClick={() =>
                          item.limitations?.length > 0
                            ? setExpandedTarget(isExpanded ? null : item.key)
                            : null
                        }
                        style={{ cursor: item.limitations?.length > 0 ? "pointer" : "default" }}
                      >
                        <div className="result-rank">#{item.rank}</div>

                        <div className="result-info">
                          <strong>{item.name}</strong>
                          <span>
                            {item.category} · {item.eventType}
                            {item.qualityLabel ? ` · ${item.qualityLabel}` : ""}
                          </span>
                        </div>

                        <div>
                          <small>Observation window</small>
                          <strong>
                            {formatClock(item.windowStart)}
                            {item.windowEnd ? ` – ${formatClock(item.windowEnd)}` : ""}
                          </strong>
                        </div>

                        <div>
                          <small>Duration</small>
                          <strong>{item.durationMinutes != null ? `${item.durationMinutes} min` : "—"}</strong>
                        </div>

                        <div>
                          <small>Score</small>
                          <ScorePill value={item.recommendationScore} label="Overall" />
                        </div>

                        <div>
                          <small>Visibility</small>
                          <ScorePill value={item.visibilityScore} label="Visibility" />
                        </div>

                        <div>
                          <small>Environment</small>
                          <ScorePill value={item.weatherScore} label="Weather" />
                        </div>
                      </article>

                      {isExpanded && item.limitations?.length > 0 && (
                        <div className="result-expanded-details">
                          <div className="limitations-title">
                            <Info size={14} /> Evaluation factors & limitations:
                          </div>
                          <ul className="limitations-list">
                            {item.limitations.map((lim, idx) => (
                              <li key={idx}>{lim}</li>
                            ))}
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
                  <div className="eyebrow">SESSION TIMELINE</div>
                  <h3>Optimized observation schedule</h3>
                  <p>Chronologically ordered schedule maximizing observation value within session constraints.</p>
                </div>
              </div>

              <div className="result-table">
                {schedule.map((item, index) => (
                  <article className="result-row" key={item.event_id || `sched-${index}`}>
                    <div className="result-rank">
                      <CheckCircle2 size={16} className="text-emerald" />
                    </div>
                    <div>
                      <strong>{item.name}</strong>
                      <span>{item.explanation || "Scheduled by AstroOS optimizer"}</span>
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
                      <ScorePill value={item.recommendation_score} label="Score" />
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
                  <div className="eyebrow">UNSCHEDULED TARGETS</div>
                  <h3>Excluded opportunities</h3>
                  <p>Targets skipped due to time constraints, below-horizon geometry, or adverse weather.</p>
                </div>
              </div>

              <ul className="skipped-list">
                {skipped.map((item, index) => (
                  <li key={item.event_id || item.name || `skip-${index}`}>
                    <div className="skipped-item-header">
                      <XCircle size={15} className="text-muted" />
                      <strong>{item.name || "Target"}</strong>
                    </div>
                    <span>
                      {item.reason ||
                        item.explanation ||
                        item.rejection_reason ||
                        "Exceeded session duration or had marginal viewing conditions."}
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
