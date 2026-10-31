
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.environmental_context import build_environmental_context


def test_missing_observation_is_reported():
    result = build_environmental_context(None)

    assert result["environmental_data_available"] is False
    assert result["freshness_status"] == "unknown"
    assert result["factors"] == {}
    assert result["limitations"]


def test_fresh_observation_provides_environmental_factors():
    now = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)

    observation = SimpleNamespace(
        observed_at=now - timedelta(minutes=10),
        expires_at=now + timedelta(hours=1),
        source="weather-provider",
        additional_data={},
        temperature_celsius=27.5,
        humidity=72,
        cloud_cover=25,
        conditions="Partly cloudy",
    )

    result = build_environmental_context(observation, now=now)

    assert result["environmental_data_available"] is True
    assert result["freshness_status"] == "fresh"
    assert result["is_synthetic"] is False
    assert result["factors"]["cloud_cover"] == 25
    assert result["limitations"] == []


def test_stale_observation_has_limitation():
    now = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)

    observation = SimpleNamespace(
        observed_at=now - timedelta(hours=2),
        expires_at=now + timedelta(hours=1),
        source="weather-provider",
        additional_data={},
        temperature_celsius=27.5,
        humidity=72,
        cloud_cover=25,
        conditions="Partly cloudy",
    )

    result = build_environmental_context(observation, now=now)

    assert result["freshness_status"] == "stale"
    assert any("stale" in item for item in result["limitations"])


def test_synthetic_observation_is_disclosed():
    now = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)

    observation = SimpleNamespace(
        observed_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=1),
        source="synthetic-test",
        additional_data={"data_type": "synthetic_test"},
        temperature_celsius=27.5,
        humidity=72,
        cloud_cover=25,
        conditions="Partly cloudy",
    )

    result = build_environmental_context(observation, now=now)

    assert result["is_synthetic"] is True
    assert any("synthetic" in item.lower() for item in result["limitations"])


def test_missing_cloud_cover_is_disclosed():
    now = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)

    observation = SimpleNamespace(
        observed_at=now - timedelta(minutes=5),
        expires_at=None,
        source="weather-provider",
        additional_data={},
        temperature_celsius=27.5,
        humidity=72,
        cloud_cover=None,
        conditions=None,
    )

    result = build_environmental_context(observation, now=now)

    assert result["factors"]["cloud_cover"] is None
    assert any("Cloud-cover" in item for item in result["limitations"])
