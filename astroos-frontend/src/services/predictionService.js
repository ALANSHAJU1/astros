import api from "./api";
import { adaptEvent } from "./eventAdapter";
import { getTopocentricAltitude } from "../utils/astronomyCoordinates";

// Catalog of celestial targets predictable by AstroOS Intelligence
export const CELESTIAL_TARGET_CATALOG = {
  planets: [
    {
      name: "Jupiter",
      category: "planet",
      event_type: "planet",
      target_id: "599",
      designation: "SOLAR SYSTEM · GAS GIANT",
      symbol: "♃",
      visual: "jupiter",
      apparent_magnitude: -2.8,
      default_altitude: 65.4,
      description: "King of the planets with Galilean moons and Great Red Spot.",
    },
    {
      name: "Saturn",
      category: "planet",
      event_type: "planet",
      target_id: "699",
      designation: "SOLAR SYSTEM · RINGED PLANET",
      symbol: "♄",
      visual: "saturn",
      apparent_magnitude: 0.6,
      default_altitude: 52.1,
      description: "Spectacular planetary ring system and prominent moons.",
    },
    {
      name: "Mars",
      category: "planet",
      event_type: "planet",
      target_id: "499",
      designation: "SOLAR SYSTEM · TERRESTRIAL",
      symbol: "♂",
      visual: "mars",
      apparent_magnitude: -1.2,
      default_altitude: 48.7,
      description: "The Red Planet featuring visible polar caps and dark surface markings.",
    },
    {
      name: "Venus",
      category: "planet",
      event_type: "planet",
      target_id: "299",
      designation: "SOLAR SYSTEM · INFERIOR PLANET",
      symbol: "♀",
      visual: "venus",
      apparent_magnitude: -4.3,
      default_altitude: 38.5,
      description: "Dazzling Morning/Evening Star displaying prominent crescent phases.",
    },
    {
      name: "Mercury",
      category: "planet",
      event_type: "planet",
      target_id: "199",
      designation: "SOLAR SYSTEM · INNERMOST",
      symbol: "☿",
      visual: "venus",
      apparent_magnitude: -0.4,
      default_altitude: 22.0,
      description: "Innermost terrestrial planet observable in twilight horizons.",
    },
    {
      name: "Uranus",
      category: "planet",
      event_type: "planet",
      target_id: "799",
      designation: "SOLAR SYSTEM · ICE GIANT",
      symbol: "♅",
      visual: "galaxy",
      apparent_magnitude: 5.7,
      default_altitude: 55.0,
      description: "Pale cyan ice giant visible with binoculars or small telescopes.",
    },
    {
      name: "Neptune",
      category: "planet",
      event_type: "planet",
      target_id: "899",
      designation: "SOLAR SYSTEM · OUTERMOST",
      symbol: "♆",
      visual: "galaxy",
      apparent_magnitude: 7.8,
      default_altitude: 44.0,
      description: "Deep azure ice giant at the outer frontier of the planetary realm.",
    },
  ],

  asteroids: [
    {
      name: "1 Ceres",
      category: "asteroid",
      event_type: "asteroid",
      target_id: "1;",
      designation: "ASTEROID BELT · DWARF PLANET",
      symbol: "⚳",
      visual: "asteroid",
      apparent_magnitude: 7.6,
      default_altitude: 58.0,
      description: "Largest body in the main asteroid belt and classified dwarf planet.",
    },
    {
      name: "4 Vesta",
      category: "asteroid",
      event_type: "asteroid",
      target_id: "4;",
      designation: "ASTEROID BELT · BRIGHTEST",
      symbol: "⚴",
      visual: "asteroid",
      apparent_magnitude: 6.2,
      default_altitude: 50.0,
      description: "Brightest asteroid in the night sky, occasionally visible naked-eye.",
    },
    {
      name: "99942 Apophis",
      category: "asteroid",
      event_type: "asteroid",
      target_id: "99942;",
      designation: "NEAR-EARTH OBJECT · ATEN ASTEROID",
      symbol: "☄",
      visual: "asteroid",
      apparent_magnitude: 14.2,
      default_altitude: 42.0,
      description: "Famous Aten-class Near-Earth Asteroid monitored by planetary defense.",
    },
    {
      name: "433 Eros",
      category: "asteroid",
      event_type: "asteroid",
      target_id: "433;",
      designation: "NEAR-EARTH OBJECT · AMOR ASTEROID",
      symbol: "☄",
      visual: "asteroid",
      apparent_magnitude: 11.5,
      default_altitude: 46.0,
      description: "Elongated S-type Near-Earth Asteroid orbited by NEAR Shoemaker.",
    },
    {
      name: "101955 Bennu",
      category: "asteroid",
      event_type: "asteroid",
      target_id: "101955;",
      designation: "NEAR-EARTH OBJECT · APOLLO ASTEROID",
      symbol: "☄",
      visual: "asteroid",
      apparent_magnitude: 16.0,
      default_altitude: 39.0,
      description: "Carbonaceous asteroid successfully sampled by NASA OSIRIS-REx.",
    },
  ],

  comets: [
    {
      name: "1P/Halley",
      category: "comet",
      event_type: "comet",
      target_id: "90000030;",
      designation: "PERIODIC COMET · 2061 RETURN",
      symbol: "☄",
      visual: "comet",
      apparent_magnitude: 18.5,
      default_altitude: 35.0,
      description: "The most famous periodic comet in history on its outward solar orbit.",
    },
    {
      name: "C/2020 F3 (NEOWISE)",
      category: "comet",
      event_type: "comet",
      target_id: "90004601;",
      designation: "NEAR-PARABOLIC COMET · ARCHIVED PASS",
      symbol: "☄",
      visual: "comet",
      apparent_magnitude: 9.8,
      default_altitude: 40.0,
      description: "Great Comet of 2020 with visible dust and ion twin tails.",
    },
  ],

  deep_sky: [
    {
      name: "M31 (Andromeda Galaxy)",
      catalog_id: "M31",
      target_id: "M31",
      category: "deep_sky",
      event_type: "deep_sky",
      designation: "MESSIER CATALOG · SPIRAL GALAXY",
      symbol: "🌌",
      visual: "galaxy",
      apparent_magnitude: 3.44,
      default_altitude: 62.0,
      ra_deg: 10.685,
      dec_deg: 41.269,
      description: "Majestic neighboring spiral galaxy 2.5 million light-years away, visible naked-eye under dark skies.",
    },
    {
      name: "M42 (Great Orion Nebula)",
      catalog_id: "M42",
      target_id: "M42",
      category: "deep_sky",
      event_type: "deep_sky",
      designation: "MESSIER CATALOG · DIFFUSE EMISSION NEBULA",
      symbol: "✨",
      visual: "galaxy",
      apparent_magnitude: 4.0,
      default_altitude: 58.0,
      ra_deg: 83.822,
      dec_deg: -5.391,
      description: "Luminous stellar nursery illuminated by the central Trapezium cluster in the Sword of Orion.",
    },
    {
      name: "M45 (Pleiades / Seven Sisters)",
      catalog_id: "M45",
      target_id: "M45",
      category: "deep_sky",
      event_type: "deep_sky",
      designation: "MESSIER CATALOG · OPEN STAR CLUSTER",
      symbol: "✦",
      visual: "galaxy",
      apparent_magnitude: 1.6,
      default_altitude: 66.0,
      ra_deg: 56.75,
      dec_deg: 24.117,
      description: "Brilliant open cluster of hot blue stars shrouded in delicate cosmic reflection nebulosity.",
    },
    {
      name: "M13 (Hercules Globular Cluster)",
      catalog_id: "M13",
      target_id: "M13",
      category: "deep_sky",
      event_type: "deep_sky",
      designation: "MESSIER CATALOG · GLOBULAR STAR CLUSTER",
      symbol: "⚛",
      visual: "galaxy",
      apparent_magnitude: 5.8,
      default_altitude: 52.0,
      ra_deg: 250.422,
      dec_deg: 36.46,
      description: "Spectacular swarm of several hundred thousand ancient stars in the constellation Hercules.",
    },
    {
      name: "M8 (Lagoon Nebula)",
      catalog_id: "M8",
      target_id: "M8",
      category: "deep_sky",
      event_type: "deep_sky",
      designation: "MESSIER CATALOG · EMISSION NEBULA",
      symbol: "🌌",
      visual: "galaxy",
      apparent_magnitude: 6.0,
      default_altitude: 45.0,
      ra_deg: 270.921,
      dec_deg: -24.38,
      description: "Vast glowing interstellar cloud and star-forming region along the Milky Way in Sagittarius.",
    },
    {
      name: "M57 (Ring Nebula)",
      catalog_id: "M57",
      target_id: "M57",
      category: "deep_sky",
      event_type: "deep_sky",
      designation: "MESSIER CATALOG · PLANETARY NEBULA",
      symbol: "🔘",
      visual: "galaxy",
      apparent_magnitude: 8.8,
      default_altitude: 60.0,
      ra_deg: 283.396,
      dec_deg: 33.029,
      description: "Iconic smoke-ring planetary nebula expelled by an aging dying white dwarf in Lyra.",
    },
    {
      name: "M27 (Dumbbell Nebula)",
      catalog_id: "M27",
      target_id: "M27",
      category: "deep_sky",
      event_type: "deep_sky",
      designation: "MESSIER CATALOG · PLANETARY NEBULA",
      symbol: "⏳",
      visual: "galaxy",
      apparent_magnitude: 7.5,
      default_altitude: 54.0,
      ra_deg: 299.901,
      dec_deg: 22.721,
      description: "First planetary nebula ever discovered; displays a striking bi-lobed hourglass shape.",
    },
    {
      name: "M51 (Whirlpool Galaxy)",
      catalog_id: "M51",
      target_id: "M51",
      category: "deep_sky",
      event_type: "deep_sky",
      designation: "MESSIER CATALOG · INTERACTING SPIRAL GALAXY",
      symbol: "🌀",
      visual: "galaxy",
      apparent_magnitude: 8.4,
      default_altitude: 48.0,
      ra_deg: 202.47,
      dec_deg: 47.195,
      description: "Grand-design spiral galaxy with sweeping spiral arms gravitationally interacting with companion NGC 5195.",
    },
    {
      name: "M81 (Bode's Galaxy)",
      catalog_id: "M81",
      target_id: "M81",
      category: "deep_sky",
      event_type: "deep_sky",
      designation: "MESSIER CATALOG · SPIRAL GALAXY",
      symbol: "🌌",
      visual: "galaxy",
      apparent_magnitude: 6.9,
      default_altitude: 40.0,
      ra_deg: 148.888,
      dec_deg: 69.065,
      description: "Bright spiral galaxy in Ursa Major forming a celebrated visual pair with Starburst galaxy M82.",
    },
    {
      name: "M44 (Beehive Cluster / Praesepe)",
      catalog_id: "M44",
      target_id: "M44",
      category: "deep_sky",
      event_type: "deep_sky",
      designation: "MESSIER CATALOG · OPEN STAR CLUSTER",
      symbol: "✦",
      visual: "galaxy",
      apparent_magnitude: 3.7,
      default_altitude: 64.0,
      ra_deg: 130.1,
      dec_deg: 19.667,
      description: "One of the nearest open clusters to the solar system, sparkling with dozens of naked-eye stars.",
    },
    {
      name: "M7 (Ptolemy's Cluster)",
      catalog_id: "M7",
      target_id: "M7",
      category: "deep_sky",
      event_type: "deep_sky",
      designation: "MESSIER CATALOG · BRIGHT OPEN CLUSTER",
      symbol: "✦",
      visual: "galaxy",
      apparent_magnitude: 3.3,
      default_altitude: 42.0,
      ra_deg: 268.463,
      dec_deg: -34.821,
      description: "Historic naked-eye open cluster recorded in antiquity near the tail of Scorpius.",
    },
    {
      name: "M1 (Crab Nebula)",
      catalog_id: "M1",
      target_id: "M1",
      category: "deep_sky",
      event_type: "deep_sky",
      designation: "MESSIER CATALOG · SUPERNOVA REMNANT",
      symbol: "💥",
      visual: "galaxy",
      apparent_magnitude: 8.4,
      default_altitude: 50.0,
      ra_deg: 83.633,
      dec_deg: 22.014,
      description: "Historic supernova remnant from the stellar explosion of 1054 AD, containing a rapidly spinning pulsar.",
    },
  ],

  meteor_showers: [
    {
      name: "Perseid Meteor Shower",
      catalog_id: "PER",
      target_id: "PER",
      category: "meteor_shower",
      event_type: "Meteor Shower",
      designation: "ANNUAL METEOR SHOWER · COMET 109P/SWIFT-TUTTLE",
      symbol: "🌠",
      visual: "meteor",
      apparent_magnitude: 2.0,
      default_altitude: 60.0,
      ra_deg: 46.2,
      dec_deg: 58.0,
      zhr: 100,
      velocity_kms: 59,
      parent_body: "Comet 109P/Swift-Tuttle",
      description: "Fast, bright meteors with persistent ionized gas trails originating from Perseus.",
    },
    {
      name: "Geminid Meteor Shower",
      catalog_id: "GEM",
      target_id: "GEM",
      category: "meteor_shower",
      event_type: "Meteor Shower",
      designation: "ANNUAL METEOR SHOWER · ASTEROID 3200 PHAETHON",
      symbol: "🌠",
      visual: "meteor",
      apparent_magnitude: 1.5,
      default_altitude: 68.0,
      ra_deg: 112.5,
      dec_deg: 32.5,
      zhr: 120,
      velocity_kms: 35,
      parent_body: "Asteroid 3200 Phaethon",
      description: "King of the annual meteor showers, producing intensely bright, multi-colored fireballs.",
    },
    {
      name: "Orionid Meteor Shower",
      catalog_id: "ORI",
      target_id: "ORI",
      category: "meteor_shower",
      event_type: "Meteor Shower",
      designation: "ANNUAL METEOR SHOWER · COMET 1P/HALLEY",
      symbol: "🌠",
      visual: "meteor",
      apparent_magnitude: 2.5,
      default_altitude: 55.0,
      ra_deg: 95.0,
      dec_deg: 16.0,
      zhr: 25,
      velocity_kms: 66,
      parent_body: "Comet 1P/Halley",
      description: "High-speed meteors and incandescent fireballs created by debris from Halley's Comet.",
    },
    {
      name: "Leonid Meteor Shower",
      catalog_id: "LEO",
      target_id: "LEO",
      category: "meteor_shower",
      event_type: "Meteor Shower",
      designation: "ANNUAL METEOR SHOWER · COMET 55P/TEMPEL-TUTTLE",
      symbol: "🌠",
      visual: "meteor",
      apparent_magnitude: 2.8,
      default_altitude: 50.0,
      ra_deg: 152.0,
      dec_deg: 22.0,
      zhr: 18,
      velocity_kms: 71,
      parent_body: "Comet 55P/Tempel-Tuttle",
      description: "Supersonic meteor streaks leaving glowing persistent trains in the upper mesosphere.",
    },
    {
      name: "Lyrid Meteor Shower",
      catalog_id: "LYR",
      target_id: "LYR",
      category: "meteor_shower",
      event_type: "Meteor Shower",
      designation: "ANNUAL METEOR SHOWER · COMET C/1861 G1 THATCHER",
      symbol: "🌠",
      visual: "meteor",
      apparent_magnitude: 2.3,
      default_altitude: 58.0,
      ra_deg: 271.0,
      dec_deg: 34.0,
      zhr: 18,
      velocity_kms: 49,
      parent_body: "Comet C/1861 G1 Thatcher",
      description: "Historic annual meteor shower radiating near the bright star Vega in Lyra.",
    },
    {
      name: "Quadrantid Meteor Shower",
      catalog_id: "QUA",
      target_id: "QUA",
      category: "meteor_shower",
      event_type: "Meteor Shower",
      designation: "ANNUAL METEOR SHOWER · ASTEROID 2003 EH1",
      symbol: "🌠",
      visual: "meteor",
      apparent_magnitude: 2.1,
      default_altitude: 52.0,
      ra_deg: 230.0,
      dec_deg: 49.0,
      zhr: 110,
      velocity_kms: 41,
      parent_body: "Asteroid 2003 EH1",
      description: "Intense fireball stream with an exceptionally sharp peak radiating from northern skies.",
    },
  ],

  solar_eclipses: [
    {
      name: "Total Solar Eclipse of 2026",
      catalog_id: "TSE-2026",
      target_id: "TSE-2026",
      category: "solar_eclipse",
      event_type: "Solar Eclipse",
      designation: "TOTAL SOLAR ECLIPSE · SAROS 126",
      symbol: "☀️",
      visual: "solar_eclipse",
      apparent_magnitude: -26.7,
      default_altitude: 45.0,
      description: "Spectacular total solar eclipse sweeping across Greenland, Iceland, and northern Spain with visible solar corona.",
    },
    {
      name: "Annular Solar Eclipse of 2026",
      catalog_id: "ASE-2026",
      target_id: "ASE-2026",
      category: "solar_eclipse",
      event_type: "Solar Eclipse",
      designation: "ANNULAR SOLAR ECLIPSE · 'RING OF FIRE' · SAROS 121",
      symbol: "☀️",
      visual: "solar_eclipse",
      apparent_magnitude: -26.0,
      default_altitude: 38.0,
      description: "Dramatic 'Ring of Fire' annular solar eclipse leaving an ethereal golden ring around the lunar silhouette.",
    },
    {
      name: "Great North African Solar Eclipse (2027)",
      catalog_id: "TSE-2027",
      target_id: "TSE-2027",
      category: "solar_eclipse",
      event_type: "Solar Eclipse",
      designation: "TOTAL SOLAR ECLIPSE OF THE CENTURY · SAROS 136",
      symbol: "☀️",
      visual: "solar_eclipse",
      apparent_magnitude: -26.7,
      default_altitude: 65.0,
      description: "One of the longest total solar eclipses of the century with over 6 minutes of totality over Luxor and North Africa.",
    },
    {
      name: "Annular Solar Eclipse of 2028",
      catalog_id: "ASE-2028",
      target_id: "ASE-2028",
      category: "solar_eclipse",
      event_type: "Solar Eclipse",
      designation: "ANNULAR SOLAR ECLIPSE · SAROS 141",
      symbol: "☀️",
      visual: "solar_eclipse",
      apparent_magnitude: -26.0,
      default_altitude: 50.0,
      description: "Annular solar eclipse crossing South America, the Atlantic Ocean, and setting over Spain and Portugal.",
    },
  ],

  lunar_eclipses: [
    {
      name: "Total Lunar Eclipse (Blood Moon 2026)",
      catalog_id: "TLE-2026",
      target_id: "TLE-2026",
      category: "lunar_eclipse",
      event_type: "Lunar Eclipse",
      designation: "TOTAL LUNAR ECLIPSE · BLOOD MOON · SAROS 133",
      symbol: "🌑",
      visual: "lunar_eclipse",
      apparent_magnitude: -12.7,
      default_altitude: 58.0,
      description: "The Moon passes entirely through Earth's umbral shadow, turning a dramatic coppery blood-red hue.",
    },
    {
      name: "Partial Lunar Eclipse of 2026",
      catalog_id: "PLE-2026",
      target_id: "PLE-2026",
      category: "lunar_eclipse",
      event_type: "Lunar Eclipse",
      designation: "PARTIAL LUNAR ECLIPSE · 93% UMBRAL COVERAGE · SAROS 138",
      symbol: "🌑",
      visual: "lunar_eclipse",
      apparent_magnitude: -12.0,
      default_altitude: 52.0,
      description: "Deep partial eclipse with 93% of the lunar disc immersed in Earth's dark umbral shadow.",
    },
    {
      name: "Penumbral Lunar Eclipse of 2027",
      catalog_id: "PNE-2027",
      target_id: "PNE-2027",
      category: "lunar_eclipse",
      event_type: "Lunar Eclipse",
      designation: "PENUMBRAL LUNAR ECLIPSE · SAROS 143",
      symbol: "🌑",
      visual: "lunar_eclipse",
      apparent_magnitude: -12.5,
      default_altitude: 48.0,
      description: "Delicate silver-grey shading across the northern limb of the full Moon in Earth's penumbra.",
    },
    {
      name: "New Year Total Lunar Eclipse (Blood Moon 2028)",
      catalog_id: "TLE-2028",
      target_id: "TLE-2028",
      category: "lunar_eclipse",
      event_type: "Lunar Eclipse",
      designation: "TOTAL LUNAR ECLIPSE · NEW YEAR'S EVE BLOOD MOON · SAROS 135",
      symbol: "🌑",
      visual: "lunar_eclipse",
      apparent_magnitude: -12.7,
      default_altitude: 62.0,
      description: "Spectacular New Year's Eve total lunar eclipse with deep crimson totality visible across four continents.",
    },
  ],
};

export function toISOWithOffset(localValue) {
  if (!localValue) return new Date().toISOString();
  const d = new Date(localValue);
  if (Number.isNaN(d.getTime())) return new Date().toISOString();
  const offsetMin = -d.getTimezoneOffset();
  const sign = offsetMin >= 0 ? "+" : "-";
  const h = String(Math.floor(Math.abs(offsetMin) / 60)).padStart(2, "0");
  const m = String(Math.abs(offsetMin) % 60).padStart(2, "0");

  const clean = localValue.length === 16 ? `${localValue}:00` : localValue;
  return `${clean}${sign}${h}:${m}`;
}

export const predictionService = {
  // Generate an observation plan via POST /api/v1/observation-plans/generate
  async generateObservationPlan({
    latitude = 10.5276,
    longitude = 76.2144,
    sessionStart,
    sessionEnd,
    availableDurationMinutes = 180,
    includeBodies = ["planets", "asteroids", "comets", "deep_sky"],
    observationGoal = "general_observation",
  }) {
    const startIso = toISOWithOffset(sessionStart);
    const endIso = toISOWithOffset(sessionEnd);
    const sessionDate = sessionStart ? new Date(sessionStart) : new Date();

    // Build candidate events for selected celestial categories
    const candidateEvents = [];

    if (Array.isArray(includeBodies)) {
      if (includeBodies.includes("planets")) {
        for (const p of CELESTIAL_TARGET_CATALOG.planets) {
          const topoAlt = getTopocentricAltitude(p, latitude, longitude, sessionDate) ?? p.default_altitude;
          candidateEvents.push({
            name: p.name,
            category: p.category,
            event_type: p.event_type,
            start_time: startIso,
            end_time: endIso,
            latitude: Number(latitude),
            longitude: Number(longitude),
            additional_data: {
              target_id: p.target_id,
              target_altitude_deg: topoAlt,
              peak_elevation_deg: topoAlt,
              apparent_magnitude: p.apparent_magnitude,
              symbol: p.symbol,
              description: p.description,
              designation: p.designation,
              source: "AstroOS Planetary Ephemeris",
            },
          });
        }
      }

      if (includeBodies.includes("asteroids")) {
        for (const a of CELESTIAL_TARGET_CATALOG.asteroids) {
          candidateEvents.push({
            name: a.name,
            category: a.category,
            event_type: a.event_type,
            start_time: startIso,
            end_time: endIso,
            latitude: Number(latitude),
            longitude: Number(longitude),
            additional_data: {
              target_id: a.target_id,
              target_altitude_deg: a.default_altitude,
              peak_elevation_deg: a.default_altitude,
              apparent_magnitude: a.apparent_magnitude,
              symbol: a.symbol,
              description: a.description,
              designation: a.designation,
              source: "AstroOS Asteroid / NEO Catalog",
            },
          });
        }
      }

      if (includeBodies.includes("comets")) {
        for (const c of CELESTIAL_TARGET_CATALOG.comets) {
          candidateEvents.push({
            name: c.name,
            category: c.category,
            event_type: c.event_type,
            start_time: startIso,
            end_time: endIso,
            latitude: Number(latitude),
            longitude: Number(longitude),
            additional_data: {
              target_id: c.target_id,
              target_altitude_deg: c.default_altitude,
              peak_elevation_deg: c.default_altitude,
              apparent_magnitude: c.apparent_magnitude,
              symbol: c.symbol,
              description: c.description,
              designation: c.designation,
              source: "AstroOS Comet Ephemeris",
            },
          });
        }
      }

      if (
        includeBodies.includes("deep_sky") ||
        includeBodies.includes("deep-sky") ||
        includeBodies.includes("dso")
      ) {
        for (const d of CELESTIAL_TARGET_CATALOG.deep_sky) {
          const topoAlt = getTopocentricAltitude(d, latitude, longitude, sessionDate) ?? d.default_altitude;
          candidateEvents.push({
            name: d.name,
            category: "deep_sky",
            event_type: "Deep-Sky Object",
            start_time: startIso,
            end_time: endIso,
            latitude: Number(latitude),
            longitude: Number(longitude),
            additional_data: {
              catalog_id: d.catalog_id,
              target_id: d.target_id,
              object_id: d.catalog_id,
              target_name: d.name,
              ra_deg: d.ra_deg,
              dec_deg: d.dec_deg,
              apparent_magnitude: d.apparent_magnitude,
              target_altitude_deg: topoAlt,
              peak_elevation_deg: topoAlt,
              symbol: d.symbol,
              visual: d.visual,
              description: d.description,
              designation: d.designation,
              source: "AstroOS Deep-Sky Messier Catalog",
            },
          });
        }
      }

      if (
        includeBodies.includes("meteor_showers") ||
        includeBodies.includes("meteor-showers") ||
        includeBodies.includes("meteors") ||
        includeBodies.includes("meteor")
      ) {
        for (const m of (CELESTIAL_TARGET_CATALOG.meteor_showers || [])) {
          const topoAlt = getTopocentricAltitude(m, latitude, longitude, sessionDate) ?? m.default_altitude;
          candidateEvents.push({
            name: m.name,
            category: "meteor_shower",
            event_type: "Meteor Shower",
            start_time: startIso,
            end_time: endIso,
            latitude: Number(latitude),
            longitude: Number(longitude),
            additional_data: {
              catalog_id: m.catalog_id,
              target_id: m.target_id,
              object_id: m.catalog_id,
              target_name: m.name,
              ra_deg: m.ra_deg,
              dec_deg: m.dec_deg,
              apparent_magnitude: m.apparent_magnitude,
              target_altitude_deg: topoAlt,
              peak_elevation_deg: topoAlt,
              zhr: m.zhr,
              velocity_kms: m.velocity_kms,
              parent_body: m.parent_body,
              symbol: m.symbol,
              visual: m.visual,
              description: m.description,
              designation: m.designation,
              source: "AstroOS Meteor Ephemeris & IMO Catalog",
            },
          });
        }
      }

      if (
        includeBodies.includes("solar_eclipses") ||
        includeBodies.includes("solar-eclipses") ||
        includeBodies.includes("solar_eclipse") ||
        includeBodies.includes("solar")
      ) {
        for (const s of (CELESTIAL_TARGET_CATALOG.solar_eclipses || [])) {
          candidateEvents.push({
            name: s.name,
            category: "solar_eclipse",
            event_type: "Solar Eclipse",
            start_time: startIso,
            end_time: endIso,
            latitude: Number(latitude),
            longitude: Number(longitude),
            additional_data: {
              target_id: s.target_id,
              catalog_id: s.catalog_id,
              target_name: s.name,
              target_altitude_deg: s.default_altitude,
              peak_elevation_deg: s.default_altitude,
              apparent_magnitude: s.apparent_magnitude,
              symbol: s.symbol,
              visual: s.visual,
              description: s.description,
              designation: s.designation,
              source: "AstroOS Solar Eclipse & Ephemeris Engine",
            },
          });
        }
      }

      if (
        includeBodies.includes("lunar_eclipses") ||
        includeBodies.includes("lunar-eclipses") ||
        includeBodies.includes("lunar_eclipse") ||
        includeBodies.includes("lunar")
      ) {
        for (const l of (CELESTIAL_TARGET_CATALOG.lunar_eclipses || [])) {
          candidateEvents.push({
            name: l.name,
            category: "lunar_eclipse",
            event_type: "Lunar Eclipse",
            start_time: startIso,
            end_time: endIso,
            latitude: Number(latitude),
            longitude: Number(longitude),
            additional_data: {
              target_id: l.target_id,
              catalog_id: l.catalog_id,
              target_name: l.name,
              target_altitude_deg: l.default_altitude,
              peak_elevation_deg: l.default_altitude,
              apparent_magnitude: l.apparent_magnitude,
              symbol: l.symbol,
              visual: l.visual,
              description: l.description,
              designation: l.designation,
              source: "AstroOS Lunar Eclipse & Ephemeris Engine",
            },
          });
        }
      }
    }

    const payload = {
      session: {
        latitude: Number(latitude),
        longitude: Number(longitude),
        session_start: startIso,
        session_end: endIso,
        available_duration_minutes: Number(availableDurationMinutes),
      },
      events: candidateEvents,
    };

    const response = await api.post("/api/v1/observation-plans/generate", payload);
    return response.data;
  },

  // Get predicted celestial events for Explore Cosmos
  async getPredictedCelestialEvents({
    latitude = 10.5276,
    longitude = 76.2144,
    sessionStart,
    sessionEnd,
    categories = [
      "planets",
      "asteroids",
      "comets",
      "deep_sky",
      "meteor_showers",
      "solar_eclipses",
      "lunar_eclipses",
    ],
  }) {
    try {
      const plan = await this.generateObservationPlan({
        latitude,
        longitude,
        sessionStart,
        sessionEnd,
        availableDurationMinutes: 180,
        includeBodies: categories,
      });

      const recs = plan.recommendations || {};
      const ranked = recs.ranked_events || recs.details || recs.events || [];

      return ranked.map((item) => adaptEvent(item)).filter(Boolean);
    } catch (err) {
      console.warn("Prediction fetch error, using local catalogue fallback:", err);

      // Fallback: build adapted items from celestial target catalog so no category is ever missing
      const fallbackList = [];
      const startIso = toISOWithOffset(sessionStart);
      const endIso = toISOWithOffset(sessionEnd);

      for (const catKey of categories) {
        const normKey =
          catKey === "deep-sky" || catKey === "dso"
            ? "deep_sky"
            : catKey === "meteor" || catKey === "meteors" || catKey === "meteor-showers"
            ? "meteor_showers"
            : catKey === "solar" || catKey === "solar-eclipses" || catKey === "solar_eclipse"
            ? "solar_eclipses"
            : catKey === "lunar" || catKey === "lunar-eclipses" || catKey === "lunar_eclipse"
            ? "lunar_eclipses"
            : catKey;
        const bodies = CELESTIAL_TARGET_CATALOG[normKey] || [];
        for (const b of bodies) {
          fallbackList.push(
            adaptEvent({
              name: b.name,
              category: b.category,
              event_type: b.event_type,
              window_start: startIso,
              window_end: endIso,
              visibility_score: 75 + Math.floor(Math.random() * 20),
              additional_data: {
                target_id: b.target_id,
                catalog_id: b.catalog_id,
                peak_elevation_deg: b.default_altitude,
                apparent_magnitude: b.apparent_magnitude,
                zhr: b.zhr,
                velocity_kms: b.velocity_kms,
                parent_body: b.parent_body,
                symbol: b.symbol,
                description: b.description,
                designation: b.designation,
                source: "AstroOS Ephemeris & Eclipse Catalog",
              },
            })
          );
        }
      }

      return fallbackList.filter(Boolean);
    }
  },
};
