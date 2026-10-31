from datetime import datetime, timedelta, timezone
from typing import Literal

from app.models.environmental_observation import EnvironmentalObservation


FreshnessStatus = Literal["fresh", "stale", "expired", "unknown"]

DEFAULT_MAX_AGE_MINUTES = 60


def classify_observation_freshness(
    observation: EnvironmentalObservation,
    *,
    now: datetime | None = None,
    max_age_minutes: int = DEFAULT_MAX_AGE_MINUTES,
) -> FreshnessStatus:
    """Classify an environmental observation using its timestamps.

    Freshness is based on observed_at, not recorded_at.
    Expiry takes precedence over age.
    """
    if max_age_minutes < 1:
        raise ValueError("max_age_minutes must be at least 1")

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

    if observed_at > current_time:
        return "unknown"

    if current_time - observed_at > timedelta(minutes=max_age_minutes):
        return "stale"

    return "fresh"
