import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Dict, List, Optional
import app.services.jpl_astronomy_adapter as jpl_adapter
from app.services.observation_duration_policy import resolve_event_duration
from app.services.catalog_event_discovery_service import discover_catalog_events

logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session
from app.api.deps import get_authenticated_principal
from app.db.session import get_db
from app.models.user import User
from app.services.environmental_service import EnvironmentalService

from app.services.visibility_scoring_engine import evaluate_event_visibility
from app.services.astronomy_adapter import BaseAstronomyAdapter
from app.services.hathim_astronomy_adapter import HathimAstronomyAdapter
import app.modules.intelligence.recommendation.backend_interface as backend_interface

router = APIRouter()


def _parse_ts(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    try:
        cleaned = str(ts).strip()
        if cleaned.endswith("Z") or cleaned.endswith("z"):
            cleaned = cleaned[:-1] + "+00:00"
        return datetime.fromisoformat(cleaned)
    except Exception:
        return None


def _normalize_discovered_event_windows(events: List[Dict[str, Any]]) -> None:
    """
    Catalog discovery returns UTC observation windows.

    Some catalog engines format timestamps without an offset, so restore
    UTC awareness for those catalog-generated events before validation.
    Do not silently reinterpret user-supplied event timestamps.
    """
    for event in events:
        if event.get("category") != "meteor_shower":
            continue

        for field in ("window_start", "window_end"):
            raw_value = event.get(field)
            if raw_value is None:
                continue

            parsed = _parse_ts(raw_value)
            if parsed is None:
                continue

            if parsed.tzinfo is None or parsed.utcoffset() is None:
                parsed = parsed.replace(tzinfo=dt_timezone.utc)

            event[field] = parsed.astimezone(dt_timezone.utc).isoformat()


def _find_best_observation_for_window(
    win_start: Optional[datetime], win_end: Optional[datetime], obs_list: List[Any]
) -> Optional[Any]:
    if not obs_list or not win_start:
        return None
    effective_end = win_end or win_start
    # Normalize timezone awareness for comparisons
    def to_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=dt_timezone.utc)
        return dt.astimezone(dt_timezone.utc)

    target_start = to_utc(win_start)
    target_end = to_utc(effective_end)

    # 1. Look for observations strictly falling within the window
    inside = []
    for obs in obs_list:
        obs_dt = _parse_ts(getattr(obs, "observed_at", None) if not isinstance(obs, dict) else obs.get("observed_at"))
        if obs_dt is not None:
            obs_utc = to_utc(obs_dt)
            if target_start <= obs_utc <= target_end:
                inside.append((obs, obs_utc))
    if inside:
        # Pick the one closest to window start or middle
        return min(inside, key=lambda x: abs((x[1] - target_start).total_seconds()))[0]

    # 2. If none strictly inside, find the closest observation within 60 minutes
    closest = None
    min_diff = None
    for obs in obs_list:
        obs_dt = _parse_ts(getattr(obs, "observed_at", None) if not isinstance(obs, dict) else obs.get("observed_at"))
        if obs_dt is not None:
            obs_utc = to_utc(obs_dt)
            diff = min(abs((obs_utc - target_start).total_seconds()), abs((obs_utc - target_end).total_seconds()))
            if diff <= 3600 and (min_diff is None or diff < min_diff):
                min_diff = diff
                closest = obs
    return closest

# Pydantic models for request validation and OpenAPI documentation
class SessionModel(BaseModel):
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    session_start: Optional[str] = None
    session_end: Optional[str] = None
    available_duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    preference_score: Optional[float] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "latitude": 10.5276,
                "longitude": 76.2144,
                "session_start": "2026-10-26T19:00:00+05:30",
                "session_end": "2026-10-26T22:00:00+05:30",
                "available_duration_minutes": 120,
            }
        }
    )

class ObservationPlanRequest(BaseModel):
    session: SessionModel = Field(default_factory=SessionModel)
    events: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session": {
                    "latitude": 10.5276,
                    "longitude": 76.2144,
                    "session_start": "2026-10-26T19:00:00+05:30",
                    "session_end": "2026-10-26T22:00:00+05:30",
                    "available_duration_minutes": 120,
                },
                "events": [],
            }
        }
    )


def _extract_target_id(event: Dict[str, Any]) -> Optional[str]:
    """Extract a Horizons target ID from a planner candidate."""
    additional = event.get("additional_data") or {}
    metadata = event.get("metadata") or {}

    target_id = (
        additional.get("target_id")
        or metadata.get("target_id")
        or event.get("target_id")
    )

    return str(target_id).strip() if target_id is not None else None


def _normalize_target_id(target_id: str) -> str:
    return target_id.strip().rstrip(";").strip()


def _enrich_candidates_with_horizons(events, horizons_events):
    """Merge actual Horizons elevation facts into matching planner candidates."""
    horizons_by_id = {}

    for horizons_event in horizons_events:
        metadata = horizons_event.get("metadata") or {}
        facts = metadata.get("nasa_horizons_facts") or {}
        target_id = facts.get("target_id") or horizons_event.get("target_id")

        if target_id is not None:
            horizons_by_id[_normalize_target_id(str(target_id))] = horizons_event

    for candidate in events:
        target_id = _extract_target_id(candidate)

        if not target_id:
            continue

        horizons_event = horizons_by_id.get(_normalize_target_id(target_id))

        if not horizons_event:
            continue

        horizons_metadata = horizons_event.get("metadata") or {}
        horizons_facts = horizons_metadata.get("nasa_horizons_facts") or {}
        derived = horizons_metadata.get("derived_astronomical_values") or {}

        peak_elevation = (
            horizons_facts.get("peak_elevation_deg")
            if horizons_facts.get("peak_elevation_deg") is not None
            else derived.get("peak_elevation_deg")
        )

        if peak_elevation is None:
            continue

        candidate_metadata = candidate.setdefault("metadata", {})
        candidate_facts = candidate_metadata.setdefault(
            "nasa_horizons_facts", {}
        )

        candidate_facts.update(horizons_facts)
        candidate_facts["peak_elevation_deg"] = peak_elevation

        candidate_derived = candidate_metadata.setdefault(
            "derived_astronomical_values", {}
        )
        candidate_derived.update(derived)
        candidate_derived["peak_elevation_deg"] = peak_elevation

        candidate["peak_elevation_deg"] = peak_elevation

        additional = candidate.setdefault("additional_data", {})
        additional["peak_elevation_deg"] = peak_elevation

    return events


@router.post("/api/v1/observation-plans/generate")
async def generate_observation_plan(
    request_body: ObservationPlanRequest,
    db: Session = Depends(get_db),
    current_caller: User = Depends(get_authenticated_principal),
):
    """Generate an observation plan.

    The request should contain a ``session`` dict and an ``events`` list.
    Each event is evaluated for visibility and then passed to the intelligence
    pipeline for ranking and explanation.
    """
    body = request_body.model_dump()
    events: List[Dict[str, Any]] = body.get("events") or []
    client_events_received = len(events) if isinstance(events, list) else 0
    discovered_events_count = 0
    if not isinstance(events, list):
        raise HTTPException(status_code=400, detail="'events' must be a list.")
    # ----- Input extraction -------------------------------------------------
    session = body.get("session") or {}
    latitude = session.get("latitude")
    longitude = session.get("longitude")
    session_start = session.get("session_start")
    session_end = session.get("session_end")
    # Parse session times to datetime for environmental fetch
    start_dt: datetime | None = _parse_ts(session_start) if session_start else None
    end_dt: datetime | None = _parse_ts(session_end) if session_end else None
    available_duration = session.get("available_duration_minutes")

    # ----- Enrich supplied asteroid/NEO candidates using JPL Horizons --------
    if events and latitude is not None and longitude is not None \
            and session_start and session_end:

        target_ids = []

        for event in events:
            category = str(
                event.get("category") or event.get("event_type") or ""
            ).lower()

            if "asteroid" in category or "neo" in category or "near-earth" in category:
                target_id = _extract_target_id(event)

                if target_id and target_id not in target_ids:
                    target_ids.append(target_id)

        if target_ids:
            try:
                horizons_events = jpl_adapter.fetch_events_from_jpl(
                    latitude=float(latitude),
                    longitude=float(longitude),
                    start_time_iso=session_start,
                    end_time_iso=session_end,
                    target_ids=target_ids,
                )

                events = _enrich_candidates_with_horizons(
                    events,
                    horizons_events,
                )

                logger.info(
                    "[ObservationPlans] Enriched supplied candidates with Horizons data: %d target(s), %d returned pass(es).",
                    len(target_ids),
                    len(horizons_events),
                )

            except Exception as exc:
                logger.warning(
                    "[ObservationPlans] Optional Horizons candidate enrichment failed: %s",
                    exc,
                )

    # ----- Automatic discovery when no events supplied ----------------------
    if not events:
        if latitude is None or longitude is None or session_start is None or session_end is None:
            raise HTTPException(
                status_code=400,
                detail="When 'events' is empty, request must include session.latitude, session.longitude, session.session_start, and session.session_end for JPL fetch.",
            )
        # 1. Fetch solar-system bodies (Moon, planets) from JPL Horizons
        try:
            fetched = jpl_adapter.fetch_events_from_jpl(
                latitude=float(latitude),
                longitude=float(longitude),
                start_time_iso=session_start,
                end_time_iso=session_end,
                target_ids=None,
            )
            events = fetched
        except Exception as exc:
            logger.error("[ObservationPlans] JPL Horizons fetch failure: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="Failed to fetch events from JPL Horizons: upstream service temporarily unavailable or timed out."
            )

        # 2. Discover catalog-backed candidates (eclipses, meteor showers, DSOs)
        #    These are pure catalog calls — no network required, no exception propagation.
        try:
            catalog_candidates = discover_catalog_events(
                latitude=float(latitude),
                longitude=float(longitude),
                session_start=start_dt if start_dt is not None else _parse_ts(session_start),
                session_end=end_dt if end_dt is not None else _parse_ts(session_end),
                available_duration_minutes=float(available_duration) if available_duration else None,
            )

            # Normalize catalog-generated event windows before merging them.
            _normalize_discovered_event_windows(catalog_candidates)

            for candidate in catalog_candidates:
                 if candidate.get("category") == "meteor_shower":
                     logger.info(
                      "[ObservationPlans] Meteor window after normalization: start=%s, end=%s",
                      candidate.get("window_start"),
                     candidate.get("window_end"),
                     )

            if catalog_candidates:
                # Deduplicate by event_id to avoid double-counting across discovery sources
                existing_ids: set[str] = {e.get("event_id") for e in events if e.get("event_id")}
                for candidate in catalog_candidates:
                    cid = candidate.get("event_id")
                    if cid not in existing_ids:
                        events.append(candidate)
                        if cid:
                            existing_ids.add(cid)
                logger.info(
                    "[ObservationPlans] Merged %d catalog candidate(s) with %d JPL event(s).",
                    len(catalog_candidates), len(fetched),
                )
        except Exception as exc:
            # Catalog discovery failures are non-fatal; log and continue with JPL results only.
            logger.warning("[ObservationPlans] Catalog event discovery error (non-fatal): %s", exc)

    if client_events_received == 0:
        discovered_events_count = len(events)

    # Resolve missing durations from the shared event-type policy.
    # The session's available_duration_minutes is only a total scheduling budget.
    for event in events:
        if not isinstance(event, dict):
            continue
        explicit_duration = (
            event.get("required_duration_minutes")
            if event.get("required_duration_minutes") is not None
            else event.get("duration_minutes")
        )
        try:
            resolved_duration = resolve_event_duration(
                event.get("event_type") or event.get("category") or event.get("type"),
                explicit_duration,
            )
        except ValueError:
            # Leave invalid explicit values intact so request validation reports them.
            continue
        if resolved_duration is not None:
            event["duration_minutes"] = resolved_duration
            event["required_duration_minutes"] = resolved_duration

    astronomy_adapter: BaseAstronomyAdapter = HathimAstronomyAdapter()
    # Initialize environmental service and fetch weather observations
    env_service = EnvironmentalService()
    observations: List[Any] = []
    if start_dt and end_dt and latitude is not None and longitude is not None:
        try:
            logger.info(
                f"[ObservationPlans] Fetching forecasts for lat={latitude}, lon={longitude}, "
                f"start_dt={start_dt.isoformat()}, end_dt={end_dt.isoformat()}"
            )
            observations = env_service.get_or_fetch_forecast_observations(
                db=db,
                latitude=float(latitude),
                longitude=float(longitude),
                start_time=start_dt,
                end_time=end_dt,
            ) or []
            logger.info(f"[ObservationPlans] Retrieved {len(observations)} observation records.")
        except Exception as exc:
            logger.warning(f"[ObservationPlans] Environmental forecast retrieval error: {exc}")
            observations = []

    enriched_events: List[Dict[str, Any]] = []
    for ev in events:

        lat = ev.get("latitude") if ev.get("latitude") is not None else latitude
        lon = ev.get("longitude") if ev.get("longitude") is not None else longitude
        if lat is None or lon is None:
            enriched_events.append(ev)
            continue

        # Ensure temporal window fields are present on the event
        if session_start and not ev.get("window_start") and not ev.get("start_time"):
            ev["window_start"] = session_start
        if session_end and not ev.get("window_end") and not ev.get("end_time"):
            ev["window_end"] = session_end
        # If event already has complete pre-assessed scores, preserve them
        prior_vis = ev.get("visibility_score")
        prior_weather = ev.get("weather_score")
        prior_status = ev.get("assessment_status")
        if prior_vis is not None and prior_weather is not None and prior_status in ("complete", "success"):
            ev["assessment_status"] = prior_status
            ev["environmental_score"] = prior_weather
            ev["weather_score"] = prior_weather
            ev["visibility_score"] = prior_vis
            if ev.get("astronomical_score") is None:
                ev["astronomical_score"] = prior_vis
            from app.services.visibility_scoring_engine import score_to_quality_and_decision
            ev["quality_label"], _ = score_to_quality_and_decision(prior_vis)
            ev["limitations"] = ev.get("limitations") or []

            session_pref = session.get("preference_score")
            ev_pref = ev.get("preference_score")
            if ev_pref is not None:
                ev["preference_score"] = ev_pref
            elif session_pref is not None:
                ev["preference_score"] = session_pref
            else:
                ev["preference_score"] = None

            # Synchronize metadata.external_assessments if present to prevent metadata contradiction
            if isinstance(ev.get("metadata"), dict) and "external_assessments" in ev["metadata"]:
                ext = ev["metadata"]["external_assessments"]
                if isinstance(ext, dict):
                    ext["weather_score"] = ev.get("weather_score")
                    ext["preference_score"] = ev.get("preference_score")
                    if ev.get("weather_score") is not None:
                        ext["weather_source"] = "External Weather Assessment"
                    if ev.get("preference_score") is not None:
                        ext["preference_source"] = "User Profile / Session Preferences"

            enriched_events.append(ev)
            continue

        ev_start = _parse_ts(ev.get("window_start") or ev.get("start_time"))
        ev_end = _parse_ts(ev.get("window_end") or ev.get("end_time")) or ev_start

        # Select matching environmental observation for this event's window
        matched_env_data = _find_best_observation_for_window(ev_start, ev_end, observations)
        logger.info(
            f"[ObservationPlans] Event '{ev.get('name')}' window: {ev_start} to {ev_end}. "
            f"Matched observation: {getattr(matched_env_data, 'observed_at', None) if matched_env_data else None}"
        )

        # Retrieve light pollution safely (does not affect weather score)
        lp_result = None
        try:
            lp_result = env_service.get_light_pollution(latitude=float(lat), longitude=float(lon))
            logger.info(f"[ObservationPlans] Light pollution result status: {getattr(lp_result, 'status', None)}, bortle: {getattr(lp_result, 'bortle_class', None)}")
        except Exception as exc:
            logger.warning(f"[ObservationPlans] DarkSkySites retrieval error: {exc}")
            lp_result = None

        try:
            eval_kwargs = {
                "event": ev,
                "environmental_data": matched_env_data,
                "latitude": lat,
                "longitude": lon,
                "light_pollution": lp_result,
                "astronomy_adapter": astronomy_adapter,
                "viewing_window_start": ev_start,
                "viewing_window_end": ev_end,
            }
            assessment = evaluate_event_visibility(**eval_kwargs)
            # Always use the assessment produced by this backend request.
            assessment_status = getattr(assessment, "status", "unavailable")

            ev["visibility_score"] = assessment.visibility_score
            ev["environmental_score"] = assessment.environmental_score
            ev["weather_score"] = assessment.environmental_score
            ev["astronomical_score"] = assessment.astronomical_score

            ev["assessment_status"] = assessment_status
            ev["quality_label"] = assessment.quality_label
            ev["limitations"] = assessment.limitations or []

            # Resolve preference score: event-level overrides session-level; preserve None if both omitted
            session_pref = session.get("preference_score")
            ev_pref = ev.get("preference_score")
            if ev_pref is not None and not (isinstance(ev_pref, (int, float)) and ev_pref == 0.0 and ev.get("source") == "NASA JPL Horizons API"):
                ev["preference_score"] = float(ev_pref)
            elif session_pref is not None:
                ev["preference_score"] = float(session_pref)
            else:
                ev["preference_score"] = None

            # Synchronize metadata.external_assessments if present to prevent metadata contradiction
            if isinstance(ev.get("metadata"), dict) and "external_assessments" in ev["metadata"]:
                ext = ev["metadata"]["external_assessments"]
                if isinstance(ext, dict):
                    ext["weather_score"] = ev.get("weather_score")
                    ext["preference_score"] = ev.get("preference_score")
                    if ev.get("weather_score") is not None:
                        ext["weather_source"] = "Open-Meteo Forecast Provider"
                    else:
                        ext["weather_source"] = "Unavailable"
                    if ev.get("preference_score") is not None:
                        ext["preference_source"] = "User Profile / Session Preferences"
                    else:
                        ext["preference_source"] = "None"

        except Exception as exc:
            logger.error("[ObservationPlans] Assessment error for event '%s': %s", ev.get("name"), exc)
            ev["processing_error"] = "Assessment could not be completed for this event."
        enriched_events.append(ev)

    intelligence_req = body.copy()
    intelligence_req["events"] = enriched_events
    intelligence_req["event_origin_counts"] = {
        "client_events_received": client_events_received,
        "events_discovered": discovered_events_count,
    }

    # Ensure required session fields for backend processing
    session_req = intelligence_req.get("session", {})
    session_req.setdefault("location", {"latitude": latitude, "longitude": longitude})
    session_req.setdefault("observation_goal", "general")

    # Derive timezone consistently from session timestamps if not explicitly provided
    resolved_tz = session_req.get("timezone") or session.get("timezone")
    if not resolved_tz and session_start:
        try:
            parsed_dt = _parse_ts(session_start)
            if parsed_dt and parsed_dt.tzinfo:
                offset_str = parsed_dt.strftime("%z")
                if offset_str:
                    resolved_tz = f"UTC{offset_str[:3]}:{offset_str[3:]}"
        except Exception:
            pass
    if not resolved_tz:
        resolved_tz = "UTC"
    session_req["timezone"] = resolved_tz

    # Include session timing and duration for the intelligence engine
    if session_start:
        session_req.setdefault("session_start", session_start)
    if session_end:
        session_req.setdefault("session_end", session_end)
    if available_duration:
        session_req.setdefault("available_duration", available_duration)
    intelligence_req["session"] = session_req
    try:
        backend_response = backend_interface.generate_recommendations(intelligence_req)
    except Exception as exc:
        logger.error("[ObservationPlans] Recommendation engine failure: %s", exc)
        raise HTTPException(status_code=500, detail="Recommendation engine encountered an unexpected error.")

    # Determine response format
    if isinstance(backend_response, dict) and "status" in backend_response:
        if backend_response.get("status") not in ("success", "empty"):
            raise HTTPException(status_code=502, detail=backend_response.get("errors", ["Recommendation error"]))
        recommendation = backend_response.get("recommendation", {})
    else:
        # Assume the returned dict is already the recommendation payload (as used in tests)
        recommendation = backend_response

    # Ensure enriched events and ranked events are included for downstream consumers/tests
    recommendation["details"] = enriched_events
    recommendation.setdefault("events", enriched_events)
    if isinstance(backend_response, dict) and "ranked_events" in backend_response:
        recommendation["ranked_events"] = backend_response["ranked_events"]

    return {
        "status": "success",
        "event_count": len(enriched_events),
        "recommendations": recommendation,
    }
