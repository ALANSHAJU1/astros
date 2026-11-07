"""Shared event observation-duration policy.

Values are configurable engineering defaults in minutes, not scientific constants.
An explicit positive event duration always takes precedence over the event-type default.
Unknown event types return None; the session budget is never used as an event duration.
"""
from __future__ import annotations

import math
import re
from typing import Any

DEFAULT_DURATION_MINUTES: dict[str, float] = {
    "full_moon": 30.0,
    "new_moon": 30.0,
    "moon": 30.0,
    "planet": 20.0,
    "meteor_shower": 30.0,
    "meteor shower": 30.0,
    "eclipse": 20.0,
    "solar_eclipse": 20.0,
    "lunar_eclipse": 20.0,
    "comet": 20.0,
    "asteroid": 20.0,
    "deep_sky": 45.0,
    "deep_sky_object": 45.0,
    "deep_sky_target": 45.0,
    "satellite": 10.0,
    "dso": 45.0,
}


def normalize_event_type(event_type: Any) -> str:
    value = str(event_type or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def resolve_event_duration(
    event_type: Any,
    explicit_duration: Any = None,
) -> float | None:
    """Resolve an event duration, preferring an explicit positive value."""
    if explicit_duration is not None:
        if (
            isinstance(explicit_duration, bool)
            or not isinstance(explicit_duration, (int, float))
            or not math.isfinite(float(explicit_duration))
            or float(explicit_duration) <= 0
        ):
            raise ValueError("Event duration must be a finite positive number.")
        return float(explicit_duration)

    key = normalize_event_type(event_type)
    # Handle canonical aliases after punctuation normalization.
    if key in DEFAULT_DURATION_MINUTES:
        return DEFAULT_DURATION_MINUTES[key]
    return None
