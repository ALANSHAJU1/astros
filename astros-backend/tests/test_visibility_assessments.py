
import uuid
from datetime import datetime, timedelta, timezone

from app.models.celestial_event import CelestialEvent
from app.models.visibility_assessment import VisibilityAssessment


def create_test_event(db):
    event = CelestialEvent(
        category="lunar",
        object_name="Test Moon",
        event_type="observation",
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        end_time=datetime.now(timezone.utc) + timedelta(days=1, hours=2),
        latitude=10.5276,
        longitude=76.2144,
        additional_data={"test": True},
    )

    db.add(event)
    db.flush()
    return event


def valid_payload(event_id):
    return {
        "event_id": str(event_id),
        "latitude": 10.5276,
        "longitude": 76.2144,
        "visibility_score": 85,
        "quality_label": "Good",
        "viewing_window_start": "2026-10-27T19:00:00+05:30",
        "viewing_window_end": "2026-10-27T21:00:00+05:30",
        "factors": {
            "cloud_cover": 10,
            "weather": "clear",
        },
        "limitations": ["Synthetic test assessment"],
        "source": "synthetic_test",
    }


def test_create_visibility_assessment(client, db):
    event = create_test_event(db)

    response = client.post(
        "/api/v1/visibility-assessments",
        json=valid_payload(event.id),
    )

    assert response.status_code == 201

    body = response.json()
    assert body["event_id"] == str(event.id)
    assert body["visibility_score"] == 85
    assert body["quality_label"] == "Good"
    assert body["source"] == "synthetic_test"
    assert "id" in body
    assert "assessed_at" in body
    assert "created_at" in body


def test_reject_visibility_score_above_100(client, db):
    event = create_test_event(db)
    payload = valid_payload(event.id)
    payload["visibility_score"] = 120

    response = client.post(
        "/api/v1/visibility-assessments",
        json=payload,
    )

    assert response.status_code == 422


def test_reject_invalid_latitude(client, db):
    event = create_test_event(db)
    payload = valid_payload(event.id)
    payload["latitude"] = 95

    response = client.post(
        "/api/v1/visibility-assessments",
        json=payload,
    )

    assert response.status_code == 422


def test_reject_invalid_longitude(client, db):
    event = create_test_event(db)
    payload = valid_payload(event.id)
    payload["longitude"] = 200

    response = client.post(
        "/api/v1/visibility-assessments",
        json=payload,
    )

    assert response.status_code == 422


def test_reject_end_time_before_start_time(client, db):
    event = create_test_event(db)
    payload = valid_payload(event.id)
    payload["viewing_window_end"] = "2026-10-27T18:00:00+05:30"

    response = client.post(
        "/api/v1/visibility-assessments",
        json=payload,
    )

    assert response.status_code == 422


def test_reject_timezone_naive_viewing_window(client, db):
    event = create_test_event(db)
    payload = valid_payload(event.id)
    payload["viewing_window_start"] = "2026-10-27T19:00:00"

    response = client.post(
        "/api/v1/visibility-assessments",
        json=payload,
    )

    assert response.status_code == 422


def test_reject_nonexistent_event(client):
    payload = valid_payload(uuid.uuid4())

    response = client.post(
        "/api/v1/visibility-assessments",
        json=payload,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Celestial event not found."


def test_get_assessment_by_id(client, db):
    event = create_test_event(db)

    create_response = client.post(
        "/api/v1/visibility-assessments",
        json=valid_payload(event.id),
    )
    assert create_response.status_code == 201

    assessment_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/visibility-assessments/{assessment_id}"
    )

    assert response.status_code == 200
    assert response.json()["id"] == assessment_id


def test_get_nonexistent_assessment(client):
    response = client.get(
        f"/api/v1/visibility-assessments/{uuid.uuid4()}"
    )

    assert response.status_code == 404


def test_get_assessments_for_event(client, db):
    event = create_test_event(db)

    create_response = client.post(
        "/api/v1/visibility-assessments",
        json=valid_payload(event.id),
    )
    assert create_response.status_code == 201

    response = client.get(
        f"/api/v1/visibility-assessments/by-event/{event.id}"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["event_id"] == str(event.id)


def test_get_assessments_for_nonexistent_event(client):
    response = client.get(
        f"/api/v1/visibility-assessments/by-event/{uuid.uuid4()}"
    )

    assert response.status_code == 404


def test_history_rejects_invalid_limit(client, db):
    event = create_test_event(db)

    response = client.get(
        f"/api/v1/visibility-assessments/by-event/{event.id}?limit=0"
    )

    assert response.status_code == 422
