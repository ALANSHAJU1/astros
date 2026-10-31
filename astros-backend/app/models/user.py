"""
app/models/user.py
==================
SQLAlchemy model for AstroOS user accounts.

Security and Access Control Policies:
- Public user registration defaults strictly to the 'user' role.
- Administrative capabilities require the 'admin' role.
- Background ingestion services and programmatic agents use the 'service' role.
- Passwords must be hashed with Argon2id prior to model assignment; plaintext
  passwords must never be stored.
- Email addresses are automatically normalized (stripped and lowercased).
"""

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.api_key import ApiKey
    from app.models.refresh_token import RefreshToken


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'admin', 'service')",
            name="ck_users_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="user",
        server_default="user",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    api_keys: Mapped[list["ApiKey"]] = relationship(
        "ApiKey",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("email")
    def validate_email(self, key: str, address: str) -> str:
        """Normalize email address to lowercase and trimmed string."""
        if not address or not isinstance(address, str):
            raise ValueError("Email must be a non-empty string.")
        normalized = address.strip().lower()
        if not normalized:
            raise ValueError("Email cannot be blank.")
        return normalized

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r} is_active={self.is_active}>"

