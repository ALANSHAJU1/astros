
import pytest
from pydantic import ValidationError

from app.api.routes.database_recommendations import (
    DatabaseRecommendationRequest,
)


def valid_request():
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
        "observation_goal": "moon_observation",
        "preferences": {},
        "category": "lunar",
    }


def test_valid_request_is_accepted():
    request = DatabaseRecommendationRequest(**valid_request())

    assert request.location["name"] == "Thrissur"
    assert request.available_duration_minutes == 120


def test_timezone_naive_start_time_is_rejected():
    data = valid_request()
    data["start_time"] = "2026-10-27T19:00:00"

    with pytest.raises(ValidationError):
        DatabaseRecommendationRequest(**data)


def test_end_time_before_start_time_is_rejected():
    data = valid_request()
    data["end_time"] = "2026-10-27T18:00:00+05:30"

    with pytest.raises(ValidationError):
        DatabaseRecommendationRequest(**data)


def test_non_positive_duration_is_rejected():
    data = valid_request()
    data["available_duration_minutes"] = 0

    with pytest.raises(ValidationError):
        DatabaseRecommendationRequest(**data)


def test_location_must_not_be_empty():
    data = valid_request()
    data["location"] = {}

    with pytest.raises(ValidationError):
        DatabaseRecommendationRequest(**data)



from app.main import app
from app.api.routes import database_recommendations


def test_database_endpoint_returns_recommendations(client, monkeypatch):
    def fake_recommendations(**kwargs):
        return {
            "status": "success",
            "ranked_events": [
                {
                    "event_id": "test-event-001",
                    "name": "Test Moon",
                    "recommendation_score": 88.5,
                }
            ],
            "data_mode": "synthetic_test",
            "database_events_found": 1,
            "database_events_rejected": [],
        }

    monkeypatch.setattr(
        database_recommendations,
        "get_database_recommendations",
        fake_recommendations,
    )

    response = client.post(
        "/api/v1/recommendations/from-database",
        json=valid_request(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["ranked_events"][0]["event_id"] == "test-event-001"
    assert body["data_mode"] == "synthetic_test"


def test_database_endpoint_rejects_timezone_naive_timestamp(client):
    data = valid_request()
    data["start_time"] = "2026-10-27T19:00:00"

    response = client.post(
        "/api/v1/recommendations/from-database",
        json=data,
    )

    assert response.status_code == 422


def test_database_endpoint_rejects_invalid_session_range(client):
    data = valid_request()
    data["end_time"] = "2026-10-27T18:00:00+05:30"

    response = client.post(
        "/api/v1/recommendations/from-database",
        json=data,
    )

    assert response.status_code == 422


def test_database_endpoint_rejects_zero_duration(client):
    data = valid_request()
    data["available_duration_minutes"] = 0

    response = client.post(
        "/api/v1/recommendations/from-database",
        json=data,
    )

    assert response.status_code == 422


def test_database_endpoint_production_real_assessment(client, monkeypatch):
    """End-to-end route call produces data_mode='real_assessment' without test_assessment_provider."""
    from datetime import datetime, timezone, timedelta
    from types import SimpleNamespace
    from app.services import database_recommendation_service as service
    from app.services.visibility_scoring_engine import FullVisibilityAssessment

    start = datetime(2026, 10, 27, 19, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    mock_ev = SimpleNamespace(
        id="db-prod-01",
        external_event_id="db-prod-01",
        category="planet",
        object_name="Saturn",
        event_type="planet",
        start_time=start,
        end_time=start + timedelta(hours=1),
        latitude=10.5276,
        longitude=76.2144,
        additional_data={},
    )

    monkeypatch.setattr(service, "get_events_for_session", lambda **kw: [mock_ev])
    monkeypatch.setattr(service, "deduplicate_events", lambda evs: evs)

    def fake_eval(**kw):
        return FullVisibilityAssessment(
            event_id="db-prod-01",
            status="success",
            visibility_score=85.0,
            environmental_score=90.0,
            astronomical_score=80.0,
            quality_label="Optimal",
            decision="Highly recommended",
            viewing_window_start=start,
            viewing_window_end=start + timedelta(hours=1),
            factors={},
            limitations=[],
            source="AstroOS Real Engine",
            assessed_at=datetime.now(timezone.utc),
            light_pollution={},
            confidence="high",
        )

    monkeypatch.setattr(service, "evaluate_event_visibility", fake_eval)

    response = client.post(
        "/api/v1/recommendations/from-database",
        json=valid_request(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data_mode"] == "real_assessment"
    assert body["data_quality"]["is_sample_data"] is False
    assert body["data_quality"]["assessment_mode"] == "real_assessment"
    assert body["ranked_events"][0]["event_id"] == "db-prod-01"




