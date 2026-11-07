import {
  ArrowLeft,
  Binoculars,
  CalendarDays,
  Camera,
  Compass,
  Eye,
  MapPin,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Telescope,
  X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { formatEventDate } from "../../services/eventAdapter";
import { getObservationGuide } from "../../utils/observationGuide";
import CelestialVisual from "./CelestialVisual";

export default function CelestialDetails({ object, onClose }) {
  const navigate = useNavigate();

  if (!object) return null;

  const guide =
    object.observationGuide ||
    getObservationGuide(
      object.name,
      object.category,
      object.magnitude,
      object.additionalData
    );

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

        <CelestialVisual
          object={object}
          symbol={object.symbol}
          size="hero"
          showCredit={true}
          showScore={false}
        />

        <div className="details-body">
          <div className="eyebrow">{object.category} · {object.isPredicted ? "PREDICTED PASS" : "CATALOGUE ENTRY"}</div>
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
                  : "Observer location topocentric"}
              </strong>
            </div>
          </div>

          {/* Dedicated Optical Equipment & Observation Guide Section */}
          <div className="details-equipment-section">
            <div className="equipment-section-header">
              <div className="equipment-header-title">
                {guide.iconType === "eye" && <Eye size={18} className="text-accent" />}
                {guide.iconType === "binoculars" && <Binoculars size={18} className="text-accent" />}
                {guide.iconType === "telescope" && <Telescope size={18} className="text-accent" />}
                {guide.iconType === "sun" && <Sun size={18} className="text-gold" />}
                {guide.iconType === "camera" && <Camera size={18} className="text-accent" />}
                <h3>How to Observe This Celestial Event</h3>
              </div>
              <span className={`equipment-badge badge-${guide.iconType}`}>
                {guide.badge}
              </span>
            </div>

            <div className="equipment-details-grid">
              <div className="equipment-detail-box">
                <span className="equipment-label">RECOMMENDED OPTICAL AID</span>
                <strong>{guide.equipmentDetail}</strong>
              </div>

              <div className="equipment-detail-box">
                <span className="equipment-label">MAGNIFICATION</span>
                <strong>{guide.magnification}</strong>
              </div>

              <div className="equipment-detail-box">
                <span className="equipment-label">VIEWING DIFFICULTY</span>
                <strong>{guide.difficulty}</strong>
              </div>

              <div className="equipment-detail-box">
                <span className="equipment-label">IDEAL SKY CONDITIONS</span>
                <strong>{guide.bestSkyCondition}</strong>
              </div>
            </div>

            {/* Recommended Optical Accessories & Components */}
            {guide.accessories && guide.accessories.length > 0 && (
              <div className="equipment-accessories-panel">
                <div className="accessories-title">
                  <SlidersHorizontal size={14} />
                  <span>RECOMMENDED ACCESSORIES & OPTICAL COMPONENTS</span>
                </div>
                <div className="accessories-tag-list">
                  {guide.accessories.map((acc, index) => (
                    <span key={index} className="accessory-tag">
                      ✦ {acc}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* How to See Step-by-Step Instructions */}
            <div className="how-to-see-card">
              <div className="how-to-see-title">
                <Sparkles size={15} />
                <span>STEP-BY-STEP VIEWING GUIDE</span>
              </div>
              <p>{guide.howToSee}</p>
            </div>
          </div>

          <div className="details-notice">
            <Telescope size={18} />
            <div>
              <strong>Observation feasibility</strong>
              <p>
                AstroOS assesses both topocentric astronomical elevation and live
                atmospheric weather. Use the Observation Planner to generate a
                full session schedule with visibility scores.
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
                  state: {
                    selectedEventId: object.id,
                    selectedTarget: object.name,
                    selectedObject: object,
                  },
                });
              }}
            >
              <Eye size={17} />
              Assess visibility
            </button>
            <button
              className="secondary-action"
              style={{ flex: "1 1 180px", justifyContent: "center" }}
              onClick={() => {
                onClose();
                navigate("/recommendations", {
                  state: {
                    selectedTarget: object.name,
                    category: object.category,
                  },
                });
              }}
            >
              <Sparkles size={17} />
              Recommendations
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
