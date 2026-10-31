"""Visibility assessment application service.

Handles orchestrating event lookup, environmental data fetching,
light pollution lookup, visibility evaluation, and persistence.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.celestial_event import CelestialEvent
from app.repositories.visibility_assessment_repository import create_assessment
from app.schemas.visibility_assessment import (
    VisibilityAssessmentCalculateRequest,
    VisibilityAssessmentCalculateResponse,
    VisibilityAssessmentCreate,
)
from app.services.environmental_service import EnvironmentalService
from app.services.visibility_scoring_engine import evaluate_event_visibility


class VisibilityAssessmentService:
    """Service orchestrating event visibility calculations."""

    def __init__(
        self,
        environmental_service: EnvironmentalService | None = None,
    ) -> None:
        self.environmental_service = environmental_service or EnvironmentalService()

    def calculate_assessment(
        self,
        db: Session,
        request: VisibilityAssessmentCalculateRequest,
        *,
        now: datetime | None = None,
    ) -> VisibilityAssessmentCalculateResponse:
        """Calculate and optionally persist a visibility assessment for a celestial event."""
        current_time = now or datetime.now(timezone.utc)

        # 1. Fetch event from database
        event = db.scalar(
            select(CelestialEvent).where(CelestialEvent.id == request.event_id)
        )
        if event is None:
            raise ValueError(f"Celestial event '{request.event_id}' not found.")

        # 2. Resolve viewing window
        start = request.viewing_window_start or event.start_time
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("viewing_window_start must be timezone-aware")

        end = request.viewing_window_end or event.end_time or (start + timedelta(hours=2))
        if end.tzinfo is None or end.utcoffset() is None:
            raise ValueError("viewing_window_end must be timezone-aware")

        if end <= start:
            raise ValueError("viewing_window_end must be after viewing_window_start")

        # 3. Retrieve environmental forecast observations
        observations = []
        try:
            observations = self.environmental_service.get_or_fetch_forecast_observations(
                db=db,
                latitude=request.latitude,
                longitude=request.longitude,
                start_time=start,
                end_time=end,
                now=current_time,
            )
        except Exception:
            # Service gracefully handles provider failure in scoring
            pass

        # Use observation closest to window start or middle
        selected_obs = observations[0] if observations else None

        # 4. Retrieve light pollution
        lp_result = self.environmental_service.get_light_pollution(
            latitude=request.latitude,
            longitude=request.longitude,
        )

        # 5. Evaluate pure visibility score
        eval_result = evaluate_event_visibility(
            event=event,
            environmental_data=selected_obs,
            latitude=request.latitude,
            longitude=request.longitude,
            light_pollution=lp_result,
            viewing_window_start=start,
            viewing_window_end=end,
            now=current_time,
        )

        persisted_id: uuid.UUID | None = None
        is_persisted = False

        # 6. Persist if requested
        if request.persist:
            create_payload = VisibilityAssessmentCreate(
                event_id=event.id,
                latitude=request.latitude,
                longitude=request.longitude,
                visibility_score=eval_result.visibility_score,
                quality_label=eval_result.quality_label,
                viewing_window_start=eval_result.viewing_window_start,
                viewing_window_end=eval_result.viewing_window_end,
                factors=eval_result.factors,
                limitations=eval_result.limitations,
                source=eval_result.source,
                expires_at=eval_result.viewing_window_end + timedelta(hours=1),
            )
            persisted = create_assessment(db, create_payload)
            try:
                db.commit()
                db.refresh(persisted)
                persisted_id = persisted.id
                is_persisted = True
            except Exception:
                db.rollback()
                raise

        return VisibilityAssessmentCalculateResponse(
            id=persisted_id,
            event_id=event.id,
            status=eval_result.status,
            visibility_score=eval_result.visibility_score,
            environmental_score=eval_result.environmental_score,
            astronomical_score=eval_result.astronomical_score,
            quality_label=eval_result.quality_label,
            decision=eval_result.decision,
            viewing_window_start=eval_result.viewing_window_start,
            viewing_window_end=eval_result.viewing_window_end,
            factors=eval_result.factors,
            limitations=eval_result.limitations,
            source=eval_result.source,
            assessed_at=eval_result.assessed_at,
            light_pollution=eval_result.light_pollution,
            confidence=eval_result.confidence,
            is_persisted=is_persisted,
        )
