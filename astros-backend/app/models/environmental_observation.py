
import uuid

from sqlalchemy import CheckConstraint, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EnvironmentalObservation(Base):
    __tablename__ = "environmental_observations"

    __table_args__ = (
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="ck_environmental_observations_latitude_range",
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="ck_environmental_observations_longitude_range",
        ),
        CheckConstraint(
            "cloud_cover IS NULL OR (cloud_cover >= 0 AND cloud_cover <= 100)",
            name="ck_environmental_observations_cloud_cover_range",
        ),
        CheckConstraint(
            "humidity IS NULL OR (humidity >= 0 AND humidity <= 100)",
            name="ck_environmental_observations_humidity_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    observed_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    temperature_celsius: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    humidity: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    cloud_cover: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    conditions: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Additional provider-specific measurements can be stored here.
    additional_data: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    # When the observation was collected by our backend.
    recorded_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Optional expiry for freshness checks.
    expires_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
