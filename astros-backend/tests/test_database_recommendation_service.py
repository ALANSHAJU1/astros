from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from app.models.environmental_observation import EnvironmentalObservation
from app.services import database_recommendation_service as service
from app.services.visibility_scoring_engine import FullVisibilityAssessment


def make_session():
    return {
        "location": {
            "name": "Thrissur",
            "latitude": 10.5276,
            "longitude": 76.2144,
            "timezone": "Asia/Kolkata",
        },
        "start_time": "2026-10-27T19:00:00+05:30",
        "end_time": "2026-10-27T21:00:00+05:30",
        "available_duration_minutes": 120,
    }


def make_test_event(event_id="test-001", object_name="Test Moon", category="lunar", event_type="full_moon"):
    start = datetime(
        2026, 10, 27, 19, 0,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )

    return SimpleNamespace(
        id=event_id,
        external_event_id=event_id,
        category=category,
        object_name=object_name,
        event_type=event_type,
        start_time=start,
        end_time=start + timedelta(hours=1),
        latitude=10.5276,
        longitude=76.2144,
        additional_data={},
    )


def test_empty_database_results(monkeypatch):
    """Empty database results return truthful 'no_events_found' provenance metadata."""
    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [],
    )

    def unexpected_engine_call(request_data):
        raise AssertionError(
            "Recommendation engine should not be called with no events."
        )

    monkeypatch.setattr(
        service,
        "generate_recommendations",
        unexpected_engine_call,
    )

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
        observation_goal="general_observation",
    )

    assert result["database_events_found"] == 0
    assert result["ranked_events"] == []
    assert result["data_mode"] == "no_events_found"
    assert result["data_quality"]["is_sample_data"] is False


def test_empty_database_results_with_synthetic_provider(monkeypatch):
    """Empty database results with synthetic test provider declare synthetic mode."""
    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [],
    )

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
        observation_goal="general_observation",
        assessment_provider=lambda ev: {},
    )

    assert result["database_events_found"] == 0
    assert result["data_mode"] == "synthetic_test"


def test_unsupported_event_is_rejected(monkeypatch):
    """Unsupported events without evaluable ephemeris or weather are rejected with limitations."""
    start = datetime(2026, 10, 27, 19, tzinfo=timezone.utc)

    unsupported_event = SimpleNamespace(
        id="unsupported-001",
        external_event_id="unsupported-001",
        category="unknown_category",
        object_name="Unknown Object",
        event_type="unknown_event",
        start_time=start,
        end_time=start + timedelta(hours=1),
        latitude=None,
        longitude=None,
        additional_data={},
    )

    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [unsupported_event],
    )

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
        observation_goal="general_observation",
    )

    assert result["database_events_found"] == 1
    assert len(result["database_events_rejected"]) == 1
    assert result["ranked_events"] == []
    assert (
        "No assessment is configured"
        in result["database_events_rejected"][0]["reason"]
    )


def test_synthetic_assessments_are_disclosed(monkeypatch):
    """When a synthetic assessment provider is injected, response explicitly discloses synthetic_test mode."""
    event = make_test_event()

    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [event],
    )

    monkeypatch.setattr(
        service,
        "get_test_assessment",
        lambda event: {
            "status": "success",
            "source": "test_assessment_provider",
            "visibility_score": 90,
            "weather_score": 85,
            "data_mode": "synthetic_test",
        },
    )

    monkeypatch.setattr(
        service,
        "generate_recommendations",
        lambda request_data: {
            "status": "success",
            "ranked_events": [],
            "data_quality": {
                "is_sample_data": False,
                "data_mode": "unverified_source_data",
                "total_events": 1,
                "verified_events_count": 0,
                "demo_events_count": 0,
                "unverified_events_count": 1,
                "sources_detected": ["database"],
                "quality_notes": (
                    "Astronomical provenance has not been verified."
                ),
            },
        },
    )

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
        observation_goal="moon_observation",
    )

    assert result["data_mode"] == "synthetic_test"
    assert result["data_quality"]["is_sample_data"] is True
    assert (
        "synthetic visibility/weather assessments"
        in result["data_quality"]["quality_notes"]
    )


def test_invalid_assessment_score_is_rejected(monkeypatch):
    """Assessment scores outside 0-100 are rejected."""
    event = make_test_event()

    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [event],
    )

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
        observation_goal="moon_observation",
        assessment_provider=lambda event: {
            "status": "success",
            "source": "mock_provider",
            "visibility_score": 150,
            "weather_score": 85,
        },
    )

    assert result["ranked_events"] == []
    assert len(result["database_events_rejected"]) == 1
    assert (
        "between 0 and 100"
        in result["database_events_rejected"][0]["reason"]
    )


def test_recommendation_engine_failure_is_handled(monkeypatch):
    """Recommendation engine exceptions return sanitized error envelope."""
    event = make_test_event()

    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [event],
    )

    def failing_engine(request_data):
        raise RuntimeError("Simulated engine failure")

    monkeypatch.setattr(
        service,
        "generate_recommendations",
        failing_engine,
    )

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
        observation_goal="moon_observation",
        assessment_provider=lambda event: {
            "status": "success",
            "source": "mock_provider",
            "visibility_score": 90,
            "weather_score": 85,
        },
    )

    assert result["status"] == "error"
    assert result["ranked_events"] == []
    assert result["errors"][0]["code"] == "RECOMMENDATION_ENGINE_FAILURE"


# ===========================================================================
# Phase 5A: Real Assessment & Regression Tests
# ===========================================================================

def test_real_assessment_pipeline_invoked_by_default(monkeypatch):
    """Production recommendation path invokes evaluate_event_visibility without test_assessment_provider."""
    event = make_test_event(event_id="real-001", object_name="Jupiter", category="planet", event_type="planet")

    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [event],
    )

    evaluated_kwargs = {}

    def fake_evaluate(**kwargs):
        evaluated_kwargs.update(kwargs)
        return FullVisibilityAssessment(
            event_id="real-001",
            status="success",
            visibility_score=82.5,
            environmental_score=85.0,
            astronomical_score=80.0,
            quality_label="Optimal",
            decision="Highly recommended",
            viewing_window_start=event.start_time,
            viewing_window_end=event.end_time,
            factors={"scoring": "real"},
            limitations=[],
            source="AstroOS Environmental & Visibility Scoring Engine v1",
            assessed_at=datetime.now(timezone.utc),
            light_pollution={"bortle_class": 4},
            confidence="high",
        )

    monkeypatch.setattr(service, "evaluate_event_visibility", fake_evaluate)

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
        observation_goal="general_observation",
    )

    assert evaluated_kwargs.get("event") == event
    assert evaluated_kwargs.get("latitude") == 10.5276
    assert evaluated_kwargs.get("longitude") == 76.2144
    assert result["data_mode"] == "real_assessment"
    assert result["data_quality"]["is_sample_data"] is False
    assert result["data_quality"]["assessment_mode"] == "real_assessment"
    assert result["data_quality"]["real_assessments_count"] == 1


def test_synthetic_provider_not_called_in_production(monkeypatch):
    """The default production path never imports or calls get_test_assessment."""
    event = make_test_event()

    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [event],
    )

    # If get_test_assessment were called, it would fail the test
    assert service.get_test_assessment is None

    fake_called = False

    def fake_eval(**kwargs):
        nonlocal fake_called
        fake_called = True
        return FullVisibilityAssessment(
            event_id=event.id,
            status="success",
            visibility_score=88.0,
            environmental_score=85.0,
            astronomical_score=90.0,
            quality_label="Optimal",
            decision="Recommended",
            viewing_window_start=event.start_time,
            viewing_window_end=event.end_time,
            factors={},
            limitations=[],
            source="AstroOS Scoring Engine",
            assessed_at=datetime.now(timezone.utc),
            light_pollution={},
            confidence="high",
        )

    monkeypatch.setattr(service, "evaluate_event_visibility", fake_eval)

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
    )

    assert fake_called is True
    assert result["data_mode"] == "real_assessment"


def test_valid_zero_scores_preserved(monkeypatch):
    """Legitimate 0.0 visibility or weather scores are preserved and not conflated with None."""
    event = make_test_event(event_id="zero-001")

    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [event],
    )

    def fake_eval(**kwargs):
        return FullVisibilityAssessment(
            event_id=event.id,
            status="success",
            visibility_score=0.0,
            environmental_score=0.0,
            astronomical_score=0.0,
            quality_label="Unusable",
            decision="Observation not recommended",
            viewing_window_start=event.start_time,
            viewing_window_end=event.end_time,
            factors={},
            limitations=["Severe cloud cover"],
            source="AstroOS Engine",
            assessed_at=datetime.now(timezone.utc),
            light_pollution={},
            confidence="high",
        )

    monkeypatch.setattr(service, "evaluate_event_visibility", fake_eval)

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
    )

    assert len(result["database_events_rejected"]) == 0
    assert len(result["ranked_events"]) == 1
    ranked = result["ranked_events"][0]
    assert ranked["visibility_score"] == 0.0
    assert ranked["weather_score"] == 0.0


def test_missing_scores_handled_with_weight_renormalization(monkeypatch):
    """When weather is None (partial assessment), missing score is preserved as None and weight renormalized."""
    event = make_test_event(event_id="partial-001")

    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [event],
    )

    def fake_eval(**kwargs):
        return FullVisibilityAssessment(
            event_id=event.id,
            status="partial_success",
            visibility_score=75.0,
            environmental_score=None,
            astronomical_score=75.0,
            quality_label="Good",
            decision="Recommended",
            viewing_window_start=event.start_time,
            viewing_window_end=event.end_time,
            factors={},
            limitations=["Weather forecast unavailable."],
            source="AstroOS Engine",
            assessed_at=datetime.now(timezone.utc),
            light_pollution={},
            confidence="medium",
        )

    monkeypatch.setattr(service, "evaluate_event_visibility", fake_eval)

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
    )

    assert len(result["database_events_rejected"]) == 0
    assert len(result["ranked_events"]) == 1
    ranked = result["ranked_events"][0]
    assert ranked["weather_score"] is None
    assert ranked["visibility_score"] == 75.0
    assert ranked["recommendation_score"] is not None


def test_complete_assessment_unavailability_rejected(monkeypatch):
    """Events with unavailable visibility status are rejected with limitations rather than assigned fake scores."""
    event = make_test_event(event_id="unavail-001")

    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [event],
    )

    def fake_eval(**kwargs):
        return FullVisibilityAssessment(
            event_id=event.id,
            status="unavailable",
            visibility_score=None,
            environmental_score=None,
            astronomical_score=None,
            quality_label="Unavailable",
            decision="Not evaluable",
            viewing_window_start=event.start_time,
            viewing_window_end=event.end_time,
            factors={},
            limitations=["Weather provider timeout", "Ephemeris missing"],
            source="AstroOS Engine",
            assessed_at=datetime.now(timezone.utc),
            light_pollution={},
            confidence="unreliable",
        )

    monkeypatch.setattr(service, "evaluate_event_visibility", fake_eval)

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
    )

    assert result["database_events_found"] == 1
    assert len(result["database_events_rejected"]) == 1
    assert result["database_events_rejected"][0]["event_id"] == "unavail-001"
    assert "Weather provider timeout" in result["database_events_rejected"][0]["reason"]
    assert result["ranked_events"] == []


def test_invalid_event_timing_rejected(monkeypatch):
    """Events with missing end_time or end_time <= start_time are safely rejected."""
    start = datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)
    ev_no_end = SimpleNamespace(
        id="bad-time-1",
        start_time=start,
        end_time=None,
        object_name="No End",
        category="lunar",
        event_type="full_moon",
        latitude=10.5,
        longitude=76.2,
        additional_data={},
    )
    ev_reversed = SimpleNamespace(
        id="bad-time-2",
        start_time=start,
        end_time=start - timedelta(hours=1),
        object_name="Reversed",
        category="lunar",
        event_type="full_moon",
        latitude=10.5,
        longitude=76.2,
        additional_data={},
    )

    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [ev_no_end, ev_reversed],
    )

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
    )

    assert len(result["database_events_rejected"]) == 2
    assert result["database_events_rejected"][0]["reason"] == "Event has no valid end time."
    assert result["database_events_rejected"][1]["reason"] == "Event has no valid end time."


def test_database_operational_error_propagates_for_rollback(monkeypatch):
    """Database errors propagate directly to let the API route perform transaction rollback."""
    mock_db = MagicMock()
    monkeypatch.setattr(
        service,
        "get_events_for_session",
        MagicMock(side_effect=OperationalError("SELECT failed", {}, Exception("Connection lost"))),
    )

    with pytest.raises(OperationalError):
        service.get_database_recommendations(
            db=mock_db,
            session=make_session(),
        )
