import pytest
from unittest.mock import MagicMock
import httpx

import app.services.jpl_astronomy_adapter as adapter


def test_jpl_unobservable_target_returns_empty_list(monkeypatch, db):
    """Test 1: When a target never reaches minimum elevation, fetch_events_from_jpl() returns []

    and does not propagate an exception or write to the database.
    """
    from sqlalchemy import select
    from app.models.celestial_event import CelestialEvent

    mock_client = MagicMock()
    mock_client.get_observer_ephemeris.return_value = MagicMock()
    monkeypatch.setattr(adapter._jpl_client, "HorizonsClient", MagicMock(return_value=mock_client))

    # Mock create_observation_passes to raise UnobservableEventError
    mock_create = MagicMock(
        side_effect=adapter._event_adapter.UnobservableEventError(
            "Target 'Moon (301)' never reaches minimum elevation threshold of 0.0° (peak elevation: -15.8°)."
        )
    )
    monkeypatch.setattr(adapter._event_adapter.HorizonsEventAdapter, "create_observation_passes", mock_create)

    initial_events = list(db.scalars(select(CelestialEvent)).all())

    events = adapter.fetch_events_from_jpl(
        latitude=10.5276,
        longitude=76.2144,
        start_time_iso="2026-10-31T19:00:00+05:30",
        end_time_iso="2026-10-31T22:00:00+05:30",
    )

    assert events == []
    final_events = list(db.scalars(select(CelestialEvent)).all())
    assert len(final_events) == len(initial_events)
    mock_client.close.assert_called_once()


def test_jpl_timeout_propagates_and_route_returns_502(client, monkeypatch):
    """Test 2: Genuine JPL timeout propagates from adapter and causes the route to return HTTP 502."""
    mock_client = MagicMock()
    mock_client.get_observer_ephemeris.side_effect = httpx.TimeoutException("Connection timed out to NASA JPL")
    monkeypatch.setattr(adapter._jpl_client, "HorizonsClient", MagicMock(return_value=mock_client))

    with pytest.raises(httpx.TimeoutException):
        adapter.fetch_events_from_jpl(
            latitude=10.5276,
            longitude=76.2144,
            start_time_iso="2026-10-31T19:00:00+05:30",
            end_time_iso="2026-10-31T22:00:00+05:30",
        )

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-31T19:00:00+05:30",
            "session_end": "2026-10-31T22:00:00+05:30",
            "available_duration_minutes": 120,
        },
        "events": [],
    }
    resp = client.post("/api/v1/observation-plans/generate", json=payload)
    assert resp.status_code == 502
    assert "Failed to fetch events from JPL Horizons" in resp.json()["detail"]


def test_jpl_service_error_propagates_and_route_returns_502(client, monkeypatch):
    """Test 3: Genuine upstream JPL HTTP/service failure propagates and route returns HTTP 502."""
    mock_client = MagicMock()
    mock_client.get_observer_ephemeris.side_effect = adapter._jpl_client.HorizonsHTTPError(
        "Horizons 503 Service Unavailable", status_code=503
    )
    monkeypatch.setattr(adapter._jpl_client, "HorizonsClient", MagicMock(return_value=mock_client))

    with pytest.raises(adapter._jpl_client.HorizonsHTTPError):
        adapter.fetch_events_from_jpl(
            latitude=10.5276,
            longitude=76.2144,
            start_time_iso="2026-10-31T19:00:00+05:30",
            end_time_iso="2026-10-31T22:00:00+05:30",
        )

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-31T19:00:00+05:30",
            "session_end": "2026-10-31T22:00:00+05:30",
            "available_duration_minutes": 120,
        },
        "events": [],
    }
    resp = client.post("/api/v1/observation-plans/generate", json=payload)
    assert resp.status_code == 502
    assert "Failed to fetch events from JPL Horizons" in resp.json()["detail"]


def test_jpl_normal_observable_target_returns_events(monkeypatch):
    """Test 4: Normal observable target ephemeris returns adapted events list unchanged."""
    mock_client = MagicMock()
    mock_client.get_observer_ephemeris.return_value = MagicMock()
    monkeypatch.setattr(adapter._jpl_client, "HorizonsClient", MagicMock(return_value=mock_client))

    expected_events = [
        {
            "event_id": "lunar-pass-01",
            "name": "Moon",
            "event_type": "moon",
            "latitude": 10.5276,
            "longitude": 76.2144,
            "target_altitude_deg": 35.0,
        }
    ]
    monkeypatch.setattr(
        adapter._event_adapter.HorizonsEventAdapter,
        "create_observation_passes",
        MagicMock(return_value=expected_events),
    )

    events = adapter.fetch_events_from_jpl(
        latitude=10.5276,
        longitude=76.2144,
        start_time_iso="2026-10-31T19:00:00+05:30",
        end_time_iso="2026-10-31T22:00:00+05:30",
    )

    assert events == expected_events
    mock_client.close.assert_called_once()


def test_observation_plan_auto_discovery_with_unobservable_moon(client, monkeypatch):
    """Test 5: Automatic discovery with an unobservable Moon executes catalog discovery

    and returns HTTP 200 with catalog candidates rather than failing with HTTP 502.
    """
    mock_client = MagicMock()
    mock_client.get_observer_ephemeris.return_value = MagicMock()
    monkeypatch.setattr(adapter._jpl_client, "HorizonsClient", MagicMock(return_value=mock_client))
    monkeypatch.setattr(
        adapter._event_adapter.HorizonsEventAdapter,
        "create_observation_passes",
        MagicMock(
            side_effect=adapter._event_adapter.UnobservableEventError(
                "Target 'Moon (301)' never reaches minimum elevation threshold of 0.0° (peak elevation: -15.8°)."
            )
        ),
    )

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-31T19:00:00+05:30",
            "session_end": "2026-10-31T22:00:00+05:30",
            "available_duration_minutes": 120,
        },
        "events": [],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    enriched = data["recommendations"]["events"]
    assert len(enriched) > 0
    event_names = [e["name"] for e in enriched]
    assert any("Pleiades" in name or "Andromeda" in name or "Cluster" in name for name in event_names)
