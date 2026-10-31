
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.deps import get_authenticated_principal
from app.db.session import get_db
from app.models.user import User
from app.services.database_recommendation_service import (
    get_database_recommendations,
)

router = APIRouter(
    prefix="/api/v1/recommendations",
    tags=["Database Recommendations"],
)


class DatabaseRecommendationRequest(BaseModel):
    location: dict[str, Any]
    start_time: datetime
    end_time: datetime
    available_duration_minutes: int = Field(gt=0, le=1440)
    observation_goal: str = "general_observation"
    preferences: dict[str, Any] = Field(default_factory=dict)
    category: str | None = None

    @model_validator(mode="after")
    def validate_session(self):
        for field_name in ("start_time", "end_time"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(
                    f"{field_name} must include a timezone offset."
                )

        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time.")

        if not self.location:
            raise ValueError("location must not be empty.")

        return self


@router.post("/from-database")
def recommend_from_database(
    request: DatabaseRecommendationRequest,
    db: Session = Depends(get_db),
    current_caller: User = Depends(get_authenticated_principal),
):
    session = {
        "location": request.location,
        "start_time": request.start_time.isoformat(),
        "end_time": request.end_time.isoformat(),
        "available_duration_minutes": (
            request.available_duration_minutes
        ),
    }

    try:
        return get_database_recommendations(
            db=db,
            session=session,
            observation_goal=request.observation_goal,
            preferences=request.preferences,
            category=request.category,
        )
    except OperationalError as exc:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service temporarily unavailable",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
