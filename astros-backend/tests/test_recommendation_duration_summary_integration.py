from datetime import datetime, timedelta, timezone

from app.modules.intelligence.recommendation.backend_interface import (
    generate_recommendations,
)


START = datetime(2026, 11, 9, 19, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))


def _event(event_id, name, duration, start=START, window_minutes=180, score=80):
    end = start + timedelta(minutes=window_minutes)
    return {
        "event_id": event_id,
        "name": name,
        "event_type": "deep_sky",
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "duration_minutes": duration,
        "required_duration_minutes": duration,
        "visibility_score": score,
        "weather_score": score,
        "preference_score": score,
        "source": "integration-test",
    }


def _request(events, origin_counts=None):
    return {
        "events": events,
        "event_origin_counts": origin_counts or {
            "client_events_received": len(events),
            "events_discovered": 0,
        },
        "session": {
            "session_start": START.isoformat(),
            "session_end": (START + timedelta(hours=3)).isoformat(),
            "available_duration_minutes": 120,
            "location": {"latitude": 10.5, "longitude": 76.2},
            "timezone": "Asia/Kolkata",
        },
    }


def test_three_events_30_40_20_fit_inside_120_minute_budget():
    events = [
        _event("A", "Target A", 30, score=90),
        _event("B", "Target B", 40, score=80),
        _event("C", "Target C", 20, score=70),
    ]

    result = generate_recommendations(_request(events))

    assert result["status"] == "success"
    recommendation = result["recommendation"]
    summary = recommendation["summary"]

    assert len(recommendation["schedule"]) == 3
    assert sum(item["scheduled_duration_minutes"] for item in recommendation["schedule"]) == 90
    assert summary["client_events_received"] == 3
    assert summary["events_discovered"] == 0
    assert summary["total_events_received"] == 3
    assert summary["total_events_evaluated"] == 3
    assert summary["total_events_scheduled"] == 3
    assert summary["total_events_skipped"] == 0
    assert summary["total_events_excluded"] == 0
    assert summary["total_events_not_scheduled"] == 0
    assert summary["remaining_minutes"] == 30


def test_all_discovered_events_excluded_returns_empty_plan_with_correct_counts():
    too_short = _event(
        "M42",
        "M42 (Great Orion Nebula)",
        15,
        window_minutes=10,
    )
    request = _request(
        [too_short],
        {"client_events_received": 0, "events_discovered": 1},
    )

    result = generate_recommendations(request)

    assert result["status"] == "empty"
    recommendation = result["recommendation"]
    summary = recommendation["summary"]

    assert recommendation["schedule"] == []
    assert recommendation["skipped_events"] == []
    assert len(recommendation["excluded_events"]) == 1
    assert summary["client_events_received"] == 0
    assert summary["events_discovered"] == 1
    assert summary["total_events_received"] == 1
    assert summary["total_events_evaluated"] == 0
    assert summary["total_events_excluded"] == 1
    assert summary["total_events_scheduled"] == 0
    assert summary["total_events_skipped"] == 0
    assert summary["total_events_not_scheduled"] == 1
    assert summary["remaining_minutes"] == 120


def test_summary_distinguishes_scheduler_skips_from_validation_exclusions():
    events = [
        _event("A", "Target A", 90, score=90),
        _event("B", "Target B", 45, score=80),
        _event("C", "Target C", 15, window_minutes=10, score=70),
    ]

    result = generate_recommendations(_request(events))
    summary = result["recommendation"]["summary"]

    assert summary["total_events_received"] == 3
    assert summary["total_events_evaluated"] == 2
    assert summary["total_events_excluded"] == 1
    assert summary["total_events_scheduled"] == 1
    assert summary["total_events_skipped"] == 1
    assert summary["total_events_not_scheduled"] == 2
    assert len(result["recommendation"]["excluded_events"]) == 1
    assert len(result["recommendation"]["skipped_events"]) == 1
