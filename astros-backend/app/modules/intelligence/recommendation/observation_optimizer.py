from datetime import datetime, timedelta, timezone
import math
from typing import Any, Dict, List, Optional, Tuple, Union


def parse_datetime(
    dt_val: Any,
    field_name: str,
    event_name: Optional[str] = None
) -> datetime:
    """
    Parse a datetime object or an ISO 8601 formatted string into a Python datetime.

    Raises:
        TypeError: If dt_val is not a datetime object or string.
        ValueError: If the string cannot be parsed as a valid ISO datetime.
    """
    prefix = f"Event '{event_name}': " if event_name else ""

    if isinstance(dt_val, bool):
        raise TypeError(f"{prefix}Field '{field_name}' cannot be a boolean.")

    if isinstance(dt_val, datetime):
        return dt_val

    if isinstance(dt_val, str):
        cleaned = dt_val.strip()
        if not cleaned:
            raise ValueError(f"{prefix}Field '{field_name}' cannot be an empty string.")
        try:
            # datetime.fromisoformat handles standard ISO 8601 strings (e.g. YYYY-MM-DDTHH:MM:SS)
            # Normalize trailing 'Z' / 'z' to '+00:00' for Python 3.10 compatibility
            if cleaned.endswith("Z") or cleaned.endswith("z"):
                iso_str = cleaned[:-1] + "+00:00"
            else:
                iso_str = cleaned
            return datetime.fromisoformat(iso_str)
        except (ValueError, TypeError) as err:
            raise ValueError(
                f"{prefix}Malformed timestamp in '{field_name}': '{dt_val}'. "
                "Expected ISO 8601 format (e.g. '2026-10-14T20:00:00')."
            ) from err

    raise TypeError(
        f"{prefix}Field '{field_name}' must be a datetime or ISO string, got {type(dt_val).__name__}."
    )


def is_timezone_aware(dt: datetime) -> bool:
    """
    Check if a datetime object is timezone-aware.
    """
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def validate_timezone_compatibility(
    user_dt: datetime,
    event_dt: datetime,
    field_name: str,
    event_name: str
) -> None:
    """
    Verify that user start time and event window datetimes both have compatible timezone status
    (both timezone-aware or both naive).

    Raises:
        ValueError: If one datetime is timezone-aware and the other is naive.
    """
    user_aware = is_timezone_aware(user_dt)
    event_aware = is_timezone_aware(event_dt)

    if user_aware != event_aware:
        user_status = "timezone-aware" if user_aware else "naive (no timezone)"
        event_status = "timezone-aware" if event_aware else "naive (no timezone)"
        raise ValueError(
            f"Incompatible timezone in event '{event_name}': 'user_start_time' is {user_status}, "
            f"but '{field_name}' is {event_status}. All timestamps must either be all aware or all naive."
        )



def validate_user_availability(
    user_start_time: Any,
    total_available_duration_minutes: Any,
    session_end_time: Any = None,
) -> Tuple[datetime, float, datetime]:
    """
    Validate the observation session window and observation time budget.

    Returns:
        Tuple of (user_start_dt, budget_minutes, user_end_dt).

    If session_end_time is provided, it defines the actual session boundary.
    Otherwise, the session end is derived from the available duration.
    """
    user_start_dt = parse_datetime(user_start_time, "user_start_time")

    # Validate the observation budget first.
    if (
        isinstance(total_available_duration_minutes, bool)
        or not isinstance(total_available_duration_minutes, (int, float))
    ):
        raise TypeError(
            "total_available_duration_minutes must be a number."
        )

    if not math.isfinite(float(total_available_duration_minutes)):
        raise ValueError(
            "total_available_duration_minutes cannot be NaN or Infinity."
        )

    if total_available_duration_minutes <= 0:
        raise ValueError(
            "total_available_duration_minutes must be strictly greater than 0."
        )

    budget_minutes = float(total_available_duration_minutes)

    # Use the explicit session end when supplied.
    if session_end_time is not None:
        user_end_dt = parse_datetime(session_end_time, "session_end")

        validate_timezone_compatibility(
            user_start_dt,
            user_end_dt,
            "session_end",
            "user session",
        )

        if user_end_dt <= user_start_dt:
            raise ValueError(
                "session_end must be later than session start."
            )
    else:
        # Backward-compatible behavior for callers without an explicit end.
        user_end_dt = user_start_dt + timedelta(minutes=budget_minutes)

    return user_start_dt, budget_minutes, user_end_dt


def validate_event(
    event: Any,
    user_start_dt: datetime
) -> Tuple[datetime, datetime, float, float]:
    """
    Validate a single celestial event dictionary.

    Required fields:
        - name (non-empty str)
        - recommendation_score (numeric, 0-100)
        - window_start (datetime / ISO str)
        - window_end (datetime / ISO str)
        - duration_minutes (numeric > 0)

    Returns:
        Tuple of (window_start_dt, window_end_dt, duration_minutes, recommendation_score)
    """
    if not isinstance(event, dict):
        raise TypeError(f"Event must be a dictionary, got {type(event).__name__}.")

    if "name" not in event or not isinstance(event["name"], str) or not event["name"].strip():
        raise ValueError("Event must contain a non-empty string 'name' field.")

    name = event["name"]

    required_fields = ["recommendation_score", "window_start", "window_end", "duration_minutes"]
    missing = [f for f in required_fields if f not in event]
    if missing:
        raise ValueError(
            f"Event '{name}' is missing required fields: {', '.join(missing)}."
        )

    # Validate recommendation score (None means unassessed)
    score = event["recommendation_score"]
    if score is not None:
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise TypeError(
                f"recommendation_score in event '{name}' must be numeric or None, got {type(score).__name__}."
            )
        if math.isnan(score) or math.isinf(score):
            raise ValueError(f"recommendation_score in event '{name}' contains a non-finite value.")
        if not (0.0 <= float(score) <= 100.0):
            raise ValueError(
                f"recommendation_score in event '{name}' must be between 0 and 100, got {score}."
            )
        score = float(score)

    # Validate duration_minutes
    duration = event["duration_minutes"]
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        raise TypeError(
            f"duration_minutes in event '{name}' must be numeric, got {type(duration).__name__}."
        )
    if math.isnan(duration) or math.isinf(duration):
        raise ValueError(f"duration_minutes in event '{name}' contains a non-finite value.")
    if duration <= 0:
        raise ValueError(
            f"duration_minutes in event '{name}' must be strictly greater than 0, got {duration}."
        )

    # Parse window timestamps
    win_start = parse_datetime(event["window_start"], "window_start", name)
    win_end = parse_datetime(event["window_end"], "window_end", name)

    # Validate timezone compatibility with user start time
    validate_timezone_compatibility(user_start_dt, win_start, "window_start", name)
    validate_timezone_compatibility(user_start_dt, win_end, "window_end", name)

    # Validate window chronological order
    if win_end <= win_start:
        raise ValueError(
            f"Event '{name}' has invalid window: window_end ({event['window_end']}) "
            f"must be strictly after window_start ({event['window_start']})."
        )

    window_span_minutes = (win_end - win_start).total_seconds() / 60.0
    # If the event duration exceeds its observation window, we now allow the optimizer to handle it.
    pass

    return win_start, win_end, float(duration), (float(score) if score is not None else None)


def intervals_overlap(
    start_a: datetime, end_a: datetime,
    start_b: datetime, end_b: datetime
) -> bool:
    """
    Check if two time intervals [start_a, end_a] and [start_b, end_b] overlap.
    Touching at the boundary (e.g. 21:00 and 21:00) is considered non-overlapping.
    """
    return max(start_a, start_b) < min(end_a, end_b)


def find_earliest_slot(
    effective_start: datetime,
    effective_end: datetime,
    duration_td: timedelta,
    scheduled_intervals: List[Tuple[datetime, datetime, str]]
) -> Optional[Tuple[datetime, datetime]]:
    """
    Find the earliest continuous slot of length duration_td inside
    [effective_start, effective_end] that does not overlap with any already scheduled intervals.

    Returns:
        (slot_start, slot_end) if a valid slot is found, else None.
    """
    if effective_start + duration_td > effective_end:
        return None

    # Candidate start times to test:
    #   - effective_start
    #   - end times of already scheduled intervals within the window
    #   - a slot that ends exactly at effective_end (latest possible start)
    candidate_starts = [effective_start]
    for s_start, s_end, _ in scheduled_intervals:
        if effective_start <= s_end <= effective_end:
            candidate_starts.append(s_end)

    # Add latest possible start that would finish at effective_end
    latest_start = effective_end - duration_td
    if latest_start >= effective_start:
        candidate_starts.append(latest_start)

    # Remove duplicates and sort in descending order to prefer later slots
    candidate_starts = sorted(set(candidate_starts))

    for start_candidate in candidate_starts:
        end_candidate = start_candidate + duration_td
        # Ensure the slot stays within the effective window
        if end_candidate > effective_end or start_candidate < effective_start:
            continue
        # Check for overlap with existing intervals
        conflict = any(
            intervals_overlap(start_candidate, end_candidate, s_start, s_end)
            for s_start, s_end, _ in scheduled_intervals
        )
        if not conflict:
            return (start_candidate, end_candidate)

    return None


def optimize_observation_schedule(
    ranked_events: List[Dict[str, Any]],
    user_start_time: Union[datetime, str],
    total_available_duration_minutes: Union[int, float],
    session_end_time: Optional[Union[datetime, str]] = None,
) -> Dict[str, Any]:
    """
    Generate a feasible celestial observation timeline from ranked events,
    constrained by user availability and target observation windows.

    Algorithm (Priority-Greedy Earliest-Slot Heuristic):
        1. Validate user start time and total duration budget.
        2. Validate each event (timestamps, score, duration <= window).
        3. Sort events descending by recommendation_score (highest priority first).
        4. For each event:
           a. Check if adding event duration exceeds remaining total duration budget.
           b. Intersect event observation window with user availability window.
           c. Search for the earliest non-overlapping slot in that intersection.
           d. If a slot is found, schedule it; otherwise, record rejection reason.
        5. Sort scheduled events chronologically by scheduled start time.

    Returns:
        Dictionary containing:
            - 'scheduled_events': Chronologically sorted list of scheduled event details.
            - 'total_scheduled_minutes': Total minutes allocated to observations.
            - 'user_available_minutes': The user's input duration budget.
            - 'remaining_minutes': Unallocated observation time.
            - 'session_start': User start datetime in ISO format.
            - 'session_end': User end datetime in ISO format.
            - 'unscheduled_events': List of skipped events with explanatory reasons.
    """
    if not isinstance(ranked_events, list):
        raise TypeError(
            f"ranked_events must be a list of event dictionaries, got {type(ranked_events).__name__}."
        )

    user_start_dt, budget_minutes, user_end_dt = validate_user_availability(
        user_start_time, total_available_duration_minutes,session_end_time=session_end_time
    )

    if not ranked_events:
        return {
            "scheduled_events": [],
            "total_scheduled_minutes": 0.0,
            "user_available_minutes": budget_minutes,
            "remaining_minutes": budget_minutes,
            "session_start": user_start_dt.isoformat(),
            "session_end": user_end_dt.isoformat(),
            "unscheduled_events": [],
        }

    # Validate all candidate events
    parsed_events = []
    for ev in ranked_events:
        win_start, win_end, duration, score = validate_event(ev, user_start_dt)
        parsed_events.append({
            "original": ev,
            "name": ev["name"],
            "score": score,
            "duration": duration,
            "win_start": win_start,
            "win_end": win_end,
        })

    # Sort candidates by recommendation_score descending (None sorts last)
    parsed_events.sort(
        key=lambda x: (x["score"] is not None, x["score"] if x["score"] is not None else -1.0),
        reverse=True
    )

    scheduled = []
    unscheduled = []
    # List of tuples: (slot_start, slot_end, event_name)
    scheduled_intervals: List[Tuple[datetime, datetime, str]] = []
    total_scheduled_duration = 0.0

    for candidate in parsed_events:
        name = candidate["name"]
        score = candidate["score"]
        dur = candidate["duration"]
        win_start = candidate["win_start"]
        win_end = candidate["win_end"]
        dur_td = timedelta(minutes=dur)

        orig = candidate["original"]
        # Check 0: An event with unavailable visibility assessment or unassessed score
        # should not be treated as a validated observation recommendation and scheduled.
        is_unassessed = (
            score is None
            or orig.get("recommendation_score") is None
            or orig.get("score_status") == "unassessed"
            or orig.get("assessment_status") == "unavailable"
        )
        if is_unassessed:
            limits = orig.get("limitations") or []
            lim_desc = f" ({'; '.join(limits)})" if limits else ""
            unscheduled.append({
                "name": name,
                "recommendation_score": None,
                "score": None,
                "duration_minutes": dur,
                "reason": (
                    f"Skipped: Visibility assessment is unavailable{lim_desc}. "
                    "Cannot schedule unverified target as a validated recommendation."
                )
            })
            continue

        # Check 1: Does adding this duration exceed remaining total budget?
        if total_scheduled_duration + dur > budget_minutes:
            remaining = round(budget_minutes - total_scheduled_duration, 2)
            unscheduled.append({
                "name": name,
                "recommendation_score": score,
                "score": score,
                "duration_minutes": dur,
                "reason": (
                    f"Skipped: Required duration ({dur} min) exceeds remaining time budget "
                    f"({remaining} min out of {budget_minutes} min total)."
                )
            })
            continue

        # Check 2: Compute effective window (intersection of event window and user session)
        effective_start = max(win_start, user_start_dt)
        effective_end = min(win_end, user_end_dt)

        if effective_start + dur_td > effective_end:
            unscheduled.append({
                "name": name,
                "recommendation_score": score,
                "score": score,
                "duration_minutes": dur,
                "reason": (
                    f"Skipped: Event visibility window ({win_start.strftime('%H:%M')} - {win_end.strftime('%H:%M')}) "
                    f"does not offer enough overlapping time with user session "
                    f"({user_start_dt.strftime('%H:%M')} - {user_end_dt.strftime('%H:%M')}) "
                    f"to fit the required {dur} minutes."
                )
            })
            continue

        # Check 3: Find earliest non-overlapping slot
        slot = find_earliest_slot(effective_start, effective_end, dur_td, scheduled_intervals)
        if slot is None:
            # Identify which scheduled events overlap with the candidate's effective window
            overlapping_names = [
                s_name for s_start, s_end, s_name in scheduled_intervals
                if intervals_overlap(effective_start, effective_end, s_start, s_end)
            ]
            conflict_desc = f"conflicts with higher-priority event(s): {', '.join(overlapping_names)}" if overlapping_names else "no continuous slot available"
            unscheduled.append({
                "name": name,
                "recommendation_score": score,
                "score": score,
                "duration_minutes": dur,
                "reason": f"Skipped: {conflict_desc} within effective window ({effective_start.strftime('%H:%M')} - {effective_end.strftime('%H:%M')})."
            })
            continue

        # Feasible: Schedule the event
        slot_start, slot_end = slot
        scheduled_intervals.append((slot_start, slot_end, name))
        total_scheduled_duration = round(total_scheduled_duration + dur, 2)
        remaining = round(budget_minutes - total_scheduled_duration, 2)

        scheduled_item = dict(candidate["original"])
        scheduled_item["scheduled_start"] = slot_start.isoformat()
        scheduled_item["scheduled_end"] = slot_end.isoformat()
        scheduled_item["scheduled_duration_minutes"] = dur
        scheduled_item["recommendation_score"] = score
        scheduled_item["inclusion_explanation"] = (
            f"Scheduled from {slot_start.strftime('%H:%M')} to {slot_end.strftime('%H:%M')} "
            f"({dur} min). Selected due to high recommendation score ({score}/100) and fits "
            f"cleanly within visibility window without overlap. Leaves {remaining} min available."
        )
        scheduled.append(scheduled_item)

    # Sort scheduled events chronologically for the observer's viewing schedule
    scheduled.sort(key=lambda ev: ev["scheduled_start"])

    return {
        "scheduled_events": scheduled,
        "total_scheduled_minutes": total_scheduled_duration,
        "user_available_minutes": budget_minutes,
        "remaining_minutes": round(budget_minutes - total_scheduled_duration, 2),
        "session_start": user_start_dt.isoformat(),
        "session_end": user_end_dt.isoformat(),
        "unscheduled_events": unscheduled,
    }


def get_sample_candidate_events() -> List[Dict[str, Any]]:
    """
    Returns illustrative mock celestial events for demonstration and testing.
    Note: These are mock scores and simulated observation windows for testing the engine,
    not live astronomical ephemeris predictions.
    """
    return [
        {
            "name": "Jupiter Great Red Spot Transit",
            "type": "Planetary",
            "recommendation_score": 92.5,
            "window_start": "2026-10-14T20:00:00",
            "window_end": "2026-10-14T22:00:00",
            "duration_minutes": 45.0,
        },
        {
            "name": "Saturn Ring Shadow Viewing",
            "type": "Planetary",
            "recommendation_score": 85.0,
            "window_start": "2026-10-14T20:15:00",
            "window_end": "2026-10-14T21:15:00",
            "duration_minutes": 40.0,
        },
        {
            "name": "Andromeda Galaxy (M31) High Altitude",
            "type": "Deep Sky",
            "recommendation_score": 89.0,
            "window_start": "2026-10-14T21:00:00",
            "window_end": "2026-10-14T23:30:00",
            "duration_minutes": 50.0,
        },
        {
            "name": "Perseid Meteor Flare Peak",
            "type": "Meteor Shower",
            "recommendation_score": 78.0,
            "window_start": "2026-10-14T22:00:00",
            "window_end": "2026-10-14T23:45:00",
            "duration_minutes": 30.0,
        },
        {
            "name": "Pleiades Star Cluster Transit",
            "type": "Deep Sky",
            "recommendation_score": 74.0,
            "window_start": "2026-10-14T23:00:00",
            "window_end": "2026-10-14T23:55:00",
            "duration_minutes": 35.0,
        },
    ]


if __name__ == "__main__":
    print("=" * 80)
    print(" AstrOS Observation Optimization Engine - Demonstration")
    print("=" * 80)

    sample_candidates = get_sample_candidate_events()
    session_start = "2026-10-14T20:00:00"
    session_duration = 150.0  # 2.5 hours total time budget

    result = optimize_observation_schedule(
        sample_candidates,
        user_start_time=session_start,
        total_available_duration_minutes=session_duration
    )

    print(f"\nUser Session Start        : {result['session_start']}")
    print(f"User Session End          : {result['session_end']}")
    print(f"Total Available Budget    : {result['user_available_minutes']} minutes")
    print(f"Total Scheduled Time      : {result['total_scheduled_minutes']} minutes")
    print(f"Remaining Time            : {result['remaining_minutes']} minutes\n")

    print("-" * 80)
    print("CHRONOLOGICAL OBSERVATION TIMELINE:")
    print("-" * 80)
    for idx, event in enumerate(result["scheduled_events"], start=1):
        print(f"\n[Slot #{idx}] {event['name']} ({event.get('type', 'Target')})")
        print(f"  Visibility Window : {event['window_start']} -> {event['window_end']}")
        print(f"  Scheduled Slot    : {event['scheduled_start']} -> {event['scheduled_end']} ({event['scheduled_duration_minutes']} min)")
        print(f"  Priority Score    : {event['recommendation_score']} / 100")
        print(f"  Reasoning         : {event['inclusion_explanation']}")

    if result["unscheduled_events"]:
        print("\n" + "-" * 80)
        print("EXCLUDED EVENTS & REASONING:")
        print("-" * 80)
        for item in result["unscheduled_events"]:
            print(f"- {item['name']} (Score: {item['recommendation_score']}/100, Needs: {item['duration_minutes']} min):")
            print(f"    {item['reason']}")

    print("\n" + "=" * 80)
    print("Demonstration completed successfully.")
    print("=" * 80)


