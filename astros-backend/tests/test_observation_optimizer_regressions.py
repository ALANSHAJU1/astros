# tests/test_observation_optimizer_regressions.py
"""Regression tests for the observation optimizer.

These tests verify edge‑case scheduling behaviour:
- exact‑fit observation within the session window
- rejection when duration exceeds the intersected window
- handling of back‑to‑back intervals that only touch at a boundary
- that the unscheduled event entries contain the expected keys and statuses.
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.modules.intelligence.recommendation.observation_optimizer import (
    optimize_observation_schedule,
    intervals_overlap,
)


def dt(s: str) -> datetime:
    """Parse an ISO string with timezone info into a UTC datetime for simplicity."""
    return datetime.fromisoformat(s)


def test_exact_fit_observation_is_scheduled():
    event = {
        "name": "Exact Fit",
        "recommendation_score": 90,
        "window_start": "2026-10-26T19:00:00+00:00",
        "window_end": "2026-10-26T20:00:00+00:00",
        "duration_minutes": 45,
    }
    result = optimize_observation_schedule(
        ranked_events=[event],
        user_start_time="2026-10-26T19:00:00+00:00",
        total_available_duration_minutes=60,
    )
    assert len(result["scheduled_events"]) == 1
    scheduled = result["scheduled_events"][0]
    assert scheduled["name"] == "Exact Fit"
    # The scheduled slot should end exactly at the session end (20:00)
    assert dt(scheduled["scheduled_end"]).isoformat() == "2026-10-26T20:00:00+00:00"


def test_duration_exceeds_intersection_is_unscheduled():
    # Session 19:00‑20:00, event window 19:30‑20:00, duration 45 (cannot fit)
    event = {
        "name": "Too Long",
        "recommendation_score": 80,
        "window_start": "2026-10-26T19:30:00+00:00",
        "window_end": "2026-10-26T20:00:00+00:00",
        "duration_minutes": 45,
    }
    result = optimize_observation_schedule(
        ranked_events=[event],
        user_start_time="2026-10-26T19:00:00+00:00",
        total_available_duration_minutes=60,
    )
    assert len(result["scheduled_events"]) == 0
    assert len(result["unscheduled_events"]) == 1
    unsched = result["unscheduled_events"][0]
    assert "does not offer enough overlapping time" in unsched["reason"]


def test_touching_intervals_do_not_overlap():
    # First event occupies 19:00‑19:45, second event window starts exactly at 19:45
    ev1 = {
        "name": "First",
        "recommendation_score": 95,
        "window_start": "2026-10-26T19:00:00+00:00",
        "window_end": "2026-10-26T20:00:00+00:00",
        "duration_minutes": 45,
    }
    ev2 = {
        "name": "Second",
        "recommendation_score": 80,
        "window_start": "2026-10-26T19:45:00+00:00",
        "window_end": "2026-10-26T20:30:00+00:00",
        "duration_minutes": 30,
    }
    result = optimize_observation_schedule(
        ranked_events=[ev1, ev2],
        user_start_time="2026-10-26T19:00:00+00:00",
        total_available_duration_minutes=120,
    )
    # Both should be scheduled, second starts right after first ends.
    assert len(result["scheduled_events"]) == 2
    s1, s2 = result["scheduled_events"]
    assert s1["name"] == "First"
    assert s2["name"] == "Second"
    # Verify that there is no overlap according to intervals_overlap helper.
    start1 = dt(s1["scheduled_start"])
    end1 = dt(s1["scheduled_end"])
    start2 = dt(s2["scheduled_start"])
    end2 = dt(s2["scheduled_end"])
    assert not intervals_overlap(start1, end1, start2, end2)


def test_unscheduled_event_structure_consistency():
    # Create an event that will be rejected because budget is exceeded.
    ev = {
        "name": "Budget Exceeded",
        "recommendation_score": 70,
        "window_start": "2026-10-26T19:00:00+00:00",
        "window_end": "2026-10-26T22:00:00+00:00",
        "duration_minutes": 120,
    }
    result = optimize_observation_schedule(
        ranked_events=[ev],
        user_start_time="2026-10-26T19:00:00+00:00",
        total_available_duration_minutes=60,
    )
    unsched = result["unscheduled_events"][0]
    # Required keys should be present.
    for key in ["name", "recommendation_score", "score", "duration_minutes", "reason"]:
        assert key in unsched
    # Reason should mention budget exceed.
    assert "exceeds remaining time budget" in unsched["reason"]
