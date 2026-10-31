"""
app/api/routes/auth.py
======================
FastAPI endpoints for authentication, registration, token refresh, and profile (Phase 5B.3).

Security Principles:
- Public registration strictly enforces role="user" on the server.
- Passwords hashed with Argon2id; hashes never returned in API responses.
- Refresh tokens are rotated on each use with strict replay detection.
- Replayed tokens trigger immediate family-wide cascade revocation.
- Concurrency-safe rotation using SELECT ... FOR UPDATE.
- Generic error messages for failed authentication to prevent account enumeration.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ENABLE_PUBLIC_REGISTRATION,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.core.security import (
    create_access_token,
    generate_refresh_token_pair,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    TokenRefreshRequest,
    TokenResponse,
    UserLogin,
    UserProfile,
    UserRegister,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# POST /register
# ---------------------------------------------------------------------------
@router.post(
    "/register",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    payload: UserRegister,
    db: Session = Depends(get_db),
):
    """Register a new user account with role='user'.

    Guarantees:
    - Rejects registration when ENABLE_PUBLIC_REGISTRATION=false.
    - Public requests cannot assign themselves 'admin' or 'service' roles.
    - Normalized email uniqueness enforced with HTTP 409 Conflict.
    - Password is hashed with Argon2id before storage; hash is never returned.
    """
    if not ENABLE_PUBLIC_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is currently disabled.",
        )

    normalized_email = payload.email.strip().lower()

    # Pre-check existing user
    existing_user = (
        db.query(User).filter(User.email == normalized_email).first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists.",
        )

    # Hash password via Argon2id
    hashed = hash_password(payload.password)

    # Construct user — strictly enforce role="user"
    user = User(
        email=normalized_email,
        hashed_password=hashed,
        full_name=payload.full_name,
        role="user",
        is_active=True,
    )

    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists.",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to a database error.",
        )

    return user


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------
@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and obtain tokens",
)
def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
):
    """Authenticate user with email and password.

    Returns:
    - Short-lived JWT access token
    - Opaque refresh token (persisting only its SHA-256 hash in a new family)
    """
    normalized_email = payload.email.strip().lower()

    user = db.query(User).filter(User.email == normalized_email).first()

    # Generic authentication error message to prevent account enumeration
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create new refresh token family for this session/login
    family_id = uuid.uuid4()
    raw_refresh, token_hash = generate_refresh_token_pair()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        family_id=family_id,
        expires_at=expires_at,
    )

    db.add(refresh_record)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize session.",
        )

    access_token = create_access_token(subject=user.id, role=user.role)

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------
@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue new access token",
)
def refresh_token_endpoint(
    payload: TokenRefreshRequest,
    db: Session = Depends(get_db),
):
    """Rotate an opaque refresh token.

    Security Lifecycle:
    - Locks row using SELECT ... FOR UPDATE to handle concurrent requests.
    - If token is already revoked (replayed): cascades revocation to the ENTIRE family.
    - Replaces old token with new token in the same family within an atomic transaction.
    """
    submitted_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()

    try:
        # Acquire row-level lock
        record = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == submitted_hash)
            .with_for_update()
            .first()
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error during token refresh.",
        )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unrecognized refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    now = datetime.now(timezone.utc)

    # 1. REPLAY DETECTION: Token was already rotated or revoked!
    if record.revoked_at is not None:
        # Invalidate the entire family immediately to protect the compromised user
        try:
            db.query(RefreshToken).filter(
                RefreshToken.family_id == record.family_id,
                RefreshToken.revoked_at.is_(None),
            ).update(
                {"revoked_at": now},
                synchronize_session=False,
            )
            db.commit()
        except SQLAlchemyError:
            db.rollback()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has already been rotated. Invalidation triggered.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. EXPIRATION CHECK
    if record.expires_at <= now:
        record.revoked_at = now
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. USER ACTIVE CHECK
    user = db.query(User).filter(User.id == record.user_id).first()
    if not user or not user.is_active:
        record.revoked_at = now
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. ATOMIC ROTATION
    new_raw_refresh, new_token_hash = generate_refresh_token_pair()
    new_expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # Revoke current token
    record.revoked_at = now

    # Issue replacement in same family
    new_record = RefreshToken(
        user_id=user.id,
        token_hash=new_token_hash,
        family_id=record.family_id,
        expires_at=new_expires_at,
    )

    db.add(new_record)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to commit rotated refresh token.",
        )

    new_access_token = create_access_token(subject=user.id, role=user.role)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_raw_refresh,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ---------------------------------------------------------------------------
# POST /logout
# ---------------------------------------------------------------------------
@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Revoke refresh token and end session",
)
def logout(
    payload: TokenRefreshRequest,
    db: Session = Depends(get_db),
):
    """Revoke the presented refresh token and end the session.

    After this call:
    - The submitted refresh token is marked as revoked in the database.
    - Any subsequent attempt to use this refresh token will be rejected with 401.
    - Tokens in a different family (other active sessions) are unaffected.

    Access-token behavior after logout
    ------------------------------------
    This endpoint does NOT immediately invalidate any access token that was
    previously issued for this session.  Access tokens are stateless JWTs;
    their validity is determined solely by their cryptographic signature and
    ``exp`` claim without a per-request database lookup.

    An access token held by the client at logout time will continue to be
    accepted by protected endpoints until the token's ``exp`` elapses
    (configured via ACCESS_TOKEN_EXPIRE_MINUTES).  This is the accepted
    trade-off of stateless JWT authentication.  Mitigate by configuring a
    short access-token lifetime.

    This design intentionally avoids a server-side token blocklist to preserve
    the stateless properties and avoid per-request database overhead.

    Safe to call repeatedly — idempotent for an already-revoked token.
    """
    submitted_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()

    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == submitted_hash)
        .first()
    )

    if record and record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()

    return {"message": "Successfully logged out."}


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------
@router.get(
    "/me",
    response_model=UserProfile,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's safe profile.

    Guarantees:
    - Never includes hashed_password or sensitive tokens.
    """
    return current_user

