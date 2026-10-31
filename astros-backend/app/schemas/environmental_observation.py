
from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal
from app.services.environmental_freshness import FreshnessStatus

class EnvironmentalObservationCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    observed_at: datetime

    temperature_celsius: float | None = None
    humidity: float | None = Field(default=None, ge=0, le=100)
    cloud_cover: float | None = Field(default=None, ge=0, le=100)

    conditions: str | None = Field(default=None, max_length=100)
    additional_data: dict = Field(default_factory=dict)

    source: str = Field(min_length=1, max_length=150)
    expires_at: datetime | None = None

    @field_validator("observed_at", "expires_at")
    @classmethod
    def require_timezone(cls, value):
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("Timestamp must include a timezone")
        return value


class EnvironmentalObservationResponse(EnvironmentalObservationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recorded_at: datetime


class EnvironmentalObservationWithFreshnessResponse(
    EnvironmentalObservationResponse
):
    """Environmental observation with an explicit freshness status."""

    freshness_status: FreshnessStatus