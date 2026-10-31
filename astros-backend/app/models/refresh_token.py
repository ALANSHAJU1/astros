"""
app/models/refresh_token.py
===========================
SQLAlchemy model for AstroOS user refresh tokens (Phase 5B.3).

Security Architecture:
- Never persists raw tokens; only stores SHA-256 hex digests (token_hash).
- Grouped by `family_id` to trace token lineage across rotation.
- Replayed tokens (already revoked) trigger immediate family-wide invalidation.
- Retains revoked records for replay detection instead of immediately deleting them.
"""

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

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

    # SHA-256 hexadecimal digest (64 chars) of the raw token.
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    # Unique family UUID tracking token lineage across rotations.
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Relationship to user
    user: Mapped["User"] = relationship(
        "User",
        back_populates="refresh_tokens",
    )

    def __repr__(self) -> str:
        return (
            f"<RefreshToken id={self.id} user_id={self.user_id} "
            f"family_id={self.family_id} revoked={self.revoked_at is not None}>"
        )

