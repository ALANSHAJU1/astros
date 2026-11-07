"""Database recommendation service.

Orchestrates database event retrieval, real environmental and astronomical assessments,
preference scoring, and ranking for observation sessions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.modules.intelligence.recommendation.backend_interface import (
    generate_recommendations,
)
from app.repositories.event_repository import get_events_for_session
from app.services.environmental_service import EnvironmentalService
from app.services.event_deduplication import deduplicate_events
from app.services.hathim_astronomy_adapter import HathimAstronomyAdapter
from app.services.preference_scoring import calculate_preference_score
from app.services.observation_duration_policy import (DEFAULT_DURATION_MINUTES,resolve_event_duration,)
from app.services.visibility_scoring_engine import (
    evaluate_event_visibility,
    score_to_quality_and_decision,
)

# get_test_assessment is None by default in production.
# Preserved on module only for backward compatibility if legacy tests monkeypatch it.
get_test_assessment = None
# Backward compatibility for existing tests and external callers.
# The shared duration policy remains the single source of truth.
DEFAULT_DURATIONS = DEFAULT_DURATION_MINUTES

def _find_best_observation_for_window(
    win_start: datetime | None,
    win_end: datetime | None,
    obs_list: list[Any],
) -> Any | None:
    """Find the environmental observation record closest to the given event window."""
    if not obs_list or not win_start:
        return None
    effective_end = win_end or win_start

    def to_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    target_start = to_utc(win_start)
    target_end = to_utc(effective_end)

    def get_obs_dt(obs: Any) -> datetime | None:
        dt = getattr(obs, "observed_at", None) if not isinstance(obs, dict) else obs.get("observed_at")
        if dt is None:
            return None
        if isinstance(dt, datetime):
            return dt
        try:
            cleaned = str(dt).strip()
            if cleaned.endswith("Z") or cleaned.endswith("z"):
                cleaned = cleaned[:-1] + "+00:00"
            return datetime.fromisoformat(cleaned)
        except Exception:
            return None

    # 1. Observations strictly inside the window
    inside: list[tuple[Any, datetime]] = []
    for obs in obs_list:
        obs_dt = get_obs_dt(obs)
        if obs_dt is not None:
            obs_utc = to_utc(obs_dt)
            if target_start <= obs_utc <= target_end:
                inside.append((obs, obs_utc))
    if inside:
        return min(inside, key=lambda x: abs((x[1] - target_start).total_seconds()))[0]

    # 2. Closest within 60 minutes
    closest = None
    min_diff = None
    for obs in obs_list:
        obs_dt = get_obs_dt(obs)
        if obs_dt is not None:
            obs_utc = to_utc(obs_dt)
            diff = min(abs((obs_utc - target_start).total_seconds()), abs((obs_utc - target_end).total_seconds()))
            if diff <= 3600 and (min_diff is None or diff < min_diff):
                min_diff = diff
                closest = obs
    return closest


def get_database_recommendations(
    db: Session,
    session: dict[str, Any],
    observation_goal: str = "general_observation",
    preferences: dict[str, Any] | None = None,
    category: str | None = None,
    assessment_provider: Any = None,
    environmental_service: Any = None,
    astronomy_adapter: Any = None,
) -> dict[str, Any]:
    """Generate recommendations from database events.

    Integrates real environmental context and transparently discloses whether
    assessments are real or synthetic test fixtures.
    """
    start_time = datetime.fromisoformat(session["start_time"])
    end_time = datetime.fromisoformat(session["end_time"])

    if start_time.tzinfo is None or start_time.utcoffset() is None:
        raise ValueError("session.start_time must include a timezone offset.")

    if end_time.tzinfo is None or end_time.utcoffset() is None:
        raise ValueError("session.end_time must include a timezone offset.")

    if end_time <= start_time:
        raise ValueError("session.end_time must be later than session.start_time.")

    if not session.get("location"):
        raise ValueError("session.location is required.")

    if not isinstance(session["location"], dict):
        raise ValueError("session.location must be an object.")

    duration_available = session.get("available_duration_minutes")
    if (
        isinstance(duration_available, bool)
        or not isinstance(duration_available, (int, float))
        or duration_available <= 0
    ):
        raise ValueError("available_duration_minutes must be positive.")

    current_time = datetime.now(timezone.utc)
    # For historical sessions/test fixtures, evaluate freshness relative to session start
    eval_now = start_time if start_time < current_time else current_time

    # Retrieve environmental context and forecast observations for the session location
    environmental_context = None
    forecast_observations: list[Any] = []
    lp_result = None

    location = session.get("location") or {}
    lat = location.get("latitude")
    lon = location.get("longitude")

    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        env_svc = environmental_service if environmental_service is not None else EnvironmentalService()
        try:
            environmental_context = env_svc.build_session_environmental_context(
                db=db,
                latitude=float(lat),
                longitude=float(lon),
                start_time=start_time,
                end_time=end_time,
                now=eval_now,
            )
        except SQLAlchemyError:
            raise
        except Exception as exc:
            environmental_context = {
                "environmental_data_available": False,
                "freshness_status": "unknown",
                "limitations": [f"Could not load environmental context: {exc}"],
            }

        try:
            forecast_observations = env_svc.get_or_fetch_forecast_observations(
                db=db,
                latitude=float(lat),
                longitude=float(lon),
                start_time=start_time,
                end_time=end_time,
                now=eval_now,
            ) or []
        except SQLAlchemyError:
            raise
        except Exception as obs_exc:
            forecast_observations = []
            if environmental_context and isinstance(environmental_context.get("limitations"), list):
                environmental_context["limitations"].append(
                    f"Hourly weather forecast unavailable: {obs_exc}"
                )

        try:
            lp_result = env_svc.get_light_pollution(
                latitude=float(lat),
                longitude=float(lon),
            )
        except Exception:
            lp_result = None

    # Retrieve database events
    database_events = get_events_for_session(
        db=db,
        session_start=start_time,
        session_end=end_time,
        category=category,
    )

    database_events = deduplicate_events(database_events)

    astro_adapter = astronomy_adapter if astronomy_adapter is not None else HathimAstronomyAdapter()

    adapted_events = []
    rejected_events = []

    # Track whether synthetic assessments were explicitly used
    explicit_synthetic_used = False

    for event in database_events:
        if event.end_time is None or event.end_time <= event.start_time:
            rejected_events.append({
                "event_id": str(event.id),
                "reason": "Event has no valid end time.",
            })
            continue

        # Coordinate resolution: use event coordinates if present, fallback to session observer location
        event_lat = event.latitude if event.latitude is not None else (float(lat) if isinstance(lat, (int, float)) else None)
        event_lon = event.longitude if event.longitude is not None else (float(lon) if isinstance(lon, (int, float)) else None)

        matched_obs = _find_best_observation_for_window(
            event.start_time,
            event.end_time,
            forecast_observations,
        )

        try:
            if assessment_provider is not None:
                assessment = assessment_provider(event)
            elif get_test_assessment is not None:
                # Backward-compatibility for monkeypatched legacy tests
                assessment = get_test_assessment(event)
            else:
                eval_res = evaluate_event_visibility(
                    event=event,
                    environmental_data=matched_obs,
                    latitude=event_lat,
                    longitude=event_lon,
                    light_pollution=lp_result,
                    astronomy_adapter=astro_adapter,
                    viewing_window_start=event.start_time,
                    viewing_window_end=event.end_time,
                    now=eval_now,
                )
                assessment = {
                    "status": eval_res.status,
                    "visibility_score": eval_res.visibility_score,
                    "weather_score": eval_res.environmental_score,
                    "astronomical_score": eval_res.astronomical_score,
                    "quality_label": eval_res.quality_label,
                    "decision": eval_res.decision,
                    "limitations": eval_res.limitations,
                    "factors": eval_res.factors,
                    "source": eval_res.source,
                    "data_mode": "real_assessment",
                }
        except SQLAlchemyError:
            raise
        except Exception:
            rejected_events.append({
                "event_id": str(event.id),
                "reason": "Assessment provider failed.",
            })
            continue

        if not isinstance(assessment, dict):
            rejected_events.append({
                "event_id": str(event.id),
                "reason": "Assessment provider returned an invalid response.",
            })
            continue

        if assessment.get("status") not in ("success", "partial_success"):
            reasons = assessment.get("limitations") or ["No assessment is configured or the assessment was unsuccessful."]
            reason_str = "; ".join(reasons) if isinstance(reasons, list) else str(reasons)
            rejected_events.append({
                "event_id": str(event.id),
                "reason": f"No assessment is configured or the assessment was unsuccessful. {reason_str}".strip(),
            })
            continue

        scores_valid = True
        has_at_least_one_score = False

        for score_name in ("visibility_score", "weather_score"):
            score = assessment.get(score_name)
            if score is None:
                continue
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not 0 <= score <= 100
            ):
                scores_valid = False
                break
            has_at_least_one_score = True

        if not scores_valid or not has_at_least_one_score:
            rejected_events.append({
                "event_id": str(event.id),
                "reason": (
                    "Assessment scores must be numeric values between 0 and 100."
                ),
            })
            continue

        assessment_source = assessment.get("source")
        if not isinstance(assessment_source, str) or not assessment_source.strip():
            rejected_events.append({
                "event_id": str(event.id),
                "reason": "Assessment source is missing or invalid.",
            })
            continue

        event_dict = {
            "event_id": str(event.id),
            "name": event.object_name,
            "category": event.category,
            "event_type": event.event_type,
            "source": "database",
        }

        preference_score = calculate_preference_score(
            event=event_dict,
            observation_goal=observation_goal,
            preferences=preferences,
        )

        event_extra = event.additional_data or {}
        explicit_duration = event_extra.get("required_duration_minutes")
        if explicit_duration is None:
            explicit_duration = event_extra.get("duration_minutes")
        duration = resolve_event_duration(
            event.event_type or event.category,
            explicit_duration,
        )
        if duration is None:
            rejected_events.append({
                "event_id": str(event.id),
                "reason": (
                    f"No observation duration is configured for event type "
                    f"'{event.event_type or event.category}'."
                ),
            })
            continue

        window_minutes = (
            event.end_time - event.start_time
        ).total_seconds() / 60

        if duration > window_minutes:
            rejected_events.append({
                "event_id": str(event.id),
                "reason": "Required duration exceeds the event window.",
            })
            continue

        assessment_data_mode = assessment.get("data_mode", "real_assessment")
        if assessment_data_mode == "synthetic_test" or assessment_source == "test_assessment_provider":
            explicit_synthetic_used = True
            assessment_data_mode = "synthetic_test"

        adapted_events.append({
            "event_id": str(event.id),
            "external_event_id": event.external_event_id,
            "name": event.object_name,
            "event_type": event.event_type,
            "type": event.event_type,
            "source": "database",
            "window_start": event.start_time.isoformat(),
            "window_end": event.end_time.isoformat(),
            "visibility_score": assessment.get("visibility_score"),
            "weather_score": assessment.get("weather_score"),
            "astronomical_score": assessment.get("astronomical_score"),
            "preference_score": preference_score,
            "duration_minutes": duration,
            "required_duration_minutes": duration,
            "latitude": event.latitude,
            "longitude": event.longitude,
            "assessment_status": assessment.get("status"),
            "quality_label": assessment.get("quality_label"),
            "decision": assessment.get("decision"),
            "limitations": assessment.get("limitations", []),
            "additional_data": {
                **(event.additional_data or {}),
                "data_mode": assessment_data_mode,
                "assessment_source": assessment_source,
                "quality_label": assessment.get("quality_label"),
                "limitations": assessment.get("limitations", []),
            },
        })

    session_payload = {
        **session,
        "timezone": (
            session.get("timezone")
            or session["location"].get("timezone")
            or "Asia/Kolkata"
        ),
        "observation_goal": observation_goal,
    }
    if environmental_context is not None:
        session_payload["environmental_context"] = environmental_context

    # Determine overall data mode
    effective_data_mode = "synthetic_test" if explicit_synthetic_used else "real_assessment"

    request_data = {
        "session": session_payload,
        "events": adapted_events,
        "data_mode": effective_data_mode,
    }
    if environmental_context is not None:
        request_data["environmental_context"] = environmental_context

    if not adapted_events:
        # Truthful data provenance when no events can be scheduled
        empty_data_mode = "synthetic_test" if (assessment_provider is not None or get_test_assessment is not None) else "no_events_found"
        result = {
            "status": "empty",
            "ranked_events": [],
            "recommendation": {
                "summary": {
                    "total_events_evaluated": 0,
                    "total_events_scheduled": 0,
                    "total_events_skipped": 0,
                    "user_available_minutes": float(duration_available),
                    "total_scheduled_minutes": 0.0,
                    "remaining_minutes": float(duration_available),
                    "session_start": start_time.isoformat(),
                    "session_end": end_time.isoformat(),
                    "location": session["location"],
                    "timezone": request_data["session"]["timezone"],
                    "observation_goal": observation_goal,
                },
                "schedule": [],
                "skipped_events": [],
            },
            "data_quality": {
                "is_sample_data": explicit_synthetic_used,
                "data_mode": empty_data_mode,
                "total_events": 0,
                "environmental_context": environmental_context,
            },
            "errors": [],
            "data_mode": empty_data_mode,
            "database_events_found": len(database_events),
            "database_events_rejected": rejected_events,
        }
        if environmental_context is not None:
            result["environmental_context"] = environmental_context
        return result

    try:
        result = generate_recommendations(request_data)

        if not isinstance(result, dict):
            raise TypeError("Recommendation engine must return a dictionary.")

    except Exception:
        return {
            "status": "error",
            "ranked_events": [],
            "recommendation": None,
            "data_mode": effective_data_mode,
            "environmental_context": environmental_context,
            "database_events_found": len(database_events),
            "database_events_rejected": rejected_events,
            "errors": [
                {
                    "code": "RECOMMENDATION_ENGINE_FAILURE",
                    "message": (
                        "The recommendation engine could not process the available events."
                    ),
                }
            ],
        }

    # Format result with truthful provenance metadata
    if isinstance(result, dict):
        result["data_mode"] = effective_data_mode
        if environmental_context is not None:
            result["environmental_context"] = environmental_context

        if isinstance(result.get("data_quality"), dict):
            quality = result["data_quality"]

            if explicit_synthetic_used:
                quality["assessment_mode"] = "synthetic_test"
                quality["synthetic_assessments_count"] = len(adapted_events)
                quality["is_sample_data"] = True
                if adapted_events:
                    quality["quality_notes"] = (
                        f"{len(adapted_events)} event(s) were processed using "
                        "synthetic visibility/weather assessments. "
                        "Astronomical provenance has not been independently verified."
                    )
            else:
                quality["assessment_mode"] = "real_assessment"
                quality["real_assessments_count"] = len(adapted_events)
                quality["is_sample_data"] = False
                quality["quality_notes"] = (
                    f"{len(adapted_events)} event(s) evaluated using real environmental "
                    "forecasts and astronomical calculations."
                )

            if environmental_context is not None:
                quality["environmental_context"] = environmental_context

        result["database_events_found"] = len(database_events)
        result["database_events_rejected"] = rejected_events

    return result
