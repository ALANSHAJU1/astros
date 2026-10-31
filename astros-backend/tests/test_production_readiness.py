"""
AstroOS11 — Stage 5: Production Readiness Regression Tests
===========================================================

Covers:
  A. Configuration security (CORS origin policy, API docs toggle, credentials safety)
  B. Session model input validation (lat/lon/duration bounds on /observation-plans/generate)
  C. Error detail sanitization (no engine internals or exceptions in API responses)
  D. Health probe endpoints (/health liveness and /health/db readiness with broad error handling)
  E. Dependency verification (httpx direct importable dependency and client instantiation)
  F. DarkSkySites retry resilience (HTTP 429 and timeouts without blocking sleeps)
  G. CORS preflight, allowed methods, allowed headers, and origin isolation
  H. JPL client lifecycle cleanup (success and failure) and error sanitization
  I. Environmental forecast error handling (504 timeout, 502 upstream, sanitized 500, rollback)
"""

from __future__ import annotations

import importlib.util
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

ROOT_PATH = Path(__file__).resolve().parents[2]
INTEL_PATH = ROOT_PATH / "astros-intelligence"
if str(INTEL_PATH) not in sys.path:
    sys.path.append(str(INTEL_PATH))

from app.main import app
from app.db.session import get_db

SESSION_START = "2026-10-27T19:00:00+05:30"
SESSION_END = "2026-10-27T23:00:00+05:30"
LOCATION = {"name": "Thrissur", "latitude": 10.5276, "longitude": 76.2144}


# ===========================================================================
# A. Configuration Security
# ===========================================================================


class TestConfigurationSecurity:
    """Verify config-driven behaviour for docs, CORS, and environment variables."""

    def test_enable_api_docs_setting_imported(self):
        """ENABLE_API_DOCS can be imported from app.core.config."""
        from app.core.config import ENABLE_API_DOCS
        assert isinstance(ENABLE_API_DOCS, bool)

    def test_cors_allowed_origins_setting_imported(self):
        """CORS_ALLOWED_ORIGINS is a list — empty by default in test environment."""
        from app.core.config import CORS_ALLOWED_ORIGINS
        assert isinstance(CORS_ALLOWED_ORIGINS, list)

    def test_cors_default_does_not_permit_arbitrary_origins(self):
        """When CORS_ALLOWED_ORIGINS is empty (default), arbitrary origins do not receive allow headers."""
        client = TestClient(app)
        response = client.get("/", headers={"Origin": "https://unauthorized-origin.example.com"})
        assert response.status_code == 200
        allow_origin = response.headers.get("access-control-allow-origin")
        assert allow_origin != "*"
        assert allow_origin != "https://unauthorized-origin.example.com"

    def test_api_docs_endpoint_reflects_configuration(self):
        """When ENABLE_API_DOCS is True (test default), /docs should return 200 or redirect."""
        from app.core.config import ENABLE_API_DOCS
        client = TestClient(app)
        response = client.get("/docs", follow_redirects=True)
        if ENABLE_API_DOCS:
            assert response.status_code == 200
        else:
            assert response.status_code == 404

    def test_database_url_not_present_in_health_response(self):
        """The /health/db endpoint must not expose DATABASE_URL or credentials."""
        mock_db = MagicMock()
        mock_db.execute.return_value = None
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/health/db")
            response_text = response.text
            assert "postgresql" not in response_text
            assert "password" not in response_text
            assert "postgres" not in response_text.lower() or "reachable" in response_text
        finally:
            app.dependency_overrides.pop(get_db, None)


# ===========================================================================
# B. Session Model Input Validation (observation-plans endpoint)
# ===========================================================================


class TestSessionModelInputValidation:
    """Verify that SessionModel now enforces lat/lon/duration boundaries.

    The /api/v1/observation-plans/generate endpoint maps all Pydantic 422 validation
    errors to HTTP 400 via the custom exception handler in app/main.py.
    """

    def test_invalid_latitude_above_range_rejected(self, client):
        """latitude > 90 should be rejected with HTTP 400 (validation error in observation plan route)."""
        payload = {
            "session": {
                "latitude": 999.0,   # invalid
                "longitude": 76.2144,
                "session_start": SESSION_START,
                "session_end": SESSION_END,
                "available_duration_minutes": 120,
            },
            "events": [{"name": "Test", "event_id": "test-01"}],
        }
        response = client.post("/api/v1/observation-plans/generate", json=payload)
        # Custom handler maps Pydantic validation errors to 400 for this endpoint
        assert response.status_code == 400

    def test_invalid_longitude_below_range_rejected(self, client):
        """longitude < -180 should be rejected."""
        payload = {
            "session": {
                "latitude": 10.5276,
                "longitude": -999.0,  # invalid
                "session_start": SESSION_START,
                "session_end": SESSION_END,
                "available_duration_minutes": 120,
            },
            "events": [{"name": "Test", "event_id": "test-01"}],
        }
        response = client.post("/api/v1/observation-plans/generate", json=payload)
        assert response.status_code == 400

    def test_duration_zero_rejected(self, client):
        """available_duration_minutes=0 should be rejected."""
        payload = {
            "session": {
                "latitude": 10.5276,
                "longitude": 76.2144,
                "session_start": SESSION_START,
                "session_end": SESSION_END,
                "available_duration_minutes": 0,  # invalid (ge=1)
            },
            "events": [{"name": "Test", "event_id": "test-01"}],
        }
        response = client.post("/api/v1/observation-plans/generate", json=payload)
        assert response.status_code == 400

    def test_duration_above_1440_rejected(self, client):
        """available_duration_minutes > 1440 (24 hours) should be rejected."""
        payload = {
            "session": {
                "latitude": 10.5276,
                "longitude": 76.2144,
                "session_start": SESSION_START,
                "session_end": SESSION_END,
                "available_duration_minutes": 9999,  # invalid (le=1440)
            },
            "events": [{"name": "Test", "event_id": "test-01"}],
        }
        response = client.post("/api/v1/observation-plans/generate", json=payload)
        assert response.status_code == 400


# ===========================================================================
# C. Error Detail Sanitization
# ===========================================================================


class TestErrorDetailSanitization:
    """Verify that internal error text is not forwarded to API clients."""

    def test_recommendation_engine_failure_does_not_leak_internal_message(self, client, monkeypatch):
        """When the recommendation engine raises, the 500 response must NOT contain the raw exception message."""
        import app.api.routes.observation_plans as plans_route

        secret_internal_message = "SegFault at address 0xDEADBEEF in _internal_ranking_engine"

        monkeypatch.setattr(
            plans_route.backend_interface,
            "generate_recommendations",
            MagicMock(side_effect=RuntimeError(secret_internal_message)),
        )

        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(role="admin", is_active=True)
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            client.raise_server_exceptions = False
            payload = {
                "session": {
                    "latitude": 10.5276,
                    "longitude": 76.2144,
                    "session_start": SESSION_START,
                    "session_end": SESSION_END,
                    "available_duration_minutes": 120,
                },
                "events": [
                    {
                        "name": "Moon",
                        "event_id": "test-moon-01",
                        "visibility_score": 80.0,
                        "weather_score": 75.0,
                        "assessment_status": "complete",
                        "window_start": SESSION_START,
                        "window_end": SESSION_END,
                        "duration_minutes": 30,
                        "required_duration_minutes": 30,
                    }
                ],
            }
            response = client.post("/api/v1/observation-plans/generate", json=payload)
            assert response.status_code == 500
            response_text = response.text
            # The raw exception message must NOT appear verbatim in the response
            assert secret_internal_message not in response_text
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_assessment_processing_error_is_generic(self, client, monkeypatch):
        """When event assessment fails, processing_error must be a generic message, not raw exception text."""
        import app.api.routes.observation_plans as plans_route
        import app.services.visibility_scoring_engine as scoring_engine

        secret_path = "C:\\Users\\admin\\super_secret\\keys.json"
        monkeypatch.setattr(
            scoring_engine,
            "evaluate_event_visibility",
            MagicMock(side_effect=FileNotFoundError(f"File not found: {secret_path}")),
        )

        # Mock a successful backend response to let the event loop complete
        monkeypatch.setattr(
            plans_route.backend_interface,
            "generate_recommendations",
            MagicMock(return_value={
                "status": "success",
                "recommendation": {"schedule": [], "skipped_events": [], "summary": {}},
                "ranked_events": [],
            }),
        )

        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(role="admin", is_active=True)
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            client.raise_server_exceptions = False
            payload = {
                "session": {
                    "latitude": 10.5276,
                    "longitude": 76.2144,
                    "session_start": SESSION_START,
                    "session_end": SESSION_END,
                },
                "events": [
                    {
                        "name": "Mars",
                        "event_id": "test-mars-01",
                        "window_start": SESSION_START,
                        "window_end": SESSION_END,
                    }
                ],
            }
            response = client.post("/api/v1/observation-plans/generate", json=payload)
            response_text = response.text
            # The secret path must not appear in any response field
            assert secret_path not in response_text
        finally:
            app.dependency_overrides.pop(get_db, None)


# ===========================================================================
# D. /health/db Endpoint
# ===========================================================================


class TestDatabaseHealthEndpoint:
    """Verify /health/db liveness probe behavior."""

    def test_health_db_returns_200_when_db_is_reachable(self):
        """A working database session returns HTTP 200 with status=ok."""
        mock_db = MagicMock()
        mock_db.execute.return_value = None
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/health/db")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["database"] == "reachable"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_health_db_returns_503_when_db_is_unreachable(self):
        """A failing database session returns HTTP 503 Service Unavailable."""
        from sqlalchemy.exc import OperationalError

        mock_db = MagicMock()
        mock_db.execute.side_effect = OperationalError(
            statement="SELECT 1",
            params={},
            orig=Exception("could not connect to server"),
        )
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/db")
            assert response.status_code == 503
            data = response.json()
            assert data["detail"] == "Database is not reachable"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_health_db_does_not_expose_credentials(self):
        """The /health/db response must never contain connection string details."""
        from sqlalchemy.exc import OperationalError

        mock_db = MagicMock()
        mock_db.execute.side_effect = OperationalError(
            statement="SELECT 1",
            params={},
            orig=Exception("password authentication failed for user postgres"),
        )
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/db")
            assert response.status_code == 503
            response_text = response.text
            assert "password" not in response_text
            assert "authentication" not in response_text
            assert "postgresql" not in response_text
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_health_endpoint_liveness(self):
        """GET /health returns HTTP 200 with ok status for container liveness probes."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert "AstroOS backend is running" in response.json()["message"]

    def test_health_db_catches_broad_sqlalchemy_error(self):
        """Any SQLAlchemyError on /health/db returns HTTP 503 and rolls back the session."""
        from sqlalchemy.exc import SQLAlchemyError

        mock_db = MagicMock()
        mock_db.execute.side_effect = SQLAlchemyError("Driver interface dropped connection / pool timeout")
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/db")
            assert response.status_code == 503
            assert response.json()["detail"] == "Database is not reachable"
            mock_db.rollback.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_db, None)


# ===========================================================================
# E. httpx Direct Import
# ===========================================================================


class TestDependencyAvailability:
    """Verify that httpx is importable as a direct dependency."""

    def test_httpx_is_importable(self):
        """httpx must be available as a direct dependency (not only transitive)."""
        spec = importlib.util.find_spec("httpx")
        assert spec is not None, "httpx must be importable — add it to requirements.txt"

    def test_httpx_client_instantiates(self):
        """httpx.Client must be constructable."""
        import httpx
        client = httpx.Client(timeout=5.0)
        assert client is not None
        client.close()


# ===========================================================================
# F. DarkSkySites Retry Resilience (No Blocking Sleep)
# ===========================================================================


class TestDarkSkySitesResilience:
    """Validate DarkSkySites non-blocking retry, HTTP 429, and timeout behaviors."""

    def test_darkskeysites_rate_limit_429_returns_unavailable_without_sleep(self, monkeypatch):
        """HTTP 429 returns unavailable immediately without executing blocking sleep."""
        from app.services.light_pollution_service import DarkSkySitesLightPollutionProvider

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "15"}
        mock_client.get.return_value = mock_response

        # Fail loudly if sleep is invoked
        monkeypatch.setattr(
            time, "sleep", MagicMock(side_effect=AssertionError("Blocking time.sleep was invoked on 429!"))
        )

        provider = DarkSkySitesLightPollutionProvider(api_key="test-key-001", client=mock_client)
        result = provider.get_light_pollution(10.5276, 76.2144)

        assert result.status == "unavailable"
        assert result.bortle_class is None
        assert result.sqm is None
        assert any("rate limit exceeded" in lim.lower() for lim in result.limitations)
        assert mock_client.get.call_count == 1

    def test_darkskeysites_timeout_returns_unavailable_without_sleep(self, monkeypatch):
        """Permanent timeout returns unavailable after bounded retries without blocking sleep."""
        from app.services.light_pollution_service import DarkSkySitesLightPollutionProvider

        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.TimeoutException("Upstream connection timed out")

        monkeypatch.setattr(
            time, "sleep", MagicMock(side_effect=AssertionError("Blocking time.sleep was invoked on timeout!"))
        )

        provider = DarkSkySitesLightPollutionProvider(api_key="test-key-001", client=mock_client)
        result = provider.get_light_pollution(10.5276, 76.2144)

        assert result.status == "unavailable"
        assert result.bortle_class is None
        assert any("timed out" in lim.lower() for lim in result.limitations)
        # Verify 2 attempts were made before giving up
        assert mock_client.get.call_count == 2

    def test_darkskeysites_transient_timeout_recovers_on_second_attempt_without_sleep(self, monkeypatch):
        """A transient timeout on attempt 1 recovers on attempt 2 without blocking sleep."""
        from app.services.light_pollution_service import DarkSkySitesLightPollutionProvider

        mock_client = MagicMock()
        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = {
            "sqm": 21.4,
            "bortleClass": 3,
            "bortleDescription": "Rural sky",
            "dataset": {"id": "10_2026", "year": 2026},
            "quality": {"status": "screened"},
            "attribution": "darkskysites.com",
        }
        mock_client.get.side_effect = [
            httpx.TimeoutException("Transient connection dropped"),
            mock_success,
        ]

        monkeypatch.setattr(
            time, "sleep", MagicMock(side_effect=AssertionError("Blocking time.sleep was invoked on retry!"))
        )

        provider = DarkSkySitesLightPollutionProvider(api_key="test-key-001", client=mock_client)
        result = provider.get_light_pollution(10.5276, 76.2144)

        assert result.status == "success"
        assert result.bortle_class == 3
        assert result.sqm == 21.4
        assert mock_client.get.call_count == 2


# ===========================================================================
# G. CORS Preflight, Methods, Headers, and Origin Isolation
# ===========================================================================


def create_isolated_cors_app(allowed_origins: list[str]) -> FastAPI:
    """Build an isolated FastAPI application mimicking production CORS configuration."""
    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @test_app.get("/api/v1/resource")
    def get_resource():
        return {"data": "read_success"}

    @test_app.post("/api/v1/resource")
    def post_resource():
        return {"data": "write_success"}

    return test_app


class TestCorsPreflightAndOriginPolicies:
    """Validate CORS preflight OPTIONS, allowed methods, allowed headers, and origin boundaries."""

    def test_cors_preflight_allowed_origin_returns_expected_headers(self):
        """Preflight OPTIONS from an authorized origin returns 200 with credentials and allowed headers."""
        test_app = create_isolated_cors_app(["https://app.astroos.com"])
        client = TestClient(test_app)

        response = client.options(
            "/api/v1/resource",
            headers={
                "Origin": "https://app.astroos.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, Authorization",
            },
        )

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "https://app.astroos.com"
        assert response.headers.get("access-control-allow-credentials") == "true"
        allow_methods = response.headers.get("access-control-allow-methods", "")
        assert "POST" in allow_methods
        allow_headers = response.headers.get("access-control-allow-headers", "").lower()
        assert "content-type" in allow_headers
        assert "authorization" in allow_headers

    def test_cors_preflight_unauthorized_origin_rejected(self):
        """Preflight OPTIONS from an unauthorized origin is rejected without allow-origin header."""
        test_app = create_isolated_cors_app(["https://app.astroos.com"])
        client = TestClient(test_app)

        response = client.options(
            "/api/v1/resource",
            headers={
                "Origin": "https://unauthorized.attacker.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        assert "access-control-allow-origin" not in response.headers

    def test_cors_preflight_disallowed_method_rejected(self):
        """Preflight OPTIONS requesting a disallowed method (e.g., PUT) is rejected with HTTP 400."""
        test_app = create_isolated_cors_app(["https://app.astroos.com"])
        client = TestClient(test_app)

        response = client.options(
            "/api/v1/resource",
            headers={
                "Origin": "https://app.astroos.com",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        assert response.status_code == 400
        assert "Disallowed CORS method" in response.text
        # Verify PUT is not permitted by the returned Access-Control-Allow-Methods policy
        allow_methods = response.headers.get("access-control-allow-methods", "")
        assert "PUT" not in allow_methods

    def test_cors_preflight_disallowed_header_rejected(self):
        """Preflight OPTIONS requesting an unapproved header is rejected with HTTP 400."""
        test_app = create_isolated_cors_app(["https://app.astroos.com"])
        client = TestClient(test_app)

        response = client.options(
            "/api/v1/resource",
            headers={
                "Origin": "https://app.astroos.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-Custom-Malicious-Header",
            },
        )

        assert response.status_code == 400
        assert "Disallowed CORS headers" in response.text
        # Verify X-Custom-Malicious-Header is not permitted by the returned Access-Control-Allow-Headers policy
        allow_headers = response.headers.get("access-control-allow-headers", "").lower()
        assert "x-custom-malicious-header" not in allow_headers

    def test_cors_actual_request_allowed_vs_unauthorized(self):
        """Actual GET requests from allowed origin get credentials and allow-origin; unauthorized do not."""
        test_app = create_isolated_cors_app(["https://app.astroos.com"])
        client = TestClient(test_app)

        # 1. Allowed Origin
        resp_allowed = client.get(
            "/api/v1/resource",
            headers={"Origin": "https://app.astroos.com"},
        )
        assert resp_allowed.status_code == 200
        assert resp_allowed.headers.get("access-control-allow-origin") == "https://app.astroos.com"
        assert resp_allowed.headers.get("access-control-allow-credentials") == "true"

        # 2. Unauthorized Origin
        resp_unauth = client.get(
            "/api/v1/resource",
            headers={"Origin": "https://unauthorized.attacker.com"},
        )
        assert resp_unauth.status_code == 200
        assert "access-control-allow-origin" not in resp_unauth.headers


# ===========================================================================
# H. JPL Client Lifecycle and Upstream Error Sanitization
# ===========================================================================


class TestJplLifecycleAndErrorSanitization:
    """Verify that HorizonsClient is closed on success/failure and errors are sanitized."""

    def test_jpl_client_closed_on_success(self, monkeypatch):
        """HorizonsClient.close() is called when ephemeris fetch succeeds."""
        import app.services.jpl_astronomy_adapter as adapter

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_client.get_observer_ephemeris.return_value = mock_response

        # Mock HorizonsClient constructor to return mock_client
        monkeypatch.setattr(adapter._jpl_client, "HorizonsClient", MagicMock(return_value=mock_client))
        monkeypatch.setattr(
            adapter._event_adapter.HorizonsEventAdapter,
            "create_observation_passes",
            MagicMock(return_value=[{"event_id": "test-pass-01"}]),
        )

        result = adapter.fetch_events_from_jpl(
            latitude=10.5276,
            longitude=76.2144,
            start_time_iso=SESSION_START,
            end_time_iso=SESSION_END,
        )

        assert len(result) == 1
        mock_client.close.assert_called_once()

    def test_jpl_client_closed_on_failure(self, monkeypatch):
        """HorizonsClient.close() is called even when get_observer_ephemeris raises an exception."""
        import app.services.jpl_astronomy_adapter as adapter

        mock_client = MagicMock()
        mock_client.get_observer_ephemeris.side_effect = RuntimeError("NASA Horizons API 500 error")

        monkeypatch.setattr(adapter._jpl_client, "HorizonsClient", MagicMock(return_value=mock_client))

        with pytest.raises(RuntimeError, match="NASA Horizons API 500 error"):
            adapter.fetch_events_from_jpl(
                latitude=10.5276,
                longitude=76.2144,
                start_time_iso=SESSION_START,
                end_time_iso=SESSION_END,
            )

        mock_client.close.assert_called_once()

    def test_jpl_upstream_failure_does_not_leak_urls_or_secrets(self, client, monkeypatch):
        """Upstream JPL failures return HTTP 502 with sanitized detail, omitting raw URLs and secrets."""
        import app.api.routes.observation_plans as routes

        secret_url = "https://ssd.jpl.nasa.gov/api/horizons.api?token=super_secret_nasa_api_key_12345"
        monkeypatch.setattr(
            routes.jpl_adapter,
            "fetch_events_from_jpl",
            MagicMock(side_effect=RuntimeError(f"HTTP connection failed at {secret_url}")),
        )

        payload = {
            "session": {
                "latitude": 10.5276,
                "longitude": 76.2144,
                "session_start": SESSION_START,
                "session_end": SESSION_END,
            },
            "events": [],
        }

        response = client.post("/api/v1/observation-plans/generate", json=payload)
        assert response.status_code == 502
        data = response.json()
        assert "Failed to fetch events from JPL Horizons" in data["detail"]
        assert "super_secret_nasa_api_key_12345" not in response.text
        assert "https://ssd.jpl.nasa.gov" not in response.text
        assert "token=" not in response.text


# ===========================================================================
# I. Environmental Forecast Error Handling and Rollback
# ===========================================================================


class TestEnvironmentalForecastErrorHandling:
    """Validate HTTP status codes, error detail sanitization, and rollback in /forecast."""

    def test_forecast_timeout_returns_504(self, client, monkeypatch):
        """WeatherProviderTimeoutError maps to HTTP 504 with a sanitized detail."""
        from app.services.environmental_service import EnvironmentalService
        from app.services.weather_provider import WeatherProviderTimeoutError

        monkeypatch.setattr(
            EnvironmentalService,
            "get_or_fetch_forecast_observations",
            MagicMock(side_effect=WeatherProviderTimeoutError("Connection timed out after 10.0s")),
        )

        payload = {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "start_time": "2026-10-27T19:00:00+05:30",
            "end_time": "2026-10-27T23:00:00+05:30",
            "force_refresh": False,
            "persist": False,
        }

        response = client.post("/api/v1/environmental-observations/forecast", json=payload)
        assert response.status_code == 504
        assert response.json()["detail"] == "Weather provider timed out while retrieving forecast."

    def test_forecast_upstream_error_returns_502(self, client, monkeypatch):
        """WeatherProviderError maps to HTTP 502 without leaking upstream URLs or tokens."""
        from app.services.environmental_service import EnvironmentalService
        from app.services.weather_provider import WeatherProviderHTTPError

        secret_url = "https://api.open-meteo.com/v1/forecast?token=super_secret_weather_token_999"
        monkeypatch.setattr(
            EnvironmentalService,
            "get_or_fetch_forecast_observations",
            MagicMock(side_effect=WeatherProviderHTTPError(500, f"Upstream error at {secret_url}")),
        )

        payload = {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "start_time": "2026-10-27T19:00:00+05:30",
            "end_time": "2026-10-27T23:00:00+05:30",
            "force_refresh": False,
            "persist": False,
        }

        response = client.post("/api/v1/environmental-observations/forecast", json=payload)
        assert response.status_code == 502
        assert response.json()["detail"] == "Weather provider service temporarily unavailable or returned an error."
        assert "super_secret_weather_token_999" not in response.text
        assert "https://api.open-meteo.com" not in response.text

    def test_forecast_unexpected_error_returns_500_sanitized(self, client, monkeypatch):
        """Unexpected internal errors map to sanitized HTTP 500 without stack details."""
        from app.services.environmental_service import EnvironmentalService

        monkeypatch.setattr(
            EnvironmentalService,
            "get_or_fetch_forecast_observations",
            MagicMock(side_effect=RuntimeError("Internal parse bug at C:\\Users\\Admin\\internal.py:42")),
        )

        payload = {
            "latitude": 10.5276,
            "longitude": 76.2144,
            "start_time": "2026-10-27T19:00:00+05:30",
            "end_time": "2026-10-27T23:00:00+05:30",
            "force_refresh": False,
            "persist": False,
        }

        response = client.post("/api/v1/environmental-observations/forecast", json=payload)
        assert response.status_code == 500
        assert response.json()["detail"] == "An unexpected error occurred while retrieving forecast."
        assert "internal.py" not in response.text

    def test_forecast_rollback_on_failure_when_persist_true_and_false(self, client, monkeypatch):
        """Transaction rollback occurs on failure when persist=True, and is skipped when persist=False."""
        from app.services.environmental_service import EnvironmentalService
        from app.services.weather_provider import WeatherProviderTimeoutError

        monkeypatch.setattr(
            EnvironmentalService,
            "get_or_fetch_forecast_observations",
            MagicMock(side_effect=WeatherProviderTimeoutError("Timed out")),
        )

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(role="admin", is_active=True)
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            base_payload = {
                "latitude": 10.5276,
                "longitude": 76.2144,
                "start_time": "2026-10-27T19:00:00+05:30",
                "end_time": "2026-10-27T23:00:00+05:30",
                "force_refresh": False,
            }

            # 1. When persist=True, rollback is called on failure
            payload_persist = {**base_payload, "persist": True}
            resp_persist = client.post("/api/v1/environmental-observations/forecast", json=payload_persist)
            assert resp_persist.status_code == 504
            mock_db.rollback.assert_called_once()

            # 2. When persist=False, rollback is NOT called
            mock_db.reset_mock()
            payload_no_persist = {**base_payload, "persist": False}
            resp_no_persist = client.post("/api/v1/environmental-observations/forecast", json=payload_no_persist)
            assert resp_no_persist.status_code == 504
            mock_db.rollback.assert_not_called()
        finally:
            app.dependency_overrides.pop(get_db, None)



