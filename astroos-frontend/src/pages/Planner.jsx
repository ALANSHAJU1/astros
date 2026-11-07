import {
  AlertCircle,
  Binoculars,
  CalendarDays,
  Camera,
  CheckCircle2,
  Clock,
  Eye,
  Info,
  LoaderCircle,
  MapPin,
  Sparkles,
  Sun,
  Telescope,
  XCircle
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";

import BrandLogo from "../components/BrandLogo";
import LocationPicker from "../components/LocationPicker";
import { getCelestialImage } from "../services/celestialImages";
import { adaptEvent } from "../services/eventAdapter";
import { eventService } from "../services/eventService";
import { observationPlanService } from "../services/observationPlanService";
import { CELESTIAL_TARGET_CATALOG } from "../services/predictionService";
import { getApiErrorMessage } from "../utils/apiErrors";
import { getTopocentricAltitude } from "../utils/astronomyCoordinates";
import {
  formatClock,
  formatDateTime,
  localInputToIso,
  minutesBetween,
  toDateTimeLocalValue,
} from "../utils/datetime";
import {
  loadObserverLocation,
  saveObserverLocation,
} from "../utils/location";
import { getObservationGuide } from "../utils/observationGuide";

const GOAL_OPTIONS = [
  { value: "general", label: "General Stargazing" },
  { value: "planetary", label: "Planetary & Lunar" },
  { value: "deep_sky", label: "Deep-Sky Objects (Nebulae & Galaxies)" },
  { value: "meteor_shower", label: "Meteor Showers & Transients" },
  { value: "astrophotography", label: "Astrophotography High-Contrast" },
];

function defaultWindow() {
  const start = new Date();
  start.setMinutes(0, 0, 0);
  start.setHours(19, 0, 0, 0);
  const end = new Date(start);
  end.setHours(23, 0, 0, 0);
  return {
    start: toDateTimeLocalValue(start),
    end: toDateTimeLocalValue(end),
  };
}

function ScorePill({ value, label }) {
  if (value == null || Number.isNaN(Number(value))) {
    return (
      <span className="score-pill unavailable" title={`${label || "Score"}: Unavailable from provider`}>
        Unavailable
      </span>
    );
  }

  const num = Number(value);
  const rounded = Math.round(num);

  let tone = "fair";
  let statusText = "Fair";

  if (num >= 80) {
    tone = "optimal";
    statusText = "Optimal";
  } else if (num >= 65) {
    tone = "good";
    statusText = "Good";
  } else if (num >= 45) {
    tone = "fair";
    statusText = "Fair";
  } else if (num >= 25) {
    tone = "poor";
    statusText = "Poor";
  } else {
    tone = "unusable";
    statusText = "Unusable";
  }

  return (
    <span
      className={`score-pill ${tone}`}
      title={`${label ? label + ": " : ""}${num.toFixed(1)}/100 (${statusText})`}
    >
      {rounded}
    </span>
  );
}

export default function Planner() {
  const routerLocation = useLocation();
  const storedLocation = loadObserverLocation();
  const windowDefaults = defaultWindow();

  const [latitude, setLatitude] = useState(storedLocation.latitude);
  const [longitude, setLongitude] = useState(storedLocation.longitude);
  const [locationName, setLocationName] = useState(storedLocation.name || "");
  const [sessionStart, setSessionStart] = useState(windowDefaults.start);
  const [sessionEnd, setSessionEnd] = useState(windowDefaults.end);
  const [duration, setDuration] = useState(180);
  const [goal, setGoal] = useState("general");
  const [selectedTargetKey, setSelectedTargetKey] = useState("");
  const [catalogue, setCatalogue] = useState([]);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedTarget, setExpandedTarget] = useState(null);

  // Category inclusion checkboxes for automatic discovery
  const [includePlanets, setIncludePlanets] = useState(true);
  const [includeAsteroids, setIncludeAsteroids] = useState(true);
  const [includeComets, setIncludeComets] = useState(true);
  const [includeDeepSky, setIncludeDeepSky] = useState(true);
  const [includeMeteorShowers, setIncludeMeteorShowers] = useState(true);
  const [includeSolarEclipses, setIncludeSolarEclipses] = useState(true);
  const [includeLunarEclipses, setIncludeLunarEclipses] = useState(true);

  // Filter for rendered opportunities
  const [opportunityFilter, setOpportunityFilter] = useState("all");

  useEffect(() => {
    let active = true;
    eventService
      .getEvents({ skip: 0, limit: 100 })
      .then((data) => {
        if (!active) return;
        const adapted = Array.isArray(data) ? data.map(adaptEvent).filter(Boolean) : [];
        setCatalogue(adapted);

        const targetName = routerLocation.state?.selectedTarget;
        if (targetName) {
          // Check if in catalogue
          const match = adapted.find(
            (event) => event.name.toLowerCase() === String(targetName).toLowerCase()
          );
          if (match) {
            setSelectedTargetKey(`db_${match.id}`);
          } else {
            // Check in predicted catalog
            for (const p of CELESTIAL_TARGET_CATALOG.planets) {
              if (p.name.toLowerCase() === String(targetName).toLowerCase()) {
                setSelectedTargetKey(`pred_planet_${p.name}`);
                break;
              }
            }
            for (const a of CELESTIAL_TARGET_CATALOG.asteroids) {
              if (a.name.toLowerCase() === String(targetName).toLowerCase()) {
                setSelectedTargetKey(`pred_asteroid_${a.name}`);
                break;
              }
            }
            for (const c of CELESTIAL_TARGET_CATALOG.comets) {
              if (c.name.toLowerCase() === String(targetName).toLowerCase()) {
                setSelectedTargetKey(`pred_comet_${c.name}`);
                break;
              }
            }
            for (const d of (CELESTIAL_TARGET_CATALOG.deep_sky || [])) {
              if (
                d.name.toLowerCase().includes(String(targetName).toLowerCase()) ||
                String(targetName).toLowerCase().includes(d.name.toLowerCase()) ||
                String(targetName).toLowerCase().includes(d.catalog_id?.toLowerCase())
              ) {
                setSelectedTargetKey(`pred_deep_sky_${d.name}`);
                break;
              }
            }
            for (const m of (CELESTIAL_TARGET_CATALOG.meteor_showers || [])) {
              if (
                m.name.toLowerCase().includes(String(targetName).toLowerCase()) ||
                String(targetName).toLowerCase().includes(m.name.toLowerCase()) ||
                String(targetName).toLowerCase().includes(m.catalog_id?.toLowerCase())
              ) {
                setSelectedTargetKey(`pred_meteor_${m.name}`);
                break;
              }
            }
            for (const s of (CELESTIAL_TARGET_CATALOG.solar_eclipses || [])) {
              if (
                s.name.toLowerCase().includes(String(targetName).toLowerCase()) ||
                String(targetName).toLowerCase().includes(s.name.toLowerCase()) ||
                String(targetName).toLowerCase().includes(s.catalog_id?.toLowerCase())
              ) {
                setSelectedTargetKey(`pred_solar_${s.name}`);
                break;
              }
            }
            for (const l of (CELESTIAL_TARGET_CATALOG.lunar_eclipses || [])) {
              if (
                l.name.toLowerCase().includes(String(targetName).toLowerCase()) ||
                String(targetName).toLowerCase().includes(l.name.toLowerCase()) ||
                String(targetName).toLowerCase().includes(l.catalog_id?.toLowerCase())
              ) {
                setSelectedTargetKey(`pred_lunar_${l.name}`);
                break;
              }
            }
          }
        }
      })
      .catch(() => {
        if (active) setCatalogue([]);
      });

    return () => {
      active = false;
    };
  }, [routerLocation.state]);

  async function handleGenerate(event) {
    if (event) event.preventDefault();
    setError("");
    setPlan(null);
    setExpandedTarget(null);

    const lat = Number(latitude);
    const lon = Number(longitude);
    const startIso = localInputToIso(sessionStart);
    const endIso = localInputToIso(sessionEnd);
    const durationNum = Number(duration);

    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      setError("Please enter a valid latitude between -90 and 90.");
      return;
    }
    if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
      setError("Please enter a valid longitude between -180 and 180.");
      return;
    }
    if (!startIso || !endIso || new Date(endIso) <= new Date(startIso)) {
      setError("Session end time must be later than the session start time.");
      return;
    }
    if (!durationNum || durationNum <= 0 || durationNum > 1440) {
      setError("Available duration must be between 1 and 1440 minutes (24 hours).");
      return;
    }

    saveObserverLocation({ latitude: lat, longitude: lon, name: locationName });
    setLoading(true);

    // Build event list
    const candidateEvents = [];

    if (selectedTargetKey.startsWith("db_")) {
      const dbId = selectedTargetKey.replace("db_", "");
      const found = catalogue.find((item) => item.id === dbId);
      if (found) {
        candidateEvents.push({
          event_id: found.id,
          name: found.name,
          category: found.category,
          event_type: found.eventType,
          window_start: startIso,
          window_end: endIso,
          latitude: found.latitude ?? lat,
          longitude: found.longitude ?? lon,
        });
      }
    } else if (selectedTargetKey.startsWith("pred_")) {
      // Specific predicted target selected
      let foundBody = null;
      for (const list of Object.values(CELESTIAL_TARGET_CATALOG)) {
        foundBody = list.find((b) => selectedTargetKey.endsWith(`_${b.name}`));
        if (foundBody) break;
      }
      if (foundBody) {
        candidateEvents.push({
          name: foundBody.name,
          category: foundBody.category,
          event_type: foundBody.event_type,
          start_time: startIso,
          end_time: endIso,
          latitude: lat,
          longitude: lon,
          additional_data: {
            target_id: foundBody.target_id,
            apparent_magnitude: foundBody.apparent_magnitude,
            symbol: foundBody.symbol,
            designation: foundBody.designation,
            description: foundBody.description,
          },
        });
      }
    } else {
      const sessionDate = sessionStart ? new Date(sessionStart) : new Date();

      // Automatic discovery with option to include Planets, Comets, Asteroids
      if (includePlanets) {
        for (const p of CELESTIAL_TARGET_CATALOG.planets) {
          const topoAlt = getTopocentricAltitude(p, lat, lon, sessionDate) ?? p.default_altitude;
          candidateEvents.push({
            name: p.name,
            category: p.category,
            event_type: p.event_type,
            start_time: startIso,
            end_time: endIso,
            latitude: lat,
            longitude: lon,
            additional_data: {
              target_id: p.target_id,
              target_altitude_deg: topoAlt,
              peak_elevation_deg: topoAlt,
              apparent_magnitude: p.apparent_magnitude,
              symbol: p.symbol,
              designation: p.designation,
              description: p.description,
            },
          });
        }
      }

      if (includeAsteroids) {
        for (const a of CELESTIAL_TARGET_CATALOG.asteroids) {
          candidateEvents.push({
            name: a.name,
            category: a.category,
            event_type: a.event_type,
            start_time: startIso,
            end_time: endIso,
            latitude: lat,
            longitude: lon,
            additional_data: {
              target_id: a.target_id,
              apparent_magnitude: a.apparent_magnitude,
              symbol: a.symbol,
              designation: a.designation,
              description: a.description,
            },
          });
        }
      }

      if (includeComets) {
        for (const c of CELESTIAL_TARGET_CATALOG.comets) {
          candidateEvents.push({
            name: c.name,
            category: c.category,
            event_type: c.event_type,
            start_time: startIso,
            end_time: endIso,
            latitude: lat,
            longitude: lon,
            additional_data: {
              target_id: c.target_id,
              target_altitude_deg: c.default_altitude,
              peak_elevation_deg: c.default_altitude,
              apparent_magnitude: c.apparent_magnitude,
              symbol: c.symbol,
              designation: c.designation,
              description: c.description,
            },
          });
        }
      }

      if (includeDeepSky) {
        for (const d of (CELESTIAL_TARGET_CATALOG.deep_sky || [])) {
          const topoAlt = getTopocentricAltitude(d, lat, lon, sessionDate) ?? d.default_altitude;
          candidateEvents.push({
            name: d.name,
            category: "deep_sky",
            event_type: "Deep-Sky Object",
            start_time: startIso,
            end_time: endIso,
            latitude: lat,
            longitude: lon,
            additional_data: {
              catalog_id: d.catalog_id,
              target_id: d.target_id,
              object_id: d.catalog_id,
              target_altitude_deg: topoAlt,
              peak_elevation_deg: topoAlt,
              apparent_magnitude: d.apparent_magnitude,
              ra_deg: d.ra_deg,
              dec_deg: d.dec_deg,
              symbol: d.symbol,
              visual: d.visual,
              designation: d.designation,
              description: d.description,
            },
          });
        }
      }

      if (includeMeteorShowers) {
        for (const m of (CELESTIAL_TARGET_CATALOG.meteor_showers || [])) {
          const topoAlt = getTopocentricAltitude(m, lat, lon, sessionDate) ?? m.default_altitude;
          candidateEvents.push({
            name: m.name,
            category: "meteor_shower",
            event_type: "Meteor Shower",
            start_time: startIso,
            end_time: endIso,
            latitude: lat,
            longitude: lon,
            additional_data: {
              target_id: m.target_id,
              catalog_id: m.catalog_id,
              target_name: m.name,
              target_altitude_deg: topoAlt,
              peak_elevation_deg: topoAlt,
              apparent_magnitude: m.apparent_magnitude,
              zhr: m.zhr,
              velocity_kms: m.velocity_kms,
              parent_body: m.parent_body,
              ra_deg: m.ra_deg,
              dec_deg: m.dec_deg,
              symbol: m.symbol,
              visual: m.visual,
              designation: m.designation,
              description: m.description,
              source: "AstroOS Meteor Ephemeris & IMO Catalog",
            },
          });
        }
      }

      if (includeSolarEclipses) {
        for (const s of (CELESTIAL_TARGET_CATALOG.solar_eclipses || [])) {
          candidateEvents.push({
            name: s.name,
            category: "solar_eclipse",
            event_type: "Solar Eclipse",
            start_time: startIso,
            end_time: endIso,
            latitude: lat,
            longitude: lon,
            additional_data: {
              target_id: s.target_id,
              catalog_id: s.catalog_id,
              target_name: s.name,
              target_altitude_deg: s.default_altitude,
              peak_elevation_deg: s.default_altitude,
              apparent_magnitude: s.apparent_magnitude,
              symbol: s.symbol,
              visual: s.visual,
              designation: s.designation,
              description: s.description,
              source: "AstroOS Solar Eclipse & Ephemeris Engine",
            },
          });
        }
      }

      if (includeLunarEclipses) {
        for (const l of (CELESTIAL_TARGET_CATALOG.lunar_eclipses || [])) {
          candidateEvents.push({
            name: l.name,
            category: "lunar_eclipse",
            event_type: "Lunar Eclipse",
            start_time: startIso,
            end_time: endIso,
            latitude: lat,
            longitude: lon,
            additional_data: {
              target_id: l.target_id,
              catalog_id: l.catalog_id,
              target_name: l.name,
              target_altitude_deg: l.default_altitude,
              peak_elevation_deg: l.default_altitude,
              apparent_magnitude: l.apparent_magnitude,
              symbol: l.symbol,
              visual: l.visual,
              designation: l.designation,
              description: l.description,
              source: "AstroOS Lunar Eclipse & Ephemeris Engine",
            },
          });
        }
      }
    }

    const payload = {
      session: {
        latitude: lat,
        longitude: lon,
        session_start: startIso,
        session_end: endIso,
        available_duration_minutes: durationNum,
        observation_goal: goal,
      },
      events: candidateEvents,
    };

    try {
      const result = await observationPlanService.generate(payload);
      setPlan(result);
    } catch (err) {
      setError(
        getApiErrorMessage(
          err,
          "Unable to generate an observation plan. Check coordinates and session dates."
        )
      );
    } finally {
      setLoading(false);
    }
  }

  // Merge ranked list with enriched event details
  const rankedItems = useMemo(() => {
    if (!plan) return [];

    const detailsMap = new Map();
    for (const d of plan.details || []) {
      if (d.event_id) detailsMap.set(String(d.event_id), d);
      if (d.id) detailsMap.set(String(d.id), d);
      if (d.name) {
        detailsMap.set(String(d.name), d);
        detailsMap.set(String(d.name).toLowerCase(), d);
      }
    }

    const sourceList =
      Array.isArray(plan.ranked) && plan.ranked.length > 0
        ? plan.ranked
        : Array.isArray(plan.details)
          ? plan.details
          : [];

    const mapped = sourceList.map((sourceItem, idx) => {
      // Be defensive: an incomplete API entry should not crash the whole results list.
      const item = sourceItem || {};
      const detail =
        detailsMap.get(String(item.event_id)) ||
        detailsMap.get(String(item.id)) ||
        detailsMap.get(String(item.name)) ||
        detailsMap.get(String(item.name || "").toLowerCase()) ||
        {};
      const name =
        item.name ||
        item.object_name ||
        detail.name ||
        detail.object_name ||
        "Celestial Object";
      const key = String(
        item.event_id || item.id || detail.event_id || detail.id || name || idx
      );

      const windowStart =
        item.window_start ||
        detail.window_start ||
        item.scheduled_start ||
        detail.start_time;
      const windowEnd =
        item.window_end ||
        detail.window_end ||
        item.scheduled_end ||
        detail.end_time;

      const durationMins =
        item.duration_minutes ||
        detail.duration_minutes ||
        detail.required_duration_minutes ||
        minutesBetween(windowStart, windowEnd);

      const rawCat = detail.category || item.category || detail.event_type || item.event_type || "";
      const lowerCat = String(rawCat).toLowerCase();
      let normalizedCategory = "Deep Sky";
      if (lowerCat.includes("planet")) normalizedCategory = "Planets";
      else if (lowerCat.includes("comet")) normalizedCategory = "Comets";
      else if (lowerCat.includes("asteroid") || lowerCat.includes("neo")) normalizedCategory = "Asteroids";
      else if (lowerCat.includes("moon") || lowerCat.includes("lunar")) normalizedCategory = "Moon";
      else if (lowerCat.includes("meteor")) normalizedCategory = "Meteor Showers";
      else if (lowerCat.includes("eclipse")) normalizedCategory = "Eclipses";

      const metadata = {
        ...(detail.metadata || {}),
        ...(item.metadata || {}),
      };

      const additionalData = {
        ...(detail.additional_data || {}),
        ...(item.additional_data || {}),
      };
      const apparentMagnitude =
        additionalData.apparent_magnitude ??
        detail.apparent_magnitude ??
        item.apparent_magnitude ??
        null;
      const observationGuide = getObservationGuide(
        name,
        rawCat || normalizedCategory,
        apparentMagnitude,
        additionalData
      );

      const horizonsFacts = metadata.nasa_horizons_facts || {};
      const derivedValues = metadata.derived_astronomical_values || {};

      const peakElevation =
        horizonsFacts.peak_elevation_deg ??
        derivedValues.peak_elevation_deg ??
        additionalData.peak_elevation_deg ??
        detail.peak_elevation_deg ??
        item.peak_elevation_deg ??
        null;
      return {
        ...detail,
        ...item,
        peakElevation,
        elevationSource: peakElevation != null ? "NASA JPL Horizons" : null,
        key: key || `target-${idx}`,
        rank: item.rank ?? idx + 1,
        name,
        category: normalizedCategory,
        eventType: detail.event_type || item.event_type || normalizedCategory,
        observationGuide,
        recommendationScore:
          item.recommendation_score ?? detail.recommendation_score ?? null,
        visibilityScore:
          detail.visibility_score ?? item.visibility_score ?? null,
        weatherScore:
          detail.weather_score ??
          detail.environmental_score ??
          item.weather_score ??
          null,
        astronomicalScore:
          detail.astronomical_score ?? item.astronomical_score ?? null,
        windowStart,
        windowEnd,
        durationMinutes: durationMins,
        qualityLabel:
          detail.quality_label || item.quality_label || detail.status || null,
        assessmentStatus:
          detail.assessment_status || item.assessment_status || null,
        limitations:
          Array.isArray(detail.limitations) && detail.limitations.length > 0
            ? detail.limitations
            : Array.isArray(item.limitations)
              ? item.limitations
              : [],
        scoreBreakdown: item.score_breakdown || detail.score_breakdown || null,
      };
    });

    if (opportunityFilter === "all") {
      return mapped;
    }
    return mapped.filter((item) => item.category.toLowerCase() === opportunityFilter.toLowerCase());
  }, [plan, opportunityFilter]);

  const schedule = plan?.schedule || [];
  const skipped = plan?.skipped || [];
  const summary = plan?.summary || {};

  return (
    <div className="page-content planner-page">
      <section className="explore-hero planner-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">
            <span className="live-dot" /> OBSERVATION PLANNING & PREDICTION
          </div>
          <h1>Plan the <span>night sky.</span></h1>
          <p>
            Configure your observing coordinates, session window, and celestial goals.
            AstroOS analyzes NASA JPL Horizons ephemerides, atmospheric transparency, and
            sky mechanics to generate an optimized observation plan for planets, comets, asteroids, and deep-sky objects.
          </p>
        </div>
        <BrandLogo size="panel" />
      </section>

      <form className="planner-form panel" onSubmit={handleGenerate}>
        <div className="planner-grid">
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

          <label>
            Session start
            <input
              type="datetime-local"
              required
              value={sessionStart}
              onChange={(event) => setSessionStart(event.target.value)}
            />
          </label>

          <label>
            Session end
            <input
              type="datetime-local"
              required
              value={sessionEnd}
              onChange={(event) => setSessionEnd(event.target.value)}
            />
          </label>

          <label>
            Available duration (minutes)
            <input
              type="number"
              min="1"
              max="1440"
              required
              value={duration}
              onChange={(event) => setDuration(event.target.value)}
            />
          </label>

          <label>
            Observation goal
            <select value={goal} onChange={(event) => setGoal(event.target.value)}>
              {GOAL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          {/* Enhanced Target Selector including Planets, Comets, Asteroids */}
          <label className="span-2">
            Target selection / Focus object
            <select
              value={selectedTargetKey}
              onChange={(event) => setSelectedTargetKey(event.target.value)}
            >
              <option value="">
                ✦ Automatic Discovery (Evaluate all selected categories below)
              </option>

              <optgroup label="🪐 Major Planets (AstroOS Planetary Ephemeris)">
                {CELESTIAL_TARGET_CATALOG.planets.map((p) => (
                  <option key={p.name} value={`pred_planet_${p.name}`}>
                    {p.name} ({p.symbol}) · Planet ({p.designation})
                  </option>
                ))}
              </optgroup>

              <optgroup label="🪨 Asteroids & NEOs (JPL Horizons Small-Body Database)">
                {CELESTIAL_TARGET_CATALOG.asteroids.map((a) => (
                  <option key={a.name} value={`pred_asteroid_${a.name}`}>
                    {a.name} ({a.symbol}) · Asteroid ({a.designation})
                  </option>
                ))}
              </optgroup>

              <optgroup label="☄️ Comets (JPL Horizons Comet Ephemeris)">
                {CELESTIAL_TARGET_CATALOG.comets.map((c) => (
                  <option key={c.name} value={`pred_comet_${c.name}`}>
                    {c.name} ({c.symbol}) · Comet ({c.designation})
                  </option>
                ))}
              </optgroup>

              {CELESTIAL_TARGET_CATALOG.deep_sky && (
                <optgroup label="✨ Deep-Sky Objects (Messier Catalog & Nebulae)">
                  {CELESTIAL_TARGET_CATALOG.deep_sky.map((d) => (
                    <option key={d.name} value={`pred_deep_sky_${d.name}`}>
                      {d.name} ({d.symbol}) · {d.designation}
                    </option>
                  ))}
                </optgroup>
              )}

              {CELESTIAL_TARGET_CATALOG.meteor_showers && (
                <optgroup label="🌠 Meteor Showers (Perseids, Geminids, Orionids...)">
                  {CELESTIAL_TARGET_CATALOG.meteor_showers.map((m) => (
                    <option key={m.name} value={`pred_meteor_${m.name}`}>
                      {m.name} ({m.symbol}) · {m.designation}
                    </option>
                  ))}
                </optgroup>
              )}

              {CELESTIAL_TARGET_CATALOG.solar_eclipses && (
                <optgroup label="☀️ Solar Eclipses (Total & Annular 'Ring of Fire')">
                  {CELESTIAL_TARGET_CATALOG.solar_eclipses.map((s) => (
                    <option key={s.name} value={`pred_solar_${s.name}`}>
                      {s.name} ({s.symbol}) · {s.designation}
                    </option>
                  ))}
                </optgroup>
              )}

              {CELESTIAL_TARGET_CATALOG.lunar_eclipses && (
                <optgroup label="🌑 Lunar Eclipses (Blood Moon Totality & Partial)">
                  {CELESTIAL_TARGET_CATALOG.lunar_eclipses.map((l) => (
                    <option key={l.name} value={`pred_lunar_${l.name}`}>
                      {l.name} ({l.symbol}) · {l.designation}
                    </option>
                  ))}
                </optgroup>
              )}

              {catalogue.length > 0 && (
                <optgroup label="📚 Stored Database Records">
                  {catalogue.map((item) => (
                    <option key={item.id} value={`db_${item.id}`}>
                      {item.name} · {item.category} ({item.eventType})
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
          </label>
        </div>

        {/* Prediction Options: Checkboxes to include Planets, Comets, Asteroids, Deep Sky, Meteor Showers */}
        {!selectedTargetKey && (
          <div className="planner-target-options">
            <div className="target-options-label">
              AUTOMATIC PREDICTION TARGET CATEGORIES
            </div>
            <div className="target-options-chips">
              <label className={`target-option-box ${includePlanets ? "checked" : ""}`}>
                <input
                  type="checkbox"
                  checked={includePlanets}
                  onChange={(e) => setIncludePlanets(e.target.checked)}
                />
                <span>🪐 Predict Planets (Jupiter, Saturn, Mars, Venus, Mercury...)</span>
              </label>

              <label className={`target-option-box ${includeAsteroids ? "checked" : ""}`}>
                <input
                  type="checkbox"
                  checked={includeAsteroids}
                  onChange={(e) => setIncludeAsteroids(e.target.checked)}
                />
                <span>🪨 Predict Asteroids & NEOs (Ceres, Vesta, Apophis...)</span>
              </label>

              <label className={`target-option-box ${includeComets ? "checked" : ""}`}>
                <input
                  type="checkbox"
                  checked={includeComets}
                  onChange={(e) => setIncludeComets(e.target.checked)}
                />
                <span>☄️ Predict Comets (1P/Halley, NEOWISE...)</span>
              </label>

              <label className={`target-option-box ${includeDeepSky ? "checked" : ""}`}>
                <input
                  type="checkbox"
                  checked={includeDeepSky}
                  onChange={(e) => setIncludeDeepSky(e.target.checked)}
                />
                <span>✨ Predict Deep-Sky Objects (M31 Andromeda, M42 Orion, M45 Pleiades...)</span>
              </label>

              <label className={`target-option-box ${includeMeteorShowers ? "checked" : ""}`}>
                <input
                  type="checkbox"
                  checked={includeMeteorShowers}
                  onChange={(e) => setIncludeMeteorShowers(e.target.checked)}
                />
                <span>🌠 Predict Meteor Showers (Perseids, Geminids, Orionids...)</span>
              </label>

              <label className={`target-option-box ${includeSolarEclipses ? "checked" : ""}`}>
                <input
                  type="checkbox"
                  checked={includeSolarEclipses}
                  onChange={(e) => setIncludeSolarEclipses(e.target.checked)}
                />
                <span>☀️ Predict Solar Eclipses (Total & Annular 'Ring of Fire')</span>
              </label>

              <label className={`target-option-box ${includeLunarEclipses ? "checked" : ""}`}>
                <input
                  type="checkbox"
                  checked={includeLunarEclipses}
                  onChange={(e) => setIncludeLunarEclipses(e.target.checked)}
                />
                <span>🌑 Predict Lunar Eclipses (Blood Moon Totality & Partial)</span>
              </label>
            </div>
          </div>
        )}

        <p className="planner-hint">
          <MapPin size={14} />
          {selectedTargetKey ? (
            <span>
              Evaluating focused target <strong>{selectedTargetKey.replace(/^pred_.*?_|^db_/, "")}</strong> for
              the selected observation session.
            </span>
          ) : (
            <span>
              The AstroOS intelligence engine evaluates topocentric elevation, twilight limits,
              and atmospheric transparency for all active categories above.
            </span>
          )}
        </p>

        {error && (
          <div className="inline-alert">
            <AlertCircle size={16} /> {error}
          </div>
        )}

        <button className="login-submit planner-submit" type="submit" disabled={loading}>
          {loading ? (
            <>
              <LoaderCircle className="loading-spinner" size={16} /> Generating observation plan...
            </>
          ) : (
            <>
              <Telescope size={16} /> Generate observation plan & predictions
            </>
          )}
        </button>
      </form>

      {plan && (
        <section className="planner-results">
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-top">
                <div className="metric-icon"><Telescope size={18} /></div>
                <span className="metric-label">Evaluated targets</span>
              </div>
              <div className="metric-value">{plan.eventCount}</div>
              <div className="metric-detail">Discovered & analyzed</div>
            </div>

            <div className="metric-card">
              <div className="metric-top">
                <div className="metric-icon"><Sparkles size={18} /></div>
                <span className="metric-label">Ranked targets</span>
              </div>
              <div className="metric-value">{rankedItems.length}</div>
              <div className="metric-detail">Assessed for suitability</div>
            </div>

            <div className="metric-card">
              <div className="metric-top">
                <div className="metric-icon"><CalendarDays size={18} /></div>
                <span className="metric-label">Scheduled</span>
              </div>
              <div className="metric-value">{schedule.length}</div>
              <div className="metric-detail">Fit in available time</div>
            </div>

            <div className="metric-card">
              <div className="metric-top">
                <div className="metric-icon"><Clock size={18} /></div>
                <span className="metric-label">Scheduled time</span>
              </div>
              <div className="metric-value">
                {summary.scheduled_duration_minutes ??
                  summary.total_scheduled_minutes ??
                  schedule.reduce((acc, s) => acc + (s.duration_minutes || 0), 0)}
                <span> min</span>
              </div>
              <div className="metric-detail">
                {summary.remaining_duration_minutes != null
                  ? `${summary.remaining_duration_minutes} min remaining`
                  : `of ${duration} min session`}
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <div>
                <div className="eyebrow">RANKED OPPORTUNITIES</div>
                <h3>Astronomical targets ranked by intelligence</h3>
                <p>
                  Scores reflect composite weighting of visibility conditions,
                  environmental forecasts, and observer preference.
                </p>
              </div>

              {/* Category filter pills for ranked opportunities */}
              <div className="result-category-filter" role="group">
                {["all", "Planets", "Comets", "Asteroids", "Deep Sky", "Meteor Showers"].map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    className={`category-chip ${opportunityFilter.toLowerCase() === cat.toLowerCase() ? "selected" : ""}`}
                    onClick={() => setOpportunityFilter(cat)}
                  >
                    {cat === "all" ? "All Objects" : cat}
                  </button>
                ))}
              </div>
            </div>

            {rankedItems.length === 0 ? (
              <div className="empty-inline">
                <BrandLogo size="sm" />
                <p>No targets found matching the "{opportunityFilter}" filter for this session.</p>
              </div>
            ) : (
              <div className="result-table">
                {rankedItems.map((item) => {
                  const isExpanded = expandedTarget === item.key;
                  return (
                    <div key={item.key} className="result-item-container">
                      <article
                        className="result-row"
                        onClick={() => setExpandedTarget(isExpanded ? null : item.key)}
                        style={{ cursor: "pointer" }}
                        title="Click to view optical observation guidance and details"
                      >
                        <div className="result-rank">#{item.rank}</div>

                        <div className="result-info">
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <div
                              style={{
                                width: "24px",
                                height: "24px",
                                borderRadius: "50%",
                                overflow: "hidden",
                                flexShrink: 0,
                                border: `1px solid ${getCelestialImage(item.name, item.category).accent || "rgba(255,255,255,0.2)"}`,
                                backgroundImage: `url(${getCelestialImage(item.name, item.category).url})`,
                                backgroundSize: "cover",
                                backgroundPosition: "center",
                              }}
                              title={item.name}
                            />
                            <strong>{item.name}</strong>
                          </div>
                          <span>
                            {item.category} · {item.eventType}
                            {item.qualityLabel ? ` · ${item.qualityLabel}` : ""}
                          </span>
                          {item.observationGuide && (
                            <span
                              className={`equipment-badge badge-${item.observationGuide.iconType}`}
                              style={{ marginTop: "4px", width: "fit-content" }}
                              title={`Equipment: ${item.observationGuide.equipmentDetail}`}
                            >
                              {item.observationGuide.iconType === "eye" && <Eye size={11} />}
                              {item.observationGuide.iconType === "binoculars" && <Binoculars size={11} />}
                              {item.observationGuide.iconType === "telescope" && <Telescope size={11} />}
                              {item.observationGuide.iconType === "sun" && <Sun size={11} />}
                              {item.observationGuide.iconType === "camera" && <Camera size={11} />}
                              <span>{item.observationGuide.badge}</span>
                            </span>
                          )}
                        </div>

                        <div>
                          <small>Observation window</small>
                          <strong>
                            {formatClock(item.windowStart)}
                            {item.windowEnd ? ` – ${formatClock(item.windowEnd)}` : ""}
                          </strong>
                        </div>

                        <div>
                          <small>Duration</small>
                          <strong>{item.durationMinutes != null ? `${item.durationMinutes} min` : "—"}</strong>
                        </div>

                        <div>
                          <small>Score</small>
                          <ScorePill value={item.recommendationScore} label="Overall" />
                        </div>

                        <div>
                          <small>Visibility</small>
                          <ScorePill value={item.visibilityScore} label="Visibility" />
                        </div>

                        <div>
                          <small>Environment</small>
                          <ScorePill value={item.weatherScore} label="Weather" />
                        </div>
                      </article>

                      {isExpanded && (
                        <div className="result-expanded-details">
                          <div className="planner-equipment-guide-box">
                            <div className="planner-guide-title">
                              <span>ASTRONOMICAL POSITION</span>
                            </div>
                            <p className="planner-gear-requirement">
                              <strong>Peak elevation:</strong>{" "}
                              {item.peakElevation != null
                                ? `${Number(item.peakElevation).toFixed(2)}°`
                                : "Unavailable from JPL Horizons"}
                            </p>
                            {item.elevationSource && (
                              <p className="planner-gear-requirement">
                                <strong>Source:</strong> {item.elevationSource}
                              </p>
                            )}
                          </div>
                          {item.observationGuide && (
                            <div className="planner-equipment-guide-box">
                              <div className="planner-guide-title">
                                <Telescope size={14} />
                                <span>OBSERVATION METHOD & OPTICAL GEAR REQUIREMENTS</span>
                              </div>
                              <p className="planner-gear-requirement">
                                <strong>Recommended Aid:</strong> {item.observationGuide.equipmentDetail}
                              </p>
                              <p className="planner-gear-requirement">
                                <strong>Magnification:</strong> {item.observationGuide.magnification}
                              </p>
                              {item.observationGuide.accessories?.length > 0 && (
                                <p className="planner-accessories-list">
                                  <strong>Accessories & Components:</strong>{" "}
                                  {item.observationGuide.accessories.join(" · ")}
                                </p>
                              )}
                              <p className="planner-how-to-see">
                                <strong>How to Observe:</strong> {item.observationGuide.howToSee}
                              </p>
                            </div>
                          )}

                          {item.limitations?.length > 0 && (
                            <div className="limitations-box" style={{ marginTop: "10px" }}>
                              <div className="limitations-title">
                                <Info size={14} /> Evaluation factors & limitations:
                              </div>
                              <ul className="limitations-list">
                                {item.limitations.map((lim, idx) => (
                                  <li key={idx}>{lim}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {schedule.length > 0 && (
            <div className="panel schedule-panel">
              <div className="panel-header">
                <div>
                  <div className="eyebrow">SESSION TIMELINE</div>
                  <h3>Optimized observation schedule</h3>
                  <p>Chronologically ordered schedule maximizing observation value within session constraints.</p>
                </div>
              </div>

              <div className="result-table">
                {schedule.map((item, index) => (
                  <article className="result-row" key={item.event_id || `sched-${index}`}>
                    <div className="result-rank">
                      <CheckCircle2 size={16} className="text-emerald" />
                    </div>
                    <div>
                      <strong>{item.name}</strong>
                      <span>{item.explanation || "Scheduled by AstroOS optimizer"}</span>
                      {(() => {
                        const schedGuide = getObservationGuide(item.name, item.category);
                        return (
                          <span
                            className={`equipment-badge badge-${schedGuide.iconType}`}
                            style={{ marginTop: "4px", width: "fit-content" }}
                          >
                            {schedGuide.iconType === "eye" && <Eye size={10} />}
                            {schedGuide.iconType === "binoculars" && <Binoculars size={10} />}
                            {schedGuide.iconType === "telescope" && <Telescope size={10} />}
                            {schedGuide.iconType === "sun" && <Sun size={10} />}
                            {schedGuide.iconType === "camera" && <Camera size={10} />}
                            <span>{schedGuide.badge}</span>
                          </span>
                        );
                      })()}
                    </div>
                    <div>
                      <small>Start</small>
                      <strong>{formatDateTime(item.scheduled_start)}</strong>
                    </div>
                    <div>
                      <small>End</small>
                      <strong>{formatDateTime(item.scheduled_end)}</strong>
                    </div>
                    <div>
                      <small>Duration</small>
                      <strong>{item.duration_minutes ?? "—"} min</strong>
                    </div>
                    <div>
                      <small>Score</small>
                      <ScorePill value={item.recommendation_score} label="Score" />
                    </div>
                  </article>
                ))}
              </div>
            </div>
          )}

          {skipped.length > 0 && (
            <div className="panel skipped-panel">
              <div className="panel-header">
                <div>
                  <div className="eyebrow">UNSCHEDULED TARGETS</div>
                  <h3>Excluded opportunities</h3>
                  <p>Targets skipped due to time constraints, below-horizon geometry, or adverse weather.</p>
                </div>
              </div>

              <ul className="skipped-list">
                {skipped.map((item, index) => (
                  <li key={item.event_id || item.name || `skip-${index}`}>
                    <div className="skipped-item-header">
                      <XCircle size={15} className="text-muted" />
                      <strong>{item.name || "Target"}</strong>
                    </div>
                    <span>
                      {item.reason ||
                        item.explanation ||
                        item.rejection_reason ||
                        "Exceeded session duration or had marginal viewing conditions."}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
