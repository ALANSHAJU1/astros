"""
tests/test_auth_routes.py
=========================
Integration tests for AstroOS authentication endpoints (Phase 5B.3).

Covers:
1. Registration success, email normalization, duplicate email (HTTP 409).
2. Registration role protection (cannot self-assign admin/service).
3. Password hash non-disclosure.
4. Login with valid credentials and generic HTTP 401 on invalid credentials.
5. Inactive account login rejection.
6. Access token validation and wrong token-type rejection.
7. Refresh token rotation (new access token, new rotated refresh token).
8. Old-token replay detection and immediate family-wide cascade revocation.
9. Expired, revoked, malformed, and unknown refresh token rejection.
10. Inactive user refresh rejection.
11. Transaction rollback on database failure.
12. Logout and repeated logout (idempotent).
13. GET /me authentication, safe profile, and unauthenticated rejection.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError

from app.core.security import (
    create_access_token,
    generate_refresh_token_pair,
    hash_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User

_TEST_JWT_SECRET = "t" * 32


@pytest.fixture(autouse=True)
def setup_jwt_secret(monkeypatch):
    """Ensure a valid test JWT secret is configured for all route tests."""
    monkeypatch.setattr("app.core.config.JWT_SECRET_KEY", _TEST_JWT_SECRET)
    monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", _TEST_JWT_SECRET)


# ===========================================================================
# 1. Registration Tests
# ===========================================================================
class TestRegistrationEndpoints:
    def test_successful_registration(self, client, db):
        payload = {
            "email": "NewAstronomer@Example.com",
            "password": "SecurePassword123!",
            "full_name": "Johannes Kepler",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["email"] == "newastronomer@example.com"  # Normalized
        assert data["full_name"] == "Johannes Kepler"
        assert data["role"] == "user"
        assert data["is_active"] is True
        assert "id" in data
        assert "password" not in data
        assert "hashed_password" not in data

        # Verify in database
        user = db.query(User).filter(User.email == "newastronomer@example.com").first()
        assert user is not None
        assert user.role == "user"
        assert user.hashed_password.startswith("$argon2id$")

    def test_duplicate_email_rejected_with_409(self, client, db):
        payload = {
            "email": "duplicate@example.com",
            "password": "Password123!",
            "full_name": "First User",
        }
        resp1 = client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        # Attempt to register with uppercase variant
        payload2 = {
            "email": "DUPLICATE@EXAMPLE.COM",
            "password": "Password456!",
            "full_name": "Second User",
        }
        resp2 = client.post("/api/v1/auth/register", json=payload2)
        assert resp2.status_code == 409
        assert "already exists" in resp2.json()["detail"].lower()

    def test_registration_ignores_or_rejects_admin_role(self, client, db):
        # Attempt to inject role="admin" in payload
        payload = {
            "email": "sneaky_admin@example.com",
            "password": "Password123!",
            "full_name": "Attacker",
            "role": "admin",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201

        # Must strictly be assigned 'user' on the server
        data = response.json()
        assert data["role"] == "user"
        assert data["role"] != "admin"

        user = db.query(User).filter(User.email == "sneaky_admin@example.com").first()
        assert user.role == "user"

    def test_registration_disabled_returns_403(self, client, monkeypatch):
        monkeypatch.setattr("app.api.routes.auth.ENABLE_PUBLIC_REGISTRATION", False)
        payload = {
            "email": "blocked@example.com",
            "password": "Password123!",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 403
        assert "disabled" in response.json()["detail"].lower()

    def test_short_password_rejected(self, client):
        payload = {
            "email": "short@example.com",
            "password": "short",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code in (400, 422)


# ===========================================================================
# 2. Login Tests
# ===========================================================================
class TestLoginEndpoints:
    def test_successful_login(self, client, db):
        # Create user
        user = User(
            email="logintest@example.com",
            hashed_password=hash_password("ValidPassword123!"),
            role="user",
            is_active=True,
        )
        db.add(user)
        db.commit()

        payload = {
            "email": "LoginTest@Example.com",
            "password": "ValidPassword123!",
        }
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

        # Verify refresh token hash is stored in DB
        submitted_refresh = data["refresh_token"]
        expected_hash = hashlib.sha256(submitted_refresh.encode()).hexdigest()

        rt = db.query(RefreshToken).filter(RefreshToken.token_hash == expected_hash).first()
        assert rt is not None
        assert rt.user_id == user.id
        assert rt.revoked_at is None

    def test_invalid_password_returns_generic_401(self, client, db):
        user = User(
            email="wrongpw@example.com",
            hashed_password=hash_password("RealPassword123!"),
            role="user",
        )
        db.add(user)
        db.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpw@example.com", "password": "WrongPassword123!"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password."

    def test_nonexistent_email_returns_generic_401(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "SomePassword123!"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password."

    def test_inactive_user_login_rejected(self, client, db):
        user = User(
            email="inactive@example.com",
            hashed_password=hash_password("ValidPassword123!"),
            role="user",
            is_active=False,
        )
        db.add(user)
        db.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "inactive@example.com", "password": "ValidPassword123!"},
        )
        assert response.status_code == 401
        assert "inactive" in response.json()["detail"].lower()


# ===========================================================================
# 3. Refresh Token Rotation & Replay Protection Tests
# ===========================================================================
class TestRefreshTokenRotation:
    def test_successful_refresh_rotation(self, client, db):
        # 1. Register & Login
        client.post(
            "/api/v1/auth/register",
            json={"email": "refresh_user@example.com", "password": "Password123!"},
        )
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": "refresh_user@example.com", "password": "Password123!"},
        )
        old_refresh = login_resp.json()["refresh_token"]

        # 2. Rotate
        refresh_resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        assert refresh_resp.status_code == 200
        new_data = refresh_resp.json()
        assert "access_token" in new_data
        assert "refresh_token" in new_data
        new_refresh = new_data["refresh_token"]
        assert new_refresh != old_refresh

        # Verify old token record is marked revoked
        old_hash = hashlib.sha256(old_refresh.encode()).hexdigest()
        old_rec = db.query(RefreshToken).filter(RefreshToken.token_hash == old_hash).first()
        assert old_rec.revoked_at is not None

        # Verify new token record is active and shares family_id
        new_hash = hashlib.sha256(new_refresh.encode()).hexdigest()
        new_rec = db.query(RefreshToken).filter(RefreshToken.token_hash == new_hash).first()
        assert new_rec.revoked_at is None
        assert new_rec.family_id == old_rec.family_id

    def test_replay_attack_revokes_entire_family(self, client, db):
        # Setup: user logs in and rotates once legitimately
        client.post(
            "/api/v1/auth/register",
            json={"email": "replay_victim@example.com", "password": "Password123!"},
        )
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": "replay_victim@example.com", "password": "Password123!"},
        )
        initial_token = login_resp.json()["refresh_token"]

        # Legitimate rotation 1
        rot1_resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": initial_token},
        )
        assert rot1_resp.status_code == 200
        active_token = rot1_resp.json()["refresh_token"]

        # Legitimate rotation 2
        rot2_resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": active_token},
        )
        assert rot2_resp.status_code == 200
        latest_token = rot2_resp.json()["refresh_token"]

        # ATTACK: Attacker replays initial_token (which was already rotated)
        replay_resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": initial_token},
        )
        assert replay_resp.status_code == 401
        assert "already been rotated" in replay_resp.json()["detail"].lower()

        # CONSEQUENCE: Even latest_token must now be revoked!
        post_attack_resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": latest_token},
        )
        assert post_attack_resp.status_code == 401

    def test_concurrent_refresh_attempts(self, test_engine):
        import concurrent.futures
        from sqlalchemy.orm import sessionmaker
        from fastapi.testclient import TestClient
        from app.main import app
        from app.db.session import get_db

        SessionMaker = sessionmaker(bind=test_engine)

        def thread_get_db():
            s = SessionMaker()
            try:
                yield s
            finally:
                s.close()

        with patch.dict(app.dependency_overrides, {get_db: thread_get_db}):
            with TestClient(app) as thread_client:
                thread_client.post(
                    "/api/v1/auth/register",
                    json={"email": "concurrent_refresh@example.com", "password": "Password123!"},
                )
                login_resp = thread_client.post(
                    "/api/v1/auth/login",
                    json={"email": "concurrent_refresh@example.com", "password": "Password123!"},
                )
                token = login_resp.json()["refresh_token"]

                def send_refresh():
                    return thread_client.post("/api/v1/auth/refresh", json={"refresh_token": token})

                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    fut1 = executor.submit(send_refresh)
                    fut2 = executor.submit(send_refresh)
                    resp1 = fut1.result()
                    resp2 = fut2.result()

                # Exactly one must succeed (200), and the other must be rejected (401)
                statuses = sorted([resp1.status_code, resp2.status_code])
                assert statuses == [200, 401]

    def test_unknown_refresh_token_rejected(self, client):
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "unknown_random_token_string_123456789"},
        )
        assert response.status_code == 401
        assert "unrecognized" in response.json()["detail"].lower()

    def test_expired_refresh_token_rejected(self, client, db):
        user = User(
            email="expired_refresh@example.com",
            hashed_password=hash_password("Password123!"),
            role="user",
        )
        db.add(user)
        db.commit()

        raw_token, token_hash = generate_refresh_token_pair()
        past = datetime.now(timezone.utc) - timedelta(days=1)
        expired_rt = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            family_id=uuid.uuid4(),
            expires_at=past,
        )
        db.add(expired_rt)
        db.commit()

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": raw_token},
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_inactive_user_cannot_refresh(self, client, db):
        user = User(
            email="inactive_refresh@example.com",
            hashed_password=hash_password("Password123!"),
            role="user",
            is_active=False,
        )
        db.add(user)
        db.commit()

        raw_token, token_hash = generate_refresh_token_pair()
        rt = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            family_id=uuid.uuid4(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(rt)
        db.commit()

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": raw_token},
        )
        assert response.status_code == 401
        assert "inactive" in response.json()["detail"].lower()

    def test_transaction_rollback_on_db_error(self, test_engine):
        """Verify database state is genuinely restored when rotation commit fails.

        Requirements:
        1. Trigger a failure during refresh-token rotation.
        2. Allow the application transaction to roll back.
        3. Open a separate independent database session.
        4. Query the original refresh-token record.
        5. Verify that the original token remains unrevoked.
        6. Verify that no replacement token was persisted.

        The test binds directly to test_engine so that setup and test runs
        commit to PostgreSQL, enabling an independent verification session
        to inspect actual database rows rather than in-memory ORM cache.
        """
        from fastapi.testclient import TestClient
        from sqlalchemy.orm import sessionmaker as _sessionmaker
        from app.main import app
        from app.db.session import get_db

        SessionMaker = _sessionmaker(bind=test_engine)

        # 1. Setup user and initial refresh token in an independent session
        setup_session = SessionMaker()
        user_id = None
        raw_token = None
        token_hash = None
        original_family_id = None
        try:
            user = User(
                email="dberror@example.com",
                hashed_password=hash_password("Password123!"),
                role="user",
            )
            setup_session.add(user)
            setup_session.commit()
            user_id = user.id

            raw_token, token_hash = generate_refresh_token_pair()
            rt = RefreshToken(
                user_id=user.id,
                token_hash=token_hash,
                family_id=uuid.uuid4(),
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            setup_session.add(rt)
            setup_session.commit()
            original_family_id = rt.family_id
        finally:
            setup_session.close()

        # 2. Configure app dependency override to yield a fresh session that fails on commit
        # Specifically, we want the final commit of atomic rotation to raise OperationalError
        active_session = None

        def failing_get_db():
            nonlocal active_session
            active_session = SessionMaker()
            # Monkeypatch commit on this session to simulate failure
            orig_commit = active_session.commit
            call_count = 0

            def patched_commit():
                nonlocal call_count
                call_count += 1
                raise OperationalError("mock", "params", Exception("DB connection lost"))

            active_session.commit = patched_commit
            try:
                yield active_session
            finally:
                active_session.close()

        try:
            with patch.dict(app.dependency_overrides, {get_db: failing_get_db}):
                with TestClient(app) as local_client:
                    response = local_client.post(
                        "/api/v1/auth/refresh",
                        json={"refresh_token": raw_token},
                    )
                    assert response.status_code == 500

            # 3. Open a separate independent database session to verify state
            verify_session = SessionMaker()
            try:
                # 4 & 5. Query original record and verify it remains unrevoked
                check_original = (
                    verify_session.query(RefreshToken)
                    .filter(RefreshToken.token_hash == token_hash)
                    .first()
                )
                assert check_original is not None, "Original token record not found"
                assert check_original.revoked_at is None, (
                    f"Original token was revoked despite rollback: "
                    f"revoked_at={check_original.revoked_at}"
                )

                # 6. Verify that no replacement token was persisted
                all_family_tokens = (
                    verify_session.query(RefreshToken)
                    .filter(RefreshToken.family_id == original_family_id)
                    .all()
                )
                assert len(all_family_tokens) == 1, (
                    f"Expected 1 token in family, found {len(all_family_tokens)} "
                    f"— replacement token was persisted despite rollback"
                )
            finally:
                verify_session.close()

        finally:
            # Cleanup test data created outside standard db rollback fixture
            cleanup_session = SessionMaker()
            try:
                cleanup_session.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
                cleanup_session.query(User).filter(User.id == user_id).delete()
                cleanup_session.commit()
            finally:
                cleanup_session.close()


# ===========================================================================
# 4. Logout Tests
# ===========================================================================
class TestLogoutEndpoints:
    def test_successful_logout_revokes_token(self, client, db):
        # Register and login
        client.post(
            "/api/v1/auth/register",
            json={"email": "logout_test@example.com", "password": "Password123!"},
        )
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": "logout_test@example.com", "password": "Password123!"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Logout
        logout_resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert logout_resp.status_code == 200

        # Verify token cannot be refreshed anymore
        refresh_attempt = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_attempt.status_code == 401

    def test_repeated_logout_is_idempotent(self, client):
        payload = {"refresh_token": "some_arbitrary_token_123456789"}
        resp1 = client.post("/api/v1/auth/logout", json=payload)
        resp2 = client.post("/api/v1/auth/logout", json=payload)
        assert resp1.status_code == 200
        assert resp2.status_code == 200


# ===========================================================================
# 5. Profile (/me) Tests
# ===========================================================================
class TestProfileEndpoint:
    def test_authenticated_user_profile(self, client, db):
        user = User(
            email="me_profile@example.com",
            hashed_password=hash_password("Password123!"),
            full_name="Sirius Black",
            role="user",
        )
        db.add(user)
        db.commit()

        token = create_access_token(subject=user.id, role=user.role)
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me_profile@example.com"
        assert data["full_name"] == "Sirius Black"
        assert data["role"] == "user"
        assert "hashed_password" not in data

    def test_unauthenticated_request_rejected(self, anonymous_client):
        response = anonymous_client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_refresh_token_rejected_on_access_endpoint(self, client, monkeypatch):
        # Craft a JWT with type="refresh" instead of type="access"
        import jwt
        from app.core.config import JWT_ALGORITHM, JWT_SECRET_KEY
        token = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "role": "user",
                "type": "refresh",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
            },
            _TEST_JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()


# ===========================================================================
# 6. JWT Subject (sub) UUID Validation Tests  (Fix 4)
# ===========================================================================
class TestJwtSubjectValidation:
    """Verify that get_current_user rejects tokens with a non-UUID sub claim.

    These tests craft JWTs directly so they can inject arbitrary ``sub`` values
    that would never be produced by create_access_token in normal operation.
    """

    def _craft_token(self, sub_value: str) -> str:
        """Return a structurally valid, currently unexpired JWT with a custom sub."""
        import jwt as _jwt
        from app.core.config import JWT_ALGORITHM

        now = datetime.now(timezone.utc)
        return _jwt.encode(
            {
                "sub": sub_value,
                "role": "user",
                "type": "access",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=15)).timestamp()),
            },
            _TEST_JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )

    def test_non_uuid_sub_returns_401_not_500(self, client):
        """A token with a plain string sub must return 401, not an unhandled 500."""
        token = self._craft_token("not-a-uuid-at-all")
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert "malformed subject" in response.json()["detail"].lower()

    def test_sql_injection_attempt_in_sub_returns_401(self, client):
        """A SQL-injection string in sub must be rejected with 401."""
        token = self._craft_token("' OR '1'='1")
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert "malformed subject" in response.json()["detail"].lower()

    def test_path_traversal_attempt_in_sub_returns_401(self, client):
        """A path-traversal string in sub must be rejected with 401."""
        token = self._craft_token("../../etc/passwd")
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert "malformed subject" in response.json()["detail"].lower()

    def test_empty_sub_returns_401(self, client):
        """An empty sub string must be rejected with 401."""
        token = self._craft_token("")
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_valid_uuid_sub_proceeds_to_user_lookup(self, client, db):
        """A token with a valid UUID sub for a real user returns the profile."""
        user = User(
            email="uuid_sub_valid@example.com",
            hashed_password=hash_password("Password123!"),
            role="user",
        )
        db.add(user)
        db.commit()

        token = create_access_token(subject=user.id, role=user.role)
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["email"] == "uuid_sub_valid@example.com"

    def test_valid_uuid_sub_for_nonexistent_user_returns_401(self, client):
        """A token with a well-formed UUID that doesn't match any user returns 401."""
        token = self._craft_token(str(uuid.uuid4()))
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
