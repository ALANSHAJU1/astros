"""Environmental data service.

Orchestrates weather forecast retrieval, normalization into EnvironmentalObservation,
freshness evaluation, light pollution context, and database persistence.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid
from sqlalchemy.orm import Session

from app.models.environmental_observation import EnvironmentalObservation
from app.repositories.environmental_observation_repository import (
    create_observation,
    get_observations_for_location,
)
from app.schemas.environmental_observation import EnvironmentalObservationCreate
from app.services.environmental_freshness import classify_observation_freshness
from app.services.light_pollution_service import (
    BaseLightPollutionProvider,
    LightPollutionResult,
    get_light_pollution_provider,
)
from app.services.weather_provider import (
    OpenMeteoWeatherProvider,
    WeatherProviderError,
)

DEFAULT_MAX_FORECAST_AGE_MINUTES = 120  # 2 hours before refetching forecasts


def classify_forecast_freshness(
    observation: EnvironmentalObservation,
    *,
    now: datetime | None = None,
    max_forecast_age_minutes: int = DEFAULT_MAX_FORECAST_AGE_MINUTES,
) -> str:
    """Classify the freshness of a forecast observation.

    Distinguishes forecasts (which apply to future/current viewing windows)
    from measured historical observations.
    """
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("now must include a timezone")

    observed_at = observation.observed_at
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        return "unknown"

    expires_at = observation.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            return "unknown"
        if expires_at <= current_time:
            return "expired"

    # For forecasts, verify how long ago the forecast was recorded
    recorded_at = observation.recorded_at
    if recorded_at is not None and recorded_at.tzinfo is not None:
        age = (current_time - recorded_at).total_seconds() / 60.0
        if age > max_forecast_age_minutes:
            return "stale"

    # If the observation window has already fully passed
    if observed_at + timedelta(hours=1) < current_time:
        return "expired"

    return "fresh"


class EnvironmentalService:
    """Service coordinating weather forecasts, light pollution, and persistence."""

    def __init__(
        self,
        weather_provider: OpenMeteoWeatherProvider | None = None,
        light_pollution_provider: BaseLightPollutionProvider | None = None,
    ) -> None:
        self.weather_provider = weather_provider or OpenMeteoWeatherProvider()
        self.light_pollution_provider = (
            light_pollution_provider or get_light_pollution_provider()
        )

    def get_or_fetch_forecast_observations(
        self,
        db: Session,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime,
        *,
        force_refresh: bool = False,
        persist: bool = True,
        now: datetime | None = None,
    ) -> list[EnvironmentalObservation]:
        """Retrieve existing fresh forecast observations from the database, or fetch,
        normalize, and persist new hourly forecasts from the weather provider.
        """
        if not -90 <= latitude <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")

        if start_time.tzinfo is None or start_time.utcoffset() is None:
            raise ValueError("start_time must include a timezone")
        if end_time.tzinfo is None or end_time.utcoffset() is None:
            raise ValueError("end_time must include a timezone")
        if end_time <= start_time:
            raise ValueError("end_time must be later than start_time")

        current_time = now or datetime.now(timezone.utc)

        # 1. Check existing observations in database
        if not force_refresh:
            existing = get_observations_for_location(
                db=db,
                latitude=latitude,
                longitude=longitude,
                start_time=start_time,
                end_time=end_time,
                limit=500,
            )
            # Check if existing observations adequately cover the window and are fresh
            if existing:
                all_fresh = all(
                    classify_forecast_freshness(obs, now=current_time) == "fresh"
                    for obs in existing
                )
                if all_fresh:
                    return existing

        # 2. Fetch fresh forecast from provider
        try:
            forecasts = self.weather_provider.fetch_hourly_forecast(
                latitude=latitude,
                longitude=longitude,
                start_time=start_time,
                end_time=end_time,
                force_refresh=force_refresh,
            )
        except WeatherProviderError:
            # If provider fails, fallback to any existing observations in DB
            existing_fallback = get_observations_for_location(
                db=db,
                latitude=latitude,
                longitude=longitude,
                start_time=start_time,
                end_time=end_time,
                limit=500,
            )
            if existing_fallback:
                return existing_fallback
            raise

        persisted_observations: list[EnvironmentalObservation] = []

        for fc in forecasts:
            additional_data = dict(fc.additional_data)
            additional_data["is_forecast"] = True
            additional_data["data_type"] = "forecast"
            additional_data["provider"] = fc.provider
            additional_data["attribution"] = fc.attribution
            additional_data["retrieved_at"] = fc.retrieved_at.isoformat()
            additional_data["raw_units"] = fc.raw_units

            # Expiry set to end of forecast valid hour
            expires_at = fc.observed_at + timedelta(hours=1)

            create_data = EnvironmentalObservationCreate(
                latitude=fc.latitude,
                longitude=fc.longitude,
                observed_at=fc.observed_at,
                temperature_celsius=fc.temperature_celsius,
                humidity=fc.humidity,
                cloud_cover=fc.cloud_cover,
                conditions=fc.conditions,
                additional_data=additional_data,
                source=f"{fc.provider} Forecast",
                expires_at=expires_at,
            )

            if persist:
                observation = create_observation(db, create_data)
                persisted_observations.append(observation)
            else:
                # In-memory transient instance if persist=False
                observation = EnvironmentalObservation(
                    id=uuid.uuid4(),
                    **create_data.model_dump(),
                    recorded_at=fc.retrieved_at,
                )
                persisted_observations.append(observation)

        return persisted_observations

    def get_light_pollution(
        self,
        latitude: float,
        longitude: float,
    ) -> LightPollutionResult:
        """Query light pollution context for coordinates."""
        return self.light_pollution_provider.get_light_pollution(
            latitude=latitude,
            longitude=longitude,
        )

    def build_session_environmental_context(
        self,
        db: Session,
        latitude: float,
        longitude: float,
        start_time: datetime,
        end_time: datetime,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Build a comprehensive, transparent environmental context combining weather
        forecasts, light pollution, freshness, and explicit limitations.
        """
        current_time = now or datetime.now(timezone.utc)
        limitations: list[str] = []

        # Weather observations
        weather_available = False
        observations: list[EnvironmentalObservation] = []
        try:
            observations = self.get_or_fetch_forecast_observations(
                db=db,
                latitude=latitude,
                longitude=longitude,
                start_time=start_time,
                end_time=end_time,
                now=current_time,
            )
            weather_available = len(observations) > 0
        except Exception as exc:
            limitations.append(f"Weather forecast retrieval failed: {exc}")

        # Light pollution
        lp_result = self.get_light_pollution(latitude, longitude)
        if lp_result.status != "success":
            limitations.extend(lp_result.limitations)

        # Evaluate freshness across observations
        freshness_status = "unknown"
        avg_cloud_cover: float | None = None
        if observations:
            freshness_statuses = [
                classify_forecast_freshness(obs, now=current_time)
                for obs in observations
            ]
            if any(s == "expired" for s in freshness_statuses):
                freshness_status = "expired"
                limitations.append("Some weather forecast data has expired.")
            elif any(s == "stale" for s in freshness_statuses):
                freshness_status = "stale"
                limitations.append("Weather forecast data is stale.")
            elif all(s == "fresh" for s in freshness_statuses):
                freshness_status = "fresh"

            valid_clouds = [
                obs.cloud_cover
                for obs in observations
                if obs.cloud_cover is not None
            ]
            if valid_clouds:
                avg_cloud_cover = round(sum(valid_clouds) / len(valid_clouds), 1)
            else:
                limitations.append("Cloud cover measurements are unavailable.")

        return {
            "environmental_data_available": weather_available,
            "freshness_status": freshness_status,
            "observations_count": len(observations),
            "average_cloud_cover": avg_cloud_cover,
            "light_pollution": lp_result.model_dump(),
            "limitations": limitations,
            "provider": "Open-Meteo",
            "attribution": "Weather data by Open-Meteo.com under CC BY 4.0",
        }
