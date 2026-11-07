import { getObservationGuide } from "../utils/observationGuide";

const CATEGORY_MAP = {
  planet: "Planets",
  planets: "Planets",
  planetary: "Planets",
  sun: "Sun",
  solar: "Sun",
  lunar: "Moon",
  moon: "Moon",
  deep_sky: "Deep Sky",
  "deep sky": "Deep Sky",
  "deep-sky": "Deep Sky",
  "deep_sky object": "Deep Sky",
  "deep sky object": "Deep Sky",
  "deep-sky object": "Deep Sky",
  dso: "Deep Sky",
  messier: "Deep Sky",
  galaxy: "Deep Sky",
  "spiral galaxy": "Deep Sky",
  "elliptical galaxy": "Deep Sky",
  nebula: "Deep Sky",
  "diffuse nebula": "Deep Sky",
  "planetary nebula": "Deep Sky",
  "supernova remnant": "Deep Sky",
  star_cluster: "Deep Sky",
  "star cluster": "Deep Sky",
  cluster: "Deep Sky",
  "open cluster": "Deep Sky",
  "globular cluster": "Deep Sky",
  ngc: "Deep Sky",
  ic: "Deep Sky",
  comet: "Comets",
  comets: "Comets",
  periodic_comet: "Comets",
  asteroid: "Asteroids",
  asteroids: "Asteroids",
  minor_planet: "Asteroids",
  neo: "Asteroids",
  near_earth_object: "Asteroids",
  meteor_shower: "Meteor Showers",
  "meteor shower": "Meteor Showers",
  meteor_showers: "Meteor Showers",
  meteor: "Meteor Showers",
  solar_eclipse: "Solar Eclipses",
  "solar eclipse": "Solar Eclipses",
  solar_eclipses: "Solar Eclipses",
  "solar eclipses": "Solar Eclipses",
  lunar_eclipse: "Lunar Eclipses",
  "lunar eclipse": "Lunar Eclipses",
  lunar_eclipses: "Lunar Eclipses",
  "lunar eclipses": "Lunar Eclipses",
  eclipse: "Eclipses",
  eclipses: "Eclipses",
};

const PLANET_NAMES = new Set([
  "mercury",
  "venus",
  "mars",
  "jupiter",
  "saturn",
  "uranus",
  "neptune",
]);

const ASTEROID_NAMES = new Set([
  "ceres",
  "1 ceres",
  "vesta",
  "4 vesta",
  "apophis",
  "99942 apophis",
  "eros",
  "433 eros",
  "bennu",
  "101955 bennu",
]);

const COMET_NAMES = new Set([
  "halley",
  "1p/halley",
  "neowise",
  "c/2020 f3",
  "c/2020 f3 (neowise)",
]);

const DEEP_SKY_NAMES = new Set([
  "andromeda",
  "orion nebula",
  "pleiades",
  "seven sisters",
  "hercules cluster",
  "ring nebula",
  "dumbbell",
  "whirlpool",
  "lagoon",
  "beehive",
  "praesepe",
  "crab nebula",
  "bode",
  "cigar galaxy",
  "triangulum",
  "pinwheel",
  "sombrero",
  "eagle nebula",
  "omega nebula",
  "trifid",
  "ptolemy",
]);

export function normalizeCategory(category = "", eventType = "", name = "") {
  const normCat = String(category || "").trim().toLowerCase();
  if (CATEGORY_MAP[normCat]) {
    return CATEGORY_MAP[normCat];
  }

  const normType = String(eventType || "").trim().toLowerCase();
  if (CATEGORY_MAP[normType]) {
    return CATEGORY_MAP[normType];
  }

  // Broad substring detection for deep-sky objects
  if (
    normCat.includes("deep") ||
    normCat.includes("dso") ||
    normCat.includes("galaxy") ||
    normCat.includes("nebula") ||
    normCat.includes("cluster") ||
    normCat.includes("messier") ||
    normType.includes("deep") ||
    normType.includes("dso") ||
    normType.includes("galaxy") ||
    normType.includes("nebula") ||
    normType.includes("cluster") ||
    normType.includes("messier")
  ) {
    return "Deep Sky";
  }

  // Fallback by object name if category/type is generic
  const normName = String(name || "").trim().toLowerCase();
  for (const p of PLANET_NAMES) {
    if (normName.includes(p)) return "Planets";
  }
  for (const a of ASTEROID_NAMES) {
    if (normName.includes(a)) return "Asteroids";
  }
  for (const c of COMET_NAMES) {
    if (normName.includes(c)) return "Comets";
  }
  for (const d of DEEP_SKY_NAMES) {
    if (normName.includes(d)) return "Deep Sky";
  }

  // Check Messier (e.g. M31, M42, M101) or NGC/IC patterns
  if (
    /\bm\d{1,3}\b/i.test(normName) ||
    /\bngc\s*\d+/i.test(normName) ||
    /\bic\s*\d+/i.test(normName)
  ) {
    return "Deep Sky";
  }

  // Solar & Lunar Eclipses
  if (
    normCat.includes("solar_eclipse") ||
    normCat.includes("solar eclipse") ||
    (normCat.includes("solar") && normCat.includes("eclipse")) ||
    normType.includes("solar_eclipse") ||
    normType.includes("solar eclipse") ||
    (normType.includes("solar") && normType.includes("eclipse")) ||
    (normName.includes("solar") && normName.includes("eclipse"))
  ) {
    return "Solar Eclipses";
  }

  if (
    normCat.includes("lunar_eclipse") ||
    normCat.includes("lunar eclipse") ||
    (normCat.includes("lunar") && normCat.includes("eclipse")) ||
    normType.includes("lunar_eclipse") ||
    normType.includes("lunar eclipse") ||
    (normType.includes("lunar") && normType.includes("eclipse")) ||
    (normName.includes("lunar") && normName.includes("eclipse")) ||
    normName.includes("blood moon")
  ) {
    return "Lunar Eclipses";
  }

  if (normName.includes("moon")) return "Moon";
  if (normName.includes("eclipse")) return "Solar Eclipses";
  if (normName.includes("meteor") || normName.includes("shower") || normName.includes("perseid") || normName.includes("geminid") || normName.includes("orionid") || normName.includes("leonid") || normName.includes("lyrid") || normName.includes("quadrantid")) return "Meteor Showers";

  if (!category && !eventType) {
    return "All Objects";
  }

  return (category || eventType)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function adaptEvent(event) {
  if (!event) return null;

  const additionalData = event.additional_data || event.metadata || {};
  const derived = additionalData.derived_astronomical_values || {};

  const name =
    event.object_name ||
    event.name ||
    additionalData.target_name ||
    "Celestial Object";

  const rawCat = event.category || event.event_type || event.type || "";
  const category = normalizeCategory(rawCat, event.event_type || event.type, name);

  const startTime =
    event.start_time ||
    event.window_start ||
    event.startTime ||
    derived.peak_timestamp_utc;

  const endTime =
    event.end_time ||
    event.window_end ||
    event.endTime;

  const score =
    event.visibility_score ??
    event.score ??
    derived.computed_visibility_score ??
    null;

  const qualityLabel =
    event.quality_label ||
    (score !== null
      ? score >= 80
        ? "Optimal"
        : score >= 60
        ? "Good"
        : score >= 40
        ? "Fair"
        : "Poor"
      : null);

  const altitude =
    event.altitude ??
    additionalData.peak_elevation_deg ??
    additionalData.target_altitude_deg ??
    derived.peak_elevation_deg ??
    null;

  const magnitude =
    additionalData.magnitude ??
    additionalData.visual_magnitude ??
    additionalData.apparent_magnitude ??
    null;

  const observationGuide = getObservationGuide(name, category, magnitude, additionalData);

  return {
    id: event.id || event.event_id || `evt-${name.toLowerCase().replace(/\s+/g, "-")}`,
    externalEventId: event.external_event_id || event.event_id,
    name,
    designation:
      additionalData.designation ||
      event.designation ||
      event.external_event_id ||
      event.event_id ||
      event.event_type ||
      category,
    category,
    eventType: event.event_type || event.type || category,
    startTime,
    endTime,
    latitude: event.latitude,
    longitude: event.longitude,
    additionalData,
    createdAt: event.created_at,
    score,
    qualityLabel,
    altitude,
    magnitude,
    observationGuide,
    source:
      event.source ||
      additionalData.source ||
      (event.window_start ? "AstroOS Prediction Engine" : "AstroOS Database"),
    isPredicted: Boolean(event.is_predicted || event.isPredicted || event.window_start || event.visibility_score !== undefined || derived.computed_visibility_score !== undefined),
    description:
      additionalData.description ||
      additionalData.summary ||
      derived.window_completion_note ||
      `${category} observation pass for ${name}.`,
    classification:
      additionalData.classification ||
      additionalData.planetary_defense_assessment?.orbit_class ||
      event.event_type ||
      category,
  };
}

export function formatEventDate(value) {
  if (!value) return "Date not specified";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return String(value);

  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
