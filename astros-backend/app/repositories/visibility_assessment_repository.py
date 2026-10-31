
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.visibility_assessment import VisibilityAssessment
from app.schemas.visibility_assessment import VisibilityAssessmentCreate


def create_assessment(
    db: Session,
    assessment_data: VisibilityAssessmentCreate,
) -> VisibilityAssessment:
    """Create and persist a visibility assessment."""
    assessment = VisibilityAssessment(
        **assessment_data.model_dump()
    )

    db.add(assessment)
    db.flush()
    db.refresh(assessment)

    return assessment


def get_assessment_by_id(
    db: Session,
    assessment_id: uuid.UUID,
) -> VisibilityAssessment | None:
    """Retrieve one assessment by its database ID."""
    statement = select(VisibilityAssessment).where(
        VisibilityAssessment.id == assessment_id
    )
    return db.scalar(statement)


def get_assessments_for_event(
    db: Session,
    event_id: uuid.UUID,
    limit: int = 100,
) -> list[VisibilityAssessment]:
    """Retrieve assessments for an event, newest assessment first."""
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    statement = (
        select(VisibilityAssessment)
        .where(VisibilityAssessment.event_id == event_id)
        .order_by(VisibilityAssessment.assessed_at.desc())
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def get_latest_assessment_for_event(
    db: Session,
    event_id: uuid.UUID,
) -> VisibilityAssessment | None:
    """Retrieve the most recently assessed record for an event."""
    statement = (
        select(VisibilityAssessment)
        .where(VisibilityAssessment.event_id == event_id)
        .order_by(VisibilityAssessment.assessed_at.desc())
        .limit(1)
    )

    return db.scalar(statement)
