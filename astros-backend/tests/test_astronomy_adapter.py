from types import SimpleNamespace
import pytest

from app.services.astronomy_adapter import (
    CelestialEventAstronomyAdapter,
)


def test_missing_ephemeris_does_not_fabricate_score():
    event = SimpleNamespace(
        id="evt-001",
        category="planet",
        event_type="opposition",
        additional_data={},
    )
    adapter = CelestialEventAstronomyAdapter()
    result = adapter.evaluate_celestial_event(event, 10.0, 76.0)

    assert result.is_calculable is False
    assert result.astronomical_score is None
    assert any("Astronomical inputs" in item for item in result.limitations)


def test_lunar_altitude_evaluation():
    # Low moon (<10°) gets severe penalty
    event_low = SimpleNamespace(
        id="evt-moon-low",
        category="lunar",
        event_type="full_moon",
        additional_data={"target_altitude_deg": 8.0},
    )
    adapter = CelestialEventAstronomyAdapter()
    res_low = adapter.evaluate_celestial_event(event_low, 10.0, 76.0)

    assert res_low.is_calculable is True
    assert res_low.astronomical_score == 60.0
    assert any("Low Moon altitude" in item for item in res_low.limitations)

    # High moon (>25°) has full score
    event_high = SimpleNamespace(
        id="evt-moon-high",
        category="lunar",
        event_type="full_moon",
        additional_data={"target_altitude_deg": 45.0},
    )
    res_high = adapter.evaluate_celestial_event(event_high, 10.0, 76.0)
    assert res_high.astronomical_score == 100.0


def test_meteor_shower_moonlight_and_bortle():
    event = SimpleNamespace(
        id="evt-perseids",
        category="meteor_shower",
        event_type="meteor_shower",
        additional_data={
            "target_altitude_deg": 35.0,
            "moon_illumination_percent": 85.0,
        },
    )
    adapter = CelestialEventAstronomyAdapter()
    # In suburban light pollution (Bortle 7) with 85% Moon
    res = adapter.evaluate_celestial_event(event, 10.0, 76.0, bortle_class=7)

    assert res.is_calculable is True
    assert res.astronomical_score == 45.0  # 100 - 30 (moon) - 25 (bortle)
    assert any("moonlight" in item.lower() for item in res.limitations)
    assert any("bortle" in item.lower() for item in res.limitations)


def test_satellite_in_earth_shadow():
    event = SimpleNamespace(
        id="evt-iss",
        category="satellite",
        event_type="visible_pass",
        additional_data={
            "target_altitude_deg": 50.0,
            "is_sunlit": False,
        },
    )
    adapter = CelestialEventAstronomyAdapter()
    res = adapter.evaluate_celestial_event(event, 10.0, 76.0)

    assert res.is_calculable is True
    assert res.astronomical_score == 0.0
    assert any("shadow" in item.lower() for item in res.limitations)
