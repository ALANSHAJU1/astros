
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_authenticated_principal, require_admin_or_service
from app.db.session import get_db
from app.models.celestial_event import CelestialEvent
from app.models.user import User
from app.models.visibility_assessment import VisibilityAssessment
from app.repositories.visibility_assessment_repository import (
    create_assessment,
    get_assessment_by_id,
    get_assessments_for_event,
)
from app.schemas.visibility_assessment import (
    VisibilityAssessmentCalculateRequest,
    VisibilityAssessmentCalculateResponse,
    VisibilityAssessmentCreate,
    VisibilityAssessmentResponse,
)
from app.services.visibility_assessment_service import (
    VisibilityAssessmentService,
)

router = APIRouter(
    prefix="/api/v1/visibility-assessments",
    tags=["Visibility Assessments"],
)


@router.post(
    "/calculate",
    response_model=VisibilityAssessmentCalculateResponse,
    status_code=status.HTTP_200_OK,
)
def calculate_event_visibility_assessment(
    payload: VisibilityAssessmentCalculateRequest,
    db: Session = Depends(get_db),
    current_caller: User = Depends(get_authenticated_principal),
):
    service = VisibilityAssessmentService()
    try:
        return service.calculate_assessment(db=db, request=payload)
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not calculate visibility assessment: {exc}",
        ) from exc



@router.post(
    "",
    response_model=VisibilityAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_visibility_assessment(
    payload: VisibilityAssessmentCreate,
    db: Session = Depends(get_db),
    current_caller: User = Depends(require_admin_or_service),
):
    event = db.scalar(
        select(CelestialEvent).where(
            CelestialEvent.id == payload.event_id
        )
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Celestial event not found.",
        )

    assessment = create_assessment(db, payload)

    try:
        db.commit()
        db.refresh(assessment)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save visibility assessment.",
        )

    return assessment


@router.get(
    "/{assessment_id}",
    response_model=VisibilityAssessmentResponse,
)
def read_visibility_assessment(
    assessment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_caller: User = Depends(get_authenticated_principal),
):
    assessment = get_assessment_by_id(db, assessment_id)

    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visibility assessment not found.",
        )

    return assessment


@router.get(
    "/by-event/{event_id}",
    response_model=list[VisibilityAssessmentResponse],
)
def read_event_visibility_assessments(
    event_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_caller: User = Depends(get_authenticated_principal),
):
    event_exists = db.scalar(
        select(CelestialEvent.id).where(
            CelestialEvent.id == event_id
        )
    )

    if event_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Celestial event not found.",
        )

    return get_assessments_for_event(db, event_id, limit)
