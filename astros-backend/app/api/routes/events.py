from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_authenticated_principal, require_admin, require_admin_or_service
from app.db.session import get_db
from app.models.celestial_event import CelestialEvent
from app.models.user import User
from app.schemas.celestial_event import (
    CelestialEventCreate,
    CelestialEventRead,
    CelestialEventUpdate
)


router = APIRouter(prefix="/api/v1/events", tags=["Events"])


@router.post(
    "",
    response_model=CelestialEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    event_data: CelestialEventCreate,
    db: Session = Depends(get_db),
    current_caller: User = Depends(require_admin_or_service),
):
    event = CelestialEvent(**event_data.model_dump())

    db.add(event)
    db.commit()
    db.refresh(event)

    return event


@router.get("", response_model=list[CelestialEventRead])
def list_events(
    category: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_caller: User = Depends(get_authenticated_principal),
):
    statement = select(CelestialEvent)

    if category:
        statement = statement.where(
            CelestialEvent.category == category
        )

    statement = (
        statement
        .order_by(CelestialEvent.start_time)
        .offset(skip)
        .limit(limit)
    )

    return db.scalars(statement).all()


@router.get("/{event_id}", response_model=CelestialEventRead)
def get_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_caller: User = Depends(get_authenticated_principal),
):
    event = db.get(CelestialEvent, event_id)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Celestial event not found",
        )

    return event



@router.patch(
    "/{event_id}",
    response_model=CelestialEventRead,
    status_code=status.HTTP_200_OK,
)
def update_event(
    event_id: UUID,
    event_data: CelestialEventUpdate,
    db: Session = Depends(get_db),
    current_caller: User = Depends(require_admin_or_service),
):
    event = db.get(CelestialEvent, event_id)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    updates = event_data.model_dump(exclude_unset=True)

    # Required fields cannot explicitly be set to null.
    required_fields = {
        "category",
        "object_name",
        "event_type",
        "start_time",
    }

    for field in required_fields:
        if field in updates and updates[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field} cannot be null",
            )

    new_start = updates.get("start_time", event.start_time)
    new_end = updates.get("end_time", event.end_time)

    if new_start is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_time cannot be null",
        )

    # Both timestamps must be timezone-aware.
    for field, value in (
        ("start_time", new_start),
        ("end_time", new_end),
    ):
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field} must be timezone-aware",
            )

    # end_time is nullable, but when supplied it must follow start_time.
    if new_end is not None and new_end <= new_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must be after start_time",
        )

    for field, value in updates.items():
        setattr(event, field, value)

    try:
        db.commit()
        db.refresh(event)
    except Exception:
        db.rollback()
        raise

    return event



@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_caller: User = Depends(require_admin),
):
    event = db.get(CelestialEvent, event_id)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    db.delete(event)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)