
from datetime import datetime

import pytest

from app.modules.intelligence.recommendation.observation_optimizer import (
    optimize_observation_schedule,
    validate_user_availability,
)


IST = "+05:30"
SESSION_START = f"2026-10-26T19:00:00{IST}"
SESSION_END = f"2026-10-26T22:00:00{IST}"


def make_event(
    name,
    start,
    end,
    duration,
    score=90,
):
    return {
        "name": name,
        "recommendation_score": score,
        "window_start": start,
        "window_end": end,
        "duration_minutes": duration,
    }


def test_explicit_session_end_is_preserved():
    start, budget, end = validate_user_availability(
        SESSION_START,
        120,
        session_end_time=SESSION_END,
    )

    assert start.isoformat() == SESSION_START
    assert budget == 120
    assert end.isoformat() == SESSION_END


def test_schedule_preserves_three_hour_session_and_two_hour_budget():
    events = [
        make_event(
            "Jupiter",
            f"2026-10-26T19:00:00{IST}",
            f"2026-10-26T22:00:00{IST}",
            60,
            95,
        ),
        make_event(
            "Saturn",
            f"2026-10-26T19:00:00{IST}",
            f"2026-10-26T22:00:00{IST}",
            60,
            90,
        ),
        make_event(
            "Andromeda",
            f"2026-10-26T19:00:00{IST}",
            f"2026-10-26T22:00:00{IST}",
            60,
            85,
        ),
    ]

    result = optimize_observation_schedule(
        ranked_events=events,
        user_start_time=SESSION_START,
        total_available_duration_minutes=120,
        session_end_time=SESSION_END,
    )

    assert result["session_start"] == SESSION_START
    assert result["session_end"] == SESSION_END
    assert result["user_available_minutes"] == 120
    assert result["total_scheduled_minutes"] == 120
    assert result["remaining_minutes"] == 0

    for event in result["scheduled_events"]:
        scheduled_start = datetime.fromisoformat(
            event["scheduled_start"]
        )
        scheduled_end = datetime.fromisoformat(
            event["scheduled_end"]
        )

        assert scheduled_start >= datetime.fromisoformat(SESSION_START)
        assert scheduled_end <= datetime.fromisoformat(SESSION_END)


def test_event_outside_session_is_not_scheduled_past_session_end():
    events = [
        make_event(
            "Late event",
            f"2026-10-26T21:30:00{IST}",
            f"2026-10-26T23:30:00{IST}",
            60,
        )
    ]

    result = optimize_observation_schedule(
        ranked_events=events,
        user_start_time=SESSION_START,
        total_available_duration_minutes=120,
        session_end_time=SESSION_END,
    )

    assert result["session_end"] == SESSION_END
    assert result["scheduled_events"] == []
    assert len(result["unscheduled_events"]) == 1


def test_omitting_session_end_preserves_backward_compatibility():
    result = optimize_observation_schedule(
        ranked_events=[],
        user_start_time=SESSION_START,
        total_available_duration_minutes=120,
    )

    expected_end = "2026-10-26T21:00:00+05:30"

    assert result["session_start"] == SESSION_START
    assert result["session_end"] == expected_end
    assert result["user_available_minutes"] == 120
    assert result["total_scheduled_minutes"] == 0
