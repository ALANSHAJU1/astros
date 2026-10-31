
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.celestial_event import CelestialEvent


def get_events_for_session(
    db: Session,
    session_start: datetime,
    session_end: datetime,
    category: str | None = None,
    limit: int = 100,
) -> list[CelestialEvent]:
    """Return database events overlapping an observation session."""

    if session_start.tzinfo is None or session_start.utcoffset() is None:
        raise ValueError("session_start must be timezone-aware")

    if session_end.tzinfo is None or session_end.utcoffset() is None:
        raise ValueError("session_end must be timezone-aware")

    if session_end <= session_start:
        raise ValueError("session_end must be later than session_start")

    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    overlaps = or_(
        (
            CelestialEvent.end_time.is_not(None)
            & (CelestialEvent.start_time < session_end)
            & (CelestialEvent.end_time > session_start)
        ),
        (
            CelestialEvent.end_time.is_(None)
            & (CelestialEvent.start_time >= session_start)
            & (CelestialEvent.start_time < session_end)
        ),
    )

    statement = select(CelestialEvent).where(overlaps)

    if category:
        statement = statement.where(
            CelestialEvent.category == category
        )

    statement = (
        statement
        .order_by(CelestialEvent.start_time)
        .limit(limit)
    )

    return list(db.scalars(statement).all())
