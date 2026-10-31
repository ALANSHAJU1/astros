import { ArrowUpRight, CalendarDays, Orbit } from "lucide-react";
import { formatEventDate } from "../../services/eventAdapter";

function getVisual(category = "") {
  const value = category.toLowerCase();

  if (value.includes("planet")) return "jupiter";
  if (value.includes("moon") || value.includes("lunar")) return "moon";
  if (value.includes("deep sky")) return "galaxy";
  if (value.includes("comet")) return "comet";
  if (value.includes("asteroid")) return "asteroid";
  if (value.includes("meteor")) return "meteor";
  if (value.includes("eclipse")) return "eclipse";

  return "cluster";
}

export default function CelestialCard({ object, onSelect }) {
  return (
    <article className="celestial-card">
      <button
        className="celestial-card-main"
        onClick={() => onSelect({
          ...object,
          visual: getVisual(object.category),
          symbol: object.externalEventId || object.name,
          longDescription: object.description,
        })}
        aria-label={`View details for ${object.name}`}
      >
        <div className={`celestial-visual visual-${getVisual(object.category)}`}>
          <span className="celestial-symbol">
            {object.externalEventId || object.name}
          </span>
          <span className="visual-decoration">?</span>
          <span className="visual-orbit" />
        </div>

        <div className="celestial-card-content">
          <div className="celestial-card-category">
            <span>{object.category}</span>
            <span className="catalogue-tag">DATABASE EVENT</span>
          </div>

          <div className="celestial-card-title">
            <h3>{object.name}</h3>
            <ArrowUpRight size={17} />
          </div>

          <p>{object.description}</p>

          <div className="celestial-card-meta">
            <span>
              <CalendarDays size={13} />
              {formatEventDate(object.startTime)}
            </span>
            <span>{object.eventType}</span>
          </div>
        </div>
      </button>
    </article>
  );
}
