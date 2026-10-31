import uuid
from datetime import datetime, timedelta, timezone
import pytest
from app.services.environmental_service import EnvironmentalService
from app.services.visibility_scoring_engine import (
    calculate_environmental_suitability,
    evaluate_event_visibility,
)
from app.services.weather_provider import (
    OpenMeteoWeatherProvider,
    WeatherProviderError,
    WeatherProviderHTTPError,
    WeatherProviderTimeoutError,
)
from app.schemas.weather import NormalizedWeatherForecast


class DummyResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


class DummyHttpClient:
    def __init__(self, handler):
        self.handler = handler

    def get(self, url, params=None, headers=None):
        return self.handler(url, params, headers)


def test_open_meteo_valid_provider_response():
    sample_data = {
        "latitude": 10.5,
        "longitude": 76.2,
        "hourly": {
            "time": ["2026-10-26T19:00", "2026-10-26T20:00"],
            "temperature_2m": [25.0, 24.5],
            "relative_humidity_2m": [70.0, 75.0],
            "dew_point_2m": [19.0, 19.5],
            "precipitation_probability": [0.0, 0.0],
            "precipitation": [0.0, 0.0],
            "cloud_cover": [10.0, 20.0],
            "cloud_cover_low": [5.0, 10.0],
            "cloud_cover_mid": [5.0, 5.0],
            "cloud_cover_high": [0.0, 5.0],
            "visibility": [10000.0, 10000.0],
            "wind_speed_10m": [8.0, 7.0],
            "weather_code": [0, 1],
        },
        "hourly_units": {"temperature_2m": "°C"},
    }
    client = DummyHttpClient(lambda url, p, h: DummyResponse(200, sample_data))
    provider = OpenMeteoWeatherProvider(client=client)
    start = datetime(2026, 10, 26, 19, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 26, 21, 0, tzinfo=timezone.utc)

    results = provider.fetch_hourly_forecast(10.5, 76.2, start, end)
    assert len(results) == 2
    assert results[0].temperature_celsius == 25.0
    assert results[0].cloud_cover == 10.0
    assert results[0].conditions == "Clear sky"


def test_open_meteo_provider_returning_no_data():
    empty_data = {
        "latitude": 10.5,
        "longitude": 76.2,
        "hourly": {
            "time": [],
            "temperature_2m": [],
            "cloud_cover": [],
        },
    }
    client = DummyHttpClient(lambda url, p, h: DummyResponse(200, empty_data))
    provider = OpenMeteoWeatherProvider(client=client)
    start = datetime(2026, 10, 26, 19, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 26, 21, 0, tzinfo=timezone.utc)

    results = provider.fetch_hourly_forecast(10.5, 76.2, start, end)
    assert len(results) == 0


def test_open_meteo_network_failure():
    def raise_err(url, p, h):
        raise WeatherProviderTimeoutError("Connection timed out")

    client = DummyHttpClient(raise_err)
    provider = OpenMeteoWeatherProvider(client=client)
    start = datetime(2026, 10, 26, 19, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 26, 21, 0, tzinfo=timezone.utc)

    with pytest.raises(WeatherProviderTimeoutError):
        provider.fetch_hourly_forecast(10.5, 76.2, start, end)


def test_environmental_scoring_genuine_zero():
    """Heavy rain and 100% cloud cover produces a genuine 0.0 or near zero score."""
    now_dt = datetime(2026, 10, 26, 19, 30, tzinfo=timezone.utc)
    data = {
        "cloud_cover": 100.0,
        "cloud_cover_low": 100.0,
        "cloud_cover_mid": 100.0,
        "cloud_cover_high": 100.0,
        "temperature_celsius": 20.0,
        "humidity": 95.0,
        "precipitation_mm": 15.0,
        "wind_speed_kmh": 40.0,
        "visibility_meters": 1500.0,
        "observed_at": now_dt,
    }
    suitability = calculate_environmental_suitability(data, now=now_dt)
    assert suitability.score is not None
    assert suitability.score <= 5.0
    assert suitability.status in ("success", "partial_success")
    assert suitability.quality_label == "Unusable"


def test_environmental_scoring_missing_cloud_cover():
    """Missing essential cloud cover produces None score, never 0.0."""
    data = {
        "temperature_celsius": 20.0,
        "humidity": 50.0,
    }
    suitability = calculate_environmental_suitability(data)
    assert suitability.score is None
    assert suitability.status == "unavailable"


def test_event_coordinates_inherited_and_evaluated():
    """Event without explicit coordinates inherits from session and evaluates."""
    now_dt = datetime(2026, 10, 26, 19, 0, tzinfo=timezone.utc)
    event = {
        "name": "Target Without Coords",
        "category": "lunar",
        "event_type": "moon",
        "start_time": now_dt.isoformat(),
        "end_time": (now_dt + timedelta(hours=1)).isoformat(),
        "additional_data": {"target_altitude_deg": 50.0, "phase_angle_deg": 20.0},
    }
    weather = {
        "cloud_cover": 10.0,
        "observed_at": now_dt + timedelta(minutes=15),
    }
    assessment = evaluate_event_visibility(
        event=event,
        environmental_data=weather,
        latitude=10.5276,
        longitude=76.2144,
    )
    assert assessment.environmental_score is not None
    assert assessment.environmental_score == 90.0
    assert assessment.astronomical_score is not None
    assert assessment.visibility_score is not None

