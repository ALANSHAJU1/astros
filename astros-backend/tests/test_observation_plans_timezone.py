from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
import pytest

from app.services.catalog_event_discovery_service import (
    discover_meteor_shower_candidates,
    _ensure_utc_aware,
)
import app.services.jpl_astronomy_adapter as jpl_adapter


def test_event_with_timezone_aware_utc_timestamps(client):
    """Test 1: Event with timezone-aware UTC timestamps is processed successfully."""
    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-31T13:30:00+00:00",
            "session_end": "2026-10-31T16:30:00+00:00",
            "available_duration_minutes": 120,
        },
        "events": [
            {
                "name": "Target UTC M31",
                "latitude": 10.5276,
                "longitude": 76.2144,
                "window_start": "2026-10-31T14:00:00Z",
                "window_end": "2026-10-31T16:00:00Z",
                "duration_minutes": 60,
                "category": "deep_sky",
            }
        ],
    }
    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    events = data["recommendations"]["events"]
    assert len(events) == 1
    assert events[0]["name"] == "Target UTC M31"


def test_event_with_timezone_aware_ist_timestamps(client):
    """Test 2: Event with timezone-aware +05:30 timestamps is processed successfully."""
    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-31T19:00:00+05:30",
            "session_end": "2026-10-31T22:00:00+05:30",
            "available_duration_minutes": 120,
        },
        "events": [
            {
                "name": "Target IST M45",
                "latitude": 10.5276,
                "longitude": 76.2144,
                "window_start": "2026-10-31T19:30:00+05:30",
                "window_end": "2026-10-31T21:30:00+05:30",
                "duration_minutes": 60,
                "category": "deep_sky",
            }
        ],
    }
    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    events = data["recommendations"]["events"]
    assert len(events) == 1
    assert events[0]["name"] == "Target IST M45"


def test_naive_timestamps_from_discovered_source_are_normalized():
    """Test 3: Naive timestamps from meteor_shower_engine source are normalized to aware UTC ISO strings."""
    # 1. Verify _ensure_utc_aware converts non-UTC timezone-aware datetimes to UTC
    ist_time = datetime(2026, 10, 31, 19, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    utc_time = _ensure_utc_aware(ist_time)
    assert utc_time.tzinfo == timezone.utc
    assert utc_time.hour == 13
    assert utc_time.minute == 30

    # 2. Verify discover_meteor_shower_candidates normalizes naive strings to UTC aware ISO
    # Perseids radiant is observable above Boulder on August 12
    candidates = discover_meteor_shower_candidates(
        latitude=40.0,
        longitude=-105.0,
        session_start=datetime(2026, 8, 12, 4, 0, tzinfo=timezone.utc),
        session_end=datetime(2026, 8, 12, 8, 0, tzinfo=timezone.utc),
        available_duration_minutes=60.0,
    )
    assert len(candidates) > 0
    for cand in candidates:
        w_start = cand["window_start"]
        w_end = cand["window_end"]
        assert isinstance(w_start, str)
        assert isinstance(w_end, str)
        # Must be valid ISO strings with timezone
        start_dt = datetime.fromisoformat(w_start)
        end_dt = datetime.fromisoformat(w_end)
        assert start_dt.tzinfo is not None
        assert end_dt.tzinfo is not None
        assert w_start.endswith("+00:00") or w_start.endswith("Z")
        assert end_dt > start_dt


def test_session_and_event_with_different_timezone_offsets(client):
    """Test 4: Session in +05:30 and event in UTC (different offsets, compatible aware instants) succeed."""
    # Session: 19:00 to 22:00 IST (which is 13:30 to 16:30 UTC)
    # Event: 14:00 to 16:00 UTC (which is 19:30 to 21:30 IST)
    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-31T19:00:00+05:30",
            "session_end": "2026-10-31T22:00:00+05:30",
            "available_duration_minutes": 120,
        },
        "events": [
            {
                "name": "Target Cross-TZ",
                "latitude": 10.5276,
                "longitude": 76.2144,
                "window_start": "2026-10-31T14:00:00+00:00",
                "window_end": "2026-10-31T16:00:00+00:00",
                "duration_minutes": 60,
                "category": "deep_sky",
            }
        ],
    }
    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    events = data["recommendations"]["events"]
    assert len(events) == 1
    assert events[0]["name"] == "Target Cross-TZ"


def test_invalid_or_ambiguous_datetime_inputs_rejected(client):
    """Test 5: Invalid and ambiguous datetime inputs are rejected without being silently misinterpreted."""
    # 5a: Client event with completely unparseable datetime string
    payload_invalid = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-31T19:00:00+05:30",
            "session_end": "2026-10-31T22:00:00+05:30",
            "available_duration_minutes": 120,
        },
        "events": [
            {
                "name": "Invalid Date Event",
                "latitude": 10.5276,
                "longitude": 76.2144,
                "window_start": "not-a-valid-date",
                "window_end": "2026-10-31T22:00:00+05:30",
                "duration_minutes": 60,
            }
        ],
    }
    resp_invalid = client.post("/api/v1/observation-plans/generate", json=payload_invalid)
    assert resp_invalid.status_code == 502
    errors = resp_invalid.json().get("detail", [])
    assert any("Invalid 'window_start'" in str(e) for e in errors)

    # 5b: Client event with naive (ambiguous) datetime when session is timezone-aware
    # Must NOT silently assume a timezone; must reject with timezone-aware requirement
    payload_naive = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-31T19:00:00+05:30",
            "session_end": "2026-10-31T22:00:00+05:30",
            "available_duration_minutes": 120,
        },
        "events": [
            {
                "name": "Naive Ambiguous Event",
                "latitude": 10.5276,
                "longitude": 76.2144,
                "window_start": "2026-10-31T19:30:00",  # missing timezone
                "window_end": "2026-10-31T21:30:00",    # missing timezone
                "duration_minutes": 60,
            }
        ],
    }
    resp_naive = client.post("/api/v1/observation-plans/generate", json=payload_naive)
    assert resp_naive.status_code == 502
    errors = resp_naive.json().get("detail", [])
    assert any("must be timezone-aware" in str(e) for e in errors)


def test_observation_plan_auto_discovery_with_empty_events(client, monkeypatch):
    """Test 6: Automatic discovery with events: [] runs cleanly and returns 200."""
    # Mock JPL to return empty list (Moon below horizon)
    mock_client = MagicMock()
    mock_client.get_observer_ephemeris.return_value = MagicMock()
    monkeypatch.setattr(jpl_adapter._jpl_client, "HorizonsClient", MagicMock(return_value=mock_client))
    monkeypatch.setattr(
        jpl_adapter._event_adapter.HorizonsEventAdapter,
        "create_observation_passes",
        MagicMock(
            side_effect=jpl_adapter._event_adapter.UnobservableEventError(
                "Target 'Moon (301)' never reaches minimum elevation threshold of 0.0° (peak elevation: -15.8°)."
            )
        ),
    )

    # User's exact reproduced request
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
    assert data["event_count"] > 0
    enriched = data["recommendations"]["events"]
    assert len(enriched) > 0

    # Verify that all discovered events have timezone-aware window timestamps
    for ev in enriched:
        w_start = ev.get("window_start")
        w_end = ev.get("window_end")
        assert w_start is not None, f"Event '{ev.get('name')}' missing window_start"
        assert w_end is not None, f"Event '{ev.get('name')}' missing window_end"
        dt_s = datetime.fromisoformat(w_start)
        dt_e = datetime.fromisoformat(w_end)
        assert dt_s.tzinfo is not None, f"Event '{ev.get('name')}' window_start is naive: {w_start}"
        assert dt_e.tzinfo is not None, f"Event '{ev.get('name')}' window_end is naive: {w_end}"

