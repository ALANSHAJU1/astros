"""Session boundary, score semantics, and metadata consistency regression tests.

Verifies:
1. Every scheduled slot starts at or after session_start and ends at or before session_end.
2. Every scheduled slot fits completely inside the event's valid observation window.
3. Timezone-aware timestamps with differing offsets (+05:30 and UTC) are handled consistently.
4. Events strictly before or strictly after the session are excluded with clear reasons.
5. Events overlapping either boundary are scheduled only within the valid session overlap.
6. Events fitting exactly at boundaries are scheduled accurately.
7. metadata.external_assessments synchronizes with final API output (no stale 0.0 placeholders).
8. Recommendation arithmetic matches configured and renormalized weights.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.modules.intelligence.recommendation.observation_optimizer import (
    optimize_observation_schedule,
)
from app.modules.intelligence.recommendation.ranking_engine import (
    calculate_score,
    rank_events,
)


# ---------------------------------------------------------------------------
# 1. Optimizer Unit Tests: Session Boundary Enforcement
# ---------------------------------------------------------------------------

def test_event_entirely_before_session_excluded():
    """An event ending before session_start cannot be scheduled."""
    session_start = "2026-10-28T20:00:00+05:30"
    session_end = "2026-10-28T23:00:00+05:30"
    events = [
        {
            "name": "Early Event",
            "recommendation_score": 90.0,
            "window_start": "2026-10-28T18:00:00+05:30",
            "window_end": "2026-10-28T19:30:00+05:30",
            "duration_minutes": 30.0,
            "score_status": "complete",
        }
    ]
    res = optimize_observation_schedule(
        ranked_events=events,
        user_start_time=session_start,
        total_available_duration_minutes=180.0,
        session_end_time=session_end,
    )
    assert len(res["scheduled_events"]) == 0
    assert len(res["unscheduled_events"]) == 1
    assert "does not offer enough overlapping time" in res["unscheduled_events"][0]["reason"]


def test_event_entirely_after_session_excluded():
    """An event starting after session_end cannot be scheduled."""
    session_start = "2026-10-28T20:00:00+05:30"
    session_end = "2026-10-28T23:00:00+05:30"
    events = [
        {
            "name": "Late Event",
            "recommendation_score": 90.0,
            "window_start": "2026-10-28T23:15:00+05:30",
            "window_end": "2026-10-29T01:00:00+05:30",
            "duration_minutes": 30.0,
            "score_status": "complete",
        }
    ]
    res = optimize_observation_schedule(
        ranked_events=events,
        user_start_time=session_start,
        total_available_duration_minutes=180.0,
        session_end_time=session_end,
    )
    assert len(res["scheduled_events"]) == 0
    assert len(res["unscheduled_events"]) == 1
    assert "does not offer enough overlapping time" in res["unscheduled_events"][0]["reason"]


def test_event_overlapping_start_boundary_constrained_to_session():
    """An event starting before session_start must be scheduled at or after session_start."""
    session_start = "2026-10-28T20:00:00+05:30"
    session_end = "2026-10-28T23:00:00+05:30"
    # Event starts at 19:30, ends at 20:45 (overlap with session is 20:00 - 20:45 = 45 min)
    events = [
        {
            "name": "Early Crossing Target",
            "recommendation_score": 88.0,
            "window_start": "2026-10-28T19:30:00+05:30",
            "window_end": "2026-10-28T20:45:00+05:30",
            "duration_minutes": 30.0,
            "score_status": "complete",
        }
    ]
    res = optimize_observation_schedule(
        ranked_events=events,
        user_start_time=session_start,
        total_available_duration_minutes=180.0,
        session_end_time=session_end,
    )
    assert len(res["scheduled_events"]) == 1
    sched = res["scheduled_events"][0]
    sched_start = datetime.fromisoformat(sched["scheduled_start"])
    sched_end = datetime.fromisoformat(sched["scheduled_end"])
    s_start = datetime.fromisoformat(session_start)
    s_end = datetime.fromisoformat(session_end)

    # Must start at or after session_start
    assert sched_start >= s_start
    # Must end at or before session_end
    assert sched_end <= s_end
    # Must fit completely inside event observation window
    win_start = datetime.fromisoformat(events[0]["window_start"])
    win_end = datetime.fromisoformat(events[0]["window_end"])
    assert sched_start >= win_start
    assert sched_end <= win_end
    # Scheduled duration must match requested duration
    assert (sched_end - sched_start).total_seconds() / 60.0 == 30.0


def test_event_overlapping_end_boundary_constrained_to_session():
    """An event extending past session_end must end at or before session_end."""
    session_start = "2026-10-28T20:00:00+05:30"
    session_end = "2026-10-28T23:00:00+05:30"
    # Event starts at 22:15, ends at 23:30 (overlap with session is 22:15 - 23:00 = 45 min)
    events = [
        {
            "name": "Late Crossing Target",
            "recommendation_score": 85.0,
            "window_start": "2026-10-28T22:15:00+05:30",
            "window_end": "2026-10-28T23:30:00+05:30",
            "duration_minutes": 40.0,
            "score_status": "complete",
        }
    ]
    res = optimize_observation_schedule(
        ranked_events=events,
        user_start_time=session_start,
        total_available_duration_minutes=180.0,
        session_end_time=session_end,
    )
    assert len(res["scheduled_events"]) == 1
    sched = res["scheduled_events"][0]
    sched_start = datetime.fromisoformat(sched["scheduled_start"])
    sched_end = datetime.fromisoformat(sched["scheduled_end"])
    s_end = datetime.fromisoformat(session_end)

    assert sched_end <= s_end
    assert (sched_end - sched_start).total_seconds() / 60.0 == 40.0


def test_event_fitting_exactly_at_boundaries():
    """Events starting exactly at session_start and ending exactly at session_end."""
    session_start = "2026-10-28T20:00:00+05:30"
    session_end = "2026-10-28T22:00:00+05:30"
    events = [
        {
            "name": "Boundary Start Event",
            "recommendation_score": 90.0,
            "window_start": "2026-10-28T20:00:00+05:30",
            "window_end": "2026-10-28T21:00:00+05:30",
            "duration_minutes": 60.0,
            "score_status": "complete",
        },
        {
            "name": "Boundary End Event",
            "recommendation_score": 80.0,
            "window_start": "2026-10-28T21:00:00+05:30",
            "window_end": "2026-10-28T22:00:00+05:30",
            "duration_minutes": 60.0,
            "score_status": "complete",
        },
    ]
    res = optimize_observation_schedule(
        ranked_events=events,
        user_start_time=session_start,
        total_available_duration_minutes=120.0,
        session_end_time=session_end,
    )
    assert len(res["scheduled_events"]) == 2
    e1, e2 = res["scheduled_events"]
    assert e1["scheduled_start"] == session_start
    assert e1["scheduled_end"] == "2026-10-28T21:00:00+05:30"
    assert e2["scheduled_start"] == "2026-10-28T21:00:00+05:30"
    assert e2["scheduled_end"] == session_end
    assert res["remaining_minutes"] == 0.0


def test_cross_timezone_session_boundary_comparison():
    """Timestamps in UTC (+00:00) and IST (+05:30) must be compared correctly."""
    # Session: 14:30 UTC to 17:30 UTC (= 20:00 IST to 23:00 IST)
    session_start = "2026-10-28T14:30:00+00:00"
    session_end = "2026-10-28T17:30:00+00:00"
    # Event: 20:00 IST to 21:00 IST (= 14:30 UTC to 15:30 UTC)
    events = [
        {
            "name": "IST Event in UTC Session",
            "recommendation_score": 85.0,
            "window_start": "2026-10-28T20:00:00+05:30",
            "window_end": "2026-10-28T21:00:00+05:30",
            "duration_minutes": 45.0,
            "score_status": "complete",
        }
    ]
    res = optimize_observation_schedule(
        ranked_events=events,
        user_start_time=session_start,
        total_available_duration_minutes=180.0,
        session_end_time=session_end,
    )
    assert len(res["scheduled_events"]) == 1
    sched = res["scheduled_events"][0]
    sched_start = datetime.fromisoformat(sched["scheduled_start"])
    sched_end = datetime.fromisoformat(sched["scheduled_end"])
    s_start = datetime.fromisoformat(session_start)
    s_end = datetime.fromisoformat(session_end)

    assert sched_start >= s_start
    assert sched_end <= s_end
    assert (sched_end - sched_start).total_seconds() / 60.0 == 45.0


# ---------------------------------------------------------------------------
# 2. End-to-End API Route Tests: Session Boundary & Metadata Consistency
# ---------------------------------------------------------------------------

def test_api_session_boundary_and_metadata_synchronization(client):
    """End-to-end API test verifying boundary enforcement and metadata synchronization."""
    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-28T20:00:00+05:30",
            "session_end": "2026-10-28T23:00:00+05:30",
            "available_duration_minutes": 180,
            "preference_score": 80.0,
        },
        "events": [
            {
                "event_id": "ev_overlap_boundary",
                "name": "Boundary Test Event",
                "category": "planet",
                "event_type": "planet",
                # Event window starts at 19:30, 30 min before session_start
                "window_start": "2026-10-28T19:30:00+05:30",
                "window_end": "2026-10-28T21:30:00+05:30",
                "duration_minutes": 45,
                "visibility_score": 85.0,
                "weather_score": 90.0,
                "assessment_status": "complete",
                "metadata": {
                    "derived_astronomical_values": {
                        "computed_visibility_score": 85.0,
                    },
                    "external_assessments": {
                        "weather_score": 0.0,  # Stale placeholder
                        "preference_score": 0.0,  # Stale placeholder
                    },
                },
            }
        ],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    recs = data["recommendations"]
    assert len(recs["schedule"]) == 1
    slot = recs["schedule"][0]

    # Boundary check: Slot must not start before 20:00:00+05:30
    slot_start = datetime.fromisoformat(slot["scheduled_start"])
    s_start = datetime.fromisoformat("2026-10-28T20:00:00+05:30")
    s_end = datetime.fromisoformat("2026-10-28T23:00:00+05:30")
    assert slot_start >= s_start
    slot_end = datetime.fromisoformat(slot["scheduled_end"])
    assert slot_end <= s_end

    # Metadata consistency check: external_assessments must not report placeholder 0.0
    detail = recs["details"][0]
    assert detail["weather_score"] == 90.0
    assert detail["preference_score"] == 80.0
    meta_ext = detail.get("metadata", {}).get("external_assessments", {})
    assert meta_ext.get("weather_score") == 90.0
    assert meta_ext.get("preference_score") == 80.0


# ---------------------------------------------------------------------------
# 3. Recommendation Arithmetic & Weight Renormalization Tests
# ---------------------------------------------------------------------------

def test_recommendation_arithmetic_complete_weights():
    """When visibility, weather, and preference are all present, weights sum to 1."""
    event = {
        "name": "Complete Score Target",
        "visibility_score": 70.0,
        "weather_score": 90.0,
        "preference_score": 80.0,
    }
    # 0.50 * 70 + 0.30 * 90 + 0.20 * 80 = 35 + 27 + 16 = 78.0
    score = calculate_score(event)
    assert score == 78.0

    ranked = rank_events([event])[0]
    assert ranked["recommendation_score"] == 78.0
    assert ranked["score_status"] == "complete"
    assert ranked["missing_scores"] == []
    assert ranked["effective_weights"] == {
        "visibility": 0.5,
        "weather": 0.3,
        "preference": 0.2,
    }
    assert sum(ranked["effective_weights"].values()) == pytest.approx(1.0)


def test_recommendation_arithmetic_partial_renormalized_weights():
    """When preference_score is None, weights are renormalized over visibility and weather."""
    event = {
        "name": "Missing Preference Target",
        "visibility_score": 80.0,
        "weather_score": 60.0,
        "preference_score": None,
    }
    # Available weights sum = 0.5 + 0.3 = 0.8
    # Effective visibility wt = 0.5 / 0.8 = 0.625
    # Effective weather wt = 0.3 / 0.8 = 0.375
    # Expected score = 0.625 * 80 + 0.375 * 60 = 50.0 + 22.5 = 72.5
    score = calculate_score(event)
    assert score == 72.5

    ranked = rank_events([event])[0]
    assert ranked["recommendation_score"] == 72.5
    assert ranked["score_status"] == "partial"
    assert ranked["missing_scores"] == ["preference"]
    assert ranked["effective_weights"]["visibility"] == pytest.approx(0.625)
    assert ranked["effective_weights"]["weather"] == pytest.approx(0.375)
    assert ranked["effective_weights"]["preference"] == 0.0
    assert (
        ranked["effective_weights"]["visibility"] + ranked["effective_weights"]["weather"]
    ) == pytest.approx(1.0)
