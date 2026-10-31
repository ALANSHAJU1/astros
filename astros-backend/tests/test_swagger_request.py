"""Live test executing the exact Swagger request payload against POST /api/v1/observation-plans/generate."""

import json
from fastapi.testclient import TestClient

from app.main import app

def test_live_swagger_request(client):

    # Exact payload requested by user
    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-28T19:30:00+05:30",
            "session_end": "2026-10-28T21:00:00+05:30",
            "available_duration_minutes": 90,
        },
        "events": [],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    print("STATUS_CODE:", response.status_code)
    try:
        data = response.json()
        print("RESPONSE_JSON:", json.dumps(data, indent=2))
    except Exception:
        print("RAW_TEXT:", response.text)

    # Must NOT return HTTP 500
    assert response.status_code in (200, 502)
    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "success"
        print("SUCCESS: Observation plan generated cleanly.")

if __name__ == "__main__":
    test_live_swagger_request()

