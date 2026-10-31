from datetime import datetime
import json
import os
from typing import Any, Dict, List, Optional, Union
import urllib.error
import urllib.request


def explain_event_score(
    event: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None
) -> str:
    """
    Explain why a celestial event received its recommendation score using its
    actual input factors and weights.

    Never invents missing data; clearly marks missing scores as unavailable.
    """
    if not isinstance(event, dict):
        raise TypeError(f"Event must be a dictionary, got {type(event).__name__}.")

    name = event.get("name", "Unnamed Event")
    score = event.get("recommendation_score")

    # Use effective_weights from ranking_engine if present, preserving dynamic renormalization
    active_weights = event.get("effective_weights") or weights or {"visibility": 0.50, "weather": 0.30, "preference": 0.20}

    # Extract score factors
    vis = event.get("visibility_score")
    wea = event.get("weather_score")
    pref = event.get("preference_score")

    factor_descriptions = []
    missing_factors = []

    if vis is not None:
        vis_wt = active_weights.get("visibility", 0.50)
        vis_pts = round(float(vis) * vis_wt, 2)
        factor_descriptions.append(f"Visibility: {vis}/100 (+{vis_pts} pts, {vis_wt*100:.0f}% wt)")
    else:
        missing_factors.append("visibility")

    if wea is not None:
        wea_wt = active_weights.get("weather", 0.30)
        wea_pts = round(float(wea) * wea_wt, 2)
        factor_descriptions.append(f"Weather: {wea}/100 (+{wea_pts} pts, {wea_wt*100:.0f}% wt)")
    else:
        missing_factors.append("weather")

    if pref is not None:
        pref_wt = active_weights.get("preference", 0.20)
        pref_pts = round(float(pref) * pref_wt, 2)
        factor_descriptions.append(f"Preference: {pref}/100 (+{pref_pts} pts, {pref_wt*100:.0f}% wt)")
    else:
        missing_factors.append("preference")

    # Formulate explanation
    parts = []
    if score is not None:
        rank_str = f" (Rank #{event['rank']})" if "rank" in event else ""
        parts.append(f"Event '{name}' received an overall recommendation score of {score}/100{rank_str}.")
    else:
        parts.append(f"Event '{name}' has no overall recommendation score computed.")

    if factor_descriptions:
        parts.append("Scoring factors breakdown: " + "; ".join(factor_descriptions) + ".")

    if missing_factors:
        parts.append(f"Information unavailable: {', '.join(missing_factors)} score(s) were not supplied.")

    return " ".join(parts)


def explain_event_status(
    event_name: str,
    pipeline_output: Dict[str, Any]
) -> str:
    """
    Explain why a specific event was scheduled, skipped, or placed in the timeline
    using verified pipeline outputs.
    """
    if not isinstance(pipeline_output, dict):
        raise TypeError(f"pipeline_output must be a dictionary, got {type(pipeline_output).__name__}.")

    if not event_name or not isinstance(event_name, str):
        raise ValueError("event_name must be a non-empty string.")

    scheduled = pipeline_output.get("observation_schedule", [])
    unscheduled = pipeline_output.get("unscheduled_events", [])
    ranked = pipeline_output.get("ranked_events", [])

    # Find event across all lists
    sched_match = next((e for e in scheduled if e.get("name") == event_name), None)
    unsched_match = next((e for e in unscheduled if e.get("name") == event_name), None)
    ranked_match = next((e for e in ranked if e.get("name") == event_name), None)

    if not sched_match and not unsched_match and not ranked_match:
        return f"Event '{event_name}' was not found in the evaluated observation dataset."

    # Case 1: Scheduled event
    if sched_match:
        start = sched_match.get("scheduled_start", "time unavailable")
        end = sched_match.get("scheduled_end", "time unavailable")
        dur = sched_match.get("scheduled_duration_minutes", "unavailable")
        score = sched_match.get("recommendation_score", "unavailable")
        rank = sched_match.get("rank")
        rank_info = f"Rank #{rank} with " if rank else ""
        reason = sched_match.get("inclusion_explanation", "Successfully fit into observation timeline.")

        return (
            f"Event '{event_name}' is SCHEDULED. {rank_info}Score: {score}/100. "
            f"Observation Window: {start} to {end} ({dur} min). Details: {reason}"
        )

    # Case 2: Skipped / Unscheduled event
    if unsched_match:
        score_val = unsched_match.get("recommendation_score")
        score_str = f"{score_val}/100" if score_val is not None else "None"
        dur = unsched_match.get("duration_minutes", "unavailable")
        reason = unsched_match.get("reason", "Reason not specified in pipeline output.")
        rank_info = f"Rank #{ranked_match['rank']} with " if (ranked_match and "rank" in ranked_match) else ""

        return (
            f"Event '{event_name}' was SKIPPED. {rank_info}Score: {score_str} (Requires: {dur} min). "
            f"Exclusion Reason: {reason}"
        )

    # Case 3: Ranked but not processed into schedule
    if ranked_match:
        rank = ranked_match.get("rank", "unavailable")
        score_val = ranked_match.get("recommendation_score")
        score_str = f"{score_val}/100" if score_val is not None else "None"
        return (
            f"Event '{event_name}' was evaluated and ranked #{rank} with score {score_str}, "
            "but was not submitted to the observation schedule."
        )

    return f"Information for event '{event_name}' is unavailable."


def explain_observation_schedule(pipeline_output: Dict[str, Any]) -> str:
    """
    Generate a complete, human-readable summary of the observation session,
    timeline allocations, time budget utilization, and skipped events.
    """
    if not isinstance(pipeline_output, dict):
        raise TypeError(f"pipeline_output must be a dictionary, got {type(pipeline_output).__name__}.")

    summary = pipeline_output.get("summary", {})
    scheduled = pipeline_output.get("observation_schedule", [])
    unscheduled = pipeline_output.get("unscheduled_events", [])

    if not summary and not scheduled and not unscheduled:
        return "Observation schedule is empty: no events were evaluated."

    session_start = summary.get("session_start", "start time unavailable")
    session_end = summary.get("session_end", "end time unavailable")
    budget = summary.get("user_available_minutes", "unavailable")
    total_sched = summary.get("total_scheduled_minutes", 0.0)
    remaining = summary.get("remaining_minutes", "unavailable")

    lines = [
        "=== AstrOS Observation Session Plan ===",
        f"Session Duration: {session_start} to {session_end} (Total Budget: {budget} min).",
        f"Utilization: {total_sched} min scheduled, {remaining} min remaining.",
        f"Events Summary: {len(scheduled)} scheduled, {len(unscheduled)} skipped out of {summary.get('total_events_evaluated', len(scheduled) + len(unscheduled))} evaluated.",
    ]

    if scheduled:
        lines.append("\nScheduled Observation Timeline:")
        for idx, item in enumerate(scheduled, start=1):
            name = item.get("name", "Unknown Target")
            start = item.get("scheduled_start", "unknown")
            end = item.get("scheduled_end", "unknown")
            dur = item.get("scheduled_duration_minutes", "unknown")
            score_val = item.get("recommendation_score")
            score_str = f"{score_val}/100" if score_val is not None else "None"
            lines.append(f"  Slot #{idx}: '{name}' | {start} -> {end} ({dur} min) | Priority Score: {score_str}")
    else:
        lines.append("\nScheduled Observation Timeline: None (no events could be scheduled).")

    if unscheduled:
        lines.append("\nSkipped Events & Conflict Explanations:")
        for item in unscheduled:
            name = item.get("name", "Unknown Target")
            reason = item.get("reason", "No reason provided.")
            score_val = item.get("recommendation_score")
            score_str = f"{score_val}/100" if score_val is not None else "None"
            lines.append(f"  - '{name}' (Score: {score_str}): {reason}")

    return "\n".join(lines)


def generate_llm_explanation(
    verified_context: str,
    api_key: Optional[str] = None
) -> str:
    """
    Optional LLM integration to format verified observation plans into natural language.

    Guardrails:
        - Strict prompt forbidding fabrication of celestial targets, coordinates, or scores.
        - Reads API key from parameter or environment variable (GEMINI_API_KEY or GOOGLE_API_KEY).
        - If API key is missing or network call fails, raises RuntimeError to trigger fallback.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("No Gemini API key supplied in arguments or environment variables.")

    system_instruction = (
        "You are an astronomical observation explanation assistant for Team AstrOS. "
        "Strict Rule: Rely ONLY on the verified factual context provided below. "
        "Do NOT invent celestial positions, constellations, magnitudes, weather, or scores. "
        "Summarize the observation plan clearly for an amateur astronomer."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_instruction}\n\nVerified Context:\n{verified_context}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 800,
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates:
                text_parts = candidates[0].get("content", {}).get("parts", [])
                if text_parts and "text" in text_parts[0]:
                    llm_text = text_parts[0]["text"].strip()
                    if llm_text:
                        return llm_text
            raise RuntimeError("Empty or invalid candidate response from Gemini API.")
    except Exception as err:
        raise RuntimeError(f"Gemini API request failed: {err}") from err


def explain_pipeline_output(
    pipeline_output: Dict[str, Any],
    use_llm: bool = False,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Produce a complete explanation package for the AstrOS recommendation pipeline.

    Dual-Mode Architecture:
        - Deterministic explanations are ALWAYS generated first as ground truth.
        - If use_llm=True, attempts LLM synthesis of the ground truth.
        - Automatically falls back to deterministic output if LLM fails or is disabled.
    """
    if not isinstance(pipeline_output, dict):
        raise TypeError(f"pipeline_output must be a dictionary, got {type(pipeline_output).__name__}.")

    # Generate reliable deterministic explanations
    schedule_summary = explain_observation_schedule(pipeline_output)

    event_explanations: Dict[str, Dict[str, str]] = {}
    ranked_events = pipeline_output.get("ranked_events", [])
    for ev in ranked_events:
        name = ev.get("name", "Unknown")
        event_explanations[name] = {
            "score_explanation": explain_event_score(ev),
            "status_explanation": explain_event_status(name, pipeline_output),
        }

    response_package: Dict[str, Any] = {
        "mode": "deterministic",
        "schedule_summary": schedule_summary,
        "event_explanations": event_explanations,
        "llm_used": False,
        "fallback_reason": None,
    }

    if use_llm:
        try:
            llm_narrative = generate_llm_explanation(schedule_summary, api_key=api_key)
            response_package["mode"] = "llm"
            response_package["llm_summary"] = llm_narrative
            response_package["llm_used"] = True
        except Exception as err:
            response_package["mode"] = "deterministic (fallback)"
            response_package["fallback_reason"] = str(err)
            response_package["llm_used"] = False

    return response_package


if __name__ == "__main__":
    from recommendation_engine import generate_recommendations, get_sample_pipeline_events

    print("=" * 80)
    print(" Team AstrOS Explanation Engine - Demonstration")
    print("=" * 80)

    sample_events = get_sample_pipeline_events()
    session_start = "2026-10-14T20:00:00"
    session_budget = 150.0

    pipeline_result = generate_recommendations(
        sample_events,
        user_start_time=session_start,
        total_available_duration_minutes=session_budget
    )

    explanations = explain_pipeline_output(pipeline_result, use_llm=False)

    print("\n[DETERMINISTIC SCHEDULE SUMMARY]")
    print(explanations["schedule_summary"])

    print("\n" + "-" * 80)
    print("[EVENT-SPECIFIC EXPLANATIONS]")
    print("-" * 80)
    for event_name, exp in explanations["event_explanations"].items():
        print(f"\nTarget: {event_name}")
        print(f"  Score Logic : {exp['score_explanation']}")
        print(f"  Schedule    : {exp['status_explanation']}")

    print("\n" + "=" * 80)
    print(f"Explanation Engine demonstration completed (Mode: {explanations['mode']}).")
    print("=" * 80)