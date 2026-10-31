
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class LocationInput(BaseModel):
    name: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = "Asia/Kolkata"


class RecommendationSession(BaseModel):
    location: LocationInput
    start_time: datetime
    end_time: datetime
    available_duration_minutes: int = Field(gt=0)
    observation_goal: str = "general_stargazing"

    
    @model_validator(mode="after")
    def validate_session_window(self):
        if (
            self.start_time.tzinfo is None
            or self.start_time.utcoffset() is None
        ):
            raise ValueError(
                "start_time must include a timezone offset, "
                "for example +05:30."
            )

        if (
            self.end_time.tzinfo is None
            or self.end_time.utcoffset() is None
        ):
            raise ValueError(
                "end_time must include a timezone offset, "
                "for example +05:30."
            )

        if self.end_time <= self.start_time:
            raise ValueError(
                "end_time must be later than start_time."
            )

        return self




class CandidateEvent(BaseModel):
    event_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    event_type: str
    window_start: datetime
    window_end: datetime
    required_duration_minutes: int = Field(gt=0)
    visibility_score: float = Field(ge=0, le=100)
    weather_score: float = Field(ge=0, le=100)
    preference_score: float = Field(ge=0, le=100)
    source: str = "demo_fixture"

    @model_validator(mode="after")
    def validate_event_window(self):
        # Validate timezone awareness before comparing timestamps.
        if (
            self.window_start.tzinfo is None
            or self.window_start.utcoffset() is None
        ):
            raise ValueError(
                "window_start must include a timezone offset, "
                "for example +05:30."
            )

        if (
            self.window_end.tzinfo is None
            or self.window_end.utcoffset() is None
        ):
            raise ValueError(
                "window_end must include a timezone offset, "
                "for example +05:30."
            )

        if self.window_end <= self.window_start:
            raise ValueError(
                "window_end must be later than window_start."
            )

        return self


class RecommendationRequest(BaseModel):
    session: RecommendationSession
    events: list[CandidateEvent]


class RankedEvent(BaseModel):
    event_id: str
    rank: int
    name: str
    recommendation_score: float
    score_breakdown: dict[str, float]


class ScheduledEvent(BaseModel):
    event_id: str
    rank: int
    name: str
    scheduled_start: datetime
    scheduled_end: datetime
    duration_minutes: int
    recommendation_score: float
    explanation: str


class RecommendationSummary(BaseModel):
    targets_evaluated: int
    targets_scheduled: int
    targets_skipped: int
    scheduled_duration_minutes: int
    remaining_duration_minutes: int


class RecommendationResult(BaseModel):
    ranked_events: list[RankedEvent]
    schedule: list[ScheduledEvent]
    skipped_events: list[dict]
    summary: RecommendationSummary
    explanation_mode: Literal["deterministic"] = "deterministic"
    data_quality: dict
