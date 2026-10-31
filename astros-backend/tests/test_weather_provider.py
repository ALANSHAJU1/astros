from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import httpx
import pytest

from app.services.weather_provider import (
    OpenMeteoWeatherProvider,
    WeatherProviderDataError,
    WeatherProviderHTTPError,
    WeatherProviderRateLimitError,
    WeatherProviderTimeoutError,
)


def mock_open_meteo_response():
    return {
        "latitude": 10.52,
        "longitude": 76.21,
        "utc_offset_seconds": 0,
        "timezone": "UTC",
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "cloud_cover": "%",
            "visibility": "m",
            "wind_speed_10m": "km/h",
        },
        "hourly": {
            "time": [
                "2026-10-27T19:00",
                "2026-10-27T20:00",
                "2026-10-27T21:00",
            ],
            "temperature_2m": [26.4, 25.8, 25.2],
            "relative_humidity_2m": [78, 82, 85],
            "dew_point_2m": [22.1, 22.4, 22.5],
            "precipitation_probability": [5, 10, 15],
            "precipitation": [0.0, 0.0, 0.1],
            "cloud_cover": [15, 20, 30],
            "cloud_cover_low": [5, 10, 10],
            "cloud_cover_mid": [10, 10, 20],
            "cloud_cover_high": [0, 0, 0],
            "visibility": [12000.0, 10000.0, 9500.0],
            "wind_speed_10m": [8.5, 7.2, 6.0],
            "weather_code": [1, 2, 61],
        },
    }


def test_fetch_forecast_success(monkeypatch):
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_open_meteo_response()
    mock_client.get.return_value = mock_resp

    provider = OpenMeteoWeatherProvider(client=mock_client)

    start = datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 27, 21, 0, tzinfo=timezone.utc)

    results = provider.fetch_hourly_forecast(
        latitude=10.5276,
        longitude=76.2144,
        start_time=start,
        end_time=end,
    )

    assert len(results) == 3
    first = results[0]
    assert first.latitude == 10.5276
    assert first.longitude == 76.2144
    assert first.observed_at == start
    assert first.temperature_celsius == 26.4
    assert first.humidity == 78
    assert first.cloud_cover == 15
    assert first.conditions == "Mainly clear"
    assert first.is_forecast is True
    assert first.provider == "Open-Meteo"
    assert "CC BY 4.0" in first.attribution
    assert first.retrieved_at.tzinfo == timezone.utc

    last = results[2]
    assert last.conditions == "Slight rain"
    assert last.precipitation_mm == 0.1


def test_fetch_forecast_missing_optional_fields():
    data = {
        "hourly": {
            "time": ["2026-10-27T19:00"],
            "temperature_2m": [20.0],
            "cloud_cover": [50],
        }
    }
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = data
    mock_client.get.return_value = mock_resp

    provider = OpenMeteoWeatherProvider(client=mock_client)
    start = datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 27, 20, 0, tzinfo=timezone.utc)

    results = provider.fetch_hourly_forecast(
        latitude=10.0,
        longitude=70.0,
        start_time=start,
        end_time=end,
    )

    assert len(results) == 1
    point = results[0]
    assert point.temperature_celsius == 20.0
    assert point.cloud_cover == 50
    assert point.humidity is None
    assert point.visibility_meters is None
    assert point.wind_speed_kmh is None
    assert point.conditions is None


def test_fetch_forecast_caching():
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = mock_open_meteo_response()
    mock_client.get.return_value = mock_resp

    provider = OpenMeteoWeatherProvider(client=mock_client, cache_ttl=3600)
    start = datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 27, 21, 0, tzinfo=timezone.utc)

    res1 = provider.fetch_hourly_forecast(10.52, 76.21, start, end)
    res2 = provider.fetch_hourly_forecast(10.52, 76.21, start, end)

    assert len(res1) == len(res2)
    assert mock_client.get.call_count == 1

    # Force refresh makes a new request
    res3 = provider.fetch_hourly_forecast(10.52, 76.21, start, end, force_refresh=True)
    assert mock_client.get.call_count == 2


def test_fetch_forecast_timeout_error():
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.side_effect = httpx.ReadTimeout("Read timed out")

    provider = OpenMeteoWeatherProvider(client=mock_client)
    start = datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 27, 21, 0, tzinfo=timezone.utc)

    with pytest.raises(WeatherProviderTimeoutError, match="Timed out"):
        provider.fetch_hourly_forecast(10.0, 70.0, start, end)


def test_fetch_forecast_rate_limit_error():
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(status_code=429, text="Too Many Requests")
    mock_client.get.return_value = mock_resp

    provider = OpenMeteoWeatherProvider(client=mock_client)
    start = datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 27, 21, 0, tzinfo=timezone.utc)

    with pytest.raises(WeatherProviderRateLimitError, match="rate limit"):
        provider.fetch_hourly_forecast(10.0, 70.0, start, end)


def test_fetch_forecast_http_error():
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(status_code=500, text="Internal Server Error")
    mock_client.get.return_value = mock_resp

    provider = OpenMeteoWeatherProvider(client=mock_client)
    start = datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 27, 21, 0, tzinfo=timezone.utc)

    with pytest.raises(WeatherProviderHTTPError, match="HTTP 500"):
        provider.fetch_hourly_forecast(10.0, 70.0, start, end)


def test_fetch_forecast_malformed_json():
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.side_effect = ValueError("Invalid JSON")
    mock_client.get.return_value = mock_resp

    provider = OpenMeteoWeatherProvider(client=mock_client)
    start = datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 27, 21, 0, tzinfo=timezone.utc)

    with pytest.raises(WeatherProviderDataError, match="Malformed JSON"):
        provider.fetch_hourly_forecast(10.0, 70.0, start, end)


def test_fetch_forecast_validation():
    provider = OpenMeteoWeatherProvider()
    valid_start = datetime.now(timezone.utc)
    valid_end = valid_start + timedelta(hours=2)

    with pytest.raises(ValueError, match="Latitude"):
        provider.fetch_hourly_forecast(95.0, 70.0, valid_start, valid_end)

    with pytest.raises(ValueError, match="Longitude"):
        provider.fetch_hourly_forecast(10.0, 200.0, valid_start, valid_end)

    with pytest.raises(ValueError, match="timezone-aware"):
        provider.fetch_hourly_forecast(10.0, 70.0, datetime(2026, 10, 27, 19), valid_end)

    with pytest.raises(ValueError, match="later than start_time"):
        provider.fetch_hourly_forecast(10.0, 70.0, valid_end, valid_start)
