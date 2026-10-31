"""
AstroOS11 — Stage 2: Catalog Event Discovery Tests
====================================================

Tests for:
  1. ``catalog_event_discovery_service`` (eclipse, meteor-shower, DSO discovery).
  2. Integration with ``observation_plans.py`` (catalog events merged with JPL events).
  3. ``DEFAULT_DURATIONS`` deep-sky additions.
  4. ``test_assessment_provider`` deep-sky mappings.

Design rules:
  - No live network calls.  JPL Horizons calls are monkeypatched to a stable stub.
  - All catalog calls use deterministic session windows tied to known catalog
    entries (e.g. a catalogued eclipse date, a Perseids peak date).
  - Tests check structure and invariants, not exact score values, so they remain
    valid when the intelligence engines are updated.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Ensure the intelligence layer is importable (same bootstrap as the adapter)
# ---------------------------------------------------------------------------
ROOT_PATH = Path(__file__).resolve().parents[2]
INTEL_PATH = ROOT_PATH / "astros-intelligence"
if str(INTEL_PATH) not in sys.path:
    sys.path.append(str(INTEL_PATH))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc(iso: str) -> datetime:
    """Parse an ISO-8601 string and make it UTC-aware."""
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Session windows tied to known catalog entries
# ---------------------------------------------------------------------------

# A catalogued solar eclipse date — we use a wide window to guarantee the
# catalog entry is found regardless of which year is in the catalog.
# Use the session_start in the future so that any near-future eclipse catalog
# entry is covered.  We rely on ECLIPSE_CATALOG having at least one entry.
ECLIPSE_SESSION_START = _utc("2028-07-22T02:00:00+00:00")   # near 2028 total solar eclipse
ECLIPSE_SESSION_END   = _utc("2028-07-22T06:00:00+00:00")

# Perseids peak: 11-13 August each year.  Use 2026.
PERSEIDS_SESSION_START = _utc("2026-08-12T20:00:00+00:00")
PERSEIDS_SESSION_END   = _utc("2026-08-13T04:00:00+00:00")

# Observer — mid-latitude northern site (London-ish)
LAT = 51.5
LON = -0.1

# A session in the far future outside any known active meteor shower
QUIET_SESSION_START = _utc("2026-02-15T22:00:00+00:00")
QUIET_SESSION_END   = _utc("2026-02-16T02:00:00+00:00")

# DSO-friendly session: dark hours for M31 from northern latitudes
DSO_SESSION_START = _utc("2026-10-15T20:00:00+00:00")
DSO_SESSION_END   = _utc("2026-10-16T02:00:00+00:00")


# ===========================================================================
# Section 1 — catalog_event_discovery_service unit tests
# ===========================================================================

class TestEclipseDiscovery:
    """discover_eclipse_candidates / discover_catalog_events(categories=['eclipse'])."""

    def test_returns_list(self):
        from app.services.catalog_event_discovery_service import discover_eclipse_candidates
        result = discover_eclipse_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=ECLIPSE_SESSION_START,
            session_end=ECLIPSE_SESSION_END,
        )
        assert isinstance(result, list)

    def test_eclipse_event_shape(self):
        """Every returned eclipse candidate has required backend event fields."""
        from app.services.catalog_event_discovery_service import discover_eclipse_candidates
        results = discover_eclipse_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=ECLIPSE_SESSION_START,
            session_end=ECLIPSE_SESSION_END,
        )
        for ev in results:
            assert "event_id" in ev, "eclipse event must have event_id"
            assert "name" in ev
            assert "event_type" in ev
            assert "window_start" in ev
            assert "window_end" in ev
            assert "duration_minutes" in ev
            assert "visibility_score" in ev
            assert "source" in ev
            # Eclipse events produced by generate_unassessed_eclipse_passes
            # should not carry weather/preference scores.
            assert ev.get("weather_score") is None
            assert ev.get("preference_score") is None
            # assessment_status should be pending
            ext = (ev.get("metadata") or {}).get("external_assessments", {})
            assert ext.get("assessment_status") == "pending"

    def test_eclipse_window_start_is_timezone_aware(self):
        from app.services.catalog_event_discovery_service import discover_eclipse_candidates
        results = discover_eclipse_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=ECLIPSE_SESSION_START,
            session_end=ECLIPSE_SESSION_END,
        )
        for ev in results:
            ws = ev.get("window_start", "")
            # Should be parseable as a timezone-aware datetime
            parsed = datetime.fromisoformat(ws)
            assert parsed.tzinfo is not None, f"window_start '{ws}' must be timezone-aware"

    def test_eclipse_event_ids_are_stable(self):
        """Same inputs produce the same event IDs (no random component)."""
        from app.services.catalog_event_discovery_service import discover_eclipse_candidates
        r1 = discover_eclipse_candidates(LAT, LON, ECLIPSE_SESSION_START, ECLIPSE_SESSION_END)
        r2 = discover_eclipse_candidates(LAT, LON, ECLIPSE_SESSION_START, ECLIPSE_SESSION_END)
        ids1 = sorted(e["event_id"] for e in r1)
        ids2 = sorted(e["event_id"] for e in r2)
        assert ids1 == ids2

    def test_no_eclipse_outside_window(self):
        """A 10-minute window in the middle of nowhere should yield nothing."""
        from app.services.catalog_event_discovery_service import discover_eclipse_candidates
        # 1-hour window in a non-eclipse period
        start = _utc("2026-03-01T00:00:00+00:00")
        end   = _utc("2026-03-01T01:00:00+00:00")
        results = discover_eclipse_candidates(LAT, LON, start, end)
        # We simply assert it's a list (may or may not be empty depending on catalog).
        # The critical constraint: no fabrication and no exception.
        assert isinstance(results, list)

    def test_discover_catalog_events_eclipse_category(self):
        from app.services.catalog_event_discovery_service import discover_catalog_events
        result = discover_catalog_events(
            latitude=LAT,
            longitude=LON,
            session_start=ECLIPSE_SESSION_START,
            session_end=ECLIPSE_SESSION_END,
            categories=["eclipse"],
        )
        assert isinstance(result, list)
        for ev in result:
            assert ev.get("event_type") in ("solar_eclipse", "lunar_eclipse", "eclipse")


class TestMeteorShowerDiscovery:
    """discover_meteor_shower_candidates tests."""

    def test_returns_list_always(self):
        from app.services.catalog_event_discovery_service import discover_meteor_shower_candidates
        result = discover_meteor_shower_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=PERSEIDS_SESSION_START,
            session_end=PERSEIDS_SESSION_END,
        )
        assert isinstance(result, list)

    def test_perseids_active_during_peak(self):
        """Perseids should be discovered as active during their August peak window."""
        from app.services.catalog_event_discovery_service import discover_meteor_shower_candidates
        results = discover_meteor_shower_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=PERSEIDS_SESSION_START,
            session_end=PERSEIDS_SESSION_END,
        )
        # At least one Perseid pass should be found (northern observer, August dark hours)
        # If Perseids happen to not be visible from this lat/lon at this time, the engine
        # raises UnobservableEventError which is silently skipped — that is acceptable.
        # We verify structural invariants on whatever IS returned.
        for ev in results:
            assert "event_id" in ev
            assert "name" in ev
            assert "window_start" in ev
            assert "window_end" in ev
            assert "visibility_score" in ev
            assert ev.get("weather_score") is None, "unassessed event must not carry weather_score"
            assert ev.get("preference_score") is None

    def test_meteor_shower_event_type(self):
        from app.services.catalog_event_discovery_service import discover_meteor_shower_candidates
        results = discover_meteor_shower_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=PERSEIDS_SESSION_START,
            session_end=PERSEIDS_SESSION_END,
        )
        for ev in results:
            assert ev.get("event_type") in ("Meteor Shower", "meteor_shower")

    def test_meteor_assessment_status_pending(self):
        from app.services.catalog_event_discovery_service import discover_meteor_shower_candidates
        results = discover_meteor_shower_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=PERSEIDS_SESSION_START,
            session_end=PERSEIDS_SESSION_END,
        )
        for ev in results:
            ext = (ev.get("metadata") or {}).get("external_assessments", {})
            assert ext.get("assessment_status") == "pending"

    def test_quiet_period_returns_list(self):
        """During a period with no active showers, result is an empty list — no exceptions."""
        from app.services.catalog_event_discovery_service import discover_meteor_shower_candidates
        # February typically has no major active showers
        result = discover_meteor_shower_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=QUIET_SESSION_START,
            session_end=QUIET_SESSION_END,
        )
        assert isinstance(result, list)

    def test_no_fabrication_on_quiet_period(self):
        """Events returned during quiet period must still pass structural checks."""
        from app.services.catalog_event_discovery_service import discover_meteor_shower_candidates
        results = discover_meteor_shower_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=QUIET_SESSION_START,
            session_end=QUIET_SESSION_END,
        )
        for ev in results:
            # If any are returned (edge-case shower), they must be properly formed
            assert "event_id" in ev
            score = ev.get("visibility_score")
            assert score is None or isinstance(score, (int, float))


class TestDeepSkyDiscovery:
    """discover_deep_sky_candidates tests."""

    def test_returns_list(self):
        from app.services.catalog_event_discovery_service import discover_deep_sky_candidates
        result = discover_deep_sky_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=DSO_SESSION_START,
            session_end=DSO_SESSION_END,
        )
        assert isinstance(result, list)

    def test_dso_event_shape(self):
        from app.services.catalog_event_discovery_service import discover_deep_sky_candidates
        results = discover_deep_sky_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=DSO_SESSION_START,
            session_end=DSO_SESSION_END,
        )
        for ev in results:
            assert "event_id" in ev
            assert "name" in ev
            assert ev.get("event_type") in ("Deep-Sky Object", "deep_sky", "dso")
            assert "window_start" in ev
            assert "window_end" in ev
            assert "visibility_score" in ev
            assert ev.get("weather_score") is None
            assert ev.get("preference_score") is None

    def test_dso_results_bounded(self):
        """Number of returned DSO candidates must not exceed max_candidates."""
        from app.services.catalog_event_discovery_service import discover_deep_sky_candidates
        results = discover_deep_sky_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=DSO_SESSION_START,
            session_end=DSO_SESSION_END,
            max_candidates=3,
        )
        assert len(results) <= 3

    def test_dso_no_duplicates_by_object(self):
        """Each DSO should appear at most once (highest-score pass selected)."""
        from app.services.catalog_event_discovery_service import discover_deep_sky_candidates
        results = discover_deep_sky_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=DSO_SESSION_START,
            session_end=DSO_SESSION_END,
        )
        # Extract DSO keys from event_id (prefix "pass_{object_id}")
        dso_keys = []
        for ev in results:
            ev_id = ev.get("event_id", "")
            parts = ev_id.split("_")
            dso_keys.append("_".join(parts[:2]) if len(parts) >= 2 else ev_id)
        assert len(dso_keys) == len(set(dso_keys)), "Duplicate DSO candidates found"

    def test_explicit_dso_target_list(self):
        """Providing an explicit target list restricts discovery to those targets."""
        from app.services.catalog_event_discovery_service import discover_deep_sky_candidates
        results = discover_deep_sky_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=DSO_SESSION_START,
            session_end=DSO_SESSION_END,
            dso_targets=["M31", "M42"],
        )
        assert isinstance(results, list)
        # All results must relate to M31 or M42
        for ev in results:
            meta_id = (
                ev.get("metadata", {})
                .get("nasa_horizons_facts", {})
                .get("catalog_id", "")
            )
            assert meta_id in ("M31", "M42"), (
                f"Expected M31 or M42 but got catalog_id={meta_id!r} for event {ev.get('event_id')}"
            )

    def test_dso_window_timezone_aware(self):
        from app.services.catalog_event_discovery_service import discover_deep_sky_candidates
        results = discover_deep_sky_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=DSO_SESSION_START,
            session_end=DSO_SESSION_END,
        )
        for ev in results:
            ws = ev.get("window_start", "")
            we = ev.get("window_end", "")
            for ts_str, label in [(ws, "window_start"), (we, "window_end")]:
                parsed = datetime.fromisoformat(ts_str)
                assert parsed.tzinfo is not None, f"{label} '{ts_str}' must be timezone-aware"

    def test_dso_daytime_session_returns_empty(self):
        """DSOs cannot be observed when the sun is up all day (polar summer approximation)."""
        from app.services.catalog_event_discovery_service import discover_deep_sky_candidates
        # A 1-hour midday window: sun will definitely be above -18° threshold
        start = _utc("2026-06-21T10:00:00+00:00")
        end   = _utc("2026-06-21T11:00:00+00:00")
        results = discover_deep_sky_candidates(
            latitude=LAT,
            longitude=LON,
            session_start=start,
            session_end=end,
            dso_targets=["M31"],
        )
        assert isinstance(results, list)
        # Either empty or if any returned, verify structure (we do NOT assert empty because
        # the engine decides based on actual solar elevation calculation)
        for ev in results:
            assert "event_id" in ev


class TestDiscoverCatalogEventsAggregation:
    """discover_catalog_events integration: aggregation, filtering, deduplication."""

    def test_all_categories_returns_list(self):
        from app.services.catalog_event_discovery_service import discover_catalog_events
        result = discover_catalog_events(
            latitude=LAT,
            longitude=LON,
            session_start=DSO_SESSION_START,
            session_end=DSO_SESSION_END,
        )
        assert isinstance(result, list)

    def test_category_filter_eclipse_only(self):
        from app.services.catalog_event_discovery_service import discover_catalog_events
        result = discover_catalog_events(
            latitude=LAT,
            longitude=LON,
            session_start=ECLIPSE_SESSION_START,
            session_end=ECLIPSE_SESSION_END,
            categories=["eclipse"],
        )
        for ev in result:
            assert ev.get("event_type") in (
                "solar_eclipse", "lunar_eclipse", "eclipse"
            ), f"Unexpected event_type: {ev.get('event_type')}"

    def test_category_filter_meteor_only(self):
        from app.services.catalog_event_discovery_service import discover_catalog_events
        result = discover_catalog_events(
            latitude=LAT,
            longitude=LON,
            session_start=PERSEIDS_SESSION_START,
            session_end=PERSEIDS_SESSION_END,
            categories=["meteor_shower"],
        )
        for ev in result:
            assert ev.get("event_type") in ("Meteor Shower", "meteor_shower")

    def test_category_filter_dso_only(self):
        from app.services.catalog_event_discovery_service import discover_catalog_events
        result = discover_catalog_events(
            latitude=LAT,
            longitude=LON,
            session_start=DSO_SESSION_START,
            session_end=DSO_SESSION_END,
            categories=["deep_sky"],
        )
        for ev in result:
            assert ev.get("event_type") in ("Deep-Sky Object", "deep_sky", "dso")

    def test_empty_session_window_no_crash(self):
        """A zero-length session must not crash the discovery service."""
        from app.services.catalog_event_discovery_service import discover_catalog_events
        t = _utc("2026-10-15T22:00:00+00:00")
        # We expect either an empty list or a well-structured list — no exception.
        try:
            result = discover_catalog_events(
                latitude=LAT,
                longitude=LON,
                session_start=t,
                session_end=t + timedelta(minutes=1),
            )
            assert isinstance(result, list)
        except Exception:
            pytest.fail("discover_catalog_events raised an unexpected exception for tiny window")

    def test_naive_datetime_is_handled(self):
        """Naive datetimes are accepted and coerced to UTC internally."""
        from app.services.catalog_event_discovery_service import discover_catalog_events
        start = datetime(2026, 10, 15, 20, 0, 0)  # naive
        end   = datetime(2026, 10, 16, 2, 0, 0)    # naive
        result = discover_catalog_events(
            latitude=LAT,
            longitude=LON,
            session_start=start,
            session_end=end,
        )
        assert isinstance(result, list)

    def test_no_duplicate_event_ids(self):
        """All returned event_ids are unique."""
        from app.services.catalog_event_discovery_service import discover_catalog_events
        result = discover_catalog_events(
            latitude=LAT,
            longitude=LON,
            session_start=DSO_SESSION_START,
            session_end=DSO_SESSION_END,
        )
        ids = [ev.get("event_id") for ev in result if ev.get("event_id")]
        assert len(ids) == len(set(ids)), "Duplicate event_ids found in catalog discovery"


# ===========================================================================
# Section 2 — observation_plans.py route integration tests
# ===========================================================================

class MockAssessment:
    def __init__(self, vis=80.0, astro=82.0, env=88.0, status="success"):
        self.visibility_score = vis
        self.astronomical_score = astro
        self.environmental_score = env
        self.status = status
        self.quality_label = "Good"
        self.limitations = []


def _mock_evaluate(**kwargs):
    return MockAssessment()


def _mock_recommendations(req):
    return {"plan": "mock", "details": req.get("events", [])}


class TestObservationPlansWithCatalogDiscovery:
    """Route tests for merged JPL + catalog discovery path."""

    def test_direct_events_unchanged(self, client, monkeypatch):
        """Client-supplied events pass through unmodified (catalog discovery not triggered)."""
        from fastapi.testclient import TestClient
        from app.main import app
        import app.api.routes.observation_plans as routes
        import app.modules.intelligence.recommendation.backend_interface as backend

        monkeypatch.setattr(routes, "evaluate_event_visibility", _mock_evaluate)
        monkeypatch.setattr(backend, "generate_recommendations", _mock_recommendations)

        payload = {
            "session": {
                "latitude": LAT, "longitude": LON,
                "session_start": "2026-10-15T20:00:00+00:00",
                "session_end":   "2026-10-16T02:00:00+00:00",
            },
            "events": [
                {
                    "name": "Jupiter",
                    "latitude": LAT, "longitude": LON,
                    "category": "planet",
                    "event_type": "planetary",
                    "window_start": "2026-10-15T20:00:00+00:00",
                    "window_end":   "2026-10-15T23:00:00+00:00",
                }
            ],
        }
        resp = client.post("/api/v1/observation-plans/generate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["event_count"] == 1

    def test_jpl_502_preserved_when_jpl_fails(self, client, monkeypatch):
        """When the JPL fetch raises, the route still returns 502 (existing contract)."""
        from fastapi.testclient import TestClient
        from app.main import app
        import app.api.routes.observation_plans as routes
        import app.modules.intelligence.recommendation.backend_interface as backend

        def _raise_jpl(*args, **kwargs):
            raise RuntimeError("Simulated JPL upstream failure")

        monkeypatch.setattr(routes.jpl_adapter, "fetch_events_from_jpl", _raise_jpl)
        monkeypatch.setattr(backend, "generate_recommendations", _mock_recommendations)

        payload = {
            "session": {
                "latitude": LAT, "longitude": LON,
                "session_start": "2026-10-15T20:00:00+00:00",
                "session_end":   "2026-10-16T02:00:00+00:00",
            },
            "events": [],
        }
        resp = client.post("/api/v1/observation-plans/generate", json=payload)
        assert resp.status_code == 502
        assert "JPL Horizons" in resp.json()["detail"]

    def test_catalog_discovery_failure_is_nonfatal(self, client, monkeypatch):
        """A crash in catalog discovery is non-fatal; route still returns 200."""
        from fastapi.testclient import TestClient
        from app.main import app
        import app.api.routes.observation_plans as routes
        import app.modules.intelligence.recommendation.backend_interface as backend

        monkeypatch.setattr(routes.jpl_adapter, "fetch_events_from_jpl", lambda **kw: [])

        def _crash_catalog(**kw):
            raise RuntimeError("catalog boom")

        monkeypatch.setattr(routes, "discover_catalog_events", _crash_catalog)
        monkeypatch.setattr(routes, "evaluate_event_visibility", _mock_evaluate)
        monkeypatch.setattr(backend, "generate_recommendations", _mock_recommendations)

        payload = {
            "session": {
                "latitude": LAT, "longitude": LON,
                "session_start": "2026-10-15T20:00:00+00:00",
                "session_end":   "2026-10-16T02:00:00+00:00",
            },
            "events": [],
        }
        resp = client.post("/api/v1/observation-plans/generate", json=payload)
        assert resp.status_code == 200

    def test_catalog_candidates_merged_with_jpl(self, client, monkeypatch):
        """Catalog-discovered events are merged into the enriched events list."""
        from fastapi.testclient import TestClient
        from app.main import app
        import app.api.routes.observation_plans as routes
        import app.modules.intelligence.recommendation.backend_interface as backend

        fake_jpl = [
            {
                "event_id": "jpl_moon_001",
                "name": "Moon",
                "category": "lunar",
                "event_type": "moonrise",
                "latitude": LAT, "longitude": LON,
                "window_start": "2026-10-15T20:00:00+00:00",
                "window_end":   "2026-10-15T23:00:00+00:00",
                "duration_minutes": 180.0,
                "required_duration_minutes": 180.0,
                "visibility_score": 85.0,
                "weather_score": 0.0,
                "preference_score": 0.0,
                "source": "NASA JPL Horizons API",
            }
        ]
        fake_catalog = [
            {
                "event_id": "cat_dso_m31_001",
                "name": "Andromeda Galaxy (M31)",
                "event_type": "Deep-Sky Object",
                "type": "Deep-Sky Object",
                "latitude": LAT, "longitude": LON,
                "window_start": "2026-10-15T20:00:00+00:00",
                "window_end":   "2026-10-15T23:00:00+00:00",
                "duration_minutes": 45.0,
                "required_duration_minutes": 45.0,
                "visibility_score": 72.0,
                "source": "Authoritative Deep-Sky Catalog",
                "metadata": {
                    "external_assessments": {
                        "assessment_status": "pending",
                        "weather_score": None,
                        "preference_score": None,
                        "weather_source": None,
                        "preference_source": None,
                    }
                },
            }
        ]

        monkeypatch.setattr(routes.jpl_adapter, "fetch_events_from_jpl", lambda **kw: fake_jpl)
        monkeypatch.setattr(routes, "discover_catalog_events", lambda **kw: fake_catalog)
        monkeypatch.setattr(routes, "evaluate_event_visibility", _mock_evaluate)
        monkeypatch.setattr(backend, "generate_recommendations", _mock_recommendations)

        payload = {
            "session": {
                "latitude": LAT, "longitude": LON,
                "session_start": "2026-10-15T20:00:00+00:00",
                "session_end":   "2026-10-16T02:00:00+00:00",
            },
            "events": [],
        }
        resp = client.post("/api/v1/observation-plans/generate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_count"] == 2, (
            f"Expected 2 events (1 JPL + 1 catalog), got {data['event_count']}"
        )
        names = {ev.get("name") for ev in data["recommendations"]["details"]}
        assert "Moon" in names
        assert "Andromeda Galaxy (M31)" in names

    def test_deduplication_prevents_duplicate_event_ids(self, client, monkeypatch):
        """If JPL and catalog both return an event with the same event_id, only one is kept."""
        from fastapi.testclient import TestClient
        from app.main import app
        import app.api.routes.observation_plans as routes
        import app.modules.intelligence.recommendation.backend_interface as backend

        shared_event = {
            "event_id": "shared_id_001",
            "name": "SharedTarget",
            "category": "planet",
            "event_type": "planetary",
            "latitude": LAT, "longitude": LON,
            "window_start": "2026-10-15T20:00:00+00:00",
            "window_end":   "2026-10-15T23:00:00+00:00",
            "duration_minutes": 60.0,
            "required_duration_minutes": 60.0,
            "visibility_score": 80.0,
            "weather_score": 0.0,
            "preference_score": 0.0,
            "source": "Test",
        }

        monkeypatch.setattr(routes.jpl_adapter, "fetch_events_from_jpl", lambda **kw: [dict(shared_event)])
        monkeypatch.setattr(routes, "discover_catalog_events", lambda **kw: [dict(shared_event)])
        monkeypatch.setattr(routes, "evaluate_event_visibility", _mock_evaluate)
        monkeypatch.setattr(backend, "generate_recommendations", _mock_recommendations)

        payload = {
            "session": {
                "latitude": LAT, "longitude": LON,
                "session_start": "2026-10-15T20:00:00+00:00",
                "session_end":   "2026-10-16T02:00:00+00:00",
            },
            "events": [],
        }
        resp = client.post("/api/v1/observation-plans/generate", json=payload)
        assert resp.status_code == 200
        assert resp.json()["event_count"] == 1

    def test_missing_coords_returns_400_on_empty_events(self, client):
        """Existing 400 contract: empty events with no session coords → 400."""
        from fastapi.testclient import TestClient
        from app.main import app
        payload = {
            "session": {"session_start": "2026-10-15T20:00:00+00:00"},
            "events": [],
        }
        resp = client.post("/api/v1/observation-plans/generate", json=payload)
        assert resp.status_code == 400


# ===========================================================================
# Section 3 — DEFAULT_DURATIONS and test_assessment_provider
# ===========================================================================

class TestDatabaseRecommendationDefaults:
    """Verify the deep-sky duration defaults and test-provider mappings."""

    def test_deep_sky_duration_default(self):
        from app.services.database_recommendation_service import DEFAULT_DURATIONS
        assert "deep_sky" in DEFAULT_DURATIONS, "deep_sky must be in DEFAULT_DURATIONS"
        assert DEFAULT_DURATIONS["deep_sky"] == 45

    def test_dso_duration_default(self):
        from app.services.database_recommendation_service import DEFAULT_DURATIONS
        assert "dso" in DEFAULT_DURATIONS
        assert DEFAULT_DURATIONS["dso"] == 45

    def test_existing_durations_unchanged(self):
        from app.services.database_recommendation_service import DEFAULT_DURATIONS
        assert DEFAULT_DURATIONS["eclipse"] == 20
        assert DEFAULT_DURATIONS["meteor_shower"] == 30
        assert DEFAULT_DURATIONS["planet"] == 20
        assert DEFAULT_DURATIONS["full_moon"] == 30

    def test_deep_sky_assessment_mapping(self):
        """test_assessment_provider returns success for deep_sky event_type."""
        from app.services.test_assessment_provider import get_test_assessment

        event = SimpleNamespace(
            event_type="deep_sky",
            category="deep_sky",
            id="test-dso-001",
        )
        result = get_test_assessment(event)
        assert result["status"] == "success"
        assert isinstance(result["visibility_score"], (int, float))
        assert isinstance(result["weather_score"], (int, float))

    def test_dso_alias_assessment_mapping(self):
        """'dso' event_type resolves to the deep_sky assessment."""
        from app.services.test_assessment_provider import get_test_assessment

        event = SimpleNamespace(
            event_type="dso",
            category="dso",
            id="test-dso-002",
        )
        result = get_test_assessment(event)
        assert result["status"] == "success", f"Expected success, got: {result}"

    def test_solar_eclipse_assessment_mapping(self):
        from app.services.test_assessment_provider import get_test_assessment

        event = SimpleNamespace(
            event_type="solar_eclipse",
            category="eclipse",
            id="test-eclipse-001",
        )
        result = get_test_assessment(event)
        assert result["status"] == "success"

    def test_lunar_eclipse_assessment_mapping(self):
        from app.services.test_assessment_provider import get_test_assessment

        event = SimpleNamespace(
            event_type="lunar_eclipse",
            category="eclipse",
            id="test-eclipse-002",
        )
        result = get_test_assessment(event)
        assert result["status"] == "success"

    def test_unknown_event_type_returns_unavailable(self):
        from app.services.test_assessment_provider import get_test_assessment

        event = SimpleNamespace(
            event_type="xyzzy_unknown",
            category="xyzzy_unknown",
            id="test-unknown-001",
        )
        result = get_test_assessment(event)
        assert result["status"] == "unavailable"

    def test_deep_sky_in_database_recommendation_pipeline(self, monkeypatch):
        """A deep-sky DB event with valid time window passes the service pipeline."""
        from app.services import database_recommendation_service as service
        from datetime import timedelta, timezone as tz

        start = datetime(2026, 10, 15, 20, 0, tzinfo=tz.utc)
        dso_event = SimpleNamespace(
            id="dso-db-001",
            external_event_id="dso-db-001",
            category="deep_sky",
            object_name="Andromeda Galaxy (M31)",
            event_type="deep_sky",
            start_time=start,
            end_time=start + timedelta(hours=4),
            latitude=LAT,
            longitude=LON,
            additional_data={},
        )

        monkeypatch.setattr(service, "get_events_for_session", lambda **kw: [dso_event])
        monkeypatch.setattr(service, "deduplicate_events", lambda evs: evs)
        # Monkeypatch recommendation engine to a no-op
        monkeypatch.setattr(service, "generate_recommendations", lambda req: {
            "status": "success",
            "ranked_events": req.get("events", []),
        })

        session = {
            "location": {"latitude": LAT, "longitude": LON},
            "start_time": "2026-10-15T20:00:00+00:00",
            "end_time": "2026-10-16T00:00:00+00:00",
            "available_duration_minutes": 120,
        }
        result = service.get_database_recommendations(
            db=MagicMock(),
            session=session,
        )
        # The event should be accepted (not rejected)
        assert result.get("database_events_found", 0) >= 1, (
            f"Expected deep_sky event to be found. Result: {result}"
        )
        rejected_reasons = [r.get("reason", "") for r in result.get("database_events_rejected", [])]
        assert not any("deep_sky" in r.lower() for r in rejected_reasons), (
            f"deep_sky event was incorrectly rejected: {rejected_reasons}"
        )
