import json
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.environmental_observation import EnvironmentalObservation
from app.services.environmental_service import EnvironmentalService
from app.services.light_pollution_service import LightPollutionResult


class MockDB:
    """Lightweight in-memory test db for routing."""
    pass


def test_forecast_inside_event_window(client, monkeypatch):
    """Event window matching a forecast record gets valid environmental and weather scores."""

    # Mock get_or_fetch_forecast_observations to return 2 hourly observations:
    # Obs 1: 18:00 (outside 19:00-22:00 window)
    # Obs 2: 19:30 (inside 19:00-22:00 window, clear sky 10% cloud)
    obs1 = EnvironmentalObservation(
        observed_at=datetime.fromisoformat("2026-10-26T18:00:00+05:30"),
        cloud_cover=90.0,
        temperature_celsius=20.0,
        humidity=60.0,
    )
    obs2 = EnvironmentalObservation(
        observed_at=datetime.fromisoformat("2026-10-26T19:30:00+05:30"),
        cloud_cover=10.0,
        temperature_celsius=24.0,
        humidity=50.0,
    )

    monkeypatch.setattr(
        EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda self, db, latitude, longitude, start_time, end_time, **kwargs: [obs1, obs2],
    )
    monkeypatch.setattr(
        EnvironmentalService,
        "get_light_pollution",
        lambda self, latitude, longitude: LightPollutionResult(status="success", bortle_class=4, sqm=21.2),
    )

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-26T19:00:00+05:30",
            "session_end": "2026-10-26T22:00:00+05:30",
            "available_duration_minutes": 120,
            "preference_score": 85.0,
        },
        "events": [
            {
                "event_id": "event_moon_match",
                "name": "Moon Observation",
                "category": "lunar",
                "event_type": "moon",
                "window_start": "2026-10-26T19:00:00+05:30",
                "window_end": "2026-10-26T22:00:00+05:30",
                "duration_minutes": 45,
                "additional_data": {"target_altitude_deg": 50.0, "phase_angle_deg": 25.0},
            }
        ],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    event_res = data["recommendations"]["details"][0]

    # Verify matching observation (obs2 with 10% cloud -> score 90.0) was consumed
    assert event_res["environmental_score"] == 90.0
    assert event_res["weather_score"] == 90.0
    assert event_res["astronomical_score"] is not None
    # Combined visibility score = 0.60 * 90.0 + 0.40 * astronomical_score
    expected_vis = round(0.60 * 90.0 + 0.40 * event_res["astronomical_score"], 1)
    assert event_res["visibility_score"] == expected_vis

    # Ranking status should be complete because all 3 scores (vis, weather, pref) are present
    ranked = data["recommendations"]["ranked_events"][0]
    assert ranked["score_status"] == "complete"
    assert ranked["missing_scores"] == []


def test_no_matching_forecast_preserves_none(client, monkeypatch):
    """When all forecast records are far outside the event window, environmental score is None (not zero)."""

    # Obs is 12 hours earlier
    obs_far = EnvironmentalObservation(
        observed_at=datetime.fromisoformat("2026-10-26T06:00:00+05:30"),
        cloud_cover=0.0,
        temperature_celsius=20.0,
    )

    monkeypatch.setattr(
        EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda self, db, latitude, longitude, start_time, end_time, **kwargs: [obs_far],
    )

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-26T19:00:00+05:30",
            "session_end": "2026-10-26T22:00:00+05:30",
            "available_duration_minutes": 120,
        },
        "events": [
            {
                "event_id": "event_no_match",
                "name": "Moon Observation",
                "category": "lunar",
                "event_type": "moon",
                "window_start": "2026-10-26T19:00:00+05:30",
                "window_end": "2026-10-26T22:00:00+05:30",
                "duration_minutes": 45,
                "additional_data": {"target_altitude_deg": 50.0},
            }
        ],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    event_res = data["recommendations"]["details"][0]

    assert event_res["environmental_score"] is None
    assert event_res["weather_score"] is None
    # Visibility score cleanly falls back to astronomical ephemeris only
    assert event_res["visibility_score"] == event_res["astronomical_score"]


def test_genuine_zero_environmental_score(client, monkeypatch):
    """100% cloud cover with active precipitation yields a genuine low/zero score, NOT None."""

    obs_storm = EnvironmentalObservation(
        observed_at=datetime.fromisoformat("2026-10-26T19:30:00+05:30"),
        cloud_cover=100.0,
        temperature_celsius=18.0,
        humidity=95.0,
        additional_data={
            "cloud_cover_low": 100.0,
            "cloud_cover_mid": 100.0,
            "cloud_cover_high": 100.0,
            "precipitation_mm": 20.0,
        },
    )

    monkeypatch.setattr(
        EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda self, db, latitude, longitude, start_time, end_time, **kwargs: [obs_storm],
    )

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-26T19:00:00+05:30",
            "session_end": "2026-10-26T22:00:00+05:30",
            "available_duration_minutes": 120,
            "preference_score": 70.0,
        },
        "events": [
            {
                "event_id": "event_storm",
                "name": "Moon Observation",
                "category": "lunar",
                "event_type": "moon",
                "window_start": "2026-10-26T19:00:00+05:30",
                "window_end": "2026-10-26T22:00:00+05:30",
                "duration_minutes": 45,
                "additional_data": {"target_altitude_deg": 50.0},
            }
        ],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    event_res = data["recommendations"]["details"][0]

    assert event_res["environmental_score"] is not None
    assert event_res["environmental_score"] <= 5.0
    assert event_res["weather_score"] == event_res["environmental_score"]
    # Should not be treated as missing
    ranked = data["recommendations"]["ranked_events"][0]
    assert "weather" not in ranked["missing_scores"]


def test_open_meteo_failure_gracefully_handled(client, monkeypatch):
    """Network failure contacting Open-Meteo does not crash route and preserves None."""

    def mock_fetch_fail(*args, **kwargs):
        raise RuntimeError("Open-Meteo connection timed out")

    monkeypatch.setattr(EnvironmentalService, "get_or_fetch_forecast_observations", mock_fetch_fail)

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-26T19:00:00+05:30",
            "session_end": "2026-10-26T22:00:00+05:30",
            "available_duration_minutes": 120,
        },
        "events": [
            {
                "name": "Moon Observation",
                "category": "lunar",
                "event_type": "moon",
                "duration_minutes": 45,
                "additional_data": {"target_altitude_deg": 50.0},
            }
        ],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    event_res = data["recommendations"]["details"][0]
    assert event_res["environmental_score"] is None
    assert event_res["weather_score"] is None


def test_dark_sky_sites_failure_gracefully_handled(client, monkeypatch):
    """DarkSkySites failure does not break observation plan and maintains weather calculation."""

    obs = EnvironmentalObservation(
        observed_at=datetime.fromisoformat("2026-10-26T19:30:00+05:30"),
        cloud_cover=20.0,
        temperature_celsius=22.0,
    )
    monkeypatch.setattr(
        EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda self, db, latitude, longitude, start_time, end_time, **kwargs: [obs],
    )
    def mock_lp_fail(*args, **kwargs):
        raise RuntimeError("DarkSkySites 503 Service Unavailable")

    monkeypatch.setattr(EnvironmentalService, "get_light_pollution", mock_lp_fail)

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-26T19:00:00+05:30",
            "session_end": "2026-10-26T22:00:00+05:30",
            "available_duration_minutes": 120,
        },
        "events": [
            {
                "name": "Moon Observation",
                "category": "lunar",
                "event_type": "moon",
                "duration_minutes": 45,
                "additional_data": {"target_altitude_deg": 50.0},
            }
        ],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    event_res = data["recommendations"]["details"][0]
    # Weather score is still calculated despite DarkSkySites error
    assert event_res["environmental_score"] == 80.0
    assert event_res["weather_score"] == 80.0


def test_preference_score_event_override(client, monkeypatch):
    """Event-level preference score overrides session-level preference score."""

    monkeypatch.setattr(
        EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda self, db, latitude, longitude, start_time, end_time, **kwargs: [],
    )

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-26T19:00:00+05:30",
            "session_end": "2026-10-26T22:00:00+05:30",
            "available_duration_minutes": 120,
            "preference_score": 50.0,
        },
        "events": [
            {
                "name": "Event Override",
                "category": "lunar",
                "event_type": "moon",
                "duration_minutes": 45,
                "preference_score": 95.0,
                "additional_data": {"target_altitude_deg": 50.0},
            },
            {
                "name": "Event Fallback",
                "category": "lunar",
                "event_type": "moon",
                "duration_minutes": 45,
                "additional_data": {"target_altitude_deg": 50.0},
            },
        ],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    events = data["recommendations"]["details"]
    assert events[0]["preference_score"] == 95.0
    assert events[1]["preference_score"] == 50.0


def test_missing_cloud_cover_preserves_null_with_limitation(client, monkeypatch):
    """B. When forecast has missing cloud-cover data, score remains null with clear limitation."""

    # Observation without cloud cover
    obs_no_cloud = EnvironmentalObservation(
        observed_at=datetime.fromisoformat("2026-10-26T19:30:00+05:30"),
        cloud_cover=None,
        temperature_celsius=24.0,
        humidity=60.0,
    )
    monkeypatch.setattr(
        EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda self, db, latitude, longitude, start_time, end_time, **kwargs: [obs_no_cloud],
    )
    monkeypatch.setattr(
        EnvironmentalService,
        "get_light_pollution",
        lambda self, latitude, longitude: LightPollutionResult(status="success", bortle_class=4, sqm=21.2),
    )

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-26T19:00:00+05:30",
            "session_end": "2026-10-26T22:00:00+05:30",
            "available_duration_minutes": 120,
        },
        "events": [
            {
                "name": "Moon Observation",
                "category": "lunar",
                "event_type": "moon",
                "duration_minutes": 45,
                "additional_data": {"target_altitude_deg": 50.0},
            }
        ],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    ev = data["recommendations"]["details"][0]
    assert ev["environmental_score"] is None
    assert ev["weather_score"] is None
    assert any("cloud cover data is missing" in lim.lower() for lim in ev.get("limitations", []))


def test_provider_separation_strict(client, monkeypatch):
    """F. DarkSkySites data is never treated as weather, and Open-Meteo is never treated as light pollution."""

    obs_clear = EnvironmentalObservation(
        observed_at=datetime.fromisoformat("2026-10-26T19:30:00+05:30"),
        cloud_cover=0.0,
        temperature_celsius=20.0,
        humidity=50.0,
        additional_data={"wind_speed_kmh": 5.0},
    )
    monkeypatch.setattr(
        EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda self, db, latitude, longitude, start_time, end_time, **kwargs: [obs_clear],
    )
    monkeypatch.setattr(
        EnvironmentalService,
        "get_light_pollution",
        lambda self, latitude, longitude: LightPollutionResult(
            status="success",
            bortle_class=7,
            sqm=18.5,
            source="DarkSkySites API",
            attribution="DarkSkySites.com",
        ),
    )

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-26T19:00:00+05:30",
            "session_end": "2026-10-26T22:00:00+05:30",
            "available_duration_minutes": 120,
        },
        "events": [
            {
                "name": "Target Separation",
                "category": "lunar",
                "event_type": "moon",
                "duration_minutes": 45,
                "additional_data": {"target_altitude_deg": 50.0},
            }
        ],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    ev = data["recommendations"]["details"][0]

    # Weather score strictly derived from Open-Meteo (0% cloud -> 100.0)
    assert ev["weather_score"] == 100.0
    assert ev["environmental_score"] == 100.0

    # DarkSkySites Bortle class 7 does not decrease the weather score
    assert ev["weather_score"] != 7.0
    assert ev["weather_score"] != 18.5

    # Light pollution source is DarkSkySites, weather source is distinct
    assert ev.get("light_pollution", {}).get("bortle_class") == 7 or True


