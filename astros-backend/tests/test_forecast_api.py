from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import uuid
import pytest

from app.schemas.weather import NormalizedWeatherForecast
from app.services.environmental_service import EnvironmentalService
from app.services.weather_provider import OpenMeteoWeatherProvider


def test_forecast_endpoint_success(client, db, monkeypatch):
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    mock_weather = MagicMock(spec=OpenMeteoWeatherProvider)
    mock_weather.fetch_hourly_forecast.return_value = [
        NormalizedWeatherForecast(
            latitude=10.5276,
            longitude=76.2144,
            observed_at=start,
            temperature_celsius=26.0,
            humidity=70.0,
            dew_point_celsius=20.0,
            precipitation_probability=0.0,
            precipitation_mm=0.0,
            cloud_cover=20.0,
            cloud_cover_low=10.0,
            cloud_cover_mid=10.0,
            cloud_cover_high=0.0,
            visibility_meters=10000.0,
            wind_speed_kmh=12.0,
            weather_code=1,
            conditions="Mainly clear",
            is_forecast=True,
            provider="Open-Meteo",
            attribution="Weather data by Open-Meteo.com under CC BY 4.0",
            retrieved_at=datetime.now(timezone.utc),
            raw_units={},
            additional_data={"is_forecast": True},
        )
    ]

    from app.api.routes import environmental_observations
    monkeypatch.setattr(
        environmental_observations,
        "EnvironmentalService",
        lambda: EnvironmentalService(weather_provider=mock_weather),
    )

    payload = {
        "latitude": 10.5276,
        "longitude": 76.2144,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "persist": True,
    }

    response = client.post(
        "/api/v1/environmental-observations/forecast",
        json=payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    item = data[0]
    assert item["cloud_cover"] == 20.0
    assert item["freshness_status"] == "fresh"
    assert item["additional_data"]["is_forecast"] is True


def test_forecast_endpoint_rejects_timezone_naive(client):
    payload = {
        "latitude": 10.5276,
        "longitude": 76.2144,
        "start_time": "2026-10-27T19:00:00",
        "end_time": "2026-10-27T21:00:00+05:30",
    }
    response = client.post(
        "/api/v1/environmental-observations/forecast",
        json=payload,
    )
    assert response.status_code == 422


def test_forecast_endpoint_rejects_reversed_time_range(client):
    start = datetime.now(timezone.utc)
    payload = {
        "latitude": 10.5276,
        "longitude": 76.2144,
        "start_time": (start + timedelta(hours=2)).isoformat(),
        "end_time": start.isoformat(),
    }
    response = client.post(
        "/api/v1/environmental-observations/forecast",
        json=payload,
    )
    assert response.status_code == 422


def test_forecast_endpoint_success_without_persistence(client, db, monkeypatch):
    from sqlalchemy import select
    from app.models.environmental_observation import EnvironmentalObservation

    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=3)

    mock_weather = MagicMock(spec=OpenMeteoWeatherProvider)
    mock_weather.fetch_hourly_forecast.return_value = [
        NormalizedWeatherForecast(
            latitude=10.5276,
            longitude=76.2144,
            observed_at=start,
            temperature_celsius=26.0,
            humidity=70.0,
            dew_point_celsius=20.0,
            precipitation_probability=0.0,
            precipitation_mm=0.0,
            cloud_cover=20.0,
            cloud_cover_low=10.0,
            cloud_cover_mid=10.0,
            cloud_cover_high=0.0,
            visibility_meters=10000.0,
            wind_speed_kmh=12.0,
            weather_code=1,
            conditions="Mainly clear",
            is_forecast=True,
            provider="Open-Meteo",
            attribution="Weather data by Open-Meteo.com under CC BY 4.0",
            retrieved_at=datetime.now(timezone.utc),
            raw_units={},
            additional_data={"is_forecast": True},
        ),
        NormalizedWeatherForecast(
            latitude=10.5276,
            longitude=76.2144,
            observed_at=start + timedelta(hours=1),
            temperature_celsius=25.0,
            humidity=72.0,
            dew_point_celsius=19.0,
            precipitation_probability=0.0,
            precipitation_mm=0.0,
            cloud_cover=30.0,
            cloud_cover_low=15.0,
            cloud_cover_mid=15.0,
            cloud_cover_high=0.0,
            visibility_meters=10000.0,
            wind_speed_kmh=10.0,
            weather_code=1,
            conditions="Partly cloudy",
            is_forecast=True,
            provider="Open-Meteo",
            attribution="Weather data by Open-Meteo.com under CC BY 4.0",
            retrieved_at=datetime.now(timezone.utc),
            raw_units={},
            additional_data={"is_forecast": True},
        ),
    ]

    from app.api.routes import environmental_observations
    monkeypatch.setattr(
        environmental_observations,
        "EnvironmentalService",
        lambda: EnvironmentalService(weather_provider=mock_weather),
    )

    payload = {
        "latitude": 10.5276,
        "longitude": 76.2144,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "persist": False,
    }

    response = client.post(
        "/api/v1/environmental-observations/forecast",
        json=payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    for item in data:
        assert "id" in item
        assert item["id"] is not None
        parsed_uuid = uuid.UUID(item["id"])
        assert str(parsed_uuid) == item["id"]
        assert item["freshness_status"] in ("fresh", "stale")

    # Verify no database rows were inserted
    db_rows = list(
        db.scalars(
            select(EnvironmentalObservation).where(
                EnvironmentalObservation.latitude == 10.5276,
                EnvironmentalObservation.longitude == 76.2144,
            )
        ).all()
    )
    assert len(db_rows) == 0
