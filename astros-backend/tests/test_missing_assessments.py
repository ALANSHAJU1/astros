"""Regression tests for Concern 1: Missing assessment values and partial data handling.

Verifies:
1. Genuine score of 0 vs missing/None score.
2. Missing weather data (weight renormalization).
3. Missing visibility data.
4. Missing preference data.
5. Provider timeout or unavailable responses.
6. Partial assessment success.
7. Ranking and scheduling when some scores are unavailable.
8. Score breakdown transparency with unavailable dimensions.
"""

import pytest
from datetime import datetime, timezone
from app.modules.intelligence.recommendation.ranking_engine import (
    calculate_score,
    rank_events,
    validate_event,
)
from app.modules.intelligence.recommendation.backend_interface import (
    validate_and_adapt_event,
    build_score_breakdown,
    generate_recommendations,
)
from app.modules.intelligence.recommendation.observation_optimizer import (
    optimize_observation_schedule,
)
from app.services.visibility_scoring_engine import (
    calculate_environmental_suitability,
    evaluate_event_visibility,
)
from app.services.astronomy_adapter import BaseAstronomyAdapter, AstronomicalAssessment


class DummyUnavailableAstroAdapter(BaseAstronomyAdapter):
    """Adapter simulating unavailable ephemeris calculation."""

    def evaluate_celestial_event(self, event, latitude, longitude, bortle_class=None):
        return AstronomicalAssessment(
            is_calculable=False,
            astronomical_score=None,
            factors={},
            limitations=["Astronomical provider timeout/unavailable"],
            adapter_source="dummy_unavailable",
        )


def test_genuine_score_of_zero_vs_missing_score():
    """Verify that a genuine score of 0.0 pulls down the score, whereas None renormalizes weights."""
    event_genuine_zero = {
        "name": "Zero Weather Event",
        "event_id": "zero_weather",
        "visibility_score": 80.0,
        "weather_score": 0.0,  # e.g., heavy rain / overcast
        "preference_score": 50.0,
    }
    event_missing_weather = {
        "name": "Missing Weather Event",
        "event_id": "missing_weather",
        "visibility_score": 80.0,
        "weather_score": None,  # Provider was offline or unassessed
        "preference_score": 50.0,
    }

    score_zero = calculate_score(event_genuine_zero)
    # Calculation: 80 * 0.5 + 0 * 0.3 + 50 * 0.2 = 40 + 0 + 10 = 50.0
    assert score_zero == pytest.approx(50.0, 0.01)

    score_missing = calculate_score(event_missing_weather)
    # Calculation: available weights sum to 0.5 + 0.2 = 0.7
    # Renormalized: (80 * 0.5 / 0.7) + (50 * 0.2 / 0.7) = 57.14 + 14.29 = 71.43
    assert score_missing == pytest.approx(71.43, 0.01)
    assert score_missing > score_zero


def test_missing_weather_data_renormalization():
    """Verify that missing weather data redistributes weights and reports missing dimensions."""
    event = {
        "name": "Target Alpha",
        "event_id": "e1",
        "visibility_score": 90.0,
        "weather_score": None,
        "preference_score": 70.0,
    }
    ranked = rank_events([event], allow_missing=True)
    assert len(ranked) == 1
    r = ranked[0]
    assert r["score_status"] == "partial"
    assert "weather" in r["missing_scores"]
    # Effective weight for visibility: 0.50 / 0.70 ≈ 0.714
    assert r["effective_weights"]["visibility"] == pytest.approx(0.5 / 0.7, 0.01)
    assert r["effective_weights"]["weather"] == 0.0
    # Score: 90 * (5/7) + 70 * (2/7) = (450 + 140)/7 = 590/7 ≈ 84.29
    assert r["recommendation_score"] == pytest.approx(84.29, 0.01)


def test_missing_visibility_data_renormalization():
    """Verify missing visibility score renormalizes across weather and preference."""
    event = {
        "name": "Target Beta",
        "event_id": "e2",
        "visibility_score": None,
        "weather_score": 80.0,
        "preference_score": 60.0,
    }
    ranked = rank_events([event], allow_missing=True)
    r = ranked[0]
    assert r["score_status"] == "partial"
    assert "visibility" in r["missing_scores"]
    # Available weights: 0.30 (weather) + 0.20 (preference) = 0.50
    # Effective weather: 0.3 / 0.5 = 0.6; Effective preference: 0.2 / 0.5 = 0.4
    assert r["effective_weights"]["weather"] == pytest.approx(0.6, 0.01)
    assert r["effective_weights"]["preference"] == pytest.approx(0.4, 0.01)
    # Score: 80 * 0.6 + 60 * 0.4 = 48 + 24 = 72.0
    assert r["recommendation_score"] == pytest.approx(72.0, 0.01)


def test_missing_preference_data_renormalization():
    """Verify missing preference score renormalizes across visibility and weather."""
    event = {
        "name": "Target Gamma",
        "event_id": "e3",
        "visibility_score": 80.0,
        "weather_score": 80.0,
        "preference_score": None,
    }
    ranked = rank_events([event], allow_missing=True)
    r = ranked[0]
    assert r["score_status"] == "partial"
    assert "preference" in r["missing_scores"]
    # Available weights: 0.50 (visibility) + 0.30 (weather) = 0.80
    assert r["effective_weights"]["visibility"] == pytest.approx(0.5 / 0.8, 0.01)
    assert r["effective_weights"]["weather"] == pytest.approx(0.3 / 0.8, 0.01)
    assert r["recommendation_score"] == pytest.approx(80.0, 0.01)


def test_all_scores_missing_unassessed():
    """Verify that when all scores are None, score_status is unassessed and recommendation_score is None."""
    event = {
        "name": "Target Unassessed",
        "event_id": "e_none",
        "visibility_score": None,
        "weather_score": None,
        "preference_score": None,
    }
    ranked = rank_events([event], allow_missing=True)
    r = ranked[0]
    assert r["score_status"] == "unassessed"
    assert r["recommendation_score"] is None
    assert set(r["missing_scores"]) == {"visibility", "weather", "preference"}


def test_provider_timeout_or_unavailable_responses():
    """Verify environmental suitability and visibility assessment when providers return None/timeout."""
    # When weather data is None (e.g. provider timeout)
    env_suitability = calculate_environmental_suitability(None)
    assert env_suitability.score is None
    assert env_suitability.status == "unavailable"
    assert env_suitability.quality_label == "Unavailable"
    assert any("missing" in lim.lower() or "not available" in lim.lower() for lim in env_suitability.limitations)

    # When evaluate_event_visibility runs with unavailable weather and unavailable astronomy
    adapter = DummyUnavailableAstroAdapter()
    event = {"id": "ev_unavail", "name": "Unavailable Event", "start_time": datetime(2026, 11, 1, 20, 0, tzinfo=timezone.utc)}
    assessment = evaluate_event_visibility(
        event=event,
        environmental_data=None,
        latitude=40.0,
        longitude=-105.0,
        astronomy_adapter=adapter,
    )
    assert assessment.status == "unavailable"
    assert assessment.environmental_score is None
    assert assessment.astronomical_score is None
    assert any("timeout" in lim.lower() for lim in assessment.limitations)


def test_partial_assessment_success():
    """Verify partial_success when environmental data is present but astronomical calculations cannot be performed."""
    weather = {
        "observed_at": datetime(2026, 11, 1, 20, 0, tzinfo=timezone.utc),
        "cloud_cover": 10.0,
        "temperature_celsius": 15.0,
    }
    adapter = DummyUnavailableAstroAdapter()
    event = {"id": "ev_partial", "name": "Partial Event", "start_time": datetime(2026, 11, 1, 20, 0, tzinfo=timezone.utc)}
    assessment = evaluate_event_visibility(
        event=event,
        environmental_data=weather,
        latitude=40.0,
        longitude=-105.0,
        astronomy_adapter=adapter,
    )
    assert assessment.status == "partial_success"
    assert assessment.environmental_score is not None
    assert assessment.astronomical_score is None
    assert any("reflects environmental suitability only" in lim for lim in assessment.limitations)


def test_score_breakdown_transparency_with_missing_scores():
    """Verify build_score_breakdown clearly marks unavailable dimensions as status: unavailable."""
    event = {
        "visibility_score": 85.0,
        "weather_score": None,
        "preference_score": 60.0,
    }
    weights = {"visibility": 0.50, "weather": 0.30, "preference": 0.20}
    breakdown = build_score_breakdown(event, weights)

    assert breakdown["weather"]["status"] == "unavailable"
    assert breakdown["weather"]["score"] is None
    assert breakdown["weather"]["points"] == 0.0

    assert breakdown["visibility"]["status"] == "available"
    assert breakdown["visibility"]["score"] == 85.0
    # Available weights sum = 0.50 + 0.20 = 0.70; eff weight = 0.5 / 0.7 ≈ 0.7143
    assert breakdown["visibility"]["weight"] == pytest.approx(0.5 / 0.7, 0.001)

    assert breakdown["preference"]["status"] == "available"
    assert breakdown["preference"]["score"] == 60.0


def test_ranking_and_scheduling_when_some_scores_unavailable():
    """Verify full recommendation pipeline sorts complete, partial, and zero scores correctly and schedules valid events."""
    payload = {
        "session": {
            "session_start": "2026-11-01T20:00:00+00:00",
            "session_end": "2026-11-01T23:00:00+00:00",
            "available_duration_minutes": 120,
        },
        "events": [
            {
                "id": "event_genuine_zero",
                "name": "Stormy Event",
                "visibility_score": 0.0,
                "weather_score": 0.0,
                "preference_score": 10.0,
                "window_start": "2026-11-01T20:00:00+00:00",
                "window_end": "2026-11-01T21:00:00+00:00",
                "duration_minutes": 30,
            },
            {
                "id": "event_partial_high",
                "name": "High Partial Event",
                "visibility_score": 95.0,
                "weather_score": None,  # Missing weather, renormalized
                "preference_score": 90.0,
                "window_start": "2026-11-01T20:00:00+00:00",
                "window_end": "2026-11-01T21:00:00+00:00",
                "duration_minutes": 30,
            },
            {
                "id": "event_complete_medium",
                "name": "Complete Medium Event",
                "visibility_score": 75.0,
                "weather_score": 70.0,
                "preference_score": 60.0,
                "window_start": "2026-11-01T21:00:00+00:00",
                "window_end": "2026-11-01T22:00:00+00:00",
                "duration_minutes": 45,
            },
            {
                "id": "event_unassessed",
                "name": "Unassessed Event",
                "visibility_score": None,
                "weather_score": None,
                "preference_score": None,
                "window_start": "2026-11-01T22:00:00+00:00",
                "window_end": "2026-11-01T23:00:00+00:00",
                "duration_minutes": 30,
            },
        ],
    }

    result = generate_recommendations(payload)
    ranked = result["ranked_events"]
    assert len(ranked) == 4

    # 1. High partial event (score > 90) should rank first
    assert ranked[0]["event_id"] == "event_partial_high"
    assert ranked[0]["score_status"] == "partial"
    assert ranked[0]["recommendation_score"] > 90.0

    # 2. Complete medium event (score ≈ 70.5) should rank second
    assert ranked[1]["event_id"] == "event_complete_medium"
    assert ranked[1]["score_status"] == "complete"
    assert ranked[1]["recommendation_score"] == pytest.approx(70.5, 0.1)

    # 3. Genuine zero event should rank third (score = 2.0)
    assert ranked[2]["event_id"] == "event_genuine_zero"
    assert ranked[2]["recommendation_score"] == pytest.approx(2.0, 0.1)

    # 4. Unassessed event should rank last with recommendation_score None
    assert ranked[3]["event_id"] == "event_unassessed"
    assert ranked[3]["recommendation_score"] is None
    assert ranked[3]["score_status"] == "unassessed"

    # Verify optimizer schedule
    schedule = result["recommendation"]["schedule"]
    scheduled_ids = [s["event_id"] for s in schedule]
    # The high partial event and complete medium event should be scheduled
    assert "event_partial_high" in scheduled_ids
    assert "event_complete_medium" in scheduled_ids
    # Total scheduled duration should not exceed available duration (120 mins)
    total_dur = result["recommendation"]["summary"]["total_scheduled_minutes"]
    assert total_dur <= 120
