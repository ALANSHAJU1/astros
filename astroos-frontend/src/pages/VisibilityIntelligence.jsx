import { useState } from "react";
import {
  AlertCircle,
  Cloud,
  Compass,
  Droplets,
  Eye,
  Info,
  LoaderCircle,
  MapPin,
  RefreshCw,
  Sun,
  Thermometer,
  Wind,
} from "lucide-react";
import api from "../services/api";
import { formatEventDate } from "../services/eventAdapter";
import { toISOWithOffset } from "../services/predictionService";
import LocationPicker from "../components/LocationPicker";
import { loadObserverLocation } from "../utils/location";

export default function VisibilityIntelligence() {
  const stored = loadObserverLocation();
  const [latitude, setLatitude] = useState(stored.latitude);
  const [longitude, setLongitude] = useState(stored.longitude);
  const [locationName, setLocationName] = useState(stored.name || "");

  const [startTime, setStartTime] = useState(() => {
    const d = new Date();
    d.setHours(19, 0, 0, 0);
    return d.toISOString().slice(0, 16);
  });

  const [endTime, setEndTime] = useState(() => {
    const d = new Date();
    d.setHours(23, 0, 0, 0);
    return d.toISOString().slice(0, 16);
  });

  const [loading, setLoading] = useState(false);
  const [forecast, setForecast] = useState(null);
  const [error, setError] = useState("");
  const [permissionNotice, setPermissionNotice] = useState(false);

  async function handleFetch(e) {
    if (e) e.preventDefault();
    setLoading(true);
    setError("");
    setPermissionNotice(false);

    try {
      const payload = {
        latitude: Number(latitude),
        longitude: Number(longitude),
        start_time: toISOWithOffset(startTime),
        end_time: toISOWithOffset(endTime),
        force_refresh: false,
        persist: false,
      };

      const response = await api.post(
        "/api/v1/environmental-observations/forecast",
        payload
      );

      setForecast(response.data);
    } catch (err) {
      const status = err.response?.status;
      if (status === 403) {
        setPermissionNotice(true);
      } else {
        setError(
          err.response?.data?.detail ||
          err.message ||
          "Unable to fetch atmospheric forecast data."
        );
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-content visibility-page">
      <section className="planner-hero">
        <div className="planner-hero-content">
          <div className="eyebrow">
            <span className="live-dot" /> ATMOSPHERIC VISIBILITY ENGINE
          </div>

          <h1>Visibility <span>Intelligence.</span></h1>

          <p>
            Real-time optical transparency, cloud coverage metrics, and
            atmospheric stability forecasts powered by Open-Meteo weather intelligence.
          </p>
        </div>
      </section>

      {/* Query Form */}
      <section className="panel planner-config-panel">
        <div className="panel-header">
          <div>
            <div className="eyebrow">OBSERVER LOCATION & WINDOW</div>
            <h3>Environmental forecast request</h3>
          </div>
          <span className="panel-tag">OPEN-METEO V1</span>
        </div>

        <form onSubmit={handleFetch} className="planner-form">
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
              <label htmlFor="vis-start">Start Time</label>
              <input
                id="vis-start"
                type="datetime-local"
                required
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="vis-end">End Time</label>
              <input
                id="vis-end"
                type="datetime-local"
                required
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <div className="planner-error">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {permissionNotice && (
            <div className="permission-info-box">
              <Info size={16} />
              <div>
                <strong>Elevated Role Required for Direct Forecast Query</strong>
                <p>
                  Direct query to <code>/forecast</code> with <code>persist: false</code> requires
                  service or admin credentials. Environmental observations are automatically evaluated
                  when generating observation plans.
                </p>
              </div>
            </div>
          )}

          <button
            type="submit"
            className="planner-generate-button"
            disabled={loading}
          >
            {loading ? (
              <>
                <LoaderCircle className="loading-spinner" size={17} />
                <span>Retrieving atmospheric conditions...</span>
              </>
            ) : (
              <>
                <Cloud size={17} />
                <span>Fetch Environmental Forecast</span>
              </>
            )}
          </button>
        </form>
      </section>

      {/* Forecast Cards Display */}
      {forecast && Array.isArray(forecast) && (
        <section className="panel" style={{ marginTop: "20px" }}>
          <div className="panel-header">
            <div>
              <div className="eyebrow">ATMOSPHERIC SAMPLES</div>
              <h3>Hourly weather readings</h3>
            </div>
            <span className="panel-tag">{forecast.length} SAMPLES</span>
          </div>

          <div className="forecast-samples-grid">
            {forecast.map((item, idx) => (
              <div className="forecast-sample-card" key={item.id || idx}>
                <div className="forecast-time">
                  {formatEventDate(item.recorded_at || item.observed_at)}
                </div>

                <div className="forecast-cloud">
                  <Cloud size={20} />
                  <strong>{Math.round(item.cloud_coverage_percent ?? 0)}%</strong>
                  <span>Cloud cover</span>
                </div>

                <div className="forecast-metrics-row">
                  <div className="f-metric">
                    <Thermometer size={13} />
                    <span>{item.temperature_celsius}°C</span>
                  </div>
                  <div className="f-metric">
                    <Wind size={13} />
                    <span>{item.wind_speed_kmh} km/h</span>
                  </div>
                  <div className="f-metric">
                    <Droplets size={13} />
                    <span>{item.humidity_percent}%</span>
                  </div>
                </div>

                <div className="forecast-summary-tag">
                  {item.conditions_summary || item.freshness_status || "Stable"}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

