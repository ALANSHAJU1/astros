from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from app.services import database_recommendation_service as service
from app.services.environmental_service import EnvironmentalService


def make_session():
    return {
        "location": {
            "name": "Thrissur",
            "latitude": 10.5276,
            "longitude": 76.2144,
            "timezone": "Asia/Kolkata",
        },
        "start_time": "2026-10-27T19:00:00+05:30",
        "end_time": "2026-10-27T22:00:00+05:30",
        "available_duration_minutes": 120,
    }


def make_test_event():
    start = datetime(
        2026, 10, 27, 19, 0,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )
    return SimpleNamespace(
        id="jupiter-01",
        external_event_id="jupiter-01",
        category="planet",
        object_name="Jupiter",
        event_type="planet",
        start_time=start,
        end_time=start + timedelta(hours=1),
        latitude=10.5276,
        longitude=76.2144,
        additional_data={},
    )


def test_recommendation_includes_environmental_context(monkeypatch):
    event = make_test_event()

    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [event],
    )

    mock_env_svc = MagicMock(spec=EnvironmentalService)
    mock_env_svc.build_session_environmental_context.return_value = {
        "environmental_data_available": True,
        "freshness_status": "fresh",
        "average_cloud_cover": 15.0,
        "light_pollution": {"status": "unavailable"},
        "limitations": [],
    }

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
        observation_goal="planetary_observation",
        environmental_service=mock_env_svc,
    )

    assert "environmental_context" in result
    env_ctx = result["environmental_context"]
    assert env_ctx["environmental_data_available"] is True
    assert env_ctx["average_cloud_cover"] == 15.0


def test_empty_events_includes_environmental_context(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [],
    )

    mock_env_svc = MagicMock(spec=EnvironmentalService)
    mock_env_svc.build_session_environmental_context.return_value = {
        "environmental_data_available": True,
        "freshness_status": "fresh",
        "average_cloud_cover": 20.0,
        "light_pollution": {"status": "unavailable"},
        "limitations": [],
    }

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
        observation_goal="general_observation",
        environmental_service=mock_env_svc,
    )

    assert result["status"] == "empty"
    assert "environmental_context" in result
    assert result["data_quality"]["environmental_context"] is not None


def test_custom_assessment_provider_used_when_supplied(monkeypatch):
    event = make_test_event()

    monkeypatch.setattr(
        service,
        "get_events_for_session",
        lambda **kwargs: [event],
    )

    def custom_provider(ev):
        return {
            "status": "success",
            "source": "custom_real_provider",
            "visibility_score": 92.0,
            "weather_score": 88.0,
            "data_mode": "verified_assessment",
        }

    captured_request = {}

    def mock_engine(req):
        captured_request.update(req)
        return {
            "status": "success",
            "ranked_events": [],
            "recommendation": {
                "summary": {},
                "schedule": [],
                "skipped_events": [],
            },
            "data_quality": {},
        }

    monkeypatch.setattr(service, "generate_recommendations", mock_engine)

    result = service.get_database_recommendations(
        db=MagicMock(),
        session=make_session(),
        observation_goal="planetary_observation",
        assessment_provider=custom_provider,
    )

    assert len(captured_request["events"]) == 1
    assert captured_request["events"][0]["visibility_score"] == 92.0
    assert captured_request["events"][0]["weather_score"] == 88.0
    assert (
        captured_request["events"][0]["additional_data"]["assessment_source"]
        == "custom_real_provider"
    )
