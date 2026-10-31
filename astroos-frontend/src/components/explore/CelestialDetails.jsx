import {
  ArrowLeft,
  CalendarDays,
  Compass,
  Eye,
  MapPin,
  Telescope,
  X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { formatEventDate } from "../../services/eventAdapter";

export default function CelestialDetails({ object, onClose }) {
  const navigate = useNavigate();

  if (!object) return null;

  return (
    <div className="details-overlay" onMouseDown={onClose}>
      <section
        className="details-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="details-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="details-header">
          <button className="details-back" onClick={onClose}>
            <ArrowLeft size={16} /> Back to exploration
          </button>
          <button className="details-close" onClick={onClose} aria-label="Close details">
            <X size={19} />
          </button>
        </div>

        <div className={`details-hero visual-${object.visual}`}>
          <span className="details-hero-symbol">{object.symbol}</span>
          <span className="visual-orbit" />
        </div>

        <div className="details-body">
          <div className="eyebrow">{object.category} · CATALOGUE ENTRY</div>
          <h2 id="details-title">{object.name}</h2>
          <div className="details-designation">{object.designation}</div>

          <p className="details-description">{object.longDescription}</p>

          <div className="details-info-grid">
            <div className="details-info-item">
              <CalendarDays size={17} />
              <span>Start</span>
              <strong>{formatEventDate(object.startTime)}</strong>
            </div>
            <div className="details-info-item">
              <CalendarDays size={17} />
              <span>End</span>
              <strong>{formatEventDate(object.endTime)}</strong>
            </div>
            <div className="details-info-item">
              <Compass size={17} />
              <span>Classification</span>
              <strong>{object.classification || object.eventType}</strong>
            </div>
            <div className="details-info-item">
              <MapPin size={17} />
              <span>Coordinates</span>
              <strong>
                {object.latitude != null && object.longitude != null
                  ? `${object.latitude}, ${object.longitude}`
                  : "Not stored on this event"}
              </strong>
            </div>
          </div>

          <div className="details-notice">
            <Telescope size={18} />
            <div>
              <strong>Observation information</strong>
              <p>
                Catalogue records represent stored database events. Use the
                Observation Planner or Visibility Intelligence to evaluate
                live visibility scores for your observer coordinates.
              </p>
            </div>
          </div>

          <div style={{ display: "flex", gap: "10px", marginTop: "12px", flexWrap: "wrap" }}>
            <button
              className="primary-action"
              style={{ flex: "1 1 180px", justifyContent: "center" }}
              onClick={() => {
                onClose();
                navigate("/planner", {
                  state: { selectedTarget: object.name },
                });
              }}
            >
              <CalendarDays size={17} />
              Plan observation
            </button>
            <button
              className="secondary-action"
              style={{ flex: "1 1 180px", justifyContent: "center" }}
              onClick={() => {
                onClose();
                navigate("/visibility", {
                  state: { selectedEventId: object.id },
                });
              }}
            >
              <Eye size={17} />
              Assess visibility
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
