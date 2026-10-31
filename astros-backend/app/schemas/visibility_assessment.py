import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VisibilityAssessmentBase(BaseModel):
    event_id: uuid.UUID

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    visibility_score: float = Field(ge=0, le=100)
    quality_label: str = Field(min_length=1, max_length=50)

    viewing_window_start: datetime
    viewing_window_end: datetime

    factors: dict = Field(default_factory=dict)
    limitations: list = Field(default_factory=list)

    source: str = Field(min_length=1, max_length=150)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_viewing_window(self):
        start = self.viewing_window_start
        end = self.viewing_window_end

        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("viewing_window_start must include a timezone")

        if end.tzinfo is None or end.utcoffset() is None:
            raise ValueError("viewing_window_end must include a timezone")

        if end <= start:
            raise ValueError(
                "viewing_window_end must be after viewing_window_start"
            )

        if self.expires_at is not None:
            if (
                self.expires_at.tzinfo is None
                or self.expires_at.utcoffset() is None
            ):
                raise ValueError("expires_at must include a timezone")

        return self


class VisibilityAssessmentCreate(VisibilityAssessmentBase):
    pass


class VisibilityAssessmentResponse(VisibilityAssessmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessed_at: datetime
    created_at: datetime


class VisibilityAssessmentCalculateRequest(BaseModel):
    event_id: uuid.UUID
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    viewing_window_start: datetime | None = None
    viewing_window_end: datetime | None = None
    persist: bool = True

    @model_validator(mode="after")
    def validate_window(self):
        start = self.viewing_window_start
        end = self.viewing_window_end
        if start is not None and (start.tzinfo is None or start.utcoffset() is None):
            raise ValueError("viewing_window_start must include a timezone")
        if end is not None and (end.tzinfo is None or end.utcoffset() is None):
            raise ValueError("viewing_window_end must include a timezone")
        if start is not None and end is not None and end <= start:
            raise ValueError("viewing_window_end must be after viewing_window_start")
        return self


class VisibilityAssessmentCalculateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    event_id: uuid.UUID
    status: str
    visibility_score: float
    environmental_score: float | None = None
    astronomical_score: float | None = None
    quality_label: str
    decision: str
    viewing_window_start: datetime
    viewing_window_end: datetime
    factors: dict = Field(default_factory=dict)
    limitations: list = Field(default_factory=list)
    source: str
    assessed_at: datetime
    light_pollution: dict = Field(default_factory=dict)
    confidence: str
    is_persisted: bool = False

