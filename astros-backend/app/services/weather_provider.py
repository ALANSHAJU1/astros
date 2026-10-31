"""Weather provider module integrating with Open-Meteo API.

Provides normalized hourly forecasts with timezone-aware timestamps,
transparent caching, timeout handling, and WMO weather code mapping.
"""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Mapping
import httpx

from app.core.config import (
    OPEN_METEO_BASE_URL,
    WEATHER_CACHE_TTL_SECONDS,
    WEATHER_REQUEST_TIMEOUT_SECONDS,
)
from app.schemas.weather import NormalizedWeatherForecast

# WMO Weather interpretation codes (WW)
WMO_CODE_MAP: Mapping[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

DEFAULT_HOURLY_VARS = (
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "precipitation_probability",
    "precipitation",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "visibility",
    "wind_speed_10m",
    "weather_code",
)


class WeatherProviderError(Exception):
    """Base exception for weather provider errors."""


class WeatherProviderHTTPError(WeatherProviderError):
    """Raised when weather provider returns an HTTP error status."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"Weather provider HTTP {status_code}: {message}")


class WeatherProviderRateLimitError(WeatherProviderHTTPError):
    """Raised when provider returns HTTP 429 rate limit."""

    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(429, message)


class WeatherProviderTimeoutError(WeatherProviderError):
    """Raised when request to weather provider times out."""


class WeatherProviderDataError(WeatherProviderError):
    """Raised when weather provider response structure is invalid."""


class OpenMeteoWeatherProvider:
    """Weather provider implementation for Open-Meteo forecast API."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        cache_ttl: int | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = (base_url or OPEN_METEO_BASE_URL).rstrip("/")
        self.timeout = (
            timeout
            if timeout is not None
            else WEATHER_REQUEST_TIMEOUT_SECONDS
        )
        self.cache_ttl = (
            cache_ttl
            if cache_ttl is not None
            else WEATHER_CACHE_TTL_SECONDS
        )
        self._external_client = client
        # In-memory cache: key -> (timestamp, list[NormalizedWeatherForecast])
        self._cache: dict[
            tuple[float, float, str, str],
            tuple[float, list[NormalizedWeatherForecast]],
        ] = {}

    def clear_cache(self) -> None:
        """Clear all cached forecast responses."""
        self._cache.clear()

    def _get_client(self) -> httpx.Client:
        if self._external_client is not None:
            return self._external_client
        return httpx.Client(timeout=self.timeout)

    def fetch_hourly_forecast(
        self,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime,
        *,
        force_refresh: bool = False,
    ) -> list[NormalizedWeatherForecast]:
        """Fetch and normalize hourly weather forecasts for coordinates and time range."""
        if not -90 <= latitude <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")

        if start_time.tzinfo is None or start_time.utcoffset() is None:
            raise ValueError("start_time must be timezone-aware")
        if end_time.tzinfo is None or end_time.utcoffset() is None:
            raise ValueError("end_time must be timezone-aware")
        if end_time <= start_time:
            raise ValueError("end_time must be later than start_time")

        # Convert to UTC for Open-Meteo dates
        start_utc = start_time.astimezone(timezone.utc)
        end_utc = end_time.astimezone(timezone.utc)

        start_date_str = start_utc.date().isoformat()
        end_date_str = end_utc.date().isoformat()

        cache_key = (
            round(latitude, 3),
            round(longitude, 3),
            start_date_str,
            end_date_str,
        )

        now_monotonic = time.monotonic()
        if not force_refresh and cache_key in self._cache:
            cached_at, cached_items = self._cache[cache_key]
            if now_monotonic - cached_at < self.cache_ttl:
                # Filter to requested window
                return [
                    item
                    for item in cached_items
                    if start_utc <= item.observed_at <= end_utc
                ]

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(DEFAULT_HOURLY_VARS),
            "start_date": start_date_str,
            "end_date": end_date_str,
            "timezone": "UTC",
        }

        retrieved_at = datetime.now(timezone.utc)

        try:
            client = self._get_client()
            if self._external_client is not None:
                response = client.get(self.base_url, params=params)
            else:
                with client:
                    response = client.get(self.base_url, params=params)
        except httpx.TimeoutException as exc:
            raise WeatherProviderTimeoutError(
                f"Timed out after {self.timeout}s contacting Open-Meteo: {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise WeatherProviderError(
                f"Failed to communicate with Open-Meteo: {exc}"
            ) from exc

        if response.status_code == 429:
            raise WeatherProviderRateLimitError("Open-Meteo rate limit exceeded.")

        if response.status_code != 200:
            raise WeatherProviderHTTPError(
                response.status_code,
                response.text or "Unknown error",
            )

        try:
            data = response.json()
        except Exception as exc:
            raise WeatherProviderDataError(
                f"Malformed JSON response from weather provider: {exc}"
            ) from exc

        normalized_list = self._parse_and_normalize(
            data=data,
            latitude=latitude,
            longitude=longitude,
            retrieved_at=retrieved_at,
        )

        # Store full date range in cache
        self._cache[cache_key] = (now_monotonic, normalized_list)

        # Return only items within requested start and end
        return [
            item
            for item in normalized_list
            if start_utc <= item.observed_at <= end_utc
        ]

    def _parse_and_normalize(
        self,
        data: dict[str, Any],
        latitude: float,
        longitude: float,
        retrieved_at: datetime,
    ) -> list[NormalizedWeatherForecast]:
        if not isinstance(data, dict):
            raise WeatherProviderDataError("Weather response is not a JSON object")

        hourly = data.get("hourly")
        if not isinstance(hourly, dict) or "time" not in hourly:
            raise WeatherProviderDataError(
                "Missing 'hourly' or 'hourly.time' in weather response"
            )

        times = hourly.get("time")
        if not isinstance(times, list):
            raise WeatherProviderDataError("'hourly.time' must be a list")

        count = len(times)
        raw_units = data.get("hourly_units", {})
        if not isinstance(raw_units, dict):
            raw_units = {}

        results: list[NormalizedWeatherForecast] = []

        for idx in range(count):
            time_str = times[idx]
            try:
                # Open-Meteo returns 'YYYY-MM-DDTHH:MM' in requested timezone (UTC)
                if not time_str.endswith("Z") and "+" not in time_str and "-" not in time_str[10:]:
                    dt = datetime.fromisoformat(time_str).replace(tzinfo=timezone.utc)
                else:
                    dt = datetime.fromisoformat(time_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
            except Exception as exc:
                raise WeatherProviderDataError(
                    f"Invalid timestamp '{time_str}' at index {idx}: {exc}"
                ) from exc

            def get_val(key: str) -> Any:
                arr = hourly.get(key)
                if isinstance(arr, list) and idx < len(arr):
                    return arr[idx]
                return None

            weather_code = get_val("weather_code")
            try:
                weather_code_int = int(weather_code) if weather_code is not None else None
            except (ValueError, TypeError):
                weather_code_int = None

            conditions = (
                WMO_CODE_MAP.get(weather_code_int, "Unknown")
                if weather_code_int is not None
                else None
            )

            # Defensive float extraction
            def get_float(key: str) -> float | None:
                val = get_val(key)
                if val is None:
                    return None
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return None

            cloud_cover = get_float("cloud_cover")
            cloud_cover_low = get_float("cloud_cover_low")
            cloud_cover_mid = get_float("cloud_cover_mid")
            cloud_cover_high = get_float("cloud_cover_high")
            temperature = get_float("temperature_2m")
            humidity = get_float("relative_humidity_2m")
            dew_point = get_float("dew_point_2m")
            precip_prob = get_float("precipitation_probability")
            precipitation = get_float("precipitation")
            visibility = get_float("visibility")
            wind_speed = get_float("wind_speed_10m")

            additional = {
                "dew_point_celsius": dew_point,
                "precipitation_probability": precip_prob,
                "precipitation_mm": precipitation,
                "cloud_cover_low": cloud_cover_low,
                "cloud_cover_mid": cloud_cover_mid,
                "cloud_cover_high": cloud_cover_high,
                "wind_speed_kmh": wind_speed,
                "visibility_meters": visibility,
                "weather_code": weather_code_int,
                "visibility_caveat": (
                    "Weather-model visibility estimates horizontal ground visibility, "
                    "not astronomical transparency."
                ),
            }

            forecast_point = NormalizedWeatherForecast(
                latitude=latitude,
                longitude=longitude,
                observed_at=dt,
                temperature_celsius=temperature,
                humidity=humidity,
                dew_point_celsius=dew_point,
                precipitation_probability=precip_prob,
                precipitation_mm=precipitation,
                cloud_cover=cloud_cover,
                cloud_cover_low=cloud_cover_low,
                cloud_cover_mid=cloud_cover_mid,
                cloud_cover_high=cloud_cover_high,
                visibility_meters=visibility,
                wind_speed_kmh=wind_speed,
                weather_code=weather_code_int,
                conditions=conditions,
                is_forecast=True,
                provider="Open-Meteo",
                attribution="Weather data by Open-Meteo.com under CC BY 4.0",
                retrieved_at=retrieved_at,
                raw_units=raw_units,
                additional_data=additional,
            )
            results.append(forecast_point)

        return results
