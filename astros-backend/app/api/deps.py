"""
app/api/deps.py
===============
Reusable FastAPI dependencies for AstroOS API endpoints (Phases 5B.3 & 5B.4).

Authentication & Authorization Architecture
-------------------------------------------
1. `get_current_user`:
   - Validates Bearer JWT access tokens exclusively.
   - Rejects missing, invalid, expired, non-access tokens, or inactive/missing users with HTTP 401.
   - Does NOT accept API keys.

2. `get_current_service`:
   - Validates service credentials provided in `X-API-Key`.
   - Hashes submitted key using SHA-256 and retrieves the `ApiKey` record.
   - Enforces key active status and expiration timestamp.
   - Requires the associated owner user to have `role="service"` and `is_active=True`.
   - Rejects ordinary user or admin API keys with HTTP 401.

3. `get_authenticated_principal`:
   - Resolves caller identity from either a Bearer JWT access token or an `X-API-Key`.
   - Ambiguity Policy: If both credentials are supplied, rejects with HTTP 400 Bad Request
     to prevent confusing identity context or silent credential fallback.
   - Returns the authenticated `User` object.

4. Role Authorization (`require_roles`, `require_admin`, `require_admin_or_service`):
   - Authenticates the principal before role validation.
   - Returns HTTP 401 on missing or invalid authentication.
   - Returns HTTP 403 on valid authentication with insufficient role privileges.
   - A service principal is never granted admin permissions.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import uuid as _uuid

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.user import User

# HTTPBearer extracts Authorization: Bearer <token>
http_bearer = HTTPBearer(auto_error=False)

# APIKeyHeader extracts X-API-Key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Valid roles defined in User model CheckConstraint ("ck_users_role")
VALID_ROLES = frozenset({"user", "admin", "service"})


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Validate bearer access token and return the authenticated active User.

    Raises:
        HTTPException(401): On missing credentials, invalid signature, expired token,
                            wrong token type, nonexistent user, or inactive account.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = credentials.credentials

    try:
        payload = decode_token(raw_token, expected_type="access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Parse `sub` as a strict UUID before querying the database.
    try:
        user_id = _uuid.UUID(subject)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: malformed subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = db.query(User).filter(User.id == user_id).first()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_service(
    api_key: str | None = Security(api_key_header),
    db: Session = Depends(get_db),
) -> User:
    """Validate X-API-Key service credential and return the associated service User.

    Security Guarantees:
    - Never logs or exposes the raw API key.
    - Hashes key using SHA-256 before database lookup.
    - Constant-time comparison between stored and computed hash.
    - Requires active key and non-expired timestamp.
    - Resolves owner User and strictly enforces `role == 'service'` and `is_active == True`.
    - Rejects ordinary user or admin API keys with HTTP 401.

    Raises:
        HTTPException(401): On missing, invalid, revoked, expired, or non-service keys.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key was not provided",
        )

    computed_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    try:
        key_record = db.query(ApiKey).filter(ApiKey.key_hash == computed_hash).first()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate API key",
        )

    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Constant-time comparison verification
    if not hmac.compare_digest(key_record.key_hash, computed_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Key active check
    if not key_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has been revoked",
        )

    # Key expiration check
    if key_record.expires_at is not None:
        now = datetime.now(timezone.utc)
        # Normalize timezone if needed
        key_exp = key_record.expires_at
        if key_exp.tzinfo is None:
            key_exp = key_exp.replace(tzinfo=timezone.utc)
        if key_exp <= now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired",
            )

    # Resolve associated user
    user = key_record.user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key owner not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key owner account is inactive",
        )

    # Enforce service role requirement: ordinary user or admin keys cannot act as service credentials
    if user.role != "service":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key does not have service credentials",
        )

    return user


def get_authenticated_principal(
    bearer_creds: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    api_key: str | None = Security(api_key_header),
    db: Session = Depends(get_db),
) -> User:
    """Resolve authenticated caller from either Bearer JWT or service API key.

    Ambiguity Policy:
    If both Bearer token and X-API-Key are supplied in the same request, the request
    is rejected with HTTP 400 Bad Request to prevent conflicting identities or silent fallback.

    Returns:
        User: The authenticated active User principal.

    Raises:
        HTTPException(400): If both credential types are provided simultaneously.
        HTTPException(401): If neither credential is provided or if the provided credential is invalid.
    """
    has_bearer = bool(bearer_creds and bearer_creds.credentials)
    has_api_key = bool(api_key)

    if has_bearer and has_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ambiguous authentication: provide either Bearer token or X-API-Key, not both",
        )

    if has_bearer:
        return get_current_user(credentials=bearer_creds, db=db)

    if has_api_key:
        return get_current_service(api_key=api_key, db=db)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials were not provided",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_roles(*allowed_roles: str):
    """Factory creating a dependency that enforces specified role membership.

    Enforces that:
    - Principal is authenticated first (via get_authenticated_principal).
    - Invalid/missing credentials raise HTTP 401.
    - Authenticated users with roles not in allowed_roles receive HTTP 403.
    """
    # Verify allowed_roles against valid schema roles
    invalid = set(allowed_roles) - VALID_ROLES
    if invalid:
        raise ValueError(f"Invalid roles in requirement: {invalid}. Must be in {VALID_ROLES}")

    def role_dependency(principal: User = Depends(get_authenticated_principal)) -> User:
        if principal.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {', '.join(allowed_roles)}.",
            )
        return principal

    return role_dependency


# Specific role dependencies for business and administration operations
require_admin = require_roles("admin")
require_admin_or_service = require_roles("admin", "service")


