"""
tests/test_security.py
======================
Unit tests for password hashing (Argon2id) and JWT token services (Phase 5B.3).
"""

from datetime import datetime, timedelta, timezone
import hashlib
import uuid

import jwt
import pytest

from app.core.config import JWT_ALGORITHM, JWT_SECRET_KEY
from app.core.security import (
    create_access_token,
    decode_token,
    generate_refresh_token_pair,
    hash_password,
    verify_password,
)


# ===========================================================================
# 1. Password Hashing Tests (Argon2id)
# ===========================================================================
class TestPasswordHashing:
    def test_hash_roundtrip_verification(self):
        password = "SecurePassword123!"
        hashed = hash_password(password)

        assert hashed.startswith("$argon2id$")
        assert verify_password(password, hashed) is True

    def test_incorrect_password_rejected(self):
        hashed = hash_password("CorrectPassword123")
        assert verify_password("WrongPassword123", hashed) is False

    @pytest.mark.parametrize(
        "malformed_hash",
        [
            "not_a_valid_argon2_hash",
            "$argon2id$v=19$corrupted_payload",
            "$pbkdf2-sha256$29000$badformat",
            "",
            "   ",
        ],
    )
    def test_malformed_hash_handled_safely(self, malformed_hash):
        assert verify_password("AnyPassword123", malformed_hash) is False

    @pytest.mark.parametrize("invalid_password", ["", None, 12345, []])
    def test_empty_or_invalid_password_raises(self, invalid_password):
        with pytest.raises(ValueError, match="non-empty string"):
            hash_password(invalid_password)

    def test_short_password_rejected(self):
        with pytest.raises(ValueError, match="at least 8 characters"):
            hash_password("short7!")

    def test_long_password_rejected(self):
        with pytest.raises(ValueError, match="cannot exceed 128 characters"):
            hash_password("a" * 129)

    def test_verify_non_string_inputs_returns_false(self):
        assert verify_password(None, "hash") is False
        assert verify_password("password", None) is False
        assert verify_password("", "") is False


# ===========================================================================
# 2. JWT Access Token Tests
# ===========================================================================
class TestJwtSecurity:
    def test_create_and_decode_valid_access_token(self, monkeypatch):
        secret = "a" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)
        user_id = uuid.uuid4()

        token = create_access_token(subject=user_id, role="user")
        payload = decode_token(token, expected_type="access")

        assert payload["sub"] == str(user_id)
        assert payload["role"] == "user"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_invalid_signature_rejected(self, monkeypatch):
        real_secret = "a" * 32
        attacker_secret = "b" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", real_secret)

        user_id = str(uuid.uuid4())
        # Forge token using attacker's secret
        now = datetime.now(timezone.utc)
        forged = jwt.encode(
            {
                "sub": user_id,
                "role": "admin",
                "type": "access",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=15)).timestamp()),
            },
            attacker_secret,
            algorithm=JWT_ALGORITHM,
        )

        with pytest.raises(jwt.InvalidSignatureError):
            decode_token(forged, expected_type="access")

    def test_expired_token_rejected(self, monkeypatch):
        secret = "a" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)

        user_id = str(uuid.uuid4())
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        expired_token = jwt.encode(
            {
                "sub": user_id,
                "role": "user",
                "type": "access",
                "iat": int((past - timedelta(minutes=15)).timestamp()),
                "exp": int(past.timestamp()),
            },
            secret,
            algorithm=JWT_ALGORITHM,
        )

        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(expired_token, expected_type="access")

    def test_wrong_token_type_rejected(self, monkeypatch):
        secret = "a" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        refresh_token = jwt.encode(
            {
                "sub": user_id,
                "role": "user",
                "type": "refresh",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(days=7)).timestamp()),
            },
            secret,
            algorithm=JWT_ALGORITHM,
        )

        with pytest.raises(jwt.InvalidTokenError, match="expected 'access', got 'refresh'"):
            decode_token(refresh_token, expected_type="access")

    def test_missing_required_claims_rejected(self, monkeypatch):
        secret = "a" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)

        now = datetime.now(timezone.utc)
        # Missing 'sub' claim
        bad_token = jwt.encode(
            {
                "role": "user",
                "type": "access",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=15)).timestamp()),
            },
            secret,
            algorithm=JWT_ALGORITHM,
        )

        with pytest.raises(jwt.MissingRequiredClaimError):
            decode_token(bad_token, expected_type="access")

    def test_tampered_payload_rejected(self, monkeypatch):
        secret = "a" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)

        token = create_access_token(subject=uuid.uuid4(), role="user")
        header, payload, signature = token.split(".")

        # Tamper with the middle payload part
        tampered_token = f"{header}.eyJzdWIiOiAiaGFja2VyIn0.{signature}"

        with pytest.raises(jwt.DecodeError):
            decode_token(tampered_token, expected_type="access")

    def test_unconfigured_secret_raises_runtime_error(self, monkeypatch):
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", None)

        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY is not configured"):
            create_access_token(subject=uuid.uuid4())

        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY is not configured"):
            decode_token("some_token")


# ===========================================================================
# 3. Refresh Token Generation Tests
# ===========================================================================
class TestRefreshTokenGeneration:
    def test_refresh_token_pair_properties(self):
        raw_token, token_hash = generate_refresh_token_pair()

        assert isinstance(raw_token, str)
        assert len(raw_token) >= 48
        assert isinstance(token_hash, str)
        assert len(token_hash) == 64  # SHA-256 hex digest length
        assert hashlib.sha256(raw_token.encode()).hexdigest() == token_hash

    def test_subsequent_tokens_are_unique(self):
        pair1 = generate_refresh_token_pair()
        pair2 = generate_refresh_token_pair()

        assert pair1[0] != pair2[0]
        assert pair1[1] != pair2[1]


# ===========================================================================
# 4. Future-IAT Rejection Tests  (Fix 5)
# ===========================================================================
class TestFutureIatRejection:
    """Verify that decode_token rejects tokens whose iat claim is in the future.

    PyJWT's ``verify_iat`` option only checks that ``iat`` is numeric; it does
    not reject future-dated values.  The explicit post-decode check in
    decode_token() must enforce this policy.

    The clock-skew allowance is IAT_CLOCK_SKEW_SECONDS (30 s).
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _make_token(secret: str, iat_offset_seconds: float, algorithm: str = "HS256") -> str:
        """Craft a JWT with iat = now + iat_offset_seconds."""
        now = datetime.now(timezone.utc)
        iat_ts = int((now + timedelta(seconds=iat_offset_seconds)).timestamp())
        exp_ts = int((now + timedelta(minutes=15)).timestamp())
        return jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "role": "user",
                "type": "access",
                "iat": iat_ts,
                "exp": exp_ts,
            },
            secret,
            algorithm=algorithm,
        )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------
    def test_current_iat_accepted(self, monkeypatch):
        """A token issued right now (iat ≈ now) must be accepted."""
        secret = "a" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)
        token = self._make_token(secret, iat_offset_seconds=0)
        payload = decode_token(token, expected_type="access")
        assert payload["sub"] is not None

    def test_slightly_past_iat_accepted(self, monkeypatch):
        """A token issued 10 s ago (iat slightly in the past) must be accepted."""
        secret = "a" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)
        token = self._make_token(secret, iat_offset_seconds=-10)
        payload = decode_token(token, expected_type="access")
        assert payload["sub"] is not None

    def test_iat_within_skew_accepted(self, monkeypatch):
        """A token with iat 20 s in the future is within the 30 s skew — accepted."""
        secret = "a" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)
        token = self._make_token(secret, iat_offset_seconds=20)
        payload = decode_token(token, expected_type="access")
        assert payload["sub"] is not None

    def test_iat_at_skew_boundary_accepted(self, monkeypatch):
        """A token with iat exactly at the skew boundary (30 s ahead) — accepted."""
        secret = "a" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)
        token = self._make_token(secret, iat_offset_seconds=30)
        payload = decode_token(token, expected_type="access")
        assert payload["sub"] is not None

    def test_iat_beyond_skew_rejected(self, monkeypatch):
        """A token with iat 60 s in the future exceeds the 30 s skew — rejected."""
        secret = "a" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)
        token = self._make_token(secret, iat_offset_seconds=60)
        with pytest.raises(jwt.InvalidTokenError, match="future"):
            decode_token(token, expected_type="access")

    def test_iat_far_future_rejected(self, monkeypatch):
        """A token with iat 1 hour in the future must be rejected."""
        secret = "a" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)
        token = self._make_token(secret, iat_offset_seconds=3600)
        with pytest.raises(jwt.InvalidTokenError, match="future"):
            decode_token(token, expected_type="access")

    def test_missing_iat_rejected(self, monkeypatch):
        """A token without an iat claim must be rejected (required claim)."""
        secret = "a" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "role": "user",
                "type": "access",
                # iat deliberately omitted
                "exp": int((now + timedelta(minutes=15)).timestamp()),
            },
            secret,
            algorithm="HS256",
        )
        with pytest.raises(jwt.MissingRequiredClaimError):
            decode_token(token, expected_type="access")

    def test_boolean_iat_rejected(self, monkeypatch):
        """A token with iat=True (bool) must be rejected — bool is a subtype of int.

        Python's json.loads parses JSON true as Python True (a bool).  Since
        bool is a subclass of int, PyJWT's numeric check accepts it; our explicit
        isinstance(iat, bool) guard in decode_token() rejects it.

        We craft the JWT manually so that the payload literally contains
        JSON ``true`` for the ``iat`` field, bypassing jwt.encode() which would
        serialise True as the integer 1.
        """
        import base64
        import hmac as _hmac
        import json as _json

        secret = "a" * 32
        monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)
        now = datetime.now(timezone.utc)

        # Build header + payload bytes that contain "iat": true (JSON boolean).
        header_bytes = _json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
        body_data = {
            "sub": str(uuid.uuid4()),
            "role": "user",
            "type": "access",
            "iat": True,   # JSON true → Python True after json.loads
            "exp": int((now + timedelta(minutes=15)).timestamp()),
        }
        body_bytes = _json.dumps(body_data, separators=(",", ":")).encode()

        header_b64 = base64.urlsafe_b64encode(header_bytes).rstrip(b"=").decode()
        body_b64 = base64.urlsafe_b64encode(body_bytes).rstrip(b"=").decode()

        signing_input = f"{header_b64}.{body_b64}".encode()
        sig = _hmac.new(secret.encode(), signing_input, "sha256").digest()
        sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()

        token = f"{header_b64}.{body_b64}.{sig_b64}"
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(token, expected_type="access")

