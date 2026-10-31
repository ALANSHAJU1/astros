
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.environmental_observation import EnvironmentalObservation
from app.schemas.environmental_observation import (
    EnvironmentalObservationCreate,
)


def create_observation(
    db: Session,
    observation_data: EnvironmentalObservationCreate,
) -> EnvironmentalObservation:
    """Add an environmental observation to the current transaction."""
    observation = EnvironmentalObservation(
        **observation_data.model_dump()
    )

    db.add(observation)
    db.flush()
    db.refresh(observation)

    return observation


def get_observation_by_id(
    db: Session,
    observation_id,
) -> EnvironmentalObservation | None:
    """Retrieve an observation by its UUID."""
    return db.get(EnvironmentalObservation, observation_id)


def get_observations_for_location(
    db: Session,
    latitude: float,
    longitude: float,
    start_time: datetime,
    end_time: datetime,
    limit: int = 100,
) -> list[EnvironmentalObservation]:
    """Retrieve observations for a location and time range."""
    if not -90 <= latitude <= 90:
        raise ValueError("latitude must be between -90 and 90")

    if not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180")

    if start_time.tzinfo is None or start_time.utcoffset() is None:
        raise ValueError("start_time must include a timezone")

    if end_time.tzinfo is None or end_time.utcoffset() is None:
        raise ValueError("end_time must include a timezone")

    if end_time <= start_time:
        raise ValueError("end_time must be after start_time")

    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    statement = (
        select(EnvironmentalObservation)
        .where(
            EnvironmentalObservation.latitude == latitude,
            EnvironmentalObservation.longitude == longitude,
            EnvironmentalObservation.observed_at >= start_time,
            EnvironmentalObservation.observed_at < end_time,
        )
        .order_by(EnvironmentalObservation.observed_at.desc())
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def get_latest_observation_for_location(
    db: Session,
    latitude: float,
    longitude: float,
) -> EnvironmentalObservation | None:
    """Retrieve the most recent observation for an exact coordinate pair."""
    if not -90 <= latitude <= 90:
        raise ValueError("latitude must be between -90 and 90")

    if not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180")

    statement = (
        select(EnvironmentalObservation)
        .where(
            EnvironmentalObservation.latitude == latitude,
            EnvironmentalObservation.longitude == longitude,
        )
        .order_by(EnvironmentalObservation.observed_at.desc())
        .limit(1)
    )

    return db.scalar(statement)
