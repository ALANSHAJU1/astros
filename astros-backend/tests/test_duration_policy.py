from app.services.duration_policy import (
    DEFAULT_DURATION_MINUTES,
    apply_default_duration,
    get_default_duration_minutes,
)
from app.modules.intelligence.recommendation.recommendation_engine import (
    normalize_event_fields,
)


def test_explicit_event_duration_is_preserved():
    event = {
        "event_type": "planet",
        "duration_minutes": 35,
        "window_start": "2026-11-07T19:00:00+05:30",
        "window_end": "2026-11-07T21:00:00+05:30",
    }

    normalized = apply_default_duration(event)

    assert normalized["duration_minutes"] == 35
    assert normalized["required_duration_minutes"] == 35


def test_known_event_type_receives_shared_default():
    normalized = apply_default_duration({"event_type": "Planetary"})

    assert normalized["duration_minutes"] == DEFAULT_DURATION_MINUTES["planet"]
    assert normalized["required_duration_minutes"] == 20


def test_unknown_event_type_does_not_receive_invented_duration():
    normalized = apply_default_duration({"event_type": "unclassified_object"})

    assert "duration_minutes" not in normalized
    assert "required_duration_minutes" not in normalized
    assert get_default_duration_minutes("unclassified_object") is None


def test_zero_duration_is_preserved_for_validation():
    normalized = apply_default_duration(
        {"event_type": "planet", "duration_minutes": 0}
    )

    assert normalized["duration_minutes"] == 0
    assert normalized["required_duration_minutes"] == 0


def test_normalizer_does_not_derive_duration_from_visibility_window():
    normalized = normalize_event_fields(
        {
            "name": "Jupiter",
            "start_time": "2026-11-07T19:00:00+05:30",
            "end_time": "2026-11-07T21:00:00+05:30",
        }
    )

    assert normalized["window_start"] == "2026-11-07T19:00:00+05:30"
    assert normalized["window_end"] == "2026-11-07T21:00:00+05:30"
    assert "duration_minutes" not in normalized


def test_normalizer_maps_explicit_required_duration():
    normalized = normalize_event_fields(
        {"name": "Jupiter", "required_duration_minutes": 30}
    )

    assert normalized["duration_minutes"] == 30
