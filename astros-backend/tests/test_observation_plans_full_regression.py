import json
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.environmental_observation import EnvironmentalObservation
from app.services.environmental_service import EnvironmentalService
from app.services.light_pollution_service import LightPollutionResult


def test_observation_plans_full_scoring_regression(client, monkeypatch):
    """Regression test ensuring:

    1. Valid matched forecast populates environmental_score and weather_score
    2. Session preference score (e.g. 80.0) is preserved and not coerced to 0
    3. Derived astronomical score (e.g. 78.3) is propagated into astronomical_score
    4. Missing scores and score_status accurately reflect availability
    5. Timezone-aware local session (UTC+05:30) correctly matches UTC ephemeris window
    """
    # Session window: 2026-10-28 19:30:00+05:30 to 21:00:00+05:30 (14:00 to 15:30 UTC)
    # Event window in UTC: 2026-10-28T14:00:00Z to 2026-10-28T15:30:00Z
    # Forecast observation: 2026-10-28T14:30:00Z with 20% cloud cover
    obs_matched = EnvironmentalObservation(
        observed_at=datetime(2026, 10, 28, 14, 30, tzinfo=timezone.utc),
        cloud_cover=20.0,
        temperature_celsius=24.0,
        humidity=60.0,
        additional_data={
            "cloud_cover_low": 10.0,
            "cloud_cover_mid": 10.0,
            "cloud_cover_high": 0.0,
            "precipitation_mm": 0.0,
            "wind_speed_kmh": 12.0,
            "visibility_meters": 10000.0,
        },
    )

    monkeypatch.setattr(
        EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda self, db, latitude, longitude, start_time, end_time, **kwargs: [obs_matched],
    )
    monkeypatch.setattr(
        EnvironmentalService,
        "get_light_pollution",
        lambda self, latitude, longitude: LightPollutionResult(
            status="success", bortle_class=4, sqm=21.2, source="DarkSkySites API"
        ),
    )

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-28T19:30:00+05:30",
            "session_end": "2026-10-28T21:00:00+05:30",
            "available_duration_minutes": 90,
            "preference_score": 80.0,
        },
        "events": [
            {
                "event_id": "horizons_301_test",
                "name": "Moon",
                "type": "moon",
                "event_type": "moon",
                "source": "NASA JPL Horizons API",
                "window_start": "2026-10-28T14:00:00+00:00",
                "window_end": "2026-10-28T15:30:00+00:00",
                "duration_minutes": 45.0,
                "required_duration_minutes": 45.0,
                "metadata": {
                    "derived_astronomical_values": {
                        "peak_elevation_deg": 48.5,
                        "computed_visibility_score": 78.3,
                    },
                    "nasa_horizons_facts": {
                        "phase_angle_deg": 45.0,
                    },
                },
            }
        ],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    event_detail = data["recommendations"]["details"][0]
    # 1. Environmental & weather score
    assert event_detail["environmental_score"] is not None
    assert event_detail["environmental_score"] == 92.0  # 100 - (0.5*10 + 0.3*10) = 92.0
    assert event_detail["weather_score"] == event_detail["environmental_score"]

    # 2. Preference score preserved from session
    assert event_detail["preference_score"] == 80.0

    # 3. Astronomical score propagated from derived values / adapter
    assert event_detail["astronomical_score"] is not None
    assert event_detail["astronomical_score"] > 70.0

    # 4. Visibility score is blended
    assert event_detail["visibility_score"] is not None
    assert event_detail["assessment_status"] == "success"

    # 5. Ranking metadata
    ranked = data["recommendations"]["ranked_events"][0]
    assert ranked["score_status"] == "complete"
    assert ranked["missing_scores"] == []
    assert ranked["recommendation_score"] is not None
    assert ranked["preference_score"] == 80.0
    assert ranked["weather_score"] == event_detail["weather_score"]


def test_missing_weather_ranking_metadata(client, monkeypatch):
    """When weather is missing, score_status must be 'partial' and 'weather' must be in missing_scores."""

    monkeypatch.setattr(
        EnvironmentalService,
        "get_or_fetch_forecast_observations",
        lambda self, db, latitude, longitude, start_time, end_time, **kwargs: [],
    )

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-28T19:30:00+05:30",
            "session_end": "2026-10-28T21:00:00+05:30",
            "available_duration_minutes": 90,
            "preference_score": 80.0,
        },
        "events": [
            {
                "event_id": "horizons_301_noweather",
                "name": "Moon",
                "type": "moon",
                "event_type": "moon",
                "source": "NASA JPL Horizons API",
                "window_start": "2026-10-28T14:00:00+00:00",
                "window_end": "2026-10-28T15:30:00+00:00",
                "duration_minutes": 45.0,
                "metadata": {
                    "derived_astronomical_values": {
                        "peak_elevation_deg": 48.5,
                        "computed_visibility_score": 78.3,
                    },
                },
            }
        ],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    event_detail = data["recommendations"]["details"][0]

    assert event_detail["environmental_score"] is None
    assert event_detail["weather_score"] is None
    assert event_detail["preference_score"] == 80.0

    ranked = data["recommendations"]["ranked_events"][0]
    assert ranked["score_status"] == "partial"
    assert "weather" in ranked["missing_scores"]
    assert ranked["weather_score"] is None
    # Effective weight on weather must be 0.0 because weather is missing
    assert ranked["effective_weights"]["weather"] == 0.0

