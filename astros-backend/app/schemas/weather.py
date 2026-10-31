from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class NormalizedWeatherForecast(BaseModel):
    """Normalized hourly weather forecast data point from a weather provider."""

    model_config = ConfigDict(frozen=True)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    observed_at: datetime
    temperature_celsius: float | None = None
    humidity: float | None = Field(default=None, ge=0, le=100)
    dew_point_celsius: float | None = None
    precipitation_probability: float | None = Field(default=None, ge=0, le=100)
    precipitation_mm: float | None = Field(default=None, ge=0)
    cloud_cover: float | None = Field(default=None, ge=0, le=100)
    cloud_cover_low: float | None = Field(default=None, ge=0, le=100)
    cloud_cover_mid: float | None = Field(default=None, ge=0, le=100)
    cloud_cover_high: float | None = Field(default=None, ge=0, le=100)
    visibility_meters: float | None = Field(default=None, ge=0)
    wind_speed_kmh: float | None = Field(default=None, ge=0)
    weather_code: int | None = None
    conditions: str | None = None
    is_forecast: bool = True
    provider: str = "Open-Meteo"
    attribution: str = "Weather data by Open-Meteo.com under CC BY 4.0"
    retrieved_at: datetime
    raw_units: dict[str, str] = Field(default_factory=dict)
    additional_data: dict[str, Any] = Field(default_factory=dict)
