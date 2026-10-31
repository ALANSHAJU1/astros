"""
AstroOS11 — Phase 5B.4 Stage 2: Authorization Matrix Tests
===========================================================

Verifies that every protected endpoint enforces the correct access policy:

  - Anonymous requests (no credentials) → 401
  - Ordinary user (role='user') → 200 on any-principal endpoints, 403 on admin-only
  - Admin (role='admin')        → 200 on all non-public endpoints
  - Service API key             → 200 on admin-or-service endpoints, 403 on admin-only
  - Invalid/expired JWT         → 401

Public endpoints (health, auth) are NOT tested here; they remain public by
design and are tested in their own test modules.
"""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def anon_client(anonymous_client):
    """Unauthenticated TestClient (no credentials)."""
    return anonymous_client


@pytest.fixture
def user_client(auth_client):
    """TestClient with a valid ordinary-user Bearer token (role='user')."""
    return auth_client


@pytest.fixture
def admin_client_fixture(admin_client):
    """TestClient with a valid admin Bearer token (role='admin')."""
    return admin_client


@pytest.fixture
def svc_client(service_client):
    """TestClient with a valid service API key (role='service')."""
    return service_client


# ---------------------------------------------------------------------------
# Minimal valid payloads for POST endpoints
# ---------------------------------------------------------------------------

OBSERVATION_PLAN_PAYLOAD = {
    "session": {
        "latitude": 10.5276,
        "longitude": 76.2144,
        "session_start": "2026-10-28T19:00:00+05:30",
        "session_end": "2026-10-28T22:00:00+05:30",
        "available_duration_minutes": 60,
    },
    "events": [],
}

RECOMMENDATION_PAYLOAD = {
    "location": {
        "name": "Thrissur",
        "latitude": 10.5276,
        "longitude": 76.2144,
        "timezone": "Asia/Kolkata",
    },
    "session_start": "2026-10-28T19:00:00+05:30",
    "session_end": "2026-10-28T22:00:00+05:30",
    "available_duration_minutes": 60,
}

DB_RECOMMENDATION_PAYLOAD = {
    "location": {
        "name": "Thrissur",
        "latitude": 10.5276,
        "longitude": 76.2144,
        "timezone": "Asia/Kolkata",
    },
    "start_time": "2026-10-28T19:00:00+05:30",
    "end_time": "2026-10-28T22:00:00+05:30",
    "available_duration_minutes": 60,
    "observation_goal": "general",
    "preferences": {},
}

FORECAST_PAYLOAD = {
    "latitude": 10.5276,
    "longitude": 76.2144,
    "start_time": "2026-10-28T19:00:00+05:30",
    "end_time": "2026-10-28T22:00:00+05:30",
    "force_refresh": False,
    "persist": True,
}

ENV_OBS_PAYLOAD = {
    "latitude": 10.5276,
    "longitude": 76.2144,
    "observed_at": "2026-10-28T20:00:00+05:30",
    "temperature_celsius": 24.0,
    "humidity": 60.0,
    "cloud_cover": 20.0,
    "conditions": "Clear",
    "source": "test",
}

EVENT_CREATE_PAYLOAD = {
    "name": "Test Event",
    "category": "planet",
    "event_type": "planetary",
    "start_time": "2026-10-28T19:00:00+05:30",
    "end_time": "2026-10-28T22:00:00+05:30",
    "latitude": 10.5276,
    "longitude": 76.2144,
}


# ===========================================================================
# 1. GET /api/v1/events  — requires get_authenticated_principal
# ===========================================================================

class TestEventListAuthorization:
    """GET /api/v1/events — any authenticated principal allowed."""

    def test_anonymous_is_rejected(self, anon_client):
        resp = anon_client.get("/api/v1/events")
        assert resp.status_code == 401

    def test_ordinary_user_is_allowed(self, user_client):
        resp = user_client.get("/api/v1/events")
        assert resp.status_code == 200

    def test_admin_is_allowed(self, admin_client_fixture):
        resp = admin_client_fixture.get("/api/v1/events")
        assert resp.status_code == 200

    def test_service_key_is_allowed(self, svc_client):
        resp = svc_client.get("/api/v1/events")
        assert resp.status_code == 200

    def test_invalid_token_is_rejected(self, anon_client):
        client = TestClient(app, headers={"Authorization": "Bearer not.a.real.token"})
        resp = client.get("/api/v1/events")
        assert resp.status_code == 401


# ===========================================================================
# 2. GET /api/v1/events/{id} — requires get_authenticated_principal
# ===========================================================================

class TestEventDetailAuthorization:
    """GET /api/v1/events/{id} — any authenticated principal allowed."""

    _fake_id = str(uuid.uuid4())

    def test_anonymous_is_rejected(self, anon_client):
        resp = anon_client.get(f"/api/v1/events/{self._fake_id}")
        assert resp.status_code == 401

    def test_ordinary_user_gets_404_not_401(self, user_client):
        # Auth passes; 404 because event doesn't exist in test DB.
        resp = user_client.get(f"/api/v1/events/{self._fake_id}")
        assert resp.status_code == 404

    def test_admin_gets_404_not_401(self, admin_client_fixture):
        resp = admin_client_fixture.get(f"/api/v1/events/{self._fake_id}")
        assert resp.status_code == 404

    def test_service_key_gets_404_not_401(self, svc_client):
        resp = svc_client.get(f"/api/v1/events/{self._fake_id}")
        assert resp.status_code == 404


# ===========================================================================
# 3. POST /api/v1/events — requires require_admin_or_service
# ===========================================================================

class TestEventCreateAuthorization:
    """POST /api/v1/events — admin or service only."""

    def test_anonymous_is_rejected(self, anon_client):
        resp = anon_client.post("/api/v1/events", json=EVENT_CREATE_PAYLOAD)
        assert resp.status_code == 401

    def test_ordinary_user_is_forbidden(self, user_client):
        resp = user_client.post("/api/v1/events", json=EVENT_CREATE_PAYLOAD)
        assert resp.status_code == 403

    def test_admin_is_allowed(self, admin_client_fixture):
        resp = admin_client_fixture.post("/api/v1/events", json=EVENT_CREATE_PAYLOAD)
        # 201 on success; 422 if schema mismatch — both indicate auth passed.
        assert resp.status_code in (201, 422)

    def test_service_key_is_allowed(self, svc_client):
        resp = svc_client.post("/api/v1/events", json=EVENT_CREATE_PAYLOAD)
        assert resp.status_code in (201, 422)


# ===========================================================================
# 4. PATCH /api/v1/events/{id} — requires require_admin_or_service
# ===========================================================================

class TestEventUpdateAuthorization:
    """PATCH /api/v1/events/{id} — admin or service only."""

    _fake_id = str(uuid.uuid4())

    def test_anonymous_is_rejected(self, anon_client):
        resp = anon_client.patch(f"/api/v1/events/{self._fake_id}", json={"name": "X"})
        assert resp.status_code == 401

    def test_ordinary_user_is_forbidden(self, user_client):
        resp = user_client.patch(f"/api/v1/events/{self._fake_id}", json={"name": "X"})
        assert resp.status_code == 403

    def test_admin_gets_404_not_401_or_403(self, admin_client_fixture):
        resp = admin_client_fixture.patch(f"/api/v1/events/{self._fake_id}", json={"name": "X"})
        assert resp.status_code == 404

    def test_service_key_gets_404_not_401_or_403(self, svc_client):
        resp = svc_client.patch(f"/api/v1/events/{self._fake_id}", json={"name": "X"})
        assert resp.status_code == 404


# ===========================================================================
# 5. DELETE /api/v1/events/{id} — requires require_admin
# ===========================================================================

class TestEventDeleteAuthorization:
    """DELETE /api/v1/events/{id} — admin only."""

    _fake_id = str(uuid.uuid4())

    def test_anonymous_is_rejected(self, anon_client):
        resp = anon_client.delete(f"/api/v1/events/{self._fake_id}")
        assert resp.status_code == 401

    def test_ordinary_user_is_forbidden(self, user_client):
        resp = user_client.delete(f"/api/v1/events/{self._fake_id}")
        assert resp.status_code == 403

    def test_service_is_forbidden(self, svc_client):
        # Service cannot delete; DELETE is admin-only.
        resp = svc_client.delete(f"/api/v1/events/{self._fake_id}")
        assert resp.status_code == 403

    def test_admin_gets_404_not_401_or_403(self, admin_client_fixture):
        resp = admin_client_fixture.delete(f"/api/v1/events/{self._fake_id}")
        assert resp.status_code == 404


# ===========================================================================
# 6. POST /api/v1/observation-plans/generate — requires get_authenticated_principal
# ===========================================================================

class TestObservationPlanAuthorization:
    """POST /api/v1/observation-plans/generate — any authenticated principal allowed."""

    def test_anonymous_is_rejected(self, anon_client):
        resp = anon_client.post("/api/v1/observation-plans/generate", json=OBSERVATION_PLAN_PAYLOAD)
        assert resp.status_code == 401

    def test_ordinary_user_is_allowed(self, user_client):
        resp = user_client.post("/api/v1/observation-plans/generate", json=OBSERVATION_PLAN_PAYLOAD)
        # 200 on success; business-logic errors like 502 are also acceptable (auth passed).
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_admin_is_allowed(self, admin_client_fixture):
        resp = admin_client_fixture.post("/api/v1/observation-plans/generate", json=OBSERVATION_PLAN_PAYLOAD)
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_service_key_is_allowed(self, svc_client):
        resp = svc_client.post("/api/v1/observation-plans/generate", json=OBSERVATION_PLAN_PAYLOAD)
        assert resp.status_code != 401
        assert resp.status_code != 403


# ===========================================================================
# 7. POST /api/v1/recommendations/from-database — requires get_authenticated_principal
# ===========================================================================

class TestDatabaseRecommendationAuthorization:
    """POST /api/v1/recommendations/from-database — any authenticated principal allowed."""

    def test_anonymous_is_rejected(self, anon_client):
        resp = anon_client.post("/api/v1/recommendations/from-database", json=DB_RECOMMENDATION_PAYLOAD)
        assert resp.status_code == 401

    def test_ordinary_user_is_allowed(self, user_client):
        resp = user_client.post("/api/v1/recommendations/from-database", json=DB_RECOMMENDATION_PAYLOAD)
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_admin_is_allowed(self, admin_client_fixture):
        resp = admin_client_fixture.post("/api/v1/recommendations/from-database", json=DB_RECOMMENDATION_PAYLOAD)
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_service_key_is_allowed(self, svc_client):
        resp = svc_client.post("/api/v1/recommendations/from-database", json=DB_RECOMMENDATION_PAYLOAD)
        assert resp.status_code != 401
        assert resp.status_code != 403


# ===========================================================================
# 8. POST /api/v1/environmental-observations/forecast — requires require_admin_or_service
# ===========================================================================

class TestForecastEndpointAuthorization:
    """POST /api/v1/environmental-observations/forecast — admin or service only."""

    def test_anonymous_is_rejected(self, anon_client):
        resp = anon_client.post("/api/v1/environmental-observations/forecast", json=FORECAST_PAYLOAD)
        assert resp.status_code == 401

    def test_ordinary_user_is_forbidden(self, user_client):
        resp = user_client.post("/api/v1/environmental-observations/forecast", json=FORECAST_PAYLOAD)
        assert resp.status_code == 403

    def test_admin_is_allowed(self, admin_client_fixture):
        resp = admin_client_fixture.post("/api/v1/environmental-observations/forecast", json=FORECAST_PAYLOAD)
        # Any non-auth response (200, 422, 502, 504…) means auth passed.
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_service_key_is_allowed(self, svc_client):
        resp = svc_client.post("/api/v1/environmental-observations/forecast", json=FORECAST_PAYLOAD)
        assert resp.status_code != 401
        assert resp.status_code != 403


# ===========================================================================
# 9. POST /api/v1/environmental-observations — requires require_admin_or_service
# ===========================================================================

class TestCreateEnvObsAuthorization:
    """POST /api/v1/environmental-observations — admin or service only."""

    def test_anonymous_is_rejected(self, anon_client):
        resp = anon_client.post("/api/v1/environmental-observations", json=ENV_OBS_PAYLOAD)
        assert resp.status_code == 401

    def test_ordinary_user_is_forbidden(self, user_client):
        resp = user_client.post("/api/v1/environmental-observations", json=ENV_OBS_PAYLOAD)
        assert resp.status_code == 403

    def test_admin_is_allowed(self, admin_client_fixture):
        resp = admin_client_fixture.post("/api/v1/environmental-observations", json=ENV_OBS_PAYLOAD)
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_service_key_is_allowed(self, svc_client):
        resp = svc_client.post("/api/v1/environmental-observations", json=ENV_OBS_PAYLOAD)
        assert resp.status_code != 401
        assert resp.status_code != 403


# ===========================================================================
# 10. GET /api/v1/environmental-observations — requires get_authenticated_principal
# ===========================================================================

class TestReadEnvObsAuthorization:
    """GET /api/v1/environmental-observations/by-location — any authenticated principal."""

    def test_anonymous_is_rejected(self, anon_client):
        resp = anon_client.get("/api/v1/environmental-observations/by-location", params={"latitude": 10.5, "longitude": 76.2})
        assert resp.status_code == 401

    def test_ordinary_user_is_allowed(self, user_client):
        resp = user_client.get("/api/v1/environmental-observations/by-location", params={"latitude": 10.5, "longitude": 76.2})
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_admin_is_allowed(self, admin_client_fixture):
        resp = admin_client_fixture.get("/api/v1/environmental-observations/by-location", params={"latitude": 10.5, "longitude": 76.2})
        assert resp.status_code != 401
        assert resp.status_code != 403


# ===========================================================================
# 11. GET /api/v1/visibility-assessments/calculate — requires get_authenticated_principal
# ===========================================================================

class TestVisibilityCalculateAuthorization:
    """POST /api/v1/visibility-assessments/calculate — any authenticated principal."""

    _payload = {
        "event_id": str(uuid.uuid4()),
        "latitude": 10.5276,
        "longitude": 76.2144,
    }

    def test_anonymous_is_rejected(self, anon_client):
        resp = anon_client.post("/api/v1/visibility-assessments/calculate", json=self._payload)
        assert resp.status_code == 401

    def test_ordinary_user_is_allowed(self, user_client):
        resp = user_client.post("/api/v1/visibility-assessments/calculate", json=self._payload)
        # 404 if event not in DB — means auth passed
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_admin_is_allowed(self, admin_client_fixture):
        resp = admin_client_fixture.post("/api/v1/visibility-assessments/calculate", json=self._payload)
        assert resp.status_code != 401
        assert resp.status_code != 403


# ===========================================================================
# 12. POST /api/v1/visibility-assessments — requires require_admin_or_service
# ===========================================================================

class TestCreateVisibilityAssessmentAuthorization:
    """POST /api/v1/visibility-assessments — admin or service only."""

    _payload = {
        "event_id": str(uuid.uuid4()),
        "visibility_score": 80.0,
        "assessment_details": {},
    }

    def test_anonymous_is_rejected(self, anon_client):
        resp = anon_client.post("/api/v1/visibility-assessments", json=self._payload)
        assert resp.status_code == 401

    def test_ordinary_user_is_forbidden(self, user_client):
        resp = user_client.post("/api/v1/visibility-assessments", json=self._payload)
        assert resp.status_code == 403

    def test_admin_is_allowed(self, admin_client_fixture):
        resp = admin_client_fixture.post("/api/v1/visibility-assessments", json=self._payload)
        assert resp.status_code != 401
        assert resp.status_code != 403

    def test_service_key_is_allowed(self, svc_client):
        resp = svc_client.post("/api/v1/visibility-assessments", json=self._payload)
        assert resp.status_code != 401
        assert resp.status_code != 403


# ===========================================================================
# 13. Public endpoints remain public
# ===========================================================================

class TestPublicEndpointsRemainPublic:
    """Health, root, and auth endpoints must remain accessible without credentials."""

    def test_root_is_public(self, anon_client):
        resp = anon_client.get("/")
        assert resp.status_code == 200

    def test_health_is_public(self, anon_client):
        resp = anon_client.get("/health")
        assert resp.status_code == 200

    def test_health_db_is_public(self, anon_client):
        resp = anon_client.get("/health/db")
        # Could be 200 or 503 depending on DB state, but not 401.
        assert resp.status_code != 401

    def test_auth_register_is_public(self, anon_client):
        # 422 on invalid body — confirms the endpoint is reachable without auth.
        resp = anon_client.post("/api/v1/auth/register", json={})
        assert resp.status_code != 401

    def test_auth_login_is_public(self, anon_client):
        resp = anon_client.post("/api/v1/auth/login", json={})
        assert resp.status_code != 401

    def test_auth_refresh_is_public(self, anon_client):
        resp = anon_client.post("/api/v1/auth/refresh", json={})
        assert resp.status_code != 401

    def test_auth_logout_is_public(self, anon_client):
        resp = anon_client.post("/api/v1/auth/logout", json={})
        assert resp.status_code != 401

