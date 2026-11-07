import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowDownWideNarrow,
  ArrowRight,
  Database,
  LoaderCircle,
  RefreshCw,
  Sparkles,
  Telescope,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import BrandLogo from "../components/BrandLogo";
import ExploreFilters from "../components/explore/ExploreFilters";
import CelestialCard from "../components/explore/CelestialCard";
import CelestialDetails from "../components/explore/CelestialDetails";
import { eventService } from "../services/eventService";
import { adaptEvent } from "../services/eventAdapter";
import { predictionService } from "../services/predictionService";
import { getObservationGuide } from "../utils/observationGuide";
import { loadObserverLocation } from "../utils/location";

const BASE_CATEGORIES = [
  "All Objects",
  "Planets",
  "Comets",
  "Asteroids",
  "Moon",
  "Deep Sky",
  "Meteor Showers",
  "Solar Eclipses",
  "Lunar Eclipses",
];

export default function Explore() {
  const location = useLocation();
  const navigate = useNavigate();

  const [databaseEvents, setDatabaseEvents] = useState([]);
  const [predictedEvents, setPredictedEvents] = useState([]);
  const [activeCategory, setActiveCategory] = useState(
    () => location.state?.category || "All Objects"
  );
  const [sourceFilter, setSourceFilter] = useState("all"); // "all" | "predicted" | "database"
  const [equipmentFilter, setEquipmentFilter] = useState("all"); // "all" | "eye" | "binoculars" | "telescope" | "sun" | "camera"
  const [search, setSearch] = useState(() => location.state?.search || "");
  const [selectedObject, setSelectedObject] = useState(null);

  useEffect(() => {
    if (location.state?.search) {
      setSearch(location.state.search);
    }
    if (location.state?.category) {
      setActiveCategory(location.state.category);
    }
  }, [location.state]);

  const [loading, setLoading] = useState(true);
  const [predicting, setPredicting] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [requiresLogin, setRequiresLogin] = useState(false);
  const [skip, setSkip] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const PAGE_SIZE = 100;

  // Load database events
  const loadDatabaseEvents = useCallback(async ({ reset = false } = {}) => {
    if (reset) {
      setLoading(true);
      setError("");
      setSkip(0);
    } else {
      setLoadingMore(true);
    }

    try {
      const offset = reset ? 0 : skip;
      const data = await eventService.getEvents({
        skip: offset,
        limit: PAGE_SIZE,
      });

      if (!Array.isArray(data)) {
        throw new Error("Unexpected event response from the backend.");
      }

      const adapted = data.map(adaptEvent).filter(Boolean);

      setDatabaseEvents((previous) => (reset ? adapted : [...previous, ...adapted]));
      setSkip(offset + data.length);
      setHasMore(data.length === PAGE_SIZE);
      setRequiresLogin(false);
    } catch (err) {
      const status = err.response?.status;
      if (status === 401 || status === 403) {
        setRequiresLogin(true);
        setError("Authentication is required to access the event catalogue.");
      } else {
        setError(
          err.response?.data?.detail ||
          err.message ||
          "Unable to load database events."
        );
      }
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [skip]);

  // Predict planets, comets, asteroids, and deep-sky objects using AstroOS Intelligence
  const loadPredictedEvents = useCallback(async () => {
    setPredicting(true);
    try {
      const now = new Date();
      const start = new Date(now.getTime() + 1000 * 60 * 60); // 1 hour ahead
      const end = new Date(start.getTime() + 1000 * 60 * 60 * 4); // 4 hour window

      const startLocal = start.toISOString().slice(0, 16);
      const endLocal = end.toISOString().slice(0, 16);

      const observer = loadObserverLocation();
      const predicted = await predictionService.getPredictedCelestialEvents({
        latitude: observer.latitude,
        longitude: observer.longitude,
        sessionStart: startLocal,
        sessionEnd: endLocal,
        categories: [
          "planets",
          "asteroids",
          "comets",
          "deep_sky",
          "meteor_showers",
          "solar_eclipses",
          "lunar_eclipses",
        ],
      });

      if (Array.isArray(predicted)) {
        setPredictedEvents(predicted);
      }
    } catch (err) {
      console.warn("Could not generate predictions:", err);
    } finally {
      setPredicting(false);
    }
  }, []);

  // Initial load: database events + predicted events
  useEffect(() => {
    loadDatabaseEvents({ reset: true });
    loadPredictedEvents();
  }, []);

  // Combined events based on sourceFilter
  const allEvents = useMemo(() => {
    if (sourceFilter === "database") {
      return databaseEvents;
    }
    if (sourceFilter === "predicted") {
      return predictedEvents;
    }

    // Merge both: prioritize predicted events for rich ephemeris scores
    const seenNames = new Set();
    const merged = [];

    for (const pe of predictedEvents) {
      const key = pe.name.toLowerCase();
      if (!seenNames.has(key)) {
        seenNames.add(key);
        merged.push(pe);
      }
    }

    for (const de of databaseEvents) {
      const key = de.name.toLowerCase();
      if (!seenNames.has(key)) {
        seenNames.add(key);
        merged.push(de);
      }
    }

    return merged;
  }, [databaseEvents, predictedEvents, sourceFilter]);

  const categories = useMemo(() => {
    const actualCategories = [...new Set(allEvents.map((event) => event.category))]
      .filter(Boolean)
      .sort();

    return [
      "All Objects",
      ...new Set([...BASE_CATEGORIES.slice(1), ...actualCategories]),
    ];
  }, [allEvents]);

  const filteredEvents = useMemo(() => {
    const query = search.trim().toLowerCase();

    return allEvents.filter((event) => {
      const matchesCategory =
        activeCategory === "All Objects" ||
        event.category.toLowerCase() === activeCategory.toLowerCase();

      const eventTime = event.startTime ? new Date(event.startTime).getTime() : null;
      const matchesFrom = !dateFrom || (eventTime != null && eventTime >= new Date(`${dateFrom}T00:00:00`).getTime());
      const matchesTo = !dateTo || (eventTime != null && eventTime <= new Date(`${dateTo}T23:59:59`).getTime());

      const guide =
        event.observationGuide ||
        getObservationGuide(
          event.name,
          event.category,
          event.magnitude,
          event.additionalData
        );
      const matchesEquipment =
        equipmentFilter === "all" ||
        (guide && guide.iconType === equipmentFilter);

      const searchableText = [
        event.name,
        event.category,
        event.eventType,
        event.designation,
        event.externalEventId,
        event.description,
        guide?.badge,
        guide?.equipmentDetail,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return (
        matchesCategory &&
        matchesEquipment &&
        matchesFrom &&
        matchesTo &&
        (!query || searchableText.includes(query))
      );
    });
  }, [allEvents, activeCategory, equipmentFilter, search, dateFrom, dateTo]);

  const predictedCount = predictedEvents.length;
  const databaseCount = databaseEvents.length;

  return (
    <div className="page-content explore-page">
      <section className="explore-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">
            <span className="live-dot" /> CELESTIAL DISCOVERY & PREDICTION
          </div>

          <h1>Explore the <span>cosmos.</span></h1>

          <p>
            Explore celestial events from the AstroOS database alongside
            live ephemeris predictions for planets, comets, asteroids, meteor showers, and deep-sky targets.
          </p>

          <div className="explore-hero-stats">
            <div>
              <strong>{allEvents.length.toString().padStart(2, "0")}</strong>
              <span>TOTAL OBJECTS</span>
            </div>
            <div className="hero-stat-divider" />
            <div>
              <strong>{predictedCount.toString().padStart(2, "0")}</strong>
              <span>PREDICTED BODIES</span>
            </div>
            <div className="hero-stat-divider" />
            <div>
              <strong>{databaseCount.toString().padStart(2, "0")}</strong>
              <span>DATABASE RECORDS</span>
            </div>
          </div>
        </div>

        <div className="explore-hero-art" aria-hidden="true">
          <div className="explore-hero-orbit orbit-a" />
          <div className="explore-hero-orbit orbit-b" />
          <div className="explore-hero-planet" />
          <div className="explore-hero-star">✦</div>
        </div>
      </section>

      <ExploreFilters
        categories={categories}
        activeCategory={activeCategory}
        onCategoryChange={setActiveCategory}
        search={search}
        onSearchChange={setSearch}
        sourceFilter={sourceFilter}
        onSourceFilterChange={setSourceFilter}
        equipmentFilter={equipmentFilter}
        onEquipmentFilterChange={setEquipmentFilter}
        onPredictClick={loadPredictedEvents}
        predicting={predicting}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
      />

      <section className="catalogue-section">
        <div className="catalogue-heading">
          <div>
            <div className="eyebrow">
              {sourceFilter === "predicted"
                ? "ASTROOS INTELLIGENCE PREDICTIONS"
                : sourceFilter === "database"
                ? "DATABASE CATALOGUE"
                : "THE ASTROOS CELESTIAL CATALOGUE"}
            </div>
            <h2>
              {activeCategory === "All Objects"
                ? "Discover celestial events"
                : activeCategory}
            </h2>
            <p>
              Showing {filteredEvents.length} of {allEvents.length} available targets
              {sourceFilter === "all" ? " (Database & Predictions combined)" : ""}
            </p>
          </div>

          <div className="catalogue-sort">
            <ArrowDownWideNarrow size={15} />
            <span>Ordered by event start time & visibility</span>
          </div>
        </div>

        {loading ? (
          <div className="empty-catalogue">
            <LoaderCircle className="loading-spinner" size={30} />
            <h3>Loading celestial events</h3>
            <p>Retrieving records from the AstroOS backend...</p>
          </div>
        ) : error && allEvents.length === 0 ? (
          <div className="empty-catalogue error-state">
            <AlertCircle size={32} />
            <h3>{requiresLogin ? "Sign in required" : "Unable to load events"}</h3>
            <p>{error}</p>

            {requiresLogin ? (
              <button className="secondary-action" onClick={() => navigate("/login")}>
                Go to login
              </button>
            ) : (
              <button
                className="secondary-action"
                onClick={() => {
                  loadDatabaseEvents({ reset: true });
                  loadPredictedEvents();
                }}
              >
                <RefreshCw size={14} /> Retry
              </button>
            )}
          </div>
        ) : filteredEvents.length > 0 ? (
          <>
            <div className="celestial-grid">
              {filteredEvents.map((event) => (
                <CelestialCard
                  key={event.id}
                  object={event}
                  onSelect={setSelectedObject}
                />
              ))}
            </div>

            {hasMore && sourceFilter !== "predicted" && activeCategory === "All Objects" && (
              <button
                className="load-more-button"
                onClick={() => loadDatabaseEvents()}
                disabled={loadingMore}
              >
                {loadingMore ? "Loading..." : "Load more events"}
              </button>
            )}
          </>
        ) : (
          <div className="empty-catalogue">
            <BrandLogo size="sm" />
            <Database size={32} />
            <h3>
              {activeCategory === "All Objects"
                ? "No celestial objects found"
                : `No matching ${activeCategory.toLowerCase()} found`}
            </h3>
            <p>
              {["Planets", "Comets", "Asteroids", "Deep Sky", "Meteor Showers", "Solar Eclipses", "Lunar Eclipses"].includes(activeCategory)
                ? `Predict ${activeCategory.toLowerCase()} for tonight using the AstroOS Intelligence Engine.`
                : "Try another category, search term, or adjust your source filter."}
            </p>

            <div style={{ display: "flex", gap: "10px", marginTop: "14px" }}>
              <button
                className="primary-action"
                onClick={loadPredictedEvents}
                disabled={predicting}
              >
                <Sparkles size={14} />
                <span>Predict {activeCategory === "All Objects" ? "Sky" : activeCategory} Now</span>
              </button>
              <button
                className="secondary-action"
                onClick={() => {
                  setSearch("");
                  setActiveCategory("All Objects");
                  setSourceFilter("all");
                  setEquipmentFilter("all");
                  setDateFrom("");
                  setDateTo("");
                }}
              >
                Clear filters
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="explore-bottom-banner">
        <div className="banner-icon"><Telescope size={23} /></div>
        <div>
          <strong>Ready to observe planets, eclipses, meteor showers, deep-sky objects, comets, or asteroids?</strong>
          <p>Generate a full multi-target observation plan with atmospheric intelligence.</p>
        </div>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <button onClick={() => navigate("/planner")}>
            Open planner <ArrowRight size={15} />
          </button>
          <button
            className="secondary-action"
            style={{ padding: "0 16px", height: "40px" }}
            onClick={() => navigate("/recommendations")}
          >
            Recommendations <Sparkles size={15} />
          </button>
        </div>
      </section>

      <div className="explore-disclaimer">
        Events include official database records and live astronomical ephemeris predictions
        (JPL Horizons & AstroOS intelligence engines). Location-specific visibility accounts
        for elevation, twilight, and atmospheric conditions.
      </div>

      {selectedObject && (
        <CelestialDetails
          object={selectedObject}
          onClose={() => setSelectedObject(null)}
        />
      )}
    </div>
  );
}
