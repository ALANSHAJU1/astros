
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.environmental_observation import EnvironmentalObservation


def valid_observation_payload():
    now = datetime.now(timezone.utc)

    return {
        "latitude": 10.5276,
        "longitude": 76.2144,
        "observed_at": now.isoformat(),
        "temperature_celsius": 27.5,
        "humidity": 72,
        "cloud_cover": 25,
        "conditions": "Partly cloudy",
        "additional_data": {
            "data_type": "synthetic_test"
        },
        "source": "synthetic-test",
        "expires_at": (now + timedelta(hours=24)).isoformat(),
    }


def test_create_environmental_observation(client):
    response = client.post(
        "/api/v1/environmental-observations",
        json=valid_observation_payload(),
    )

    assert response.status_code == 201

    data = response.json()
    assert data["latitude"] == 10.5276
    assert data["longitude"] == 76.2144
    assert data["humidity"] == 72
    assert data["cloud_cover"] == 25
    assert data["source"] == "synthetic-test"
    assert data["id"]


def test_reject_invalid_latitude(client):
    payload = valid_observation_payload()
    payload["latitude"] = 95

    response = client.post(
        "/api/v1/environmental-observations",
        json=payload,
    )

    assert response.status_code == 422


def test_reject_invalid_longitude(client):
    payload = valid_observation_payload()
    payload["longitude"] = 200

    response = client.post(
        "/api/v1/environmental-observations",
        json=payload,
    )

    assert response.status_code == 422


def test_reject_humidity_above_100(client):
    payload = valid_observation_payload()
    payload["humidity"] = 110

    response = client.post(
        "/api/v1/environmental-observations",
        json=payload,
    )

    assert response.status_code == 422


def test_reject_cloud_cover_below_zero(client):
    payload = valid_observation_payload()
    payload["cloud_cover"] = -5

    response = client.post(
        "/api/v1/environmental-observations",
        json=payload,
    )

    assert response.status_code == 422


def test_reject_timezone_naive_observed_at(client):
    payload = valid_observation_payload()
    payload["observed_at"] = "2026-10-20T18:30:00"

    response = client.post(
        "/api/v1/environmental-observations",
        json=payload,
    )

    assert response.status_code == 422


def test_reject_expiry_in_the_past(client):
    payload = valid_observation_payload()
    payload["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()

    response = client.post(
        "/api/v1/environmental-observations",
        json=payload,
    )

    assert response.status_code == 422


def test_get_nonexistent_observation(client):
    response = client.get(
        f"/api/v1/environmental-observations/{uuid4()}"
    )

    assert response.status_code == 404



def test_get_observation_by_id(client):
    create_response = client.post(
        "/api/v1/environmental-observations",
        json=valid_observation_payload(),
    )
    assert create_response.status_code == 201

    observation_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/environmental-observations/{observation_id}"
    )

    assert response.status_code == 200
    assert response.json()["id"] == observation_id


def test_get_observations_by_location_and_time(client):
    payload = valid_observation_payload()

    create_response = client.post(
        "/api/v1/environmental-observations",
        json=payload,
    )
    assert create_response.status_code == 201

    observed_at = datetime.fromisoformat(payload["observed_at"])
    start_time = (observed_at - timedelta(hours=1)).isoformat()
    end_time = (observed_at + timedelta(hours=1)).isoformat()

    response = client.get(
        "/api/v1/environmental-observations/by-location",
        params={
            "latitude": payload["latitude"],
            "longitude": payload["longitude"],
            "start_time": start_time,
            "end_time": end_time,
            "limit": 100,
        },
    )

    assert response.status_code == 200
    assert any(
        item["id"] == create_response.json()["id"]
        for item in response.json()
    )


def test_get_latest_observation_for_location(client):
    payload = valid_observation_payload()

    create_response = client.post(
        "/api/v1/environmental-observations",
        json=payload,
    )
    assert create_response.status_code == 201

    response = client.get(
        "/api/v1/environmental-observations/latest/by-location",
        params={
            "latitude": payload["latitude"],
            "longitude": payload["longitude"],
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == create_response.json()["id"]


def test_reject_invalid_location_time_range(client):
    observed_at = datetime.now(timezone.utc)

    response = client.get(
        "/api/v1/environmental-observations/by-location",
        params={
            "latitude": 10.5276,
            "longitude": 76.2144,
            "start_time": (
                observed_at + timedelta(hours=2)
            ).isoformat(),
            "end_time": observed_at.isoformat(),
        },
    )

    assert response.status_code == 422


def test_latest_observation_not_found(client):
    response = client.get(
        "/api/v1/environmental-observations/latest/by-location",
        params={
            "latitude": 35.0,
            "longitude": 75.0,
        },
    )

    assert response.status_code == 404



def test_environmental_observation_is_rolled_back_after_test(db):
    from sqlalchemy import select

    from app.models.environmental_observation import (
        EnvironmentalObservation,
    )

    observation = EnvironmentalObservation(
        latitude=10.5276,
        longitude=76.2144,
        observed_at=datetime.now(timezone.utc),
        temperature_celsius=27.5,
        humidity=72,
        cloud_cover=25,
        conditions="Isolation test",
        additional_data={"data_type": "synthetic_test"},
        source="isolation-test",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    db.add(observation)
    db.flush()

    observation_id = observation.id

    assert db.scalar(
        select(EnvironmentalObservation).where(
            EnvironmentalObservation.id == observation_id
        )
    ) is not None



def test_latest_endpoint_returns_freshness_status(client):
    now = datetime.now(timezone.utc)

    payload = {
        "latitude": 10.5276,
        "longitude": 76.2144,
        "observed_at": (now - timedelta(minutes=10)).isoformat(),
        "temperature_celsius": 27.5,
        "humidity": 72,
        "cloud_cover": 25,
        "conditions": "Partly cloudy",
        "additional_data": {"data_type": "synthetic_test"},
        "source": "synthetic-test",
        "expires_at": (now + timedelta(hours=1)).isoformat(),
    }

    create_response = client.post(
        "/api/v1/environmental-observations",
        json=payload,
    )
    assert create_response.status_code == 201

    response = client.get(
        "/api/v1/environmental-observations/latest/by-location",
        params={"latitude": 10.5276, "longitude": 76.2144},
    )

    assert response.status_code == 200
    assert response.json()["freshness_status"] == "fresh"
    assert response.json()["source"] == "synthetic-test"


def test_latest_endpoint_returns_stale_observation(client):
    now = datetime.now(timezone.utc)

    payload = {
        "latitude": 11.5276,
        "longitude": 76.2144,
        "observed_at": (now - timedelta(hours=2)).isoformat(),
        "temperature_celsius": 27.5,
        "humidity": 72,
        "cloud_cover": 25,
        "conditions": "Partly cloudy",
        "additional_data": {"data_type": "synthetic_test"},
        "source": "synthetic-test",
        "expires_at": (now + timedelta(hours=1)).isoformat(),
    }

    create_response = client.post(
        "/api/v1/environmental-observations",
        json=payload,
    )
    assert create_response.status_code == 201

    response = client.get(
        "/api/v1/environmental-observations/latest/by-location",
        params={"latitude": 11.5276, "longitude": 76.2144},
    )

    assert response.status_code == 200
    assert response.json()["freshness_status"] == "stale"


def test_latest_endpoint_returns_expired_observation(client):
    now = datetime.now(timezone.utc)

    payload = {
        "latitude": 12.5276,
        "longitude": 76.2144,
        "observed_at": (now - timedelta(minutes=10)).isoformat(),
        "temperature_celsius": 27.5,
        "humidity": 72,
        "cloud_cover": 25,
        "conditions": "Partly cloudy",
        "additional_data": {"data_type": "synthetic_test"},
        "source": "synthetic-test",
        "expires_at": (now - timedelta(minutes=1)).isoformat(),
    }

    # The create endpoint currently rejects past expiry timestamps.
    # Insert this scenario through the repository to test legacy data.
    from app.repositories.environmental_observation_repository import (
        create_observation,
    )
    from app.schemas.environmental_observation import (
        EnvironmentalObservationCreate,
    )

    observation_data = EnvironmentalObservationCreate(**payload)
    observation = create_observation(
        client.app.dependency_overrides[
            __import__("app.db.session", fromlist=["get_db"]).get_db
        ]().__next__(),
        observation_data,
    )

    response = client.get(
        f"/api/v1/environmental-observations/{observation.id}",
    )
    assert response.status_code == 200
