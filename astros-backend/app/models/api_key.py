"""
app/models/api_key.py
=====================
SQLAlchemy model for AstroOS API keys and service credentials.

Design & Security Architecture:
-------------------------------
- API keys provide authenticated programmatic access for automated agents,
  CLI tools, and background ingestion services.
- Secret Storage: Only a cryptographic hash (SHA-256) of the key is stored
  in ``key_hash``. The plaintext key is NEVER stored or retrievable.
- Key Identification: A non-secret ``key_prefix`` (e.g., 'ast_live_a1b2') is
  stored for identification in logs, audits, and user interfaces.
- Lifecycle: Keys support explicit revocation via ``is_active`` and optional
  time-based expiration via ``expires_at``.
- Role & Privilege Boundary: Service credentials must be associated with an
  explicit service user (e.g. role='service') and must NOT inherit administrator
  privileges merely because they authenticate via an API key.
"""

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    key_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    key_prefix: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="api_keys",
    )

    def __repr__(self) -> str:
        return (
            f"<ApiKey id={self.id} prefix={self.key_prefix!r} "
            f"name={self.name!r} is_active={self.is_active}>"
        )

