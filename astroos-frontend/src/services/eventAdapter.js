const CATEGORY_MAP = {
  planet: "Planets",
  planets: "Planets",
  sun: "Sun",
  solar: "Sun",
  lunar: "Moon",
  moon: "Moon",
  deep_sky: "Deep Sky",
  "deep sky": "Deep Sky",
  galaxy: "Deep Sky",
  nebula: "Deep Sky",
  star_cluster: "Deep Sky",
  comet: "Comets",
  comets: "Comets",
  asteroid: "Asteroids",
  asteroids: "Asteroids",
  meteor_shower: "Meteor Showers",
  "meteor shower": "Meteor Showers",
  meteor_showers: "Meteor Showers",
  solar_eclipse: "Solar Eclipses",
  "solar eclipse": "Solar Eclipses",
  lunar_eclipse: "Lunar Eclipses",
  "lunar eclipse": "Lunar Eclipses",
};

export function normalizeCategory(category = "") {
  const normalized = category.trim().toLowerCase();
  return CATEGORY_MAP[normalized] || category
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function adaptEvent(event) {
  const additionalData = event.additional_data || {};

  return {
    id: event.id,
    externalEventId: event.external_event_id,
    name: event.object_name,
    designation:
      event.external_event_id || event.event_type || "Celestial event",
    category: normalizeCategory(event.category),
    eventType: event.event_type,
    startTime: event.start_time,
    endTime: event.end_time,
    latitude: event.latitude,
    longitude: event.longitude,
    additionalData,
    createdAt: event.created_at,
    description:
      additionalData.description ||
      additionalData.summary ||
      `${event.event_type} involving ${event.object_name}.`,
    source: additionalData.source || additionalData.provider,
    classification: additionalData.classification || event.event_type,
  };
}

export function formatEventDate(value) {
  if (!value) return "Date not specified";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Invalid date";

  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
