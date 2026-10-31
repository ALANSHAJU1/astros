import json
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app

def test_capture_swagger_verification():
    client = TestClient(app)

    payload = {
        "session": {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "session_start": "2026-10-28T19:30:00+05:30",
            "session_end": "2026-10-28T21:00:00+05:30",
            "available_duration_minutes": 90,
            "preference_score": 80.0,
        },
        "events": [],
    }

    response = client.post("/api/v1/observation-plans/generate", json=payload)
    print("STATUS_CODE:", response.status_code)
    try:
        body = response.json()
        print("JSON_RESPONSE:", json.dumps(body, indent=2))
    except Exception:
        print("TEXT:", response.text)

if __name__ == "__main__":
    test_capture_swagger_verification()

