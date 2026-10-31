from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.environmental_freshness import (
    classify_observation_freshness,
)


@pytest.fixture
def fixed_now():
    return datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)


def make_observation(
    *,
    observed_at,
    expires_at=None,
):
    """Create a lightweight observation for freshness tests."""
    return SimpleNamespace(
        observed_at=observed_at,
        expires_at=expires_at,
    )


def test_fresh_observation(fixed_now):
    observation = make_observation(
        observed_at=fixed_now - timedelta(minutes=10),
    )

    result = classify_observation_freshness(
        observation,
        now=fixed_now,
    )

    assert result == "fresh"


def test_stale_observation(fixed_now):
    observation = make_observation(
        observed_at=fixed_now - timedelta(minutes=90),
    )

    result = classify_observation_freshness(
        observation,
        now=fixed_now,
    )

    assert result == "stale"


def test_expired_observation(fixed_now):
    observation = make_observation(
        observed_at=fixed_now - timedelta(minutes=10),
        expires_at=fixed_now - timedelta(minutes=1),
    )

    result = classify_observation_freshness(
        observation,
        now=fixed_now,
    )

    assert result == "expired"


def test_expiry_takes_precedence_over_stale_age(fixed_now):
    observation = make_observation(
        observed_at=fixed_now - timedelta(hours=3),
        expires_at=fixed_now - timedelta(minutes=5),
    )

    result = classify_observation_freshness(
        observation,
        now=fixed_now,
    )

    assert result == "expired"


def test_observation_without_expiry_can_be_fresh(fixed_now):
    observation = make_observation(
        observed_at=fixed_now - timedelta(minutes=5),
        expires_at=None,
    )

    result = classify_observation_freshness(
        observation,
        now=fixed_now,
    )

    assert result == "fresh"


def test_naive_observed_at_returns_unknown(fixed_now):
    observation = make_observation(
        observed_at=datetime(2026, 10, 21, 9, 55),
    )

    result = classify_observation_freshness(
        observation,
        now=fixed_now,
    )

    assert result == "unknown"


def test_naive_expiry_returns_unknown(fixed_now):
    observation = make_observation(
        observed_at=fixed_now - timedelta(minutes=5),
        expires_at=datetime(2026, 10, 21, 11, 0),
    )

    result = classify_observation_freshness(
        observation,
        now=fixed_now,
    )

    assert result == "unknown"


def test_future_observation_returns_unknown(fixed_now):
    observation = make_observation(
        observed_at=fixed_now + timedelta(minutes=5),
    )

    result = classify_observation_freshness(
        observation,
        now=fixed_now,
    )

    assert result == "unknown"


def test_custom_max_age_allows_fresh_observation(fixed_now):
    observation = make_observation(
        observed_at=fixed_now - timedelta(minutes=90),
    )

    result = classify_observation_freshness(
        observation,
        now=fixed_now,
        max_age_minutes=120,
    )

    assert result == "fresh"


def test_observation_at_max_age_boundary_is_fresh(fixed_now):
    observation = make_observation(
        observed_at=fixed_now - timedelta(minutes=60),
    )

    result = classify_observation_freshness(
        observation,
        now=fixed_now,
        max_age_minutes=60,
    )

    assert result == "fresh"


def test_naive_current_time_is_rejected(fixed_now):
    observation = make_observation(
        observed_at=fixed_now - timedelta(minutes=5),
    )

    with pytest.raises(ValueError, match="now must include a timezone"):
        classify_observation_freshness(
            observation,
            now=datetime(2026, 10, 21, 10, 0),
        )


@pytest.mark.parametrize("max_age_minutes", [0, -1, -60])
def test_invalid_max_age_is_rejected(fixed_now, max_age_minutes):
    observation = make_observation(
        observed_at=fixed_now - timedelta(minutes=5),
    )

    with pytest.raises(
        ValueError,
        match="max_age_minutes must be at least 1",
    ):
        classify_observation_freshness(
            observation,
            now=fixed_now,
            max_age_minutes=max_age_minutes,
        )
