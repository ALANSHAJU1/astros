# tests/test_visibility_scoring_regressions.py
"""Regression tests for visibility scoring engine behavior.

These tests verify that a valid astronomical score is propagated when environmental data is missing,
and that no invalid scores are introduced when the astronomy adapter reports non‑calculable data.
"""

import pytest
from datetime import datetime, timezone

from app.services.visibility_scoring_engine import evaluate_event_visibility
from app.services.astronomy_adapter import CelestialEventAstronomyAdapter


def make_event_with_altitude(altitude_deg: float, magnitude: float | None = None) -> dict:
    """Create a minimal event dictionary containing required astronomical fields.
    The adapter reads values from ``additional_data``.
    """
    return {
        "id": "event123",
        "name": "Test Planet",
        "category": "planet",
        "event_type": "planet",
        "start_time": "2026-10-26T19:00:00+00:00",
        "end_time": "2026-10-26T20:00:00+00:00",
        "duration_minutes": 60,
        "additional_data": {
            "target_altitude_deg": altitude_deg,
            "apparent_magnitude": magnitude,
        },
    }


def test_astronomical_score_propagates_when_environment_missing():
    # Event with a calculable astronomical score (altitude > 30 gives no penalty)
    event = make_event_with_altitude(altitude_deg=45)
    # No environmental data supplied (None)
    result = evaluate_event_visibility(
        event=event,
        environmental_data=None,
        latitude=10.0,
        longitude=20.0,
        light_pollution=None,
        astronomy_adapter=CelestialEventAstronomyAdapter(),
        viewing_window_start=None,
        viewing_window_end=None,
    )
    # Expect the visibility_score to equal the astronomical_score
    assert result.astronomical_score is not None
    assert result.visibility_score == result.astronomical_score
    # Since environmental data is missing we should be in partial_success mode
    assert result.status == "partial_success"
    # There must be a limitation explaining the missing environment
    assert any("environmental" in lim.lower() for lim in result.limitations)


def test_uncalculable_astronomical_input_does_not_propagate_score():
    # Event lacking altitude/magnitude/ephemeris data – adapter returns is_calculable=False
    event = {
        "id": "event456",
        "name": "Missing Data",
        "category": "planet",
        "event_type": "planet",
        "start_time": "2026-10-26T19:00:00+00:00",
        "end_time": "2026-10-26T20:00:00+00:00",
        "duration_minutes": 60,
        "additional_data": {},  # no required fields
    }
    result = evaluate_event_visibility(
        event=event,
        environmental_data=None,
        latitude=10.0,
        longitude=20.0,
        light_pollution=None,
        astronomy_adapter=CelestialEventAstronomyAdapter(),
        viewing_window_start=None,
        viewing_window_end=None,
    )
    # No astronomical score should be present
    assert result.astronomical_score is None
    # Visibility score must also be None because neither env nor astro is calculable
    assert result.visibility_score is None
    assert result.status == "unavailable"
    # Limitations should mention missing astronomical inputs
    assert any("astronomical" in lim.lower() for lim in result.limitations)
