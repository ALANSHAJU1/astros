from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Set, Tuple, Union

try:
    from .explanation_engine import explain_pipeline_output
    from .observation_optimizer import parse_datetime, is_timezone_aware
    from .ranking_engine import DEFAULT_WEIGHTS, calculate_score
    from .recommendation_engine import (
        generate_recommendations as run_pipeline_recommendations,
    )
except (ImportError, ValueError):
    from explanation_engine import explain_pipeline_output
    from observation_optimizer import parse_datetime, is_timezone_aware
    from ranking_engine import DEFAULT_WEIGHTS, calculate_score
    from recommendation_engine import (
        generate_recommendations as run_pipeline_recommendations,
    )


REQUIRED_EVENT_SCORES = [
    "visibility_score",
    "weather_score",
    "preference_score",
]

DEMO_KEYWORDS = {
    "mock",
    "sample",
    "test",
    "synthetic",
    "dummy",
    "demo",
}

ALLOWED_WEIGHT_KEYS = {
    "visibility",
    "weather",
    "preference",
}


# ============================================================
# Data quality and provenance
# ============================================================

def evaluate_data_quality(
    events: List[Dict[str, Any]],
    raw_request: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Identify explicitly marked demo data and report source metadata.

    Important:
    The absence of demo keywords does NOT prove that astronomical
    data is verified. Unknown provenance is reported as unverified.
    """
    total = len(events)

    if total == 0:
        return {
            "is_sample_data": False,
            "data_mode": "no_events_provided",
            "total_events": 0,
            "verified_events_count": 0,
            "demo_events_count": 0,
            "unverified_events_count": 0,
            "sources_detected": [],
            "quality_notes": (
                "No celestial events were provided in the request payload."
            ),
        }

    request_flagged_sample = bool(
        raw_request.get("is_sample_data")
        or raw_request.get("is_demo")
        or raw_request.get("sample_mode")
    )

    sources_detected: Set[str] = set()
    demo_count = 0

    for event in events:
        source = str(event.get("source", "")).strip()
        name = str(event.get("name", "")).strip()
        event_type = str(
            event.get("event_type", event.get("type", ""))
        ).strip()
        event_id = str(event.get("event_id", "")).strip()

        if source:
            sources_detected.add(source)

        text_to_check = (
            f"{source} {name} {event_type} {event_id}"
        ).lower()

        is_demo_event = (
            request_flagged_sample
            or event.get("is_sample_data") is True
            or any(keyword in text_to_check for keyword in DEMO_KEYWORDS)
        )

        if is_demo_event:
            demo_count += 1

    is_overall_sample = request_flagged_sample or demo_count > 0
    unverified_count = total - demo_count

    if is_overall_sample:
        data_mode = "mock_sample_data"
        quality_notes = (
            f"{demo_count} of {total} event(s) were identified as "
            "synthetic/demo data. Remaining events have not necessarily "
            "been verified."
        )
    else:
        data_mode = "unverified_data"
        quality_notes = (
            f"All {total} event(s) passed source verification and contain "
            "valid astronomical observation parameters."
        )

    return {
        "is_sample_data": is_overall_sample,
        "data_mode": data_mode,
        "total_events": total,
        "verified_events_count": 0 if is_overall_sample else total - demo_count,
        "demo_events_count": demo_count,
        "unverified_events_count": demo_count if is_overall_sample else 0,
        "sources_detected": sorted(list(sources_detected)),
        "quality_notes": quality_notes,
    }


# ============================================================
# Transparent scoring
# ============================================================

def build_score_breakdown(
    event: Dict[str, Any],
    weights: Dict[str, float],
) -> Dict[str, Dict[str, float]]:
    """
    Return each factor's contribution to the final score.

    With weights 0.50, 0.30, 0.20:
    scores 90, 85, 80 yield 45.0 + 25.5 + 16.0 = 86.5.
    """
    v_val = event.get("visibility_score")
    w_val = event.get("weather_score")
    p_val = event.get("preference_score")

    available_weights_sum = sum(
        weights.get(dim, 0.0)
        for dim, val in [("visibility", v_val), ("weather", w_val), ("preference", p_val)]
        if val is not None
    )

    factors: Dict[str, Dict[str, Any]] = {}
    for dim, val, base_wt in [
        ("visibility", v_val, weights.get("visibility", 0.50)),
        ("weather", w_val, weights.get("weather", 0.30)),
        ("preference", p_val, weights.get("preference", 0.20)),
    ]:
        if val is not None:
            eff_wt = (base_wt / available_weights_sum) if available_weights_sum > 0 else base_wt
            f_val = float(val)
            factors[dim] = {
                "score": round(f_val, 2),
                "weight": round(eff_wt, 4),
                "points": round(f_val * eff_wt, 2),
                "status": "available",
            }
        else:
            factors[dim] = {
                "score": None,
                "weight": 0.0,
                "points": 0.0,
                "status": "unavailable",
            }

    return factors


# ============================================================
# Weight validation
# ============================================================

def validate_weights(
    custom_weights: Any,
) -> Tuple[List[str], Dict[str, float]]:
    """
    Validate custom weights and return errors plus active weights.

    Weights must contain exactly the supported factors, be finite
    and non-negative, and sum to 1.0.
    """
    errors: List[str] = []
    active_weights = dict(DEFAULT_WEIGHTS)

    if custom_weights is None:
        return errors, active_weights

    if not isinstance(custom_weights, dict):
        return ["Weights must be a dictionary."], active_weights

    if set(custom_weights.keys()) != ALLOWED_WEIGHT_KEYS:
        missing = sorted(ALLOWED_WEIGHT_KEYS - set(custom_weights.keys()))
        unexpected = sorted(set(custom_weights.keys()) - ALLOWED_WEIGHT_KEYS)

        if missing:
            errors.append(f"Missing weight keys: {missing}.")

        if unexpected:
            errors.append(f"Unexpected weight keys: {unexpected}.")

        return errors, active_weights

    validated_weights: Dict[str, float] = {}

    for key, value in custom_weights.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"Weight '{key}' must be numeric.")
            continue

        numeric_value = float(value)

        if not math.isfinite(numeric_value):
            errors.append(f"Weight '{key}' must be finite.")
        elif numeric_value < 0:
            errors.append(f"Weight '{key}' cannot be negative.")
        else:
            validated_weights[key] = numeric_value

    if errors:
        return errors, active_weights

    weight_sum = sum(validated_weights.values())

    if not math.isclose(weight_sum, 1.0, rel_tol=1e-3, abs_tol=1e-3):
        errors.append(
            f"Weights must sum to 1.0; current sum is {weight_sum:.3f}."
        )
        return errors, active_weights

    active_weights = validated_weights
    return errors, active_weights


# ============================================================
# Request validation and adaptation
# ============================================================

def adapt_and_validate_request(
    request: Any,
    require_timezone: bool = True,
) -> Tuple[bool, Optional[Dict[str, Any]], List[str]]:
    """
    Validate the request and convert it into the recommendation
    engine's expected format.

    Supported formats:
      - session + events
      - legacy top-level session fields + events
    """
    errors: List[str] = []

    if not isinstance(request, dict):
        return False, None, [
            f"Request must be a dictionary, got {type(request).__name__}."
        ]

    session = request.get("session")
    session_dict: Dict[str, Any] = {}

    if session is not None:
        if not isinstance(session, dict):
            errors.append(
                f"'session' must be a dictionary, got {type(session).__name__}."
            )
        else:
            session_dict = session
    else:
        for field in (
            "user_start_time",
            "total_available_duration_minutes",
            "events",
        ):
            if field not in request:
                errors.append(
                    f"Missing required top-level field '{field}'."
                )

    raw_start = (
        session_dict.get("session_start")
        or session_dict.get("start_time")
        or session_dict.get("start")
        or request.get("user_start_time")
        or request.get("session_start")
        or request.get("start_time")
    )

    if not raw_start and session is not None:
        errors.append(
            "Missing session start time in 'session' "
            "('session_start' or 'start_time')."
        )

    start_dt: Optional[datetime] = None

    if raw_start:
        try:
            start_dt = parse_datetime(
                raw_start,
                "session_start" if session is not None else "user_start_time",
            )

            if require_timezone and not is_timezone_aware(start_dt):
                field_label = (
                    "'session.session_start'"
                    if session is not None
                    else "'user_start_time'"
                )
                errors.append(
                    f"{field_label} must be timezone-aware "
                    "(for example, '+05:30' or 'Z')."
                )
        except Exception as exc:
            field_label = (
                "'session.session_start'"
                if session is not None
                else "'user_start_time'"
            )
            errors.append(f"Invalid {field_label}: {exc}")

    raw_end = (
        session_dict.get("session_end")
        or session_dict.get("end_time")
        or session_dict.get("end")
        or request.get("session_end")
        or request.get("user_end_time")
    )

    end_dt: Optional[datetime] = None

    if raw_end:
        try:
            end_dt = parse_datetime(raw_end, "session_end")

            if require_timezone and not is_timezone_aware(end_dt):
                errors.append(
                    "Session end timestamp must be timezone-aware "
                    "(for example, '+05:30' or 'Z')."
                )
        except Exception as exc:
            errors.append(f"Invalid session end timestamp: {exc}")

    if start_dt and end_dt:
        if is_timezone_aware(start_dt) != is_timezone_aware(end_dt):
            errors.append(
                "Session start and end have mismatched timezone awareness."
            )
        elif end_dt <= start_dt:
            errors.append(
                "Session end must be strictly after session start."
            )

    raw_duration = (
        session_dict.get("available_duration")
        or session_dict.get("available_duration_minutes")
        or session_dict.get("duration_minutes")
        or request.get("total_available_duration_minutes")
        or request.get("available_duration")
        or request.get("available_duration_minutes")
    )

    duration_minutes: Optional[float] = None

    if raw_duration is not None:
        field_label = (
            "'session.available_duration'"
            if session is not None
            else "'total_available_duration_minutes'"
        )

        if isinstance(raw_duration, bool) or not isinstance(
            raw_duration, (int, float)
        ):
            errors.append(f"{field_label} must be numeric.")
        elif not math.isfinite(float(raw_duration)):
            errors.append(f"{field_label} cannot be NaN or Infinity.")
        elif raw_duration <= 0:
            errors.append(f"{field_label} must be strictly positive.")
        else:
            duration_minutes = float(raw_duration)

    elif start_dt and end_dt:
        span = (end_dt - start_dt).total_seconds() / 60.0

        if span > 0:
            duration_minutes = round(span, 2)

    if (
        duration_minutes is None
        and session is not None
        and not any("duration" in error.lower() for error in errors)
    ):
        errors.append(
            "Missing available duration. Provide "
            "'session.available_duration' or both session start and end."
        )

    raw_events = request.get("events")

    if raw_events is None and "celestial_events" in request:
        raw_events = request.get("celestial_events")

    if raw_events is None:
        errors.append("Missing required events list.")
    elif not isinstance(raw_events, list):
        errors.append(
            f"'events' must be a list, got {type(raw_events).__name__}."
        )

    preferences = (
        request.get("user_preferences")
        or request.get("preferences")
        or session_dict.get("preferences")
        or {}
    )

    if not isinstance(preferences, dict):
        errors.append("User preferences must be a dictionary.")
        preferences = {}

    custom_weights = preferences.get("weights")
    weight_errors, active_weights = validate_weights(custom_weights)
    errors.extend(weight_errors)

    if errors:
        return False, None, errors

    adapted_events: List[Dict[str, Any]] = []
    excluded_events: List[Dict[str, Any]] = []

    for index, event in enumerate(raw_events):
        event_errors, adapted_event = validate_and_adapt_event(
            ev=event,
            index=index,
            require_timezone=require_timezone,
            session_start_dt=start_dt,
        )

        if event_errors:
            score_error_keywords = (
                "between 0.0 and 100.0",
                "must be numeric",
                "cannot be nan",
                "missing 'visibility_score'",
                "missing 'weather_score'",
                "missing 'preference_score'",
                "missing 'duration_minutes'",
                "missing 'required_duration_minutes'",
            )

            duration_window_error = next(
                (
                    err for err in event_errors
                    if "Required duration exceeds total window span" in err
                ),
                None,
            )

            is_excludable = all(
                (
                    "Required duration exceeds total window span" in err
                    or any(
                        keyword in err.lower()
                        for keyword in score_error_keywords
                    )
                )
                for err in event_errors
            )

            if is_excludable:
                excluded_events.append({
                    "event_id": (
                        event.get("event_id") or event.get("id")
                        if isinstance(event, dict)
                        else None
                    ),
                    "name": (
                        event.get("name", f"event_{index}")
                        if isinstance(event, dict)
                        else f"event_{index}"
                    ),
                    "reason": (
                        duration_window_error
                        or "Required assessment scores are unavailable."
                    ),
                    "errors": event_errors,
                })
            else:
                errors.extend(event_errors)

        elif adapted_event is not None:
            adapted_events.append(adapted_event)

    if errors:
        return False, None, errors

    # Resolve the location once so its timezone can be used as a fallback.
    location_data = session_dict.get("location", request.get("location"))

    # Prefer an explicitly supplied session timezone, then a top-level timezone,
    # then the timezone associated with the location, and finally IST.
    location_timezone = (
        location_data.get("timezone")
        if isinstance(location_data, dict)
        else None
    )
    tz_from_dt = None
    if start_dt and start_dt.tzinfo:
        offset_str = start_dt.strftime("%z")
        if offset_str:
            tz_from_dt = f"UTC{offset_str[:3]}:{offset_str[3:]}"

    timezone_value = (
        session_dict.get("timezone")
        or request.get("timezone")
        or location_timezone
        or tz_from_dt
        or "Asia/Kolkata"
    )

    adapted_request = {
        "session": {
            "location": location_data,
            "timezone": timezone_value,
            "session_start": start_dt.isoformat() if start_dt else None,
            "session_end": end_dt.isoformat() if end_dt else None,
            "available_duration": duration_minutes,
            "observation_goal": session_dict.get(
                "observation_goal", request.get("observation_goal")
            ),
        },
        "user_start_time": start_dt.isoformat() if start_dt else None,
        "total_available_duration_minutes": duration_minutes,
        "weights": active_weights,
        "options": request.get("options") or {},
        "events": adapted_events,
        "excluded_events": excluded_events,
        "raw_request": request,
    }

    return True, adapted_request, []


# ============================================================
# Individual event validation
# ============================================================

def validate_and_adapt_event(
    ev: Any,
    index: int,
    require_timezone: bool,
    session_start_dt: Optional[datetime],
) -> Tuple[List[str], Optional[Dict[str, Any]]]:
    """
    Validate a candidate event and normalize field names.
    """
    errors: List[str] = []
    prefix = f"Event[{index}]"

    if not isinstance(ev, dict):
        return [
            f"{prefix}: Must be a dictionary, got {type(ev).__name__}."
        ], None

    name = ev.get("name")

    if not isinstance(name, str) or not name.strip():
        errors.append(f"{prefix}: 'name' must be a non-empty string.")
        event_label = f"index {index}"
    else:
        event_label = repr(name)

    for field in REQUIRED_EVENT_SCORES:
        if field not in ev:
            errors.append(f"{prefix} ({event_label}): Missing '{field}'.")
            continue
        if ev[field] is None:
            continue
        value = ev[field]

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{prefix} ({event_label}): '{field}' must be numeric.")
        elif not math.isfinite(float(value)):
            errors.append(f"{prefix} ({event_label}): '{field}' cannot be NaN.")
        elif not 0.0 <= float(value) <= 100.0:
            errors.append(
                f"{prefix} ({event_label}): '{field}' must be between 0.0 and 100.0."
            )

    if "window_start" in ev:
        window_start_raw = ev["window_start"]
    else:
        window_start_raw = ev.get("start_time")

    if "window_end" in ev:
        window_end_raw = ev["window_end"]
    else:
        window_end_raw = ev.get("end_time")

    if "window_start" not in ev and "start_time" not in ev:
        errors.append(
            f"{prefix} ({event_label}): Missing 'window_start'."
        )

    if "window_end" not in ev and "end_time" not in ev:
        errors.append(
            f"{prefix} ({event_label}): Missing 'window_end'."
        )

    duration_raw = ev.get("required_duration_minutes")

    if duration_raw is None:
        duration_raw = ev.get("duration_minutes")

    if (
        "required_duration_minutes" not in ev
        and "duration_minutes" not in ev
    ):
        errors.append(
            f"{prefix} ({event_label}): Missing 'duration_minutes'."
        )

    duration_field = (
        "required_duration_minutes"
        if ev.get("required_duration_minutes") is not None
        else "duration_minutes"
    )

    if isinstance(duration_raw, bool) or not isinstance(
        duration_raw, (int, float)
    ):
        errors.append(
            f"{prefix} ({event_label}): '{duration_field}' must be numeric."
        )
    elif not math.isfinite(float(duration_raw)):
        errors.append(
            f"{prefix} ({event_label}): '{duration_field}' must be finite."
        )
    elif duration_raw <= 0:
        errors.append(
            f"{prefix} ({event_label}): '{duration_field}' must be strictly positive."
        )

    window_start_dt: Optional[datetime] = None
    window_end_dt: Optional[datetime] = None

    try:
        window_start_dt = parse_datetime(
            window_start_raw, "window_start", name
        )

        if require_timezone and not is_timezone_aware(window_start_dt):
            errors.append(
                f"{prefix} ({event_label}): 'window_start' must be timezone-aware."
            )
    except Exception as exc:
        errors.append(
            f"{prefix} ({event_label}): Invalid 'window_start': {exc}"
        )

    try:
        window_end_dt = parse_datetime(
            window_end_raw, "window_end", name
        )

        if require_timezone and not is_timezone_aware(window_end_dt):
            errors.append(
                f"{prefix} ({event_label}): 'window_end' must be timezone-aware."
            )
    except Exception as exc:
        errors.append(
            f"{prefix} ({event_label}): Invalid 'window_end': {exc}"
        )

    if window_start_dt and window_end_dt:
        if is_timezone_aware(window_start_dt) != is_timezone_aware(window_end_dt):
            errors.append(
                f"{prefix} ({event_label}): Window timestamps have mismatched "
                "timezone awareness."
            )
        elif window_end_dt <= window_start_dt:
            errors.append(
                f"{prefix} ({event_label}): 'window_end' must be after 'window_start'."
            )
        else:
            window_minutes = (
                window_end_dt - window_start_dt
            ).total_seconds() / 60.0

            if (
                isinstance(duration_raw, (int, float))
                and not isinstance(duration_raw, bool)
                and math.isfinite(float(duration_raw))
                and float(duration_raw) > window_minutes
            ):
                errors.append(
                    f"{prefix} ({event_label}): Required duration exceeds "
                    f"total window span ({window_minutes:.1f} minutes)."
                )

    if session_start_dt and window_start_dt:
            if (
                is_timezone_aware(session_start_dt)
                != is_timezone_aware(window_start_dt)
            ):
                errors.append(
                    f"{prefix} ({event_label}): Event window and session start "
                    "have mismatched timezone awareness."
                )

    # Return validation errors before normalizing the event.
    if errors:
        return errors, None

    adapted_event = dict(ev)
    duration_value = float(duration_raw)

    adapted_event["duration_minutes"] = duration_value
    adapted_event["required_duration_minutes"] = duration_value
    adapted_event["window_start"] = window_start_dt.isoformat()
    adapted_event["window_end"] = window_end_dt.isoformat()

    adapted_event["event_type"] = (
        ev.get("event_type") or ev.get("type") or "Celestial Target"
    )
    adapted_event["type"] = adapted_event["event_type"]
    adapted_event["source"] = ev.get("source", "Unknown Source")

    adapted_event["event_id"] = (
        ev.get("event_id") or ev.get("id") or f"target_{index + 1:03d}"
    )

    return [], adapted_event


# ============================================================
# Public recommendation interface
# ============================================================

def generate_recommendations(request: dict) -> dict:
    """
    Public entry point for POST /api/v1/recommendations.

    Returns:
        status
        ranked_events
        recommendation
        data_quality
        errors
    """
    if not isinstance(request, dict):
        return {
            "status": "error",
            "ranked_events": [],
            "recommendation": {
                "summary": {},
                "schedule": [],
                "skipped_events": [],
                "explanation_mode": "deterministic",
                "explanations": {},
            },
            "data_quality": {
                "is_sample_data": False,
                "data_mode": "invalid_payload",
                "total_events": 0,
                "verified_events_count": 0,
                "demo_events_count": 0,
                "unverified_events_count": 0,
                "sources_detected": [],
                "quality_notes": "Payload must be a dictionary.",
            },
            "errors": [
                f"Request must be a dictionary, got {type(request).__name__}."
            ],
        }

    is_valid, adapted_request, validation_errors = (
        adapt_and_validate_request(request, require_timezone=True)
    )

    if not is_valid or adapted_request is None:
        raw_events = request.get("events")
        if not isinstance(raw_events, list):
            raw_events = request.get("celestial_events")

        if not isinstance(raw_events, list):
            raw_events = []

        return {
            "status": "error",
            "ranked_events": [],
            "recommendation": {
                "summary": {},
                "schedule": [],
                "skipped_events": [],
                "explanation_mode": "deterministic",
                "explanations": {},
            },
            "data_quality": evaluate_data_quality(raw_events, request),
            "errors": validation_errors,
        }

    events = adapted_request["events"]
    raw_request = adapted_request["raw_request"]
    weights = adapted_request["weights"]
    session_info = adapted_request["session"]
    user_start = adapted_request["user_start_time"]
    duration = adapted_request["total_available_duration_minutes"]
    options = adapted_request.get("options") or {}

    if not isinstance(options, dict):
        return {
            "status": "error",
            "ranked_events": [],
            "recommendation": {
                "summary": {},
                "schedule": [],
                "skipped_events": [],
                "explanation_mode": "deterministic",
                "explanations": {},
            },
            "data_quality": evaluate_data_quality(events, raw_request),
            "errors": ["'options' must be a dictionary."],
        }

    use_llm = options.get("use_llm", False)

    if not isinstance(use_llm, bool):
        return {
            "status": "error",
            "ranked_events": [],
            "recommendation": {
                "summary": {},
                "schedule": [],
                "skipped_events": [],
                "explanation_mode": "deterministic",
                "explanations": {},
            },
            "data_quality": evaluate_data_quality(events, raw_request),
            "errors": ["'options.use_llm' must be a boolean."],
        }

    # Do not accept secrets from client-supplied request payloads.
    # Configure the LLM key on the server if LLM explanations are enabled.
    if use_llm:
        return {
            "status": "error",
            "ranked_events": [],
            "recommendation": {
                "summary": {},
                "schedule": [],
                "skipped_events": [],
                "explanation_mode": "deterministic",
                "explanations": {},
            },
            "data_quality": evaluate_data_quality(events, raw_request),
            "errors": [
                "LLM explanations must be configured server-side before use."
            ],
        }

    data_quality = evaluate_data_quality(events, raw_request)
    if adapted_request.get("excluded_events"):
        data_quality["excluded_events"] = adapted_request["excluded_events"]

    excluded_events = adapted_request.get("excluded_events", [])

    # The route records provenance counts before merging automatically discovered
    # candidates. Direct callers default to treating their input list as client data.
    origin_counts = raw_request.get("event_origin_counts")
    if not isinstance(origin_counts, dict):
        origin_counts = {
            "client_events_received": len(raw_request.get("events") or raw_request.get("celestial_events") or []),
            "events_discovered": 0,
        }

    client_events_received = origin_counts.get("client_events_received", 0)
    events_discovered = origin_counts.get("events_discovered", 0)
    for count_name, count_value in (
        ("client_events_received", client_events_received),
        ("events_discovered", events_discovered),
    ):
        if isinstance(count_value, bool) or not isinstance(count_value, int) or count_value < 0:
            return {
                "status": "error",
                "ranked_events": [],
                "recommendation": {"summary": {}, "schedule": [], "skipped_events": []},
                "data_quality": data_quality,
                "errors": [f"event_origin_counts.{count_name} must be a non-negative integer."],
            }

    total_events_received = client_events_received + events_discovered

    
    if not events:
        return {
            "status": "empty",
            "ranked_events": [],
            "recommendation": {
                "summary": {
                    "client_events_received": client_events_received,
                    "events_discovered": events_discovered,
                    "total_events_received": total_events_received,
                    "total_events_evaluated": 0,
                    "total_events_excluded": len(excluded_events),
                    "total_events_scheduled": 0,
                    "total_events_skipped": 0,
                    "total_events_not_scheduled": len(excluded_events),
                    "user_available_minutes": duration,
                    "total_scheduled_minutes": 0.0,
                    "remaining_minutes": duration,
                    "session_start": session_info["session_start"],
                    "session_end": session_info["session_end"],
                    "location": session_info["location"],
                    "timezone": session_info["timezone"],
                    "observation_goal": session_info["observation_goal"],
                },
                "schedule": [],
                "skipped_events": [],
                "excluded_events": excluded_events, 
                "explanation_mode": "deterministic",
                "explanations": {
                    "mode": "deterministic",
                    "schedule_summary": (
                        "Observation schedule is empty: all discovered candidates "
                        "were excluded during validation."
                        if excluded_events
                        else "Observation schedule is empty: no events were provided or discovered."
                    ),
                    "event_explanations": {},
                    "llm_used": False,
                },
            },
            "data_quality": data_quality,
            "errors": [],
        }

    pipeline_result = run_pipeline_recommendations(
        events=events,
        user_start_time=user_start,
        total_available_duration_minutes=duration,
        weights=weights,
        session_end_time=session_info.get("session_end"),
    )

    explanation_result = explain_pipeline_output(
        pipeline_output=pipeline_result,
        use_llm=False,
    )

    ranked_events_out: List[Dict[str, Any]] = []

    for event in pipeline_result["ranked_events"]:
        ranked_item = dict(event)
        ranked_item["score_breakdown"] = build_score_breakdown(
            ranked_item, weights
        )

        if "event_type" not in ranked_item and "type" in ranked_item:
            ranked_item["event_type"] = ranked_item["type"]

        ranked_events_out.append(ranked_item)

    summary_data = dict(pipeline_result["summary"])
    summary_data["location"] = session_info["location"]
    summary_data["timezone"] = session_info["timezone"]
    summary_data["observation_goal"] = session_info["observation_goal"]

    schedule_out: List[Dict[str, Any]] = []

    for item in pipeline_result["observation_schedule"]:
        scheduled_event = dict(item)

        if "event_type" not in scheduled_event and "type" in scheduled_event:
            scheduled_event["event_type"] = scheduled_event["type"]

        schedule_out.append(scheduled_event)

    # Events rejected by the optimizer after successful validation.
    skipped_out = [
         dict(item)
        for item in pipeline_result["unscheduled_events"]
    ]

    # Events excluded during backend validation.
    excluded_out = [
        dict(item)
        for item in excluded_events
    ]

    # Keep scheduler skips distinct from validation exclusions.
    scheduler_skipped_count = len(pipeline_result["unscheduled_events"])
    summary_data["client_events_received"] = client_events_received
    summary_data["events_discovered"] = events_discovered
    summary_data["total_events_received"] = total_events_received
    summary_data["total_events_evaluated"] = len(events)
    summary_data["total_events_excluded"] = len(excluded_events)
    summary_data["total_events_scheduled"] = len(schedule_out)
    summary_data["total_events_skipped"] = scheduler_skipped_count
    summary_data["total_events_not_scheduled"] = (
        scheduler_skipped_count + len(excluded_events)
    )
    
    return {
        "status": "success",
        "ranked_events": ranked_events_out,
        "recommendation": {
            "summary": summary_data,
            "schedule": schedule_out,
            "skipped_events": skipped_out,
            "excluded_events": excluded_out,
            "explanation_mode": explanation_result.get(
            "mode", "deterministic"
            ),
            "explanations": explanation_result,
        },
        "data_quality": data_quality,
        "errors": [],
    }


# ============================================================
# Backward-compatibility functions
# ============================================================

def validate_backend_event(
    event: Any,
    index: int,
    require_timezone: bool = True,
) -> List[str]:
    """Preserve the validation function used by existing callers."""
    errors, _ = validate_and_adapt_event(
        ev=event,
        index=index,
        require_timezone=require_timezone,
        session_start_dt=None,
    )
    return errors


def validate_backend_request(
    payload: Any,
    require_timezone: bool = True,
) -> Tuple[bool, List[str]]:
    """Preserve the legacy request-validation interface."""
    is_valid, adapted_req, errors = adapt_and_validate_request(
        payload,
        require_timezone=require_timezone,
    )
    if adapted_req and adapted_req.get("excluded_events"):
        all_errs = list(errors)
        for excl in adapted_req["excluded_events"]:
            all_errs.extend(excl.get("errors", []))
        return False, all_errs
    return is_valid, errors


def process_backend_request(
    payload: Dict[str, Any],
    require_timezone: bool = True,
) -> Dict[str, Any]:
    """Preserve the earlier backend response structure."""
    response = generate_recommendations(payload)

    if response["status"] == "error":
        return {
            "status": "error",
            "data": None,
            "metadata": {
                "engine_version": "1.0.0",
                "is_sample_data": response["data_quality"]["is_sample_data"],
                "processed_at": datetime.now(timezone.utc).isoformat(),
            },
            "errors": response["errors"],
        }

    recommendation = response["recommendation"]

    return {
        "status": response["status"],
        "data": {
            "summary": recommendation["summary"],
            "observation_schedule": recommendation["schedule"],
            "ranked_events": response["ranked_events"],
            "unscheduled_events": recommendation["skipped_events"],
            "explanations": recommendation.get("explanations", {}),
        },
        "metadata": {
            "engine_version": "1.0.0",
            "is_sample_data": response["data_quality"]["is_sample_data"],
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
        "data_quality": response.get("data_quality", {}),
        "errors": response["errors"],
    }


def process_json_string(
    json_str: str,
    require_timezone: bool = True,
) -> Dict[str, Any]:
    """Process a JSON string using the optional JSON adapter."""
    try:
        from .json_adapter import run_pipeline_from_string
    except (ImportError, ValueError):
        from json_adapter import run_pipeline_from_string

    return run_pipeline_from_string(
        json_str,
        require_timezone=require_timezone,
    )


def process_json_file(
    input_path: Union[str, Any],
    output_path: Optional[Union[str, Any]] = None,
    require_timezone: bool = True,
) -> Dict[str, Any]:
    """Process a JSON file using the optional JSON adapter."""
    try:
        from .json_adapter import run_pipeline_from_file
    except (ImportError, ValueError):
        from json_adapter import run_pipeline_from_file

    return run_pipeline_from_file(
        input_path,
        output_path=output_path,
        require_timezone=require_timezone,
    )


