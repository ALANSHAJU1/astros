import { ArrowUpRight, Binoculars, CalendarDays, Camera, Eye, Sun, Telescope } from "lucide-react";
import { formatEventDate } from "../../services/eventAdapter";
import { getObservationGuide } from "../../utils/observationGuide";
import CelestialVisual from "./CelestialVisual";

const PLANET_SYMBOLS = {
  mercury: "☿",
  venus: "♀",
  earth: "♁",
  mars: "♂",
  jupiter: "♃",
  saturn: "♄",
  uranus: "♅",
  neptune: "♆",
  moon: "☽",
};

function getObjectSymbol(name = "", symbol = "") {
  if (symbol && symbol.length <= 4) return symbol;
  const n = String(name).toLowerCase();
  for (const [planet, sym] of Object.entries(PLANET_SYMBOLS)) {
    if (n.includes(planet)) return sym;
  }
  if (n.includes("ceres")) return "⚳";
  if (n.includes("vesta")) return "⚴";
  if (n.includes("halley") || n.includes("neowise") || n.includes("comet")) return "☄";
  if (n.includes("solar eclipse") || (n.includes("solar") && n.includes("eclipse"))) return "☀️";
  if (n.includes("lunar eclipse") || (n.includes("lunar") && n.includes("eclipse")) || n.includes("blood moon")) return "🌑";
  if (n.includes("meteor") || n.includes("shower") || n.includes("perseid") || n.includes("geminid") || n.includes("orionid") || n.includes("leonid") || n.includes("lyrid")) return "🌠";
  if (n.startsWith("m") && /m\d+/i.test(n.split(" ")[0])) return n.split(" ")[0].toUpperCase();
  if (n.length <= 4) return n.toUpperCase();
  return name.slice(0, 3).toUpperCase();
}

function getCelestialVisual(category = "", name = "") {
  const cat = String(category).toLowerCase();
  const n = String(name).toLowerCase();

  if (n.includes("mars")) return "mars";
  if (n.includes("saturn")) return "saturn";
  if (n.includes("venus") || n.includes("mercury")) return "venus";
  if (n.includes("jupiter")) return "jupiter";
  if (cat.includes("eclipse") || n.includes("eclipse")) return "eclipse";
  if (n.includes("moon") || cat.includes("moon") || cat.includes("lunar")) return "moon";
  if (n.includes("nebula") || cat.includes("nebula") || n.includes("orion")) return "nebula";
  if (n.includes("cluster") || cat.includes("cluster") || n.includes("pleiades")) return "cluster";
  if (n.includes("galaxy") || cat.includes("galaxy") || n.includes("andromeda") || cat.includes("deep sky")) return "galaxy";
  if (cat.includes("comet") || n.includes("comet") || n.includes("halley") || n.includes("neowise")) return "comet";
  if (cat.includes("asteroid") || n.includes("asteroid") || n.includes("ceres") || n.includes("vesta") || n.includes("apophis")) return "asteroid";
  if (cat.includes("meteor") || n.includes("meteor")) return "meteor";
  if (cat.includes("eclipse") || n.includes("eclipse")) return "eclipse";
  if (cat.includes("planet")) return "jupiter";

  return "cluster";
}

export default function CelestialCard({ object, onSelect }) {
  const visualType = getCelestialVisual(object.category, object.name);
  const symbol = getObjectSymbol(object.name, object.additionalData?.symbol);
  const guide =
    object.observationGuide ||
    getObservationGuide(
      object.name,
      object.category,
      object.magnitude,
      object.additionalData
    );

  return (
    <article className="celestial-card">
      <button
        className="celestial-card-main"
        onClick={() =>
          onSelect({
            ...object,
            visual: visualType,
            symbol,
            observationGuide: guide,
            longDescription: object.description,
          })
        }
        aria-label={`View details for ${object.name}`}
      >
        <CelestialVisual
          object={{ ...object, visual: visualType }}
          symbol={symbol}
          size="card"
          showCredit={true}
          showScore={true}
        />

        <div className="celestial-card-content">
          <div className="celestial-card-category">
            <span>{object.category}</span>
            <span className={`catalogue-tag ${object.isPredicted ? "tag-predicted" : ""}`}>
              {object.isPredicted ? "PREDICTED PASS" : "CATALOGUE EVENT"}
            </span>
          </div>

          <div className="celestial-card-title">
            <h3>{object.name}</h3>
            <ArrowUpRight size={17} />
          </div>

          <p>{object.description}</p>

          <div className="card-equipment-row">
            <span
              className={`equipment-badge badge-${guide.iconType}`}
              title={`Equipment: ${guide.equipmentDetail}`}
            >
              {guide.iconType === "eye" && <Eye size={12} />}
              {guide.iconType === "binoculars" && <Binoculars size={12} />}
              {guide.iconType === "telescope" && <Telescope size={12} />}
              {guide.iconType === "sun" && <Sun size={12} />}
              {guide.iconType === "camera" && <Camera size={12} />}
              <span>{guide.badge}</span>
            </span>
          </div>

          <div className="celestial-card-meta">
            <span>
              <CalendarDays size={13} />
              {formatEventDate(object.startTime)}
            </span>
            <span>
              {object.qualityLabel
                ? `${object.qualityLabel} visibility`
                : object.eventType}
            </span>
          </div>
        </div>
      </button>
    </article>
  );
}
