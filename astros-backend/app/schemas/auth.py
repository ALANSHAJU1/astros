"""
app/schemas/auth.py
===================
Pydantic v2 validation schemas for authentication and authorization (Phase 5B.3).

Security Constraints:
- 'role' is never accepted as an input field on public registration schemas.
- 'hashed_password' is never included in any API response model.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegister(BaseModel):
    """Schema for public user registration."""

    email: str = Field(..., max_length=255, description="User email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plaintext password (hashed via Argon2id before storage)",
    )
    full_name: str | None = Field(
        default=None,
        max_length=255,
        description="Optional full name or display name",
    )

    @field_validator("email")
    @classmethod
    def validate_and_normalize_email(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Email cannot be blank.")
        normalized = v.strip().lower()
        if "@" not in normalized or "." not in normalized.split("@")[-1]:
            raise ValueError("Invalid email format.")
        return normalized


class UserLogin(BaseModel):
    """Schema for user credentials login."""

    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower() if v else v


class TokenResponse(BaseModel):
    """Standard OAuth 2.0-compliant token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class TokenRefreshRequest(BaseModel):
    """Payload for rotating refresh token."""

    refresh_token: str = Field(..., min_length=16, description="Opaque refresh token")


class UserProfile(BaseModel):
    """Public/authenticated safe profile of the user (never includes password hashes)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime

