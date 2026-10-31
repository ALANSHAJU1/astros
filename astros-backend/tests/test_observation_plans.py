import json
from fastapi.testclient import TestClient

from app.main import app

# Mock assessment class
class MockAssessment:
    def __init__(self, visibility_score=80.0, astronomical_score=85.0, environmental_score=90.0):
        self.visibility_score = visibility_score
        self.astronomical_score = astronomical_score
        self.environmental_score = environmental_score

# Mock functions
def mock_evaluate_event_visibility(*, event, environmental_data, latitude, longitude, light_pollution, astronomy_adapter, viewing_window_start=None, viewing_window_end=None):
    return MockAssessment()

def mock_generate_recommendations(request):
    return {"plan": "dummy", "details": request.get("events", [])}

def test_successful_observation_plan(client, monkeypatch):
    import app.api.routes.observation_plans as routes
    import app.modules.intelligence.recommendation.backend_interface as backend
    monkeypatch.setattr(routes, "evaluate_event_visibility", mock_evaluate_event_visibility)
    monkeypatch.setattr(backend, "generate_recommendations", mock_generate_recommendations)
    payload = {
        "session": {"session_start": "2026-10-26T19:00:00+05:30", "session_end": "2026-10-26T22:00:00+05:30"},
        "events": [{"name": "Moon", "latitude": 10.0, "longitude": 20.0, "category": "lunar", "event_type": "moonrise"}]
    }
    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["event_count"] == 1
    assert data["recommendations"]["plan"] == "dummy"
    enriched = data["recommendations"]["details"]
    assert enriched[0]["visibility_score"] == 80.0
    assert enriched[0]["astronomical_score"] == 85.0
    assert enriched[0]["environmental_score"] == 90.0

def test_invalid_body_type(client):
    response = client.post("/api/v1/observation-plans/generate", json=[1,2,3])
    assert response.status_code == 400
    assert "must be a JSON object" in response.json()["detail"]

def test_missing_coordinates_and_error_handling(client, monkeypatch):
    call_counter = {"i": 0}
    def eval_mock(*, event, environmental_data, latitude, longitude, light_pollution, astronomy_adapter, viewing_window_start=None, viewing_window_end=None):
        if latitude is None or longitude is None:
            raise AssertionError("Unexpected call for missing coords")
        if call_counter["i"] == 1:
            raise RuntimeError("simulated failure")
        call_counter["i"] += 1
        return MockAssessment(visibility_score=70.0, astronomical_score=75.0, environmental_score=80.0)
    monkeypatch.setattr("app.api.routes.observation_plans.evaluate_event_visibility", eval_mock)
    monkeypatch.setattr("app.modules.intelligence.recommendation.backend_interface.generate_recommendations", lambda req: {"plan": "ok"})
    payload = {
        "events": [
            {"name": "Event1", "latitude": 0.0, "longitude": 0.0},
            {"name": "Event2"}
        ]
    }
    response = client.post("/api/v1/observation-plans/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["event_count"] == 2
    ev1 = data["recommendations"]["events"][0]
    assert ev1["visibility_score"] == 70.0
    ev2 = data["recommendations"]["events"][1]
    assert "visibility_score" not in ev2

def test_openapi_contains_route():
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    assert "/api/v1/observation-plans/generate" in spec.get("paths", {})
    assert "post" in spec["paths"]["/api/v1/observation-plans/generate"]
