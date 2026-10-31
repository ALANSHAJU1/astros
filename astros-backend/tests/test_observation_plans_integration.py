import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

# Helper mock event returned by JPL adapter
MOCK_JPL_EVENTS = [
    {
        "id": "event1",
        "name": "Mock Lunar Event",
        "event_type": "lunar",
        "latitude": 40.0,
        "longitude": -105.0,
        "target_altitude_deg": 45,
        "phase_angle_deg": 30,
    }
]

# Minimal dummy recommendation payload expected from backend_interface
DUMMY_RECOMMENDATION = {
    "ranked_events": [],
    "summary": {},
    "schedule": [],
    "explanations": {"mode": "deterministic"},
}

def test_jpl_fetch_called_and_events_processed(client):
    session = {
        "latitude": 40.0,
        "longitude": -105.0,
        "session_start": "2026-11-01T20:00:00+00:00",
        "session_end": "2026-11-01T22:00:00+00:00",
        "available_duration_minutes": 120,
    }
    payload = {"session": session, "events": []}
    with patch("app.services.jpl_astronomy_adapter.fetch_events_from_jpl", return_value=MOCK_JPL_EVENTS) as mock_fetch:
        with patch("app.modules.intelligence.recommendation.backend_interface.generate_recommendations", return_value=DUMMY_RECOMMENDATION) as mock_rec:
            response = client.post("/api/v1/observation-plans/generate", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            mock_fetch.assert_called_once_with(
                latitude=40.0,
                longitude=-105.0,
                start_time_iso=session["session_start"],
                end_time_iso=session["session_end"],
                target_ids=None,
            )
            enriched = data["recommendations"]["events"]
            assert isinstance(enriched, list)
            assert enriched[0]["id"] == "event1"
            assert "visibility_score" in enriched[0]

def test_jpl_timeout_returns_502(client):
    session = {
        "latitude": 40.0,
        "longitude": -105.0,
        "session_start": "2026-11-01T20:00:00+00:00",
        "session_end": "2026-11-01T22:00:00+00:00",
        "available_duration_minutes": 120,
    }
    payload = {"session": session, "events": []}
    with patch("app.services.jpl_astronomy_adapter.fetch_events_from_jpl", side_effect=Exception("Timeout")):
        response = client.post("/api/v1/observation-plans/generate", json=payload)
        assert response.status_code == 502
        assert "Failed to fetch events from JPL Horizons" in response.json()["detail"]

def test_session_fields_preserved_for_intelligence(client):
    session = {
        "latitude": 40.0,
        "longitude": -105.0,
        "session_start": "2026-11-01T20:00:00+00:00",
        "session_end": "2026-11-01T22:00:00+00:00",
        "available_duration_minutes": 120,
    }
    payload = {"session": session, "events": []}
    captured_req = {}
    def fake_generate(req):
        captured_req.update(req)
        return DUMMY_RECOMMENDATION
    with patch("app.services.jpl_astronomy_adapter.fetch_events_from_jpl", return_value=MOCK_JPL_EVENTS):
        with patch("app.modules.intelligence.recommendation.backend_interface.generate_recommendations", side_effect=fake_generate):
            response = client.post("/api/v1/observation-plans/generate", json=payload)
            assert response.status_code == 200
            assert "session" in captured_req
            sess = captured_req["session"]
            assert sess["session_start"] == session["session_start"]
            assert sess["session_end"] == session["session_end"]
            assert sess["available_duration_minutes"] == session["available_duration_minutes"]

def test_full_pipeline_execution_with_real_events(client):
    event = {
        "id": "evt1",
        "name": "Test Planet",
        "event_type": "planet",
        "latitude": 40.0,
        "longitude": -105.0,
        "target_altitude_deg": 50,
        "apparent_magnitude": 2.5,
    }
    session = {
        "latitude": 40.0,
        "longitude": -105.0,
        "session_start": "2026-11-01T20:00:00+00:00",
        "session_end": "2026-11-01T22:00:00+00:00",
        "available_duration_minutes": 120,
    }
    payload = {"session": session, "events": [event]}
    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    rec = data["recommendations"]
    assert "summary" in rec
    assert "schedule" in rec
    assert "explanations" in rec
    assert rec["explanations"].get("mode") == "deterministic"
    enriched = data["recommendations"]["events"]
    assert enriched[0]["visibility_score"] is not None
    assert enriched[0]["astronomical_score"] is not None
    # Verify environmental/weather score handling: accept None when unavailable or a numeric value when provider succeeds
    env_score = enriched[0]["environmental_score"]
    assert env_score is None or isinstance(env_score, (int, float))

