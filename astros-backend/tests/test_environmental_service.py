from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import uuid
import pytest

from app.models.environmental_observation import EnvironmentalObservation
from app.schemas.weather import NormalizedWeatherForecast
from app.services.environmental_service import (
    EnvironmentalService,
    classify_forecast_freshness,
)
from app.services.light_pollution_service import UnavailableLightPollutionProvider
from app.services.weather_provider import (
    OpenMeteoWeatherProvider,
    WeatherProviderError,
)


def make_mock_forecast(dt, cloud_cover=20.0, temp=25.0):
    return NormalizedWeatherForecast(
        latitude=10.5276,
        longitude=76.2144,
        observed_at=dt,
        temperature_celsius=temp,
        humidity=75.0,
        dew_point_celsius=20.0,
        precipitation_probability=0.0,
        precipitation_mm=0.0,
        cloud_cover=cloud_cover,
        cloud_cover_low=10.0,
        cloud_cover_mid=10.0,
        cloud_cover_high=0.0,
        visibility_meters=10000.0,
        wind_speed_kmh=10.0,
        weather_code=1,
        conditions="Mainly clear",
        is_forecast=True,
        provider="Open-Meteo",
        attribution="Weather data by Open-Meteo.com under CC BY 4.0",
        retrieved_at=datetime.now(timezone.utc),
        raw_units={},
        additional_data={"is_forecast": True},
    )


def test_classify_forecast_freshness():
    now = datetime(2026, 10, 27, 20, 0, tzinfo=timezone.utc)

    # Fresh forecast
    fresh_obs = EnvironmentalObservation(
        latitude=10.0,
        longitude=76.0,
        observed_at=now + timedelta(hours=1),
        recorded_at=now - timedelta(minutes=15),
        expires_at=now + timedelta(hours=2),
        source="Open-Meteo",
    )
    assert classify_forecast_freshness(fresh_obs, now=now) == "fresh"

    # Expired forecast (expires_at in past)
    expired_obs = EnvironmentalObservation(
        latitude=10.0,
        longitude=76.0,
        observed_at=now - timedelta(hours=2),
        recorded_at=now - timedelta(hours=3),
        expires_at=now - timedelta(minutes=1),
        source="Open-Meteo",
    )
    assert classify_forecast_freshness(expired_obs, now=now) == "expired"

    # Stale forecast (recorded more than max_forecast_age ago)
    stale_obs = EnvironmentalObservation(
        latitude=10.0,
        longitude=76.0,
        observed_at=now + timedelta(hours=1),
        recorded_at=now - timedelta(hours=4),
        expires_at=now + timedelta(hours=2),
        source="Open-Meteo",
    )
    assert classify_forecast_freshness(stale_obs, now=now) == "stale"


def test_fetch_and_persist_forecast(db):
    mock_weather = MagicMock(spec=OpenMeteoWeatherProvider)
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    mock_weather.fetch_hourly_forecast.return_value = [
        make_mock_forecast(start),
        make_mock_forecast(start + timedelta(hours=1)),
    ]

    service = EnvironmentalService(weather_provider=mock_weather)

    observations = service.get_or_fetch_forecast_observations(
        db=db,
        latitude=10.5276,
        longitude=76.2144,
        start_time=start,
        end_time=end,
    )

    assert len(observations) == 2
    assert observations[0].cloud_cover == 20.0
    assert observations[0].additional_data["is_forecast"] is True
    assert observations[0].additional_data["data_type"] == "forecast"
    assert "Open-Meteo" in observations[0].source


def test_avoid_duplicate_persistence_when_cached_in_db(db):
    mock_weather = MagicMock(spec=OpenMeteoWeatherProvider)
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    mock_weather.fetch_hourly_forecast.return_value = [
        make_mock_forecast(start),
    ]

    service = EnvironmentalService(weather_provider=mock_weather)

    # First call: fetches from provider and persists
    obs1 = service.get_or_fetch_forecast_observations(
        db=db,
        latitude=10.5276,
        longitude=76.2144,
        start_time=start,
        end_time=end,
    )
    assert mock_weather.fetch_hourly_forecast.call_count == 1

    # Second call: finds fresh DB observations, does not refetch
    obs2 = service.get_or_fetch_forecast_observations(
        db=db,
        latitude=10.5276,
        longitude=76.2144,
        start_time=start,
        end_time=end,
    )
    assert mock_weather.fetch_hourly_forecast.call_count == 1
    assert len(obs2) == len(obs1)


def test_provider_failure_with_fallback(db):
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    # 1. Insert an existing observation in DB
    existing_obs = EnvironmentalObservation(
        latitude=10.5276,
        longitude=76.2144,
        observed_at=start,
        recorded_at=datetime.now(timezone.utc) - timedelta(hours=3),
        cloud_cover=40.0,
        source="Open-Meteo",
        additional_data={"is_forecast": True},
        expires_at=start + timedelta(hours=1),
    )
    db.add(existing_obs)
    db.flush()

    # 2. Weather provider raises error
    mock_weather = MagicMock(spec=OpenMeteoWeatherProvider)
    mock_weather.fetch_hourly_forecast.side_effect = WeatherProviderError("Network down")

    service = EnvironmentalService(weather_provider=mock_weather)

    # Should fallback to existing observation
    observations = service.get_or_fetch_forecast_observations(
        db=db,
        latitude=10.5276,
        longitude=76.2144,
        start_time=start,
        end_time=end,
        force_refresh=True,
    )

    assert len(observations) >= 1
    assert observations[0].cloud_cover == 40.0


def test_build_session_environmental_context(db):
    mock_weather = MagicMock(spec=OpenMeteoWeatherProvider)
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    mock_weather.fetch_hourly_forecast.return_value = [
        make_mock_forecast(start, cloud_cover=15.0),
        make_mock_forecast(start + timedelta(hours=1), cloud_cover=25.0),
    ]

    service = EnvironmentalService(
        weather_provider=mock_weather,
        light_pollution_provider=UnavailableLightPollutionProvider(),
    )

    context = service.build_session_environmental_context(
        db=db,
        latitude=10.5276,
        longitude=76.2144,
        start_time=start,
        end_time=end,
    )

    assert context["environmental_data_available"] is True
    assert context["average_cloud_cover"] == 20.0
    assert context["light_pollution"]["status"] == "unavailable"
    assert any("not configured" in item for item in context["limitations"])


def test_forecast_observations_without_persistence(db):
    from sqlalchemy import select

    mock_weather = MagicMock(spec=OpenMeteoWeatherProvider)
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    mock_weather.fetch_hourly_forecast.return_value = [
        make_mock_forecast(start, cloud_cover=10.0),
        make_mock_forecast(start + timedelta(hours=1), cloud_cover=20.0),
    ]

    service = EnvironmentalService(weather_provider=mock_weather)

    observations = service.get_or_fetch_forecast_observations(
        db=db,
        latitude=10.5276,
        longitude=76.2144,
        start_time=start,
        end_time=end,
        persist=False,
    )

    assert len(observations) == 2
    for obs in observations:
        assert obs.id is not None
        assert isinstance(obs.id, uuid.UUID)

    # Verify no database persistence occurred
    db_records = list(
        db.scalars(
            select(EnvironmentalObservation).where(
                EnvironmentalObservation.latitude == 10.5276,
                EnvironmentalObservation.longitude == 76.2144,
            )
        ).all()
    )
    assert len(db_records) == 0
