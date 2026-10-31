
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from pydantic import BaseModel, Field, model_validator

from app.api.deps import get_authenticated_principal, require_admin_or_service
from app.db.session import get_db
from app.models.user import User
from app.repositories.environmental_observation_repository import (
    create_observation,
    get_observation_by_id,
    get_observations_for_location,
    get_latest_observation_for_location,
)
from app.schemas.environmental_observation import (
    EnvironmentalObservationCreate,
    EnvironmentalObservationResponse,
    EnvironmentalObservationWithFreshnessResponse,
)
from app.services.environmental_freshness import classify_observation_freshness
from app.services.environmental_service import (
    EnvironmentalService,
    classify_forecast_freshness,
)
from app.services.weather_provider import (
    WeatherProviderError,
    WeatherProviderTimeoutError,
)

router = APIRouter(
    prefix="/api/v1/environmental-observations",
    tags=["Environmental Observations"],
)


class ForecastFetchRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    start_time: datetime
    end_time: datetime
    force_refresh: bool = False
    persist: bool = True

    @model_validator(mode="after")
    def validate_window(self):
        if self.start_time.tzinfo is None or self.start_time.utcoffset() is None:
            raise ValueError("start_time must include a timezone")
        if self.end_time.tzinfo is None or self.end_time.utcoffset() is None:
            raise ValueError("end_time must include a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


@router.post(
    "/forecast",
    response_model=list[EnvironmentalObservationWithFreshnessResponse],
    status_code=status.HTTP_200_OK,
)
def fetch_and_persist_forecast(
    payload: ForecastFetchRequest,
    db: Session = Depends(get_db),
    current_caller: User = Depends(require_admin_or_service),
):
    service = EnvironmentalService()
    try:
        observations = service.get_or_fetch_forecast_observations(
            db=db,
            latitude=payload.latitude,
            longitude=payload.longitude,
            start_time=payload.start_time,
            end_time=payload.end_time,
            force_refresh=payload.force_refresh,
            persist=payload.persist,
        )
        if payload.persist:
            db.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except WeatherProviderTimeoutError as exc:
        if payload.persist:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Weather provider timed out while retrieving forecast.",
        ) from exc
    except WeatherProviderError as exc:
        if payload.persist:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Weather provider service temporarily unavailable or returned an error.",
        ) from exc
    except Exception as exc:
        if payload.persist:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving forecast.",
        ) from exc

    return [
        {
            "id": obs.id,
            "latitude": obs.latitude,
            "longitude": obs.longitude,
            "observed_at": obs.observed_at,
            "temperature_celsius": obs.temperature_celsius,
            "humidity": obs.humidity,
            "cloud_cover": obs.cloud_cover,
            "conditions": obs.conditions,
            "additional_data": obs.additional_data,
            "source": obs.source,
            "recorded_at": obs.recorded_at,
            "expires_at": obs.expires_at,
            "freshness_status": classify_forecast_freshness(obs),
        }
        for obs in observations
    ]



@router.post(
    "",
    response_model=EnvironmentalObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_environmental_observation(
    payload: EnvironmentalObservationCreate,
    db: Session = Depends(get_db),
    current_caller: User = Depends(require_admin_or_service),
):
    if payload.expires_at is not None:
        if payload.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="expires_at must be in the future.",
            )

    observation = create_observation(db, payload)

    try:
        db.commit()
        db.refresh(observation)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save environmental observation.",
        )

    return observation






@router.get(
    "/by-location",
    response_model=list[EnvironmentalObservationWithFreshnessResponse],
)
def read_observations_for_location(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    start_time: datetime = Query(),
    end_time: datetime = Query(),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_caller: User = Depends(get_authenticated_principal),
):
    if start_time.tzinfo is None or start_time.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_time must include a timezone.",
        )

    if end_time.tzinfo is None or end_time.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must include a timezone.",
        )

    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must be after start_time.",
        )

    observations = get_observations_for_location(
        db=db,
        latitude=latitude,
        longitude=longitude,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )

    return [
        {
            "id": observation.id,
            "latitude": observation.latitude,
            "longitude": observation.longitude,
            "observed_at": observation.observed_at,
            "temperature_celsius": observation.temperature_celsius,
            "humidity": observation.humidity,
            "cloud_cover": observation.cloud_cover,
            "conditions": observation.conditions,
            "additional_data": observation.additional_data,
            "source": observation.source,
            "recorded_at": observation.recorded_at,
            "expires_at": observation.expires_at,
            "freshness_status": classify_observation_freshness(
                observation
            ),
        }
        for observation in observations
    ]


@router.get(
    "/latest/by-location",
    response_model=EnvironmentalObservationWithFreshnessResponse,
)
def read_latest_observation_for_location(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    db: Session = Depends(get_db),
    current_caller: User = Depends(get_authenticated_principal),
):
    observation = get_latest_observation_for_location(
        db=db,
        latitude=latitude,
        longitude=longitude,
    )

    if observation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No environmental observations found for this location.",
        )

    response = {
        "id": observation.id,
        "latitude": observation.latitude,
        "longitude": observation.longitude,
        "observed_at": observation.observed_at,
        "temperature_celsius": observation.temperature_celsius,
        "humidity": observation.humidity,
        "cloud_cover": observation.cloud_cover,
        "conditions": observation.conditions,
        "additional_data": observation.additional_data,
        "source": observation.source,
        "recorded_at": observation.recorded_at,
        "expires_at": observation.expires_at,
        "freshness_status": classify_observation_freshness(
            observation
        ),
    }

    return response



@router.get(
    "/{observation_id}",
    response_model=EnvironmentalObservationResponse,
)
def read_environmental_observation(
    observation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_caller: User = Depends(get_authenticated_principal),
):
    observation = get_observation_by_id(db, observation_id)

    if observation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Environmental observation not found.",
        )

    return observation