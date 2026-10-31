import json
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
import app.services.jpl_astronomy_adapter as jpl_adapter


def test_observation_plans_end_to_end_capture(client):
    """End-to-end test capturing response from POST /api/v1/observation-plans/generate."""

    # 1. Test with complete valid event payload
    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-26T19:00:00+05:30",
            "session_end": "2026-10-26T22:00:00+05:30",
            "available_duration_minutes": 120,
            "preference_score": 80.0,
        },
        "events": [
            {
                "event_id": "test_moon_001",
                "name": "Moon Observation",
                "category": "lunar",
                "event_type": "moon",
                "latitude": 10.5276,
                "longitude": 76.2144,
                "window_start": "2026-10-26T19:00:00+05:30",
                "window_end": "2026-10-26T22:00:00+05:30",
                "duration_minutes": 45,
                "additional_data": {
                    "target_altitude_deg": 45.0,
                    "phase_angle_deg": 30.0,
                },
            }
        ],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    print("STATUS_CODE:", response.status_code)
    print("RESPONSE_JSON:", json.dumps(response.json(), indent=2))
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    event_details = data["recommendations"]["details"][0]

    # Verify score propagation and missing-score handling
    assert event_details["astronomical_score"] is not None
    assert event_details["astronomical_score"] > 0
    # environmental_score is None because no weather db/forecast was present
    assert event_details["environmental_score"] is None
    assert event_details["weather_score"] is None
    # visibility_score falls back to astronomical_score when weather is missing
    assert event_details["visibility_score"] == event_details["astronomical_score"]

    # In ranked events, verify recommendation score & missing_scores metadata
    ranked = data["recommendations"]["ranked_events"][0]
    assert ranked["score_status"] == "partial"
    assert "weather" in ranked["missing_scores"]
    assert ranked["recommendation_score"] is not None

