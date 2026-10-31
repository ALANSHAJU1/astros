
from typing import Any

from app.models.celestial_event import CelestialEvent


# Configurable defaults in minutes.
# These are initial engineering defaults, not astronomy-derived values.
DEFAULT_DURATION_MINUTES = {
    "full_moon": 30,
    "new_moon": 30,
    "planet": 20,
    "meteor_shower": 30,
    "eclipse": 20,
    "comet": 20,
    "asteroid": 20,
}

FALLBACK_DURATION_MINUTES = 20

SCORE_KEYS = (
    "visibility_score",
    "weather_score",
)


def _valid_score(value: Any) -> bool:
    """Return whether a score is numeric and within 0–100."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 <= value <= 100
    )


def adapt_celestial_event(
    event: CelestialEvent,
    duration_override: float | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """
    Convert a database event to recommendation-engine input.

    Scores are read from additional_data only when available.
    Preference scoring must be supplied by the preference-scoring logic.
    """
    errors: list[str] = []
    extra = event.additional_data or {}

    if not event.object_name.strip():
        errors.append("Event has no object_name.")

    if event.end_time is None:
        errors.append(
            f"Event {event.id}: end_time is missing."
        )

    if (
        event.end_time is not None
        and event.end_time <= event.start_time
    ):
        errors.append(
            f"Event {event.id}: end_time must be after start_time."
        )

    scores: dict[str, float] = {}

    for key in SCORE_KEYS:
        value = extra.get(key)

        if not _valid_score(value):
            errors.append(
                f"Event {event.id}: valid '{key}' is not available "
                "in additional_data."
            )
        else:
            scores[key] = float(value)

    # Preference score is intentionally not fabricated here.
    preference_score = extra.get("preference_score")

    if not _valid_score(preference_score):
        errors.append(
            f"Event {event.id}: preference_score must be supplied "
            "by the preference-scoring logic."
        )

    event_type = (event.event_type or "").strip().lower()

    if duration_override is not None:
        duration = duration_override
    else:
        duration = DEFAULT_DURATION_MINUTES.get(
            event_type,
            FALLBACK_DURATION_MINUTES,
        )

    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or duration <= 0
    ):
        errors.append(
            f"Event {event.id}: duration must be a positive number."
        )
    elif event.end_time is not None:
        available_minutes = (
            event.end_time - event.start_time
        ).total_seconds() / 60

        if duration > available_minutes:
            errors.append(
                f"Event {event.id}: required duration exceeds "
                "the event's available time window."
            )

    if errors:
        return None, errors

    adapted_event = {
        "event_id": str(event.id),
        "external_event_id": event.external_event_id,
        "name": event.object_name,
        "event_type": event.event_type,
        "type": event.event_type,
        "source": extra.get("source", "database"),
        "window_start": event.start_time.isoformat(),
        "window_end": event.end_time.isoformat(),
        "visibility_score": scores["visibility_score"],
        "weather_score": scores["weather_score"],
        "preference_score": float(preference_score),
        "duration_minutes": float(duration),
        "required_duration_minutes": float(duration),
        "latitude": event.latitude,
        "longitude": event.longitude,
        "additional_data": extra,
    }

    return adapted_event, []
