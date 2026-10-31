from datetime import datetime
import math
from typing import Any, Dict, List, Optional, Union

from .observation_optimizer import (
    optimize_observation_schedule,
    parse_datetime,
    validate_user_availability,
)

from .ranking_engine import DEFAULT_WEIGHTS, rank_events

# Import domain logic directly from existing modules (no duplicate logic)
from .observation_optimizer import (
    optimize_observation_schedule,
    parse_datetime,
    validate_user_availability,
)
from .ranking_engine import (
    DEFAULT_WEIGHTS,
    rank_events,
)


def normalize_event_fields(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure event dictionary fields are compatible between the Ranking Engine
    and the Observation Optimization Engine.

    Field mapping & defaults:
        - If 'start_time' is supplied without 'window_start', maps to 'window_start'.
        - If 'end_time' is supplied without 'window_end', maps to 'window_end'.
        - If 'duration_minutes' is omitted but start and end are provided,
          calculates the full window duration as default.

    Returns:
        A shallow copy of the event with standardized field names.
    """
    normalized = dict(event)

    # Normalize window start
    if "window_start" not in normalized and "start_time" in normalized:
        normalized["window_start"] = normalized["start_time"]

    # Normalize window end
    if "window_end" not in normalized and "end_time" in normalized:
        normalized["window_end"] = normalized["end_time"]

    # If duration_minutes is not explicitly set, attempt to derive it from window span
    if "duration_minutes" not in normalized and "window_start" in normalized and "window_end" in normalized:
        try:
            start_dt = parse_datetime(normalized["window_start"], "window_start", normalized.get("name"))
            end_dt = parse_datetime(normalized["window_end"], "window_end", normalized.get("name"))
            if end_dt > start_dt:
                normalized["duration_minutes"] = round((end_dt - start_dt).total_seconds() / 60.0, 2)
        except Exception:
            # Let downstream validator handle any format errors
            pass

    return normalized


def generate_recommendations(
    events: List[Dict[str, Any]],
    user_start_time: Union[datetime, str],
    total_available_duration_minutes: Union[int, float],
    weights: Optional[Dict[str, float]] = None,
    session_end_time: Optional[Union[datetime, str]] = None,
) -> Dict[str, Any]:
    """
    Execute the unified Team AstrOS recommendation pipeline.

    Args:
        events: List of celestial event dictionaries.
        user_start_time: ISO string or datetime when observer is ready.
        total_available_duration_minutes: Total minutes observer can spend.
        weights: Optional custom weighting for ranking criteria.

    Returns:
        A unified dictionary containing:
            - 'ranked_events': Full list of events ranked by multi-criteria score.
            - 'observation_schedule': Chronologically ordered observation timeline.
            - 'unscheduled_events': Events that could not fit with explicit reasons.
            - 'summary': High-level session metrics and time budget utilization.
    """
    if not isinstance(events, list):
        raise TypeError(f"events must be a list of dictionaries, got {type(events).__name__}.")

    # Validate user availability upfront
    user_start_dt, budget_minutes, user_end_dt = validate_user_availability(
        user_start_time, total_available_duration_minutes,session_end_time=session_end_time,
    )

    if not events:
        return {
            "ranked_events": [],
            "observation_schedule": [],
            "unscheduled_events": [],
            "summary": {
                "total_events_evaluated": 0,
                "total_events_scheduled": 0,
                "total_events_skipped": 0,
                "user_available_minutes": budget_minutes,
                "total_scheduled_minutes": 0.0,
                "remaining_minutes": budget_minutes,
                "session_start": user_start_dt.isoformat(),
                "session_end": user_end_dt.isoformat(),
            },
        }

    # Step 1: Normalize event fields across modules
    normalized_events = [normalize_event_fields(ev) for ev in events]

    # Step 2: Rank events using the existing Ranking Engine
    # Note: rank_events validates ranking scores (visibility, weather, preference)
    # and appends 'recommendation_score', 'rank', and 'explanation'
    ranked_events_list = rank_events(normalized_events, weights=weights)

    # Step 3: Optimize observation schedule using the existing Optimizer
    # Note: optimize_observation_schedule validates windows, timezones, and duration budgets
    optimization_result = optimize_observation_schedule(
        ranked_events=ranked_events_list,
        user_start_time=user_start_dt,
        total_available_duration_minutes=budget_minutes,
        session_end_time=session_end_time
    )

    # Step 4: Construct unified response package
    scheduled = optimization_result["scheduled_events"]
    unscheduled = optimization_result["unscheduled_events"]

    return {
        "ranked_events": ranked_events_list,
        "observation_schedule": scheduled,
        "unscheduled_events": unscheduled,
        "summary": {
            "total_events_evaluated": len(events),
            "total_events_scheduled": len(scheduled),
            "total_events_skipped": len(unscheduled),
            "user_available_minutes": budget_minutes,
            "total_scheduled_minutes": optimization_result["total_scheduled_minutes"],
            "remaining_minutes": optimization_result["remaining_minutes"],
            "session_start": optimization_result["session_start"],
            "session_end": optimization_result["session_end"],
        },
    }


def get_sample_pipeline_events() -> List[Dict[str, Any]]:
    """
    Returns illustrative mock celestial events containing both ranking criteria
    and observation window metadata for pipeline demonstration and integration testing.

    Note: These are mock scores and simulated observation windows for testing the engine,
    not live astronomical ephemeris predictions.
    """
    return [
        {
            "name": "Jupiter Opposition & Great Red Spot",
            "type": "Planetary",
            "visibility_score": 94.0,
            "weather_score": 90.0,
            "preference_score": 88.0,
            "window_start": "2026-10-14T20:00:00",
            "window_end": "2026-10-14T22:30:00",
            "duration_minutes": 45.0,
        },
        {
            "name": "Andromeda Galaxy (M31) Core Observation",
            "type": "Deep Sky",
            "visibility_score": 88.0,
            "weather_score": 85.0,
            "preference_score": 92.0,
            "window_start": "2026-10-14T20:45:00",
            "window_end": "2026-10-14T23:00:00",
            "duration_minutes": 50.0,
        },
        {
            "name": "Saturn Ring Shadow Transit",
            "type": "Planetary",
            "visibility_score": 80.0,
            "weather_score": 75.0,
            "preference_score": 85.0,
            "window_start": "2026-10-14T20:15:00",
            "window_end": "2026-10-14T21:15:00",
            "duration_minutes": 40.0,
        },
        {
            "name": "Perseid Meteor Shower Peak Activity",
            "type": "Meteor Shower",
            "visibility_score": 75.0,
            "weather_score": 80.0,
            "preference_score": 95.0,
            "window_start": "2026-10-14T22:00:00",
            "window_end": "2026-10-14T23:45:00",
            "duration_minutes": 35.0,
        },
        {
            "name": "Pleiades Star Cluster (M45)",
            "type": "Open Cluster",
            "visibility_score": 70.0,
            "weather_score": 70.0,
            "preference_score": 75.0,
            "window_start": "2026-10-14T22:45:00",
            "window_end": "2026-10-14T23:55:00",
            "duration_minutes": 30.0,
        },
    ]


if __name__ == "__main__":
    print("=" * 80)
    print(" Team AstrOS Unified Recommendation Pipeline - Demonstration")
    print("=" * 80)

    sample_events = get_sample_pipeline_events()
    session_start = "2026-10-14T20:00:00"
    session_duration = 150.0  # 2.5 hours

    pipeline_output = generate_recommendations(
        events=sample_events,
        user_start_time=session_start,
        total_available_duration_minutes=session_duration
    )

    summary = pipeline_output["summary"]
    print(f"\nObservation Session Window : {summary['session_start']} -> {summary['session_end']}")
    print(f"Total Available Budget     : {summary['user_available_minutes']} minutes")
    print(f"Total Scheduled Time       : {summary['total_scheduled_minutes']} minutes")
    print(f"Remaining Unused Time      : {summary['remaining_minutes']} minutes")
    print(f"Events Evaluated           : {summary['total_events_evaluated']}")
    print(f"Events Scheduled           : {summary['total_events_scheduled']}")
    print(f"Events Skipped             : {summary['total_events_skipped']}")

    print("\n" + "-" * 80)
    print("PHASE 1: RANKED CELESTIAL EVENTS (Full Catalog)")
    print("-" * 80)
    for ev in pipeline_output["ranked_events"]:
        print(f"[Rank #{ev['rank']}] {ev['name']} - Score: {ev['recommendation_score']}/100")
        print(f"  Scores Breakdown : Vis={ev['visibility_score']} | Wea={ev['weather_score']} | Pref={ev['preference_score']}")
        print(f"  AI Explanation   : {ev['explanation']}")

    print("\n" + "-" * 80)
    print("PHASE 2: FEASIBLE OBSERVATION SCHEDULE (Chronological Viewing Timeline)")
    print("-" * 80)
    for idx, slot in enumerate(pipeline_output["observation_schedule"], start=1):
        print(f"[Slot #{idx}] {slot['name']}")
        print(f"  Scheduled Time : {slot['scheduled_start']} -> {slot['scheduled_end']} ({slot['scheduled_duration_minutes']} min)")
        print(f"  Score / Priority: {slot['recommendation_score']}/100")
        print(f"  Reasoning      : {slot['inclusion_explanation']}")

    if pipeline_output["unscheduled_events"]:
        print("\n" + "-" * 80)
        print("PHASE 3: SKIPPED / EXCLUDED EVENTS")
        print("-" * 80)
        for item in pipeline_output["unscheduled_events"]:
            print(f"- {item['name']} (Score: {item['recommendation_score']}/100, Needs: {item['duration_minutes']} min):")
            print(f"    {item['reason']}")

    print("\n" + "=" * 80)
    print("Pipeline execution completed successfully.")
    print("=" * 80)