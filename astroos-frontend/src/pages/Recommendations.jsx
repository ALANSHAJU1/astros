import { useState } from "react";
import { AlertCircle, LoaderCircle, Sparkles } from "lucide-react";

import BrandLogo from "../components/BrandLogo";
import { recommendationService } from "../services/recommendationService";
import { parseObservationPlan } from "../services/observationPlanService";
import { getApiErrorMessage } from "../utils/apiErrors";
import { formatDateTime, localInputToIso, toDateTimeLocalValue } from "../utils/datetime";
import { loadObserverLocation, saveObserverLocation } from "../utils/location";

function defaultWindow() {
  const start = new Date();
  start.setHours(19, 0, 0, 0);
  const end = new Date(start);
  end.setHours(22, 0, 0, 0);
  return {
    start: toDateTimeLocalValue(start),
    end: toDateTimeLocalValue(end),
  };
}

export default function Recommendations() {
  const stored = loadObserverLocation();
  const windowDefaults = defaultWindow();
  const [latitude, setLatitude] = useState(stored.latitude);
  const [longitude, setLongitude] = useState(stored.longitude);
  const [startTime, setStartTime] = useState(windowDefaults.start);
  const [endTime, setEndTime] = useState(windowDefaults.end);
  const [duration, setDuration] = useState(120);
  const [category, setCategory] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);

    const lat = Number(latitude);
    const lon = Number(longitude);
    saveObserverLocation({ latitude: lat, longitude: lon });

    try {
      const data = await recommendationService.fromDatabase({
        location: { latitude: lat, longitude: lon },
        start_time: localInputToIso(startTime),
        end_time: localInputToIso(endTime),
        available_duration_minutes: Number(duration),
        observation_goal: "general_observation",
        category: category || null,
      });
      setResult(parseObservationPlan(data.status ? data : { status: "success", recommendations: data }));
    } catch (err) {
      setError(getApiErrorMessage(err, "Catalog recommendations could not be generated."));
    } finally {
      setLoading(false);
    }
  }

  const ranked = result?.ranked || result?.details || [];

  return (
    <div className="page-content">
      <section className="explore-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">DATABASE RECOMMENDATIONS</div>
          <h1>Rank stored <span>catalogue events.</span></h1>
          <p>
            This page uses POST /api/v1/recommendations/from-database. It ranks
            events already stored in AstroOS rather than discovering live JPL targets.
          </p>
        </div>
        <BrandLogo size="panel" />
      </section>

      <form className="planner-form panel" onSubmit={handleSubmit}>
        <div className="planner-grid">
          <label>
            Latitude
            <input type="number" step="0.0001" required value={latitude} onChange={(e) => setLatitude(e.target.value)} />
          </label>
          <label>
            Longitude
            <input type="number" step="0.0001" required value={longitude} onChange={(e) => setLongitude(e.target.value)} />
          </label>
          <label>
            Start
            <input type="datetime-local" required value={startTime} onChange={(e) => setStartTime(e.target.value)} />
          </label>
          <label>
            End
            <input type="datetime-local" required value={endTime} onChange={(e) => setEndTime(e.target.value)} />
          </label>
          <label>
            Duration (minutes)
            <input type="number" min="1" max="1440" value={duration} onChange={(e) => setDuration(e.target.value)} />
          </label>
          <label>
            Category filter
            <input
              type="text"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="Optional API category, e.g. planet"
            />
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
              <LoaderCircle className="loading-spinner" size={16} /> Ranking catalogue...
            </>
          ) : (
            <>
              <Sparkles size={16} /> Rank stored events
            </>
          )}
        </button>
      </form>

      {result && (
        <div className="panel">
          <h3>Recommendation result</h3>
          {ranked.length === 0 ? (
            <p className="muted-copy">
              The database recommendation engine returned no ranked catalogue events
              for this window.
            </p>
          ) : (
            <div className="result-table">
              {ranked.map((item, index) => (
                <article className="result-row" key={item.event_id || item.id || index}>
                  <div className="result-rank">#{item.rank ?? index + 1}</div>
                  <div>
                    <strong>{item.name || item.object_name}</strong>
                    <span>{item.event_type || item.category}</span>
                  </div>
                  <div>
                    <small>Window</small>
                    <strong>{formatDateTime(item.window_start || item.start_time)}</strong>
                  </div>
                  <div>
                    <small>Score</small>
                    <strong>{item.recommendation_score ?? item.visibility_score ?? "—"}</strong>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
