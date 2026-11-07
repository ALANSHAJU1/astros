"""Shared observation-duration defaults and normalization helpers.

Durations in this module are engineering defaults used only when an event
producer does not provide an explicit observation duration. They are not
astronomical measurements and should be tuned through configuration as the
product requirements mature.
"""

from __future__ import annotations

from typing import Any

# Canonical event-type defaults, in minutes.
DEFAULT_DURATION_MINUTES: dict[str, float] = {
    "full_moon": 30.0,
    "new_moon": 30.0,
    "moon": 30.0,
    "planet": 20.0,
    "meteor_shower": 30.0,
    "eclipse": 20.0,
    "solar_eclipse": 20.0,
    "lunar_eclipse": 20.0,
    "comet": 20.0,
    "asteroid": 20.0,
    "visible_pass": 10.0,
    "satellite": 10.0,
    "deep_sky": 45.0,
    "deep_sky_object": 45.0,
    "dso": 45.0,
}


def normalize_event_type(value: Any) -> str:
    """Normalize event type/category labels to a stable lookup key."""
    if not isinstance(value, str):
        return ""
    return "_".join(value.strip().lower().replace("-", " ").split())


def get_default_duration_minutes(event_type: Any, category: Any = None) -> float | None:
    """Return a configured default, or None when the type is not recognized."""
    for value in (event_type, category):
        key = normalize_event_type(value)
        if key in DEFAULT_DURATION_MINUTES:
            return DEFAULT_DURATION_MINUTES[key]

        # Common labels emitted by astronomy modules.
        aliases = {
            "planetary": "planet",
            "planets": "planet",
            "deep_sky_object": "deep_sky",
            "deep_sky_objects": "deep_sky",
            "meteor": "meteor_shower",
            "neo": "asteroid",
            "minor_planet": "asteroid",
            "solar_eclipse_event": "solar_eclipse",
            "lunar_eclipse_event": "lunar_eclipse",
        }
        canonical = aliases.get(key)
        if canonical in DEFAULT_DURATION_MINUTES:
            return DEFAULT_DURATION_MINUTES[canonical]
    return None


def apply_default_duration(event: dict[str, Any]) -> dict[str, Any]:
    """Copy an event and fill duration only when neither duration field exists.

    Explicit zero/invalid values are deliberately preserved for validation;
    they must not be silently replaced by a default.
    """
    normalized = dict(event)
    explicit = normalized.get("required_duration_minutes")
    if explicit is None:
        explicit = normalized.get("duration_minutes")

    if explicit is not None:
        normalized.setdefault("duration_minutes", explicit)
        normalized.setdefault("required_duration_minutes", explicit)
        return normalized

    default = get_default_duration_minutes(
        normalized.get("event_type") or normalized.get("type"),
        normalized.get("category"),
    )
    if default is not None:
        normalized["duration_minutes"] = default
        normalized["required_duration_minutes"] = default
    return normalized
