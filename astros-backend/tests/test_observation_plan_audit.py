"""Regression tests verifying all 7 audit requirements for observation plan generation.

Requirements verified:
1. Event with missing altitude and environmental data produces visibility_score=None,
   recommendation_score=None, and is excluded from schedule.
2. Genuinely measured visibility score of 0.0 is preserved as 0.0 and pulls down the score.
3. Event with valid visibility assessment (visibility_score > 0) is scheduled when budget allows.
4. Unassessed/unavailable events are excluded by the optimizer with explicit exclusion reasons.
5. Session timestamps with '+05:30' offset preserve 'UTC+05:30' in summary.timezone.
6. Explanation engine percentages match effective_weights exactly (no 100% vs 50% mismatch).
7. Missing scores remain None / JSON null throughout details, events, and skipped_events.
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.services.visibility_scoring_engine import (
    evaluate_event_visibility,
    FullVisibilityAssessment,
)
from app.modules.intelligence.recommendation.ranking_engine import (
    calculate_score,
    rank_events,
)
from app.modules.intelligence.recommendation.observation_optimizer import (
    optimize_observation_schedule,
)
from app.modules.intelligence.recommendation.explanation_engine import (
    explain_event_score,
    explain_pipeline_output,
)
from app.services.astronomy_adapter import AstronomicalAssessment



# ---------------------------------------------------------------------------
# Test 1: Event with missing altitude and environmental data
# ---------------------------------------------------------------------------
def test_missing_altitude_and_environmental_data(client):
    """Event without pre-calculated astronomical ephemeris or environmental data
    must have visibility_score=None, recommendation_score=None, and not be scheduled."""
    payload = {
        "session": {
            "latitude": 10.0159,
            "longitude": 76.3419,
            "session_start": "2026-10-26T19:30:00+05:30",
            "session_end": "2026-10-26T20:30:00+05:30",
            "available_duration_minutes": 30,
        },
        "events": [
            {
                "name": "Jupiter",
                "category": "planet",
                "event_type": "planet",
                "start_time": "2026-10-26T19:30:00+05:30",
                "end_time": "2026-10-26T20:30:00+05:30",
            }
        ],
    }
    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    recs = data["recommendations"]
    details = recs.get("details", [])
    assert len(details) == 1
    event_detail = details[0]

    # Scores must be None (JSON null), NOT 0.0
    assert event_detail["visibility_score"] is None
    assert event_detail["weather_score"] is None
    assert event_detail["preference_score"] is None
    assert event_detail["assessment_status"] == "unavailable"

    # Optimizer must exclude it from scheduled events
    assert recs["schedule"] == []

    # Must be in skipped_events
    skipped = recs.get("skipped_events", [])
    assert len(skipped) == 1
    assert skipped[0]["name"] == "Jupiter"
    assert skipped[0]["score"] is None


# ---------------------------------------------------------------------------
# Test 2: Genuinely measured visibility score of 0.0
# ---------------------------------------------------------------------------
def test_genuinely_measured_zero_visibility_score():
    """A genuinely evaluated visibility score of 0.0 must be preserved as 0.0,
    and must not be confused with None / missing."""
    event_zero = {
        "name": "Sub-horizon Target",
        "visibility_score": 0.0,
        "weather_score": 100.0,
        "preference_score": 100.0,
    }
    event_none = {
        "name": "Unassessed Target",
        "visibility_score": None,
        "weather_score": 100.0,
        "preference_score": 100.0,
    }

    # calculate_score: zero pulls score down
    # weights: vis=0.5, wea=0.3, pref=0.2
    # event_zero: 0.0*0.5 + 100*0.3 + 100*0.2 = 50.0
    score_zero = calculate_score(event_zero)
    assert score_zero == pytest.approx(50.0, 0.01)

    # event_none: visibility missing, remaining weights sum to 0.5 (wea=0.3/0.5=0.6, pref=0.2/0.5=0.4)
    # 100*0.6 + 100*0.4 = 100.0
    score_none = calculate_score(event_none)
    assert score_none == pytest.approx(100.0, 0.01)

    # Ranking preserving 0.0
    ranked_zero = rank_events([event_zero], allow_missing=True)
    assert ranked_zero[0]["recommendation_score"] == pytest.approx(50.0, 0.01)
    assert ranked_zero[0]["score_status"] == "complete"
    assert ranked_zero[0]["missing_scores"] == []


# ---------------------------------------------------------------------------
# Test 3: Event with valid visibility assessment is scheduled
# ---------------------------------------------------------------------------
def test_valid_visibility_assessment_scheduled(client):
    """An event with valid pre-assessed visibility score > 0 is ranked and scheduled."""
    payload = {
        "session": {
            "latitude": 10.0159,
            "longitude": 76.3419,
            "session_start": "2026-10-26T19:30:00+05:30",
            "session_end": "2026-10-26T21:30:00+05:30",
            "available_duration_minutes": 60,
        },
        "events": [
            {
                "name": "Saturn Transit",
                "category": "planet",
                "event_type": "planet",
                "start_time": "2026-10-26T19:30:00+05:30",
                "end_time": "2026-10-26T20:30:00+05:30",
                "visibility_score": 85.0,
                "weather_score": 90.0,
                "preference_score": 75.0,
                "assessment_status": "complete",
            }
        ],
    }
    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    recs = data["recommendations"]

    assert len(recs["schedule"]) == 1
    scheduled_item = recs["schedule"][0]
    assert (scheduled_item.get("recommendation_score") or scheduled_item.get("score")) == pytest.approx(84.5, 0.1)


# ---------------------------------------------------------------------------
# Test 4: Unassessed / unavailable event excluded with explicit reason
# ---------------------------------------------------------------------------
def test_unassessed_event_excluded_by_optimizer():
    """Unassessed events passed to optimize_observation_schedule must be placed
    in unscheduled_events with clear reason."""
    ranked_events = [
        {
            "name": "Unassessed Comet",
            "recommendation_score": None,
            "score_status": "unassessed",
            "assessment_status": "unavailable",
            "window_start": "2026-10-26T19:30:00+05:30",
            "window_end": "2026-10-26T20:30:00+05:30",
            "duration_minutes": 30.0,
        }
    ]
    opt_result = optimize_observation_schedule(
        ranked_events=ranked_events,
        user_start_time="2026-10-26T19:30:00+05:30",
        total_available_duration_minutes=60,
    )
    assert opt_result["scheduled_events"] == []
    assert len(opt_result["unscheduled_events"]) == 1
    un = opt_result["unscheduled_events"][0]
    assert un["name"] == "Unassessed Comet"
    assert "unavailable" in un["reason"].lower() or "unassessed" in un["reason"].lower()


# ---------------------------------------------------------------------------
# Test 5: Timezone preservation (+05:30 -> UTC+05:30)
# ---------------------------------------------------------------------------
def test_timezone_preservation(client):
    """Session timestamps with +05:30 offset must not be converted or relabeled to UTC."""
    payload = {
        "session": {
            "latitude": 10.0159,
            "longitude": 76.3419,
            "session_start": "2026-10-26T19:30:00+05:30",
            "session_end": "2026-10-26T20:30:00+05:30",
            "available_duration_minutes": 30,
        },
        "events": [
            {
                "name": "Target in Timezone",
                "start_time": "2026-10-26T19:30:00+05:30",
                "end_time": "2026-10-26T20:30:00+05:30",
            }
        ],
    }
    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    summary = data["recommendations"]["summary"]
    assert "05:30" in summary["timezone"]
    assert summary["timezone"] != "UTC"


# ---------------------------------------------------------------------------
# Test 6: Harmonization of effective_weights and explanation percentages
# ---------------------------------------------------------------------------
def test_effective_weights_harmonization_with_explanation():
    """When weather and preference are missing, visibility effective weight is 1.0 (100%),
    and the explanation engine must report 100% wt, not the default 50% wt."""
    event = {
        "name": "Only Visibility Assessed",
        "visibility_score": 75.0,
        "weather_score": None,
        "preference_score": None,
    }
    ranked = rank_events([event], allow_missing=True)
    r = ranked[0]
    assert r["effective_weights"]["visibility"] == pytest.approx(1.0, 0.01)

    exp = explain_event_score(r)
    # Explanation should report 100% weight, not 50%
    assert "100% wt" in exp
    assert "50% wt" not in exp


# ---------------------------------------------------------------------------
# Test 7: Missing scores remain None/null throughout details, events, skipped_events
# ---------------------------------------------------------------------------
def test_missing_scores_remain_none_across_all_fields(client):
    """Verify that throughout details, events, and skipped_events, missing scores
    remain None and are never silently cast to numeric 0.0."""
    payload = {
        "session": {
            "latitude": 10.0159,
            "longitude": 76.3419,
            "session_start": "2026-10-26T19:30:00+05:30",
            "session_end": "2026-10-26T20:30:00+05:30",
            "available_duration_minutes": 30,
        },
        "events": [
            {
                "name": "Unknown Target",
                "category": "deep_sky",
                "start_time": "2026-10-26T19:30:00+05:30",
                "end_time": "2026-10-26T20:30:00+05:30",
            }
        ],
    }
    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    res = response.json()["recommendations"]

    # Check details
    for d in res["details"]:
        assert d["visibility_score"] is None
        assert d["weather_score"] is None
        assert d["preference_score"] is None

    # Check events
    for e in res["events"]:
        assert e["visibility_score"] is None
        assert e["weather_score"] is None
        assert e["preference_score"] is None

    # Check skipped_events
    for s in res["skipped_events"]:
        assert s["score"] is None
