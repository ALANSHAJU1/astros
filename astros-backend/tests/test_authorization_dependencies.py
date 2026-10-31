"""
tests/test_authorization_dependencies.py
========================================
Unit and integration tests for Phase 5B.4 Stage 1 dependencies:
- get_current_user (JWT only)
- get_current_service (X-API-Key service principal)
- get_authenticated_principal (Bearer JWT or X-API-Key with ambiguity rejection)
- Role-based authorization factories: require_roles, require_admin, require_admin_or_service
"""

from datetime import datetime, timedelta, timezone
import hashlib
import uuid

from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient
import jwt
import pytest

from app.api.deps import (
    get_authenticated_principal,
    get_current_service,
    get_current_user,
    require_admin,
    require_admin_or_service,
    require_roles,
)
from app.core.config import JWT_ALGORITHM
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.user import User

_TEST_JWT_SECRET = "t" * 32


@pytest.fixture(autouse=True)
def setup_jwt_secret(monkeypatch):
    monkeypatch.setattr("app.core.config.JWT_SECRET_KEY", _TEST_JWT_SECRET)
    monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", _TEST_JWT_SECRET)


# Build a dedicated test FastAPI app using the dependencies
test_app = FastAPI()


@test_app.get("/test/user-only")
def user_only_endpoint(current_user: User = Depends(get_current_user)):
    return {"user_id": str(current_user.id), "role": current_user.role}


@test_app.get("/test/service-only")
def service_only_endpoint(current_service: User = Depends(get_current_service)):
    return {"service_id": str(current_service.id), "role": current_service.role}


@test_app.get("/test/principal")
def principal_endpoint(principal: User = Depends(get_authenticated_principal)):
    return {"principal_id": str(principal.id), "role": principal.role}


@test_app.get("/test/admin-only")
def admin_only_endpoint(admin: User = Depends(require_admin)):
    return {"admin_id": str(admin.id), "role": admin.role}


@test_app.get("/test/admin-or-service")
def admin_or_service_endpoint(caller: User = Depends(require_admin_or_service)):
    return {"caller_id": str(caller.id), "role": caller.role}


@pytest.fixture
def auth_client(db):
    def override_get_db():
        yield db

    test_app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(test_app) as client:
            yield client
    finally:
        test_app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _create_test_user(db, email: str, role: str = "user", is_active: bool = True) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("Password123!"),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_test_api_key(
    db,
    user: User,
    raw_key: str,
    name: str = "Test Key",
    is_active: bool = True,
    expires_at: datetime | None = None,
) -> ApiKey:
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    api_key = ApiKey(
        user_id=user.id,
        key_hash=key_hash,
        key_prefix=raw_key[:8],
        name=name,
        is_active=is_active,
        expires_at=expires_at,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key


# ===========================================================================
# 1. JWT User Authentication Tests
# ===========================================================================
class TestJwtAuthentication:
    def test_valid_jwt_user_authentication(self, auth_client, db):
        user = _create_test_user(db, "valid_jwt@example.com", role="user")
        token = create_access_token(subject=user.id, role="user")

        response = auth_client.get(
            "/test/user-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == str(user.id)
        assert response.json()["role"] == "user"

    def test_missing_jwt_rejected_with_401(self, auth_client):
        response = auth_client.get("/test/user-only")
        assert response.status_code == 401
        assert "not provided" in response.json()["detail"].lower()

    def test_expired_jwt_rejected_with_401(self, auth_client, db):
        user = _create_test_user(db, "expired_jwt@example.com")
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        expired_token = jwt.encode(
            {
                "sub": str(user.id),
                "role": "user",
                "type": "access",
                "iat": int((past - timedelta(minutes=15)).timestamp()),
                "exp": int(past.timestamp()),
            },
            _TEST_JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )
        response = auth_client.get(
            "/test/user-only",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_invalid_jwt_signature_rejected_with_401(self, auth_client, db):
        user = _create_test_user(db, "bad_sig@example.com")
        forged = jwt.encode(
            {
                "sub": str(user.id),
                "role": "user",
                "type": "access",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
            },
            "wrong_secret" * 4,
            algorithm=JWT_ALGORITHM,
        )
        response = auth_client.get(
            "/test/user-only",
            headers={"Authorization": f"Bearer {forged}"},
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_wrong_token_type_rejected_with_401(self, auth_client, db):
        user = _create_test_user(db, "wrong_type@example.com")
        refresh_jwt = jwt.encode(
            {
                "sub": str(user.id),
                "role": "user",
                "type": "refresh",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp()),
            },
            _TEST_JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )
        response = auth_client.get(
            "/test/user-only",
            headers={"Authorization": f"Bearer {refresh_jwt}"},
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_inactive_user_jwt_rejected_with_401(self, auth_client, db):
        inactive_user = _create_test_user(db, "inactive_jwt@example.com", is_active=False)
        token = create_access_token(subject=inactive_user.id, role="user")

        response = auth_client.get(
            "/test/user-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert "inactive" in response.json()["detail"].lower()

    def test_api_key_not_accepted_by_get_current_user(self, auth_client, db):
        service_user = _create_test_user(db, "service_for_user_dep@example.com", role="service")
        raw_key = "ast_live_service_key_123456789"
        _create_test_api_key(db, service_user, raw_key)

        response = auth_client.get(
            "/test/user-only",
            headers={"X-API-Key": raw_key},
        )
        # get_current_user must only accept Bearer token; X-API-Key is ignored
        assert response.status_code == 401


# ===========================================================================
# 2. Service API-Key Authentication Tests (get_current_service)
# ===========================================================================
class TestServiceApiKeyAuthentication:
    def test_valid_service_api_key_authentication(self, auth_client, db):
        service_user = _create_test_user(db, "ingestion_service@example.com", role="service")
        raw_key = "ast_live_valid_service_key_abcdef"
        _create_test_api_key(db, service_user, raw_key, name="JPL Ingestion")

        response = auth_client.get(
            "/test/service-only",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["service_id"] == str(service_user.id)
        assert data["role"] == "service"

    def test_missing_api_key_rejected_with_401(self, auth_client):
        response = auth_client.get("/test/service-only")
        assert response.status_code == 401
        assert "not provided" in response.json()["detail"].lower()

    def test_invalid_api_key_rejected_with_401(self, auth_client):
        response = auth_client.get(
            "/test/service-only",
            headers={"X-API-Key": "ast_live_nonexistent_key_999999999"},
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_revoked_api_key_rejected_with_401(self, auth_client, db):
        service_user = _create_test_user(db, "revoked_service@example.com", role="service")
        raw_key = "ast_live_revoked_key_123456"
        _create_test_api_key(db, service_user, raw_key, is_active=False)

        response = auth_client.get(
            "/test/service-only",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 401
        assert "revoked" in response.json()["detail"].lower()

    def test_expired_api_key_rejected_with_401(self, auth_client, db):
        service_user = _create_test_user(db, "expired_service@example.com", role="service")
        raw_key = "ast_live_expired_key_123456"
        past_date = datetime.now(timezone.utc) - timedelta(days=2)
        _create_test_api_key(db, service_user, raw_key, expires_at=past_date)

        response = auth_client.get(
            "/test/service-only",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_ordinary_user_api_key_rejected_as_service(self, auth_client, db):
        normal_user = _create_test_user(db, "normal_user@example.com", role="user")
        raw_key = "ast_live_user_key_cannot_be_service"
        _create_test_api_key(db, normal_user, raw_key)

        response = auth_client.get(
            "/test/service-only",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 401
        assert "service credentials" in response.json()["detail"].lower()

    def test_admin_api_key_rejected_as_service(self, auth_client, db):
        admin_user = _create_test_user(db, "admin_user@example.com", role="admin")
        raw_key = "ast_live_admin_key_cannot_be_service"
        _create_test_api_key(db, admin_user, raw_key)

        response = auth_client.get(
            "/test/service-only",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 401
        assert "service credentials" in response.json()["detail"].lower()

    def test_inactive_service_user_rejected_with_401(self, auth_client, db):
        inactive_service = _create_test_user(
            db, "inactive_service@example.com", role="service", is_active=False
        )
        raw_key = "ast_live_inactive_service_key_123"
        _create_test_api_key(db, inactive_service, raw_key)

        response = auth_client.get(
            "/test/service-only",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 401
        assert "inactive" in response.json()["detail"].lower()


# ===========================================================================
# 3. Authenticated Principal & Credential Precedence (get_authenticated_principal)
# ===========================================================================
class TestAuthenticatedPrincipalResolution:
    def test_principal_via_valid_jwt(self, auth_client, db):
        user = _create_test_user(db, "principal_jwt@example.com", role="user")
        token = create_access_token(subject=user.id, role="user")

        response = auth_client.get(
            "/test/principal",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["principal_id"] == str(user.id)
        assert response.json()["role"] == "user"

    def test_principal_via_valid_service_api_key(self, auth_client, db):
        service_user = _create_test_user(db, "principal_service@example.com", role="service")
        raw_key = "ast_live_principal_service_key"
        _create_test_api_key(db, service_user, raw_key)

        response = auth_client.get(
            "/test/principal",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 200
        assert response.json()["principal_id"] == str(service_user.id)
        assert response.json()["role"] == "service"

    def test_ambiguous_credentials_both_supplied_rejected_with_400(self, auth_client, db):
        user = _create_test_user(db, "ambig_user@example.com", role="user")
        token = create_access_token(subject=user.id, role="user")

        service_user = _create_test_user(db, "ambig_service@example.com", role="service")
        raw_key = "ast_live_ambig_key"
        _create_test_api_key(db, service_user, raw_key)

        response = auth_client.get(
            "/test/principal",
            headers={
                "Authorization": f"Bearer {token}",
                "X-API-Key": raw_key,
            },
        )
        assert response.status_code == 400
        assert "ambiguous" in response.json()["detail"].lower()

    def test_no_credentials_rejected_with_401(self, auth_client):
        response = auth_client.get("/test/principal")
        assert response.status_code == 401


# ===========================================================================
# 4. Role-Based Authorization Tests (require_admin, require_admin_or_service)
# ===========================================================================
class TestRoleBasedAuthorization:
    def test_admin_receives_admin_authorization(self, auth_client, db):
        admin = _create_test_user(db, "real_admin@example.com", role="admin")
        token = create_access_token(subject=admin.id, role="admin")

        response = auth_client.get(
            "/test/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    def test_regular_user_rejected_from_admin_with_403(self, auth_client, db):
        user = _create_test_user(db, "regular_user_denied@example.com", role="user")
        token = create_access_token(subject=user.id, role="user")

        response = auth_client.get(
            "/test/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert "not permitted" in response.json()["detail"].lower()

    def test_service_principal_rejected_from_admin_with_403(self, auth_client, db):
        service = _create_test_user(db, "service_not_admin@example.com", role="service")
        raw_key = "ast_live_service_not_admin_key"
        _create_test_api_key(db, service, raw_key)

        response = auth_client.get(
            "/test/admin-only",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 403
        assert "not permitted" in response.json()["detail"].lower()

    def test_admin_or_service_accepts_admin(self, auth_client, db):
        admin = _create_test_user(db, "admin_for_both@example.com", role="admin")
        token = create_access_token(subject=admin.id, role="admin")

        response = auth_client.get(
            "/test/admin-or-service",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    def test_admin_or_service_accepts_service(self, auth_client, db):
        service = _create_test_user(db, "service_for_both@example.com", role="service")
        raw_key = "ast_live_service_for_both_key"
        _create_test_api_key(db, service, raw_key)

        response = auth_client.get(
            "/test/admin-or-service",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "service"

    def test_admin_or_service_rejects_regular_user_with_403(self, auth_client, db):
        user = _create_test_user(db, "regular_for_both_denied@example.com", role="user")
        token = create_access_token(subject=user.id, role="user")

        response = auth_client.get(
            "/test/admin-or-service",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_unauthenticated_request_to_protected_role_returns_401_not_403(self, auth_client):
        # Missing credentials must produce 401, not 403
        resp1 = auth_client.get("/test/admin-only")
        assert resp1.status_code == 401

        resp2 = auth_client.get("/test/admin-or-service")
        assert resp2.status_code == 401

    def test_invalid_role_in_factory_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid roles in requirement"):
            require_roles("superadmin")

