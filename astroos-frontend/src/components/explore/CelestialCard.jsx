import { ArrowUpRight, CalendarDays } from "lucide-react";
import { formatEventDate } from "../../services/eventAdapter";

function getCelestialVisual(category = "", name = "") {
  const cat = String(category).toLowerCase();
  const n = String(name).toLowerCase();

  if (n.includes("mars")) return "mars";
  if (n.includes("saturn")) return "saturn";
  if (n.includes("venus")) return "venus";
  if (n.includes("jupiter")) return "jupiter";
  if (n.includes("moon") || cat.includes("moon") || cat.includes("lunar")) return "moon";
  if (n.includes("nebula") || cat.includes("nebula") || n.includes("orion")) return "nebula";
  if (n.includes("cluster") || cat.includes("cluster") || n.includes("pleiades")) return "cluster";
  if (n.includes("galaxy") || cat.includes("galaxy") || n.includes("andromeda") || cat.includes("deep sky")) return "galaxy";
  if (cat.includes("comet") || n.includes("comet")) return "comet";
  if (cat.includes("asteroid") || n.includes("asteroid")) return "asteroid";
  if (cat.includes("meteor") || n.includes("meteor")) return "meteor";
  if (cat.includes("eclipse") || n.includes("eclipse")) return "eclipse";
  if (cat.includes("planet")) return "jupiter";

  return "cluster";
}

export default function CelestialCard({ object, onSelect }) {
  const visualType = getCelestialVisual(object.category, object.name);

  return (
    <article className="celestial-card">
      <button
        className="celestial-card-main"
        onClick={() => onSelect({
          ...object,
          visual: visualType,
          symbol: object.externalEventId || object.name,
          longDescription: object.description,
        })}
        aria-label={`View details for ${object.name}`}
      >
        <div className={`celestial-visual visual-${visualType}`}>
          <span className="celestial-symbol">
            {object.externalEventId || object.name}
          </span>
          <span className="visual-decoration">✦</span>
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
