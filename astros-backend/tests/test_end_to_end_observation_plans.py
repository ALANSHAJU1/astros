"""
AstroOS11 — Stage 3: End-to-End Integration and Real-Data Validation Tests
===========================================================================

Comprehensive end-to-end integration tests validating:
  1. Full request pipeline for ``/api/v1/observation-plans/generate`` combining
     JPL Horizons ephemerides and catalog discovery candidates.
  2. Pure catalog candidate discovery path (when JPL returns no planets/moon).
  3. No-observable-candidates scenario (graceful empty schedule).
  4. Environmental data failure and dynamic weight renormalization.
  5. Uncalculable astronomy assessment handling and graceful skip in scheduling.
  6. Coexistence of all 5 supported celestial categories in a single observation plan:
     Lunar, Planetary, Eclipse, Meteor Shower, Deep-Sky Object.
  7. Scheduler interval knapsack constraints, non-overlap, and timezone-awareness.
  8. ``/api/v1/recommendations/from-database`` workflow with all categories.
  9. Error contracts, status codes, and regression safeguards.

Design constraints:
  - No live network requests.  External APIs (NASA JPL, Open-Meteo, DarkSkySites)
    are mocked or stubbed deterministically.
  - Assertions test contract integrity, status codes, scheduling invariants, and
    non-fabrication rules rather than arbitrary floating-point scores.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Setup intelligence and backend import paths
# ---------------------------------------------------------------------------
ROOT_PATH = Path(__file__).resolve().parents[2]
INTEL_PATH = ROOT_PATH / "astros-intelligence"
if str(INTEL_PATH) not in sys.path:
    sys.path.append(str(INTEL_PATH))
if str(ROOT_PATH) not in sys.path:
    sys.path.append(str(ROOT_PATH))

from app.main import app
from app.services.hathim_astronomy_adapter import HathimAstronomyAdapter
from app.models.environmental_observation import EnvironmentalObservation

# ---------------------------------------------------------------------------
# Common test constants
# ---------------------------------------------------------------------------
LAT = 10.5276   # Thrissur, Kerala
LON = 76.2144
TZ_OFFSET = "+05:30"
SESSION_START = f"2026-10-15T19:00:00{TZ_OFFSET}"
SESSION_END   = f"2026-10-15T23:00:00{TZ_OFFSET}"


def _make_mock_observation(observed_at_iso: str, cloud_cover: float = 15.0) -> EnvironmentalObservation:
    """Create an in-memory EnvironmentalObservation record with realistic parameters."""
    dt = datetime.fromisoformat(observed_at_iso)
    return EnvironmentalObservation(
        latitude=LAT,
        longitude=LON,
        observed_at=dt,
        temperature_celsius=24.5,
        humidity=65.0,
        cloud_cover=cloud_cover,
        conditions="Clear",
        source="Open-Meteo Forecast",
        expires_at=dt + timedelta(hours=1),
        additional_data={
            "cloud_cover_low": 5.0,
            "cloud_cover_mid": 10.0,
            "cloud_cover_high": 15.0,
            "precipitation_mm": 0.0,
            "wind_speed_kmh": 8.0,
        },
    )


# ===========================================================================
# 1. Pipeline Combining JPL Events and Catalog Discovery Candidates
# ===========================================================================

def test_e2e_combine_jpl_and_catalog_candidates(client, monkeypatch):
    """Observation plan generates successfully with both JPL events and catalog candidates."""
    import app.api.routes.observation_plans as routes

    jpl_moon_event = {
        "event_id": "jpl_moon_pass_001",
        "name": "Moon",
        "category": "lunar",
        "event_type": "moonrise",
        "type": "lunar",
        "latitude": LAT,
        "longitude": LON,
        "window_start": f"2026-10-15T19:00:00{TZ_OFFSET}",
        "window_end": f"2026-10-15T21:00:00{TZ_OFFSET}",
        "duration_minutes": 30.0,
        "required_duration_minutes": 30.0,
        "source": "NASA JPL Horizons API",
        "metadata": {
            "target": "Moon (301)",
            "derived_astronomical_values": {
                "max_altitude_deg": 45.0,
                "peak_elevation_deg": 45.0,
            },
        },
    }

    catalog_dso_event = {
        "event_id": "pass_M31_1",
        "name": "Andromeda Galaxy (M31)",
        "category": "deep_sky",
        "event_type": "Deep-Sky Object",
        "type": "Deep-Sky Object",
        "latitude": LAT,
        "longitude": LON,
        "window_start": f"2026-10-15T21:00:00{TZ_OFFSET}",
        "window_end": f"2026-10-15T23:00:00{TZ_OFFSET}",
        "duration_minutes": 45.0,
        "required_duration_minutes": 45.0,
        "source": "Authoritative Deep-Sky Catalog",
        "metadata": {
            "derived_astronomical_values": {
                "peak_elevation_deg": 55.0,
                "mean_sun_elevation_deg": -25.0,
                "target": "M31",
            },
        },
    }

    monkeypatch.setattr(routes.jpl_adapter, "fetch_events_from_jpl", lambda **kw: [jpl_moon_event])
    monkeypatch.setattr(routes, "discover_catalog_events", lambda **kw: [catalog_dso_event])

    mock_obs = [
        _make_mock_observation(f"2026-10-15T19:00:00{TZ_OFFSET}"),
        _make_mock_observation(f"2026-10-15T21:00:00{TZ_OFFSET}"),
    ]
    monkeypatch.setattr(
        routes.EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda *args, **kw: mock_obs,
    )

    payload = {
        "session": {
            "latitude": LAT,
            "longitude": LON,
            "session_start": SESSION_START,
            "session_end": SESSION_END,
            "available_duration_minutes": 180,
            "preference_score": 85.0,
        },
        "events": [],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["event_count"] == 2

    recs = data["recommendations"]
    assert "schedule" in recs
    assert len(recs["schedule"]) >= 1

    event_names = [e["name"] for e in recs["details"]]
    assert "Moon" in event_names
    assert "Andromeda Galaxy (M31)" in event_names

    # Check non-overlap in schedule
    sched = recs["schedule"]
    if len(sched) >= 2:
        for i in range(len(sched) - 1):
            end_current = datetime.fromisoformat(sched[i]["scheduled_end"])
            start_next = datetime.fromisoformat(sched[i + 1]["scheduled_start"])
            assert end_current <= start_next, "Scheduled sessions must not overlap"


# ===========================================================================
# 2. Pipeline with Only Catalog Candidates (JPL Empty)
# ===========================================================================

def test_e2e_catalog_only_candidates(client, monkeypatch):
    """Observation plan succeeds when only catalog candidates are discovered."""
    import app.api.routes.observation_plans as routes

    catalog_meteor_event = {
        "event_id": "meteor_perseids_pass_001",
        "name": "Perseid Meteor Shower Observation Pass 1",
        "category": "meteor_shower",
        "event_type": "Meteor Shower",
        "type": "Meteor Shower",
        "latitude": LAT,
        "longitude": LON,
        "window_start": f"2026-10-15T19:30:00{TZ_OFFSET}",
        "window_end": f"2026-10-15T21:00:00{TZ_OFFSET}",
        "duration_minutes": 30.0,
        "required_duration_minutes": 30.0,
        "source": "International Meteor Organization",
        "metadata": {
            "astronomical_facts": {"shower_id": "perseids"},
            "derived_astronomical_values": {
                "peak_radiant_elevation_deg": 40.0,
                "sun_elevation_deg": -22.0,
            },
        },
    }

    monkeypatch.setattr(routes.jpl_adapter, "fetch_events_from_jpl", lambda **kw: [])
    monkeypatch.setattr(routes, "discover_catalog_events", lambda **kw: [catalog_meteor_event])

    mock_obs = [_make_mock_observation(f"2026-10-15T19:30:00{TZ_OFFSET}")]
    monkeypatch.setattr(
        routes.EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda *args, **kw: mock_obs,
    )

    payload = {
        "session": {
            "latitude": LAT,
            "longitude": LON,
            "session_start": SESSION_START,
            "session_end": SESSION_END,
            "available_duration_minutes": 60,
        },
        "events": [],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["event_count"] == 1
    assert data["recommendations"]["details"][0]["category"] == "meteor_shower"


# ===========================================================================
# 3. No Observable Candidates Returns Valid Empty Schedule
# ===========================================================================

def test_e2e_no_observable_candidates(client, monkeypatch):
    """Empty candidate pool returns valid 200 OK structure with 0 scheduled events."""
    import app.api.routes.observation_plans as routes

    monkeypatch.setattr(routes.jpl_adapter, "fetch_events_from_jpl", lambda **kw: [])
    monkeypatch.setattr(routes, "discover_catalog_events", lambda **kw: [])

    payload = {
        "session": {
            "latitude": LAT,
            "longitude": LON,
            "session_start": SESSION_START,
            "session_end": SESSION_END,
            "available_duration_minutes": 120,
        },
        "events": [],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["event_count"] == 0

    recs = data["recommendations"]
    assert recs["summary"]["total_events_evaluated"] == 0
    assert recs["summary"]["total_events_scheduled"] == 0
    assert recs["schedule"] == []


# ===========================================================================
# 4. Weather Unavailable: Graceful Fallback & Weight Renormalization
# ===========================================================================

def test_e2e_weather_unavailable_weight_renormalization(client, monkeypatch):
    """When weather is unavailable, astronomical score is used directly and weights renormalize."""
    import app.api.routes.observation_plans as routes

    direct_event = {
        "event_id": "direct_jupiter_001",
        "name": "Jupiter",
        "category": "planet",
        "event_type": "planetary",
        "latitude": LAT,
        "longitude": LON,
        "window_start": f"2026-10-15T19:00:00{TZ_OFFSET}",
        "window_end": f"2026-10-15T22:00:00{TZ_OFFSET}",
        "duration_minutes": 30.0,
        "required_duration_minutes": 30.0,
        "metadata": {
            "target": "Jupiter (599)",
            "derived_astronomical_values": {
                "max_altitude_deg": 50.0,
                "peak_elevation_deg": 50.0,
            },
        },
    }

    # Simulate weather service error / complete absence of observations
    monkeypatch.setattr(
        routes.EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda *args, **kw: [],
    )

    payload = {
        "session": {
            "latitude": LAT,
            "longitude": LON,
            "session_start": SESSION_START,
            "session_end": SESSION_END,
            "available_duration_minutes": 60,
            "preference_score": 80.0,
        },
        "events": [direct_event],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    enriched = data["recommendations"]["details"][0]
    # Weather score must be None (not fabricated to 100 or 0)
    assert enriched.get("weather_score") is None
    # Astronomical score is preserved
    assert enriched.get("astronomical_score") is not None
    # Visibility score reflects ephemeris only
    assert enriched.get("visibility_score") == enriched.get("astronomical_score")
    # Limitations disclose weather absence
    assert any("environmental" in lim.lower() for lim in enriched.get("limitations", []))


# ===========================================================================
# 5. Astronomy Uncalculable: Gracefully Skipped in Scheduling
# ===========================================================================

def test_e2e_astronomy_uncalculable_gracefully_skipped(client, monkeypatch):
    """Events with uncalculable astronomical scores are not scheduled as recommendations."""
    import app.api.routes.observation_plans as routes

    # Deep sky object with unknown solar elevation and no timestamp/coords to compute it
    unscorable_dso = {
        "event_id": "unscorable_dso_001",
        "name": "Unknown Nebula Target",
        "category": "deep_sky",
        "event_type": "deep_sky",
        "latitude": None,
        "longitude": None,
        "window_start": None,
        "window_end": None,
        "duration_minutes": 45.0,
        "required_duration_minutes": 45.0,
    }

    payload = {
        "session": {
            "latitude": LAT,
            "longitude": LON,
            "session_start": SESSION_START,
            "session_end": SESSION_END,
            "available_duration_minutes": 60,
        },
        "events": [unscorable_dso],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    recs = data["recommendations"]
    # The unscorable event should not be in the scheduled plan
    assert len(recs.get("schedule", [])) == 0
    # Must appear in skipped events
    skipped = recs.get("skipped_events", [])
    assert len(skipped) == 1
    assert "unavailable" in skipped[0]["reason"].lower() or "unverified" in skipped[0]["reason"].lower()


# ===========================================================================
# 6. Coexistence of All 5 Supported Categories in One Observation Plan
# ===========================================================================

def test_e2e_multi_category_coexistence(client, monkeypatch):
    """A single observation plan request supports all 5 celestial categories concurrently."""
    import app.api.routes.observation_plans as routes

    events_payload = [
        {
            "event_id": "ev_lunar_01",
            "name": "Moon",
            "category": "lunar",
            "event_type": "moonrise",
            "latitude": LAT, "longitude": LON,
            "window_start": f"2026-10-15T19:00:00{TZ_OFFSET}",
            "window_end": f"2026-10-15T20:00:00{TZ_OFFSET}",
            "duration_minutes": 20.0,
            "metadata": {"derived_astronomical_values": {"peak_elevation_deg": 35.0}},
        },
        {
            "event_id": "ev_planetary_01",
            "name": "Saturn",
            "category": "planet",
            "event_type": "planetary",
            "latitude": LAT, "longitude": LON,
            "window_start": f"2026-10-15T19:30:00{TZ_OFFSET}",
            "window_end": f"2026-10-15T21:00:00{TZ_OFFSET}",
            "duration_minutes": 20.0,
            "metadata": {"derived_astronomical_values": {"peak_elevation_deg": 42.0}},
        },
        {
            "event_id": "ev_eclipse_01",
            "name": "Total Lunar Eclipse",
            "category": "eclipse",
            "event_type": "lunar_eclipse",
            "latitude": LAT, "longitude": LON,
            "window_start": f"2026-10-15T20:00:00{TZ_OFFSET}",
            "window_end": f"2026-10-15T22:00:00{TZ_OFFSET}",
            "duration_minutes": 20.0,
            "metadata": {"derived_astronomical_values": {"peak_elevation_deg": 30.0}},
        },
        {
            "event_id": "ev_meteor_01",
            "name": "Orionids",
            "category": "meteor_shower",
            "event_type": "Meteor Shower",
            "latitude": LAT, "longitude": LON,
            "window_start": f"2026-10-15T21:00:00{TZ_OFFSET}",
            "window_end": f"2026-10-15T23:00:00{TZ_OFFSET}",
            "duration_minutes": 30.0,
            "metadata": {
                "astronomical_facts": {"shower_id": "orionids"},
                "derived_astronomical_values": {"peak_radiant_elevation_deg": 45.0, "sun_elevation_deg": -30.0},
            },
        },
        {
            "event_id": "ev_dso_01",
            "name": "M42 (Orion Nebula)",
            "category": "deep_sky",
            "event_type": "Deep-Sky Object",
            "latitude": LAT, "longitude": LON,
            "window_start": f"2026-10-15T21:30:00{TZ_OFFSET}",
            "window_end": f"2026-10-15T23:00:00{TZ_OFFSET}",
            "duration_minutes": 45.0,
            "metadata": {
                "nasa_horizons_facts": {"catalog_id": "M42"},
                "derived_astronomical_values": {"peak_elevation_deg": 50.0, "mean_sun_elevation_deg": -32.0},
            },
        },
    ]

    mock_obs = [_make_mock_observation(f"2026-10-15T20:00:00{TZ_OFFSET}")]
    monkeypatch.setattr(
        routes.EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda *args, **kw: mock_obs,
    )

    payload = {
        "session": {
            "latitude": LAT,
            "longitude": LON,
            "session_start": SESSION_START,
            "session_end": SESSION_END,
            "available_duration_minutes": 240,
            "preference_score": 90.0,
        },
        "events": events_payload,
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["event_count"] == 5

    categories_found = {ev.get("category") for ev in data["recommendations"]["details"]}
    expected_categories = {"lunar", "planet", "eclipse", "meteor_shower", "deep_sky"}
    assert expected_categories.issubset(categories_found), f"Missing categories: {expected_categories - categories_found}"


# ===========================================================================
# 7. Scheduling Constraints, Feasibility, and Timezone Bounds
# ===========================================================================

def test_e2e_scheduling_constraints_and_timezone_bounds(client, monkeypatch):
    """Scheduled slots respect session boundaries, duration budgets, and timezone offsets."""
    import app.api.routes.observation_plans as routes

    start_iso = f"2026-10-15T20:00:00{TZ_OFFSET}"
    end_iso   = f"2026-10-15T22:00:00{TZ_OFFSET}"
    session_start_dt = datetime.fromisoformat(start_iso)
    session_end_dt   = datetime.fromisoformat(end_iso)

    events_payload = [
        {
            "event_id": "slot_m31_test",
            "name": "M31 (Andromeda Galaxy)",
            "category": "deep_sky",
            "event_type": "deep_sky",
            "latitude": LAT, "longitude": LON,
            "window_start": start_iso,
            "window_end": end_iso,
            "duration_minutes": 45.0,
            "metadata": {
                "nasa_horizons_facts": {"catalog_id": "M31"},
                "derived_astronomical_values": {"peak_elevation_deg": 60.0, "mean_sun_elevation_deg": -30.0},
            },
        },
        {
            "event_id": "slot_m42_test",
            "name": "M42 (Orion Nebula)",
            "category": "deep_sky",
            "event_type": "deep_sky",
            "latitude": LAT, "longitude": LON,
            "window_start": start_iso,
            "window_end": end_iso,
            "duration_minutes": 45.0,
            "metadata": {
                "nasa_horizons_facts": {"catalog_id": "M42"},
                "derived_astronomical_values": {"peak_elevation_deg": 55.0, "mean_sun_elevation_deg": -30.0},
            },
        },
    ]

    mock_obs = [_make_mock_observation(start_iso)]
    monkeypatch.setattr(
        routes.EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda *args, **kw: mock_obs,
    )

    payload = {
        "session": {
            "latitude": LAT,
            "longitude": LON,
            "session_start": start_iso,
            "session_end": end_iso,
            "available_duration_minutes": 100,  # Room for both 45m passes (90m total)
            "preference_score": 85.0,
        },
        "events": events_payload,
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    schedule = data["recommendations"]["schedule"]
    assert len(schedule) == 2

    for item in schedule:
        slot_s = datetime.fromisoformat(item["scheduled_start"])
        slot_e = datetime.fromisoformat(item["scheduled_end"])
        assert slot_s.tzinfo is not None, "Scheduled slot must be timezone-aware"
        assert slot_e.tzinfo is not None, "Scheduled slot must be timezone-aware"
        assert slot_s >= session_start_dt, "Slot cannot start before session start"
        assert slot_e <= session_end_dt, "Slot cannot end after session end"
        assert (slot_e - slot_s).total_seconds() / 60.0 == pytest.approx(45.0, rel=1e-3)


# ===========================================================================
# 8. Database Recommendations Endpoint: Retrieval & Multi-Category Support
# ===========================================================================

def test_e2e_database_recommendations_all_categories(client, monkeypatch):
    """POST /api/v1/recommendations/from-database retrieves and scores all categories."""
    from app.services import database_recommendation_service as service

    start_dt = datetime.fromisoformat(SESSION_START)
    end_dt = datetime.fromisoformat(SESSION_END)

    # 5 DB entities representing each category
    mock_db_events = [
        SimpleNamespace(
            id="db-moon-01",
            external_event_id="db-moon-01",
            category="lunar",
            object_name="Waxing Gibbous Moon",
            event_type="full_moon",
            start_time=start_dt,
            end_time=start_dt + timedelta(hours=2),
            latitude=LAT, longitude=LON, additional_data={},
        ),
        SimpleNamespace(
            id="db-planet-01",
            external_event_id="db-planet-01",
            category="planet",
            object_name="Jupiter",
            event_type="planet",
            start_time=start_dt,
            end_time=start_dt + timedelta(hours=2),
            latitude=LAT, longitude=LON, additional_data={},
        ),
        SimpleNamespace(
            id="db-eclipse-01",
            external_event_id="db-eclipse-01",
            category="eclipse",
            object_name="Total Solar Eclipse",
            event_type="solar_eclipse",
            start_time=start_dt,
            end_time=start_dt + timedelta(hours=1),
            latitude=LAT, longitude=LON, additional_data={},
        ),
        SimpleNamespace(
            id="db-meteor-01",
            external_event_id="db-meteor-01",
            category="meteor_shower",
            object_name="Geminids",
            event_type="meteor_shower",
            start_time=start_dt,
            end_time=start_dt + timedelta(hours=3),
            latitude=LAT, longitude=LON, additional_data={},
        ),
        SimpleNamespace(
            id="db-dso-01",
            external_event_id="db-dso-01",
            category="deep_sky",
            object_name="Whirlpool Galaxy (M51)",
            event_type="deep_sky",
            start_time=start_dt,
            end_time=start_dt + timedelta(hours=4),
            latitude=LAT, longitude=LON, additional_data={},
        ),
    ]

    monkeypatch.setattr(service, "get_events_for_session", lambda **kw: mock_db_events)
    monkeypatch.setattr(service, "deduplicate_events", lambda evs: evs)

    mock_obs = [
        _make_mock_observation(f"2026-10-15T{h:02d}:00:00{TZ_OFFSET}", cloud_cover=15.0)
        for h in range(19, 24)
    ]
    monkeypatch.setattr(
        service.EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda *a, **kw: mock_obs,
    )

    payload = {
        "location": {"name": "Thrissur", "latitude": LAT, "longitude": LON},
        "start_time": SESSION_START,
        "end_time": SESSION_END,
        "available_duration_minutes": 240,
        "observation_goal": "general_observation",
        "preferences": {},
    }

    response = client.post("/api/v1/recommendations/from-database", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["database_events_found"] == 5
    assert len(data["database_events_rejected"]) == 0
    assert len(data["ranked_events"]) == 5

    # Verify duration defaults: deep_sky should have 45 mins, meteor 30 mins, eclipse 20 mins
    ranked_map = {ev["event_id"]: ev for ev in data["ranked_events"]}
    assert ranked_map["db-dso-01"]["duration_minutes"] == 45
    assert ranked_map["db-meteor-01"]["duration_minutes"] == 30
    assert ranked_map["db-eclipse-01"]["duration_minutes"] == 20


# ===========================================================================
# 9. API Error Contracts, Status Codes, and Regressions
# ===========================================================================

class TestApiErrorContractsAndRegressions:
    """Validate documented error contracts across endpoints."""

    def test_missing_coordinates_when_events_empty_returns_400(self, client):
        payload = {
            "session": {"session_start": SESSION_START, "session_end": SESSION_END},
            "events": [],
        }
        resp = client.post("/api/v1/observation-plans/generate", json=payload)
        assert resp.status_code == 400
        assert "must include session.latitude" in resp.json()["detail"]

    def test_jpl_horizons_upstream_failure_returns_502(self, client, monkeypatch):
        import app.api.routes.observation_plans as routes
        monkeypatch.setattr(
            routes.jpl_adapter,
            "fetch_events_from_jpl",
            MagicMock(side_effect=RuntimeError("NASA JPL 503 Service Unavailable")),
        )
        payload = {
            "session": {
                "latitude": LAT,
                "longitude": LON,
                "session_start": SESSION_START,
                "session_end": SESSION_END,
            },
            "events": [],
        }
        resp = client.post("/api/v1/observation-plans/generate", json=payload)
        assert resp.status_code == 502
        assert "Failed to fetch events from JPL Horizons" in resp.json()["detail"]

    def test_database_endpoint_rejects_session_end_before_start(self, client):
        payload = {
            "location": {"name": "Thrissur", "latitude": LAT, "longitude": LON},
            "start_time": SESSION_END,
            "end_time": SESSION_START,  # invalid reversed order
            "available_duration_minutes": 120,
        }
        resp = client.post("/api/v1/recommendations/from-database", json=payload)
        assert resp.status_code == 422
        assert resp.json().get("detail") == "Invalid request"

    def test_database_endpoint_rejects_naive_timestamp(self, client):
        payload = {
            "location": {"name": "Thrissur", "latitude": LAT, "longitude": LON},
            "start_time": "2026-10-15T19:00:00",  # missing tz offset
            "end_time": "2026-10-15T21:00:00",
            "available_duration_minutes": 120,
        }
        resp = client.post("/api/v1/recommendations/from-database", json=payload)
        assert resp.status_code == 422
        assert resp.json().get("detail") == "Invalid request"

    def test_observation_plans_invalid_body_type_returns_400(self, client):
        resp = client.post("/api/v1/observation-plans/generate", json=["invalid", "array"])
        assert resp.status_code == 400
        assert "must be a JSON object" in resp.json()["detail"]

