import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VisibilityAssessment(Base):
    __tablename__ = "visibility_assessments"

    __table_args__ = (
        CheckConstraint(
            "visibility_score >= 0 AND visibility_score <= 100",
            name="ck_visibility_assessments_score_range",
        ),
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="ck_visibility_assessments_latitude_range",
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="ck_visibility_assessments_longitude_range",
        ),
        CheckConstraint(
            "viewing_window_end > viewing_window_start",
            name="ck_visibility_assessments_window_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("celestial_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    visibility_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    quality_label: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    viewing_window_start: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    viewing_window_end: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    factors: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    limitations: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    assessed_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    expires_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
