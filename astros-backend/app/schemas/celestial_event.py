from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic import model_validator




class CelestialEventCreate(BaseModel):
    external_event_id: str | None = Field(
        default=None, max_length=150
    )
    category: str = Field(min_length=1, max_length=50)
    object_name: str = Field(min_length=1, max_length=150)
    event_type: str = Field(min_length=1, max_length=100)
    start_time: datetime
    end_time: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    additional_data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_event_dates(self):
        if (
            self.end_time is not None
            and self.end_time < self.start_time
        ):
            raise ValueError(
                "end_time must be after start_time"
            )
        return self


class CelestialEventUpdate(BaseModel):
    """Fields that can be updated on an existing event."""

    external_event_id: str | None = Field(
        default=None, max_length=150
    )
    category: str | None = Field(
        default=None, min_length=1, max_length=50
    )
    object_name: str | None = Field(
        default=None, min_length=1, max_length=150
    )
    event_type: str | None = Field(
        default=None, min_length=1, max_length=100
    )
    start_time: datetime | None = None
    end_time: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    additional_data: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_event_dates(self):
        # Validate when both dates are provided in this PATCH.
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time < self.start_time
        ):
            raise ValueError(
                "end_time must be after start_time"
            )
        return self




class CelestialEventRead(CelestialEventCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime

