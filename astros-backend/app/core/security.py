"""
app/core/security.py
====================
Cryptographic utilities for password hashing and JWT token management (Phase 5B.3).

Security Guarantees:
- Passwords are exclusively hashed using Argon2id with RFC 9106 parameters.
- Plaintext passwords and raw tokens are never logged or stored.
- JWT decoding strictly enforces the configured signing algorithm (algorithms=[JWT_ALGORITHM])
  to eliminate algorithm-confusion attacks.
- Tokens enforce required claims ('sub', 'exp', 'iat', 'type') and distinguish
  access tokens from refresh tokens.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
import jwt

from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
)

# ---------------------------------------------------------------------------
# Argon2id Password Hasher (RFC 9106 recommended profile)
# ---------------------------------------------------------------------------
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id.

    Raises:
        ValueError: If password is empty, not a string, or outside valid length bounds.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )

    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters."
        )

    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash.

    Returns False safely on mismatch, malformed hash, or non-string inputs.
    Never raises an uncaught hashing exception.
    """
    if not isinstance(plain_password, str) or not isinstance(hashed_password, str):
        return False

    if not plain_password or not hashed_password:
        return False

    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


# ---------------------------------------------------------------------------
# JWT Access and Refresh Token Utilities
# ---------------------------------------------------------------------------
def create_access_token(
    subject: str | uuid.UUID,
    role: str = "user",
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Generate a signed JWT access token.

    Claims:
        sub (str): User identifier (UUID string).
        role (str): User role ('user', 'admin', 'service').
        type (str): Token type ('access').
        iat (datetime): Issued-at timestamp (UTC).
        exp (datetime): Expiration timestamp (UTC).
    """
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not configured.")

    now = datetime.now(timezone.utc)
    lifetime = expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + lifetime

    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    if extra_claims:
        # Do not allow overriding reserved claims
        reserved = {"sub", "type", "iat", "exp"}
        for key, value in extra_claims.items():
            if key not in reserved:
                payload[key] = value

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# IAT clock-skew allowance
#
# IAT_CLOCK_SKEW_SECONDS controls the tolerance for tokens whose ``iat`` claim
# is slightly in the future (e.g. due to minor clock differences between
# servers).
#
# 30 seconds is deliberately small:
# - It accommodates typical NTP drift between distributed services.
# - Tokens issued more than 30 s in the future are unambiguously invalid and
#   are rejected here rather than silently accepted.
#
# NOTE: PyJWT's ``verify_iat`` option only checks that the claim is numeric;
# it does NOT reject future-dated ``iat`` values.  The post-decode check in
# decode_token() closes that gap.
# ---------------------------------------------------------------------------
IAT_CLOCK_SKEW_SECONDS: int = 30


def decode_token(
    token: str,
    expected_type: str = "access",
) -> dict[str, Any]:
    """Verify and decode a JWT token.

    Enforces:
    - Algorithm strictly matches JWT_ALGORITHM (rejects untrusted headers).
    - Signature validity.
    - Expiration time.
    - Presence of required claims: sub, exp, iat, type.
    - Token type matches expected_type.
    - ``iat`` is a finite integer and is not significantly in the future
      (tolerance: ``IAT_CLOCK_SKEW_SECONDS``).

    Raises:
        jwt.PyJWTError: On invalid signature, expired token, or claim mismatch.
        jwt.InvalidTokenError: On wrong token type or future-dated ``iat``.
    """
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not configured.")

    payload = jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        options={
            "require": ["sub", "exp", "iat", "type"],
            "verify_exp": True,
            # Disabled built-in verify_iat so we can apply our configured clock-skew tolerance
            "verify_iat": False,
        },
    )

    token_type = payload.get("type")
    if token_type != expected_type:
        raise jwt.InvalidTokenError(
            f"Invalid token type: expected '{expected_type}', got '{token_type}'"
        )

    # Explicit future-iat check with clock skew allowance.
    # PyJWT guarantees `iat` is present (via `require`), but a boolean satisfies
    # `isinstance(x, int)` in Python, so we must exclude booleans explicitly.
    iat = payload.get("iat")
    if isinstance(iat, bool) or not isinstance(iat, (int, float)):
        raise jwt.InvalidTokenError("Token 'iat' claim is not a valid numeric timestamp.")

    now_ts = datetime.now(timezone.utc).timestamp()
    if iat > now_ts + IAT_CLOCK_SKEW_SECONDS:
        raise jwt.InvalidTokenError(
            "Token 'iat' claim is in the future; token is not yet valid."
        )

    return payload


# ---------------------------------------------------------------------------
# Refresh Token Secret Material
# ---------------------------------------------------------------------------
def generate_refresh_token_pair() -> tuple[str, str]:
    """Generate an opaque high-entropy refresh token and its SHA-256 hash.

    Returns:
        tuple[str, str]: (raw_refresh_token, sha256_token_hash)
        The raw token is delivered to the client; ONLY the hash is persisted.
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash

