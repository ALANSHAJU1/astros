import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowDownWideNarrow,
  Database,
  LoaderCircle,
  RefreshCw,
  Telescope,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import BrandLogo from "../components/BrandLogo";
import ExploreFilters from "../components/explore/ExploreFilters";
import CelestialCard from "../components/explore/CelestialCard";
import CelestialDetails from "../components/explore/CelestialDetails";
import { eventService } from "../services/eventService";
import { adaptEvent } from "../services/eventAdapter";

const BASE_CATEGORIES = [
  "All Objects",
  "Sun",
  "Moon",
  "Planets",
  "Deep Sky",
  "Comets",
  "Asteroids",
  "Meteor Showers",
  "Solar Eclipses",
  "Lunar Eclipses",
];

export default function Explore() {
  const navigate = useNavigate();

  const [events, setEvents] = useState([]);
  const [activeCategory, setActiveCategory] = useState("All Objects");
  const [search, setSearch] = useState("");
  const [selectedObject, setSelectedObject] = useState(null);

  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [requiresLogin, setRequiresLogin] = useState(false);
  const [skip, setSkip] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const PAGE_SIZE = 100;

  async function loadEvents({ reset = false } = {}) {
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

      const adapted = data.map(adaptEvent);

      setEvents((previous) => reset ? adapted : [...previous, ...adapted]);
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
          "Unable to load celestial events."
        );
      }
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  useEffect(() => {
    loadEvents({ reset: true });
  }, []);

  const categories = useMemo(() => {
    const actualCategories = [...new Set(events.map((event) => event.category))]
      .filter(Boolean)
      .sort();

    return [
      "All Objects",
      ...new Set([...BASE_CATEGORIES.slice(1), ...actualCategories]),
    ];
  }, [events]);

  const filteredEvents = useMemo(() => {
    const query = search.trim().toLowerCase();

    return events.filter((event) => {
      const matchesCategory =
        activeCategory === "All Objects" ||
        event.category.toLowerCase() === activeCategory.toLowerCase();

      const eventTime = event.startTime ? new Date(event.startTime).getTime() : null;
      const matchesFrom = !dateFrom || (eventTime != null && eventTime >= new Date(`${dateFrom}T00:00:00`).getTime());
      const matchesTo = !dateTo || (eventTime != null && eventTime <= new Date(`${dateTo}T23:59:59`).getTime());

      const searchableText = [
        event.name,
        event.category,
        event.eventType,
        event.designation,
        event.externalEventId,
        event.description,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return matchesCategory && matchesFrom && matchesTo && (!query || searchableText.includes(query));
    });
  }, [events, activeCategory, search, dateFrom, dateTo]);

  return (
    <div className="page-content explore-page">
      <section className="explore-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">
            <span className="live-dot" /> CELESTIAL DISCOVERY
          </div>

          <h1>Explore the <span>cosmos.</span></h1>

          <p>
            Discover celestial events stored in AstroOS and explore
            astronomical targets for your next observation session.
          </p>

          <div className="explore-hero-stats">
            <div>
              <strong>{events.length.toString().padStart(2, "0")}</strong>
              <span>LOADED EVENTS</span>
            </div>
            <div className="hero-stat-divider" />
            <div>
              <strong>{new Set(events.map((event) => event.category)).size
                .toString().padStart(2, "0")}</strong>
              <span>EVENT CATEGORIES</span>
            </div>
          </div>
        </div>

        <div className="explore-hero-art" aria-hidden="true">
          <div className="explore-hero-orbit orbit-a" />
          <div className="explore-hero-orbit orbit-b" />
          <div className="explore-hero-planet" />
          <div className="explore-hero-star">?</div>
        </div>
      </section>

      <ExploreFilters
        categories={categories}
        activeCategory={activeCategory}
        onCategoryChange={setActiveCategory}
        search={search}
        onSearchChange={setSearch}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
      />

      <section className="catalogue-section">
        <div className="catalogue-heading">
          <div>
            <div className="eyebrow">THE ASTROOS EVENT CATALOGUE</div>
            <h2>
              {activeCategory === "All Objects"
                ? "Discover celestial events"
                : activeCategory}
            </h2>
            <p>
              Showing {filteredEvents.length} of {events.length} loaded events
            </p>
          </div>

          <div className="catalogue-sort">
            <ArrowDownWideNarrow size={15} />
            <span>Ordered by event start time</span>
          </div>
        </div>

        {loading ? (
          <div className="empty-catalogue">
            <LoaderCircle className="loading-spinner" size={30} />
            <h3>Loading celestial events</h3>
            <p>Retrieving records from the AstroOS backend...</p>
          </div>
        ) : error ? (
          <div className="empty-catalogue error-state">
            <AlertCircle size={32} />
            <h3>{requiresLogin ? "Sign in required" : "Unable to load events"}</h3>
            <p>{error}</p>

            {requiresLogin ? (
              <button className="secondary-action" onClick={() => navigate("/login")}>
                Go to login
              </button>
            ) : (
              <button className="secondary-action" onClick={() => loadEvents({ reset: true })}>
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

            {hasMore && activeCategory === "All Objects" && (
              <button
                className="load-more-button"
                onClick={() => loadEvents()}
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
              {events.length === 0
                ? "No events stored yet"
                : "No matching celestial events"}
            </h3>
            <p>
              {events.length === 0
                ? "The event API returned an empty catalogue. Events discovered by the astronomy engine are not automatically stored here."
                : "Try another category or search term."}
            </p>

            <button
              className="secondary-action"
              onClick={() => {
                setSearch("");
                setActiveCategory("All Objects");
              }}
            >
              Clear filters
            </button>
          </div>
        )}
      </section>

      <section className="explore-bottom-banner">
        <div className="banner-icon"><Telescope size={23} /></div>
        <div>
          <strong>Ready to observe the universe?</strong>
          <p>Generate an observation session using AstroOS intelligence.</p>
        </div>
        <button onClick={() => navigate("/planner")}>
          Open planner <span>?</span>
        </button>
      </section>

      <div className="explore-disclaimer">
        Event records are retrieved from the AstroOS database.
        Location-specific visibility and observation scores require assessment.
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
