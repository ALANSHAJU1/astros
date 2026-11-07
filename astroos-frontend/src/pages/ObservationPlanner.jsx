import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  AlertCircle,
  ArrowRight,
  Binoculars,
  Calendar,
  Camera,
  CheckCircle2,
  Clock,
  Cloud,
  Compass,
  Eye,
  Info,
  LoaderCircle,
  MapPin,
  RefreshCw,
  Sparkles,
  Sun,
  Telescope,
  Wind,
} from "lucide-react";
import { predictionService, toISOWithOffset } from "../services/predictionService";
import { formatEventDate } from "../services/eventAdapter";
import { getObservationGuide } from "../utils/observationGuide";
import LocationPicker from "../components/LocationPicker";
import { loadObserverLocation } from "../utils/location";

export default function ObservationPlanner() {
  const location = useLocation();
  const navigate = useNavigate();

  // Pre-selected target from Explore page
  const initialTarget = location.state?.selectedTarget || "";

  const stored = loadObserverLocation();
  const [latitude, setLatitude] = useState(stored.latitude);
  const [longitude, setLongitude] = useState(stored.longitude);
  const [locationName, setLocationName] = useState(stored.name || "");
  const [duration, setDuration] = useState(180);

  // Default times: today 19:00 to 23:00 local time
  const [sessionStart, setSessionStart] = useState(() => {
    const d = new Date();
    d.setHours(19, 0, 0, 0);
    return d.toISOString().slice(0, 16);
  });
  const [sessionEnd, setSessionEnd] = useState(() => {
    const d = new Date();
    d.setHours(23, 0, 0, 0);
    return d.toISOString().slice(0, 16);
  });

  // Target categories to include in the plan
  const [includePlanets, setIncludePlanets] = useState(true);
  const [includeComets, setIncludeComets] = useState(true);
  const [includeAsteroids, setIncludeAsteroids] = useState(true);
  const [includeDeepSky, setIncludeDeepSky] = useState(true);

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function handleGenerate(e) {
    if (e) e.preventDefault();
    setGenerating(true);
    setError("");

    const selectedBodies = [];
    if (includePlanets) selectedBodies.push("planets");
    if (includeAsteroids) selectedBodies.push("asteroids");
    if (includeComets) selectedBodies.push("comets");
    if (includeDeepSky) selectedBodies.push("deep_sky");

    try {
      const response = await predictionService.generateObservationPlan({
        latitude: Number(latitude),
        longitude: Number(longitude),
        sessionStart,
        sessionEnd,
        availableDurationMinutes: Number(duration),
        includeBodies: selectedBodies,
      });

      setResult(response);
    } catch (err) {
      const status = err.response?.status;
      if (status === 401) {
        setError("Authentication required. Please sign in to generate observation plans.");
      } else if (status === 502) {
        setError(
          err.response?.data?.detail ||
          "Astronomy upstream service temporarily unavailable. Try again in a moment."
        );
      } else {
        setError(
          err.response?.data?.detail ||
          err.message ||
          "Failed to generate observation plan. Check your session timings and backend connection."
        );
      }
    } finally {
      setGenerating(false);
    }
  }

  // Auto-generate on first visit if target was passed
  useEffect(() => {
    if (initialTarget) {
      handleGenerate();
    }
  }, [initialTarget]);

  const recs = result?.recommendations || {};
  const rankedEvents = recs.ranked_events || recs.details || recs.events || [];
  const schedule = recs.schedule || recs.observation_schedule || [];
  const summary = recs.summary || {};

  return (
    <div className="page-content planner-page">
      <section className="planner-hero">
        <div className="planner-hero-content">
          <div className="eyebrow">
            <span className="live-dot" /> ASTRONOMICAL INTELLIGENCE
          </div>

          <h1>Observation <span>Planner.</span></h1>

          <p>
            Generate multi-target observation plans predicting optimal viewing windows
            for planets, comets, asteroids, moon passes, and deep-sky treasures
            ranked by atmospheric and elevation models.
          </p>

          {initialTarget && (
            <div className="focused-target-pill">
              <Sparkles size={13} />
              <span>Planning session around target: <strong>{initialTarget}</strong></span>
            </div>
          )}
        </div>
      </section>

      {/* Main Form Section */}
      <section className="panel planner-config-panel">
        <div className="panel-header">
          <div>
            <div className="eyebrow">SESSION PARAMETERS</div>
            <h3>Observation configuration</h3>
          </div>
          <span className="panel-tag">INTELLIGENCE ENGINE</span>
        </div>

        <form onSubmit={handleGenerate} className="planner-form">
          <div className="planner-form-grid">
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

            <div className="form-group">
              <label htmlFor="planner-start">
                <Calendar size={14} /> Session Start
              </label>
              <input
                id="planner-start"
                type="datetime-local"
                required
                value={sessionStart}
                onChange={(e) => setSessionStart(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="planner-end">
                <Calendar size={14} /> Session End
              </label>
              <input
                id="planner-end"
                type="datetime-local"
                required
                value={sessionEnd}
                onChange={(e) => setSessionEnd(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="planner-dur">
                <Clock size={14} /> Duration (minutes)
              </label>
              <input
                id="planner-dur"
                type="number"
                min="15"
                max="1440"
                required
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                placeholder="180"
              />
            </div>
          </div>

          {/* Target Prediction Options */}
          <div className="planner-target-options">
            <div className="target-options-label">PREDICT CELESTIAL TARGETS</div>
            <div className="target-options-chips">
              <label className={`target-option-box ${includePlanets ? "checked" : ""}`}>
                <input
                  type="checkbox"
                  checked={includePlanets}
                  onChange={(e) => setIncludePlanets(e.target.checked)}
                />
                <span>🪐 Major Planets (Jupiter, Saturn, Mars, Venus...)</span>
              </label>

              <label className={`target-option-box ${includeAsteroids ? "checked" : ""}`}>
                <input
                  type="checkbox"
                  checked={includeAsteroids}
                  onChange={(e) => setIncludeAsteroids(e.target.checked)}
                />
                <span>🪨 Bright Asteroids & NEOs (Ceres, Vesta, Apophis...)</span>
              </label>

              <label className={`target-option-box ${includeComets ? "checked" : ""}`}>
                <input
                  type="checkbox"
                  checked={includeComets}
                  onChange={(e) => setIncludeComets(e.target.checked)}
                />
                <span>☄️ Comets (1P/Halley, NEOWISE...)</span>
              </label>

              <label className={`target-option-box ${includeDeepSky ? "checked" : ""}`}>
                <input
                  type="checkbox"
                  checked={includeDeepSky}
                  onChange={(e) => setIncludeDeepSky(e.target.checked)}
                />
                <span>✨ Deep-Sky Objects (M31 Andromeda, M42 Orion, M45 Pleiades...)</span>
              </label>
            </div>
          </div>

          {error && (
            <div className="planner-error">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            className="planner-generate-button"
            disabled={generating}
          >
            {generating ? (
              <>
                <LoaderCircle className="loading-spinner" size={17} />
                <span>Computing celestial ephemeris & visibility...</span>
              </>
            ) : (
              <>
                <Sparkles size={17} />
                <span>Generate Observation Plan</span>
              </>
            )}
          </button>
        </form>
      </section>

      {/* Results Section */}
      {result && (
        <section className="planner-results">
          {/* Summary Banner */}
          <div className="panel planner-summary-panel">
            <div className="summary-stat">
              <span>EVALUATED OBJECTS</span>
              <strong>{result.event_count || rankedEvents.length}</strong>
            </div>
            <div className="summary-divider" />
            <div className="summary-stat">
              <span>SCHEDULED PASSES</span>
              <strong>{schedule.length}</strong>
            </div>
            <div className="summary-divider" />
            <div className="summary-stat">
              <span>SESSION WINDOW</span>
              <strong>{duration} min</strong>
            </div>
            {summary.high_visibility_events_count !== undefined && (
              <>
                <div className="summary-divider" />
                <div className="summary-stat">
                  <span>HIGH VISIBILITY</span>
                  <strong style={{ color: "#58d6a0" }}>
                    {summary.high_visibility_events_count}
                  </strong>
                </div>
              </>
            )}
          </div>

          {/* Ranked Events List */}
          <div className="panel planner-events-panel">
            <div className="panel-header">
              <div>
                <div className="eyebrow">RANKED CELESTIAL TARGETS</div>
                <h3>Predicted visibility & ranking</h3>
              </div>
              <span className="panel-tag">OPTIMIZED SCHEDULE</span>
            </div>

            {rankedEvents.length === 0 ? (
              <div className="empty-catalogue" style={{ minHeight: "180px" }}>
                <Telescope size={28} />
                <h3>No observable passes found for this window</h3>
                <p>Targets may be below the horizon or daylight twilight at your chosen location.</p>
              </div>
            ) : (
              <div className="ranked-events-grid">
                {rankedEvents.map((ev, index) => {
                  const score =
                    ev.visibility_score ??
                    ev.score ??
                    ev.metadata?.derived_astronomical_values?.computed_visibility_score;
                  const name = ev.name || ev.object_name || "Target";
                  const quality =
                    ev.quality_label ||
                    (score !== null
                      ? score >= 80
                        ? "Optimal"
                        : score >= 60
                        ? "Good"
                        : score >= 40
                        ? "Fair"
                        : "Poor"
                      : "Unassessed");
                  const env = ev.environmental_conditions || {};

                  const guide = getObservationGuide(name, ev.category || ev.event_type);

                  return (
                    <div className="ranked-event-card" key={ev.event_id || index}>
                      <div className="event-card-header">
                        <div className="event-rank-pill">#{index + 1}</div>
                        <div className="event-title-group">
                          <h4>{name}</h4>
                          <span className="event-category-badge">
                            {ev.category || ev.event_type || "Celestial Body"}
                          </span>
                          <span
                            className={`equipment-badge badge-${guide.iconType}`}
                            style={{ marginTop: "3px", width: "fit-content" }}
                          >
                            {guide.iconType === "eye" && <Eye size={10} />}
                            {guide.iconType === "binoculars" && <Binoculars size={10} />}
                            {guide.iconType === "telescope" && <Telescope size={10} />}
                            {guide.iconType === "sun" && <Sun size={10} />}
                            {guide.iconType === "camera" && <Camera size={10} />}
                            <span>{guide.badge}</span>
                          </span>
                        </div>

                        {score !== null && score !== undefined && (
                          <div className={`event-score-box ${quality.toLowerCase()}`}>
                            <strong>{Math.round(score)}</strong>
                            <span>/100</span>
                            <small>{quality}</small>
                          </div>
                        )}
                      </div>

                      <div className="event-window-info">
                        <div className="window-row">
                          <Clock size={13} />
                          <span>Window:</span>
                          <strong>
                            {formatEventDate(ev.window_start || ev.start_time)} –{" "}
                            {formatEventDate(ev.window_end || ev.end_time)}
                          </strong>
                        </div>

                        {ev.duration_minutes && (
                          <div className="window-row">
                            <CheckCircle2 size={13} />
                            <span>Recommended duration:</span>
                            <strong>{Math.round(ev.duration_minutes)} minutes</strong>
                          </div>
                        )}
                      </div>

                      {/* Environmental indicators if present */}
                      {(env.temperature_celsius !== undefined || env.cloud_coverage_percent !== undefined) && (
                        <div className="event-env-row">
                          {env.cloud_coverage_percent !== undefined && (
                            <span>
                              <Cloud size={12} /> {Math.round(env.cloud_coverage_percent)}% cloud
                            </span>
                          )}
                          {env.wind_speed_kmh !== undefined && (
                            <span>
                              <Wind size={12} /> {env.wind_speed_kmh} km/h
                            </span>
                          )}
                          {env.temperature_celsius !== undefined && (
                            <span>{env.temperature_celsius}°C</span>
                          )}
                        </div>
                      )}

                      {/* Explanations or notes */}
                      {(ev.explanation || ev.notes || ev.description) && (
                        <p className="event-notes">
                          {ev.explanation || ev.notes || ev.description}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

