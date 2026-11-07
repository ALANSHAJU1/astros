import pytest

from app.services.observation_duration_policy import resolve_event_duration


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        ("Planet", 20.0),
        ("Moon", 30.0),
        ("Full Moon", 30.0),
        ("Meteor Shower", 30.0),
        ("Solar Eclipse", 20.0),
        ("Comet", 20.0),
        ("Asteroid", 20.0),
        ("Deep-Sky Object", 45.0),
        ("Satellite", 10.0),
    ],
)
def test_shared_duration_policy_resolves_event_type_defaults(event_type, expected):
    assert resolve_event_duration(event_type) == expected


def test_explicit_duration_overrides_event_type_default():
    assert resolve_event_duration("planet", 37) == 37.0


def test_unknown_event_type_does_not_inherit_session_budget_or_fabricate_duration():
    assert resolve_event_duration("unknown-celestial-category") is None


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, "30"])
def test_invalid_explicit_duration_is_rejected(value):
    with pytest.raises(ValueError):
        resolve_event_duration("planet", value)
