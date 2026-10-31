from datetime import datetime, timedelta, timezone
import uuid
import pytest
from unittest.mock import MagicMock

from app.models.celestial_event import CelestialEvent
from app.models.visibility_assessment import VisibilityAssessment
from app.schemas.weather import NormalizedWeatherForecast
from app.services.environmental_service import EnvironmentalService
from app.services.light_pollution_service import LightPollutionResult
from app.services.weather_provider import OpenMeteoWeatherProvider


def create_test_event(db):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)
    event = CelestialEvent(
        category="planet",
        object_name="Jupiter",
        event_type="opposition",
        start_time=start,
        end_time=end,
        latitude=10.5276,
        longitude=76.2144,
        additional_data={"target_altitude_deg": 45.0, "apparent_magnitude": -2.5},
    )
    db.add(event)
    db.flush()
    return event


def test_calculate_endpoint_success(client, db, monkeypatch):
    event = create_test_event(db)

    # Mock weather provider
    mock_weather = MagicMock(spec=OpenMeteoWeatherProvider)
    mock_weather.fetch_hourly_forecast.return_value = [
        NormalizedWeatherForecast(
            latitude=10.5276,
            longitude=76.2144,
            observed_at=event.start_time,
            temperature_celsius=25.0,
            humidity=60.0,
            dew_point_celsius=17.0,
            precipitation_probability=0.0,
            precipitation_mm=0.0,
            cloud_cover=10.0,
            cloud_cover_low=5.0,
            cloud_cover_mid=5.0,
            cloud_cover_high=0.0,
            visibility_meters=15000.0,
            wind_speed_kmh=10.0,
            weather_code=0,
            conditions="Clear sky",
            is_forecast=True,
            provider="Open-Meteo",
            attribution="Weather data by Open-Meteo.com under CC BY 4.0",
            retrieved_at=datetime.now(timezone.utc),
            raw_units={},
            additional_data={"is_forecast": True},
        )
    ]

    mock_lp = MagicMock()
    mock_lp.get_light_pollution.return_value = LightPollutionResult(
        status="unavailable",
        limitations=["Light pollution dataset is not configured."],
    )

    fake_env_service = EnvironmentalService(
        weather_provider=mock_weather,
        light_pollution_provider=mock_lp,
    )

    from app.services import visibility_assessment_service
    monkeypatch.setattr(
        visibility_assessment_service,
        "EnvironmentalService",
        lambda: fake_env_service,
    )

    payload = {
        "event_id": str(event.id),
        "latitude": 10.5276,
        "longitude": 76.2144,
        "persist": True,
    }

    response = client.post(
        "/api/v1/visibility-assessments/calculate",
        json=payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == str(event.id)
    assert data["status"] == "success"
    assert data["environmental_score"] == 90.0
    assert data["astronomical_score"] == 100.0
    assert data["visibility_score"] == 94.0
    assert data["quality_label"] == "Optimal"
    assert data["is_persisted"] is True
    assert data["id"] is not None

    # Check persistence in DB
    assessment_id = uuid.UUID(data["id"])
    persisted = db.get(VisibilityAssessment, assessment_id)
    assert persisted is not None
    assert persisted.visibility_score == 94.0


def test_calculate_endpoint_nonexistent_event(client):
    payload = {
        "event_id": str(uuid.uuid4()),
        "latitude": 10.5276,
        "longitude": 76.2144,
    }

    response = client.post(
        "/api/v1/visibility-assessments/calculate",
        json=payload,
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_calculate_endpoint_invalid_coordinates(client):
    payload = {
        "event_id": str(uuid.uuid4()),
        "latitude": 95.0,  # Invalid
        "longitude": 76.2144,
    }

    response = client.post(
        "/api/v1/visibility-assessments/calculate",
        json=payload,
    )

    assert response.status_code == 422


def test_calculate_endpoint_without_persistence(client, db, monkeypatch):
    event = create_test_event(db)

    payload = {
        "event_id": str(event.id),
        "latitude": 10.5276,
        "longitude": 76.2144,
        "persist": False,
    }

    response = client.post(
        "/api/v1/visibility-assessments/calculate",
        json=payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_persisted"] is False
    assert data["id"] is None
