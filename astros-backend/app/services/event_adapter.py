
from typing import Any

from app.models.celestial_event import CelestialEvent
from app.services.observation_duration_policy import resolve_event_duration


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

    explicit_duration = duration_override
    if explicit_duration is None:
        explicit_duration = extra.get("required_duration_minutes")
        if explicit_duration is None:
            explicit_duration = extra.get("duration_minutes")

    try:
        duration = resolve_event_duration(event_type, explicit_duration)
    except ValueError as exc:
        errors.append(f"Event {event.id}: {exc}")
        duration = None

    if duration is None:
        errors.append(
            f"Event {event.id}: no duration is defined for event type "
            f"'{event_type or 'unknown'}'; provide an explicit duration."
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
