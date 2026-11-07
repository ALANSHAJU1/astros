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


def get_deterministic_target_advisory(
    name: str = "",
    category: str = "",
    magnitude: Optional[float] = None,
    score: float = 75.0,
) -> Dict[str, Any]:
    """Provide verified rule-based optical gear and observing guidance for any target."""
    n = (name or "").lower()
    cat = (category or "").lower()
    mag_str = f"apparent magnitude {magnitude}" if magnitude is not None else "prominent brightness"

    # 1. Solar Eclipses & Sun
    if "sun" in n or "sun" in cat or "solar" in cat or "solar eclipse" in n:
        return {
            "name": name or "Solar Event",
            "ai_narrative": "High-contrast daytime solar event. Certified safety filtration mandatory for all observers.",
            "naked_eye": "CRITICAL: Do NOT view unaided except during 100% totality! Use ISO 12312-2 certified eclipse glasses at all partial phases.",
            "binoculars": "Requires certified front-mounted Baader solar filters attached securely to objective lenses.",
            "telescope": "Requires full-aperture front solar filter (white-light) or dedicated H-alpha solar telescope to safely view sunspots, prominences, and flares.",
            "accessories": ["ISO 12312-2 Certified Eclipse Glasses", "Full-Aperture Solar Filter", "Solar Projection Screen"],
            "observing_tip": "Never point an unfiltered optical instrument at the Sun—instant irreversible eye damage will occur.",
        }

    # 2. Meteor Showers
    if "meteor" in cat or "meteor" in n or "shower" in n or "perseid" in n or "geminid" in n or "orionid" in n:
        return {
            "name": name or "Meteor Shower",
            "ai_narrative": "Stream of cometary/asteroidal debris burning up in the upper mesosphere, producing bright fireballs and glowing ion trains.",
            "naked_eye": "The optimal way to observe! Human peripheral vision captures fast streaks across a wide swath of the dark sky.",
            "binoculars": "Not recommended for general viewing; narrow field of view severely reduces chances of catching streaks.",
            "telescope": "Not recommended; field of view is too narrow (<1°) to catch sudden, unpredictable meteor streaks.",
            "accessories": ["Reclining Lawn Chair", "Warm Blanket / Sleeping Bag", "Red LED Flashlight"],
            "observing_tip": "Face 45° to 60° away from the radiant point after midnight when your horizon rotates into the debris stream.",
        }

    # 3. Lunar Eclipses
    if "lunar eclipse" in n or "blood moon" in n or "lunar_eclipse" in cat or ("lunar" in cat and "eclipse" in cat):
        return {
            "name": name or "Lunar Eclipse",
            "ai_narrative": "The Moon enters Earth's shadow, turning a dramatic coppery blood-red hue illuminated by refracted sunset light from around Earth.",
            "naked_eye": "100% safe to observe directly unaided; watch Earth's curved umbral shadow swallow the lunar surface.",
            "binoculars": "7x50 or 10x50 binoculars reveal rich color gradients between the dark charcoal umbra and copper-red totality.",
            "telescope": "Low magnification (30x–60x) provides a stunning view of the crimson lunar disk suspended among background stars.",
            "accessories": ["10x50 Binoculars", "Tripod Mount", "Camera on Tripod for long exposure"],
            "observing_tip": "Allow your eyes to dark-adapt during totality to see faint stars emerge around the darkened Moon.",
        }

    # 4. Moon
    if "moon" in n or "lunar" in cat:
        return {
            "name": name or "The Moon",
            "ai_narrative": "Earth's natural satellite displaying complex crater ejecta rays, basaltic maria, and mountainous rilles.",
            "naked_eye": "Easily visible naked eye; major maria ('seas') and ray craters like Tycho and Copernicus stand out.",
            "binoculars": "Shows sharp crater rims, mountain chains (Apennines), and shadows along the day/night terminator.",
            "telescope": "Any telescope at 50x–150x magnification delivers breathtaking 3D views of crater terraces, central peaks, and rilles.",
            "accessories": ["Neutral Density Lunar Filter", "Variable Polarizing Filter to tame glare"],
            "observing_tip": "Always observe along the terminator line where low-angle sunlight casts long shadows, revealing maximum surface topography.",
        }

    # 5. Jupiter
    if "jupiter" in n:
        return {
            "name": name or "Jupiter",
            "ai_narrative": f"Gas giant shining at {mag_str}. High surface brightness cuts easily through city light domes.",
            "naked_eye": "Brilliant silvery-gold beacon, outshining all stellar objects in the evening sky.",
            "binoculars": "Resolves the creamy disk and all four Galilean moons (Io, Europa, Ganymede, Callisto) lined up as pinpoint stars.",
            "telescope": "70mm–200mm+ at 80x–150x magnification reveals the dark reddish-brown Equatorial Belts, Great Red Spot, and moon transit shadows.",
            "accessories": ["Light-Blue Filter (Wratten 80A)", "Neutral Density Filter", "2x Barlow Lens"],
            "observing_tip": "Observe when Jupiter culminates near its highest altitude to minimize turbulent atmospheric refraction.",
        }

    # 6. Saturn
    if "saturn" in n:
        return {
            "name": name or "Saturn",
            "ai_narrative": f"The ringed jewel of the solar system shining with a warm, steady golden hue at {mag_str}.",
            "naked_eye": "Steady, non-twinkling yellowish-gold point of light.",
            "binoculars": "Appears as an elongated, oval-shaped disk; large 10x50 binoculars hint at the separation of the rings.",
            "telescope": "60mm–150mm+ at 75x–150x magnification clearly reveals the ring plane, the Cassini Division, and Saturn's largest moon Titan.",
            "accessories": ["Light-Yellow Filter (Wratten 12)", "Star Diagonal", "Plössl Eyepiece (9mm-15mm)"],
            "observing_tip": "Allow telescope optics 20–30 minutes to cool down to ambient air temperature for razor-sharp ring resolution.",
        }

    # 7. Mars
    if "mars" in n:
        return {
            "name": name or "Mars",
            "ai_narrative": f"The Red Planet with iron-oxide deserts and dynamic polar caps shining at {mag_str}.",
            "naked_eye": "Distinct, fiery amber-orange celestial beacon.",
            "binoculars": "Small, distinct orange-red disk.",
            "telescope": "100mm+ aperture at 100x–200x magnification resolves white polar ice caps and dark surface albedo markings (Syrtis Major).",
            "accessories": ["Red or Orange Filter (Wratten 21/23A)", "High-Power Eyepiece"],
            "observing_tip": "Be patient at the eyepiece; atmospheric turbulence fluctuates, revealing crisp surface markings during brief moments of still air.",
        }

    # 8. Venus
    if "venus" in n:
        return {
            "name": name or "Venus",
            "ai_narrative": "Shrouded in dense reflective sulfuric acid clouds, Venus is the brightest celestial object after the Sun and Moon.",
            "naked_eye": "Blinding silvery-white beacon in the twilight western or dawn eastern sky.",
            "binoculars": "Readily displays crescent or gibbous phases.",
            "telescope": "50x–100x magnification reveals dynamic phase progression similar to lunar phases.",
            "accessories": ["Neutral Density Filter", "Polarizing Filter to reduce overpowering glare"],
            "observing_tip": "Observe during twilight before full darkness; the lower sky contrast prevents glare from obscuring the phase boundary.",
        }

    # 9. Deep-Sky Objects (Galaxies, Nebulae, Clusters)
    if "deep" in cat or "dso" in cat or "galaxy" in cat or "nebula" in cat or "cluster" in cat or "m31" in n or "m42" in n or "m45" in n:
        is_cluster = "cluster" in cat or "pleiades" in n or "m45" in n or "m13" in n
        return {
            "name": name or "Deep-Sky Target",
            "ai_narrative": "Deep-space wonder millions of light-years away or thousands of light-years across our Milky Way.",
            "naked_eye": "Visible as a delicate, ghostly smudge or sparkling knot under dark skies (Bortle 1–4)." if is_cluster else "Requires dark skies to spot unaided.",
            "binoculars": "7x50 or 10x50 binoculars reveal open clusters as sparkling jewels and bright nebulae/galaxies as glowing ethereal clouds.",
            "telescope": "100mm–250mm+ at low-to-medium magnification (35x–80x) provides optimal contrast, resolving cluster stars, spiral arms, or gas clouds.",
            "accessories": ["Narrowband UHC or O-III Filter (for emission nebulae)", "Wide-Field 25mm Eyepiece"],
            "observing_tip": "Use 'averted vision'—look slightly to the side of the object so light strikes the more sensitive rod cells of your retina.",
        }

    # 10. Default / Comets / Asteroids
    return {
        "name": name or "Celestial Target",
        "ai_narrative": f"Observing opportunity evaluated and ranked #{score} by the AstroOS multi-criteria recommendation engine.",
        "naked_eye": "Look in direction of high elevation away from bright local artificial lighting.",
        "binoculars": "7x50 or 10x50 binoculars provide increased light gathering for faint targets.",
        "telescope": "Small-to-medium telescope (70mm+) reveals pinpoint structure, cometary comas, or asteroid movement against background stars.",
        "accessories": ["Star Chart / Planetarium App", "Red Flashlight"],
        "observing_tip": "Allow 20 minutes in the dark for full rhodopsin dark adaptation before observing faint targets.",
    }


def generate_deterministic_observation_advisory(
    pipeline_output: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate high-quality verified optical guidance deterministically without external API calls."""
    summary = pipeline_output.get("summary", {})
    ranked = pipeline_output.get("ranked_events", [])[:5]
    top_name = ranked[0].get("name", "celestial targets") if ranked else "the night sky"

    briefing = (
        f"AstroOS Intelligence evaluated your observing window and identified prime opportunities led by {top_name}. "
        "Top-ranked targets maximize elevation above the horizon to minimize atmospheric distortion, providing optimal contrast for optical equipment."
    )

    target_advisories = []
    for ev in ranked:
        name = ev.get("name", "Unknown")
        cat = (ev.get("category") or "").lower()
        mag = ev.get("apparent_magnitude")
        score = ev.get("recommendation_score") or ev.get("score", 75.0)

        target_advisories.append(get_deterministic_target_advisory(name, cat, mag, score))

    return {
        "executive_briefing": briefing,
        "target_advisories": target_advisories,
    }


def generate_llm_observation_advisory(
    pipeline_output: Dict[str, Any],
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Call Google Gemini 1.5 Flash to synthesize verified deterministic outputs into a natural-language
    astronomer debrief with detailed optical equipment recommendations (Naked Eye, Binoculars, Telescope).
    """
    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("No Gemini API key supplied in arguments or environment variables.")

    summary = pipeline_output.get("summary", {})
    ranked = pipeline_output.get("ranked_events", [])[:5]

    targets_context = []
    for ev in ranked:
        targets_context.append({
            "name": ev.get("name"),
            "category": ev.get("category"),
            "apparent_magnitude": ev.get("apparent_magnitude"),
            "altitude_deg": ev.get("target_altitude_deg") or ev.get("peak_elevation_deg"),
            "visibility_score": ev.get("visibility_score"),
            "weather_score": ev.get("weather_score"),
            "overall_score": ev.get("recommendation_score") or ev.get("score"),
            "rank": ev.get("rank"),
        })

    prompt_text = (
        "You are an astronomical observation explanation assistant and expert telescope guide for Team AstrOS.\n"
        "Strict Rule: Rely ONLY on the verified factual context provided below. "
        "Do NOT invent celestial positions, constellations, magnitudes, weather, or scores.\n\n"
        f"Verified Session Summary:\n{json.dumps(summary, default=str)}\n\n"
        f"Verified Ranked Targets:\n{json.dumps(targets_context, default=str)}\n\n"
        "Provide your response as a valid JSON object with the following schema:\n"
        "{\n"
        '  "executive_briefing": "A concise, engaging 2-3 sentence overview of tonight\'s observing highlights for the amateur astronomer.",\n'
        '  "target_advisories": [\n'
        "    {\n"
        '      "name": "Target Name",\n'
        '      "ai_narrative": "A lively 1-2 sentence description of why to observe this target tonight.",\n'
        '      "naked_eye": "How it looks with the naked eye (e.g. bright point in east, faint fuzz, invisible).",\n'
        '      "binoculars": "Details visible through 7x50 or 10x50 binoculars.",\n'
        '      "telescope": "Recommended aperture, magnification (e.g. 80x-150x), and visible surface/ring/nebula details.",\n'
        '      "accessories": "Recommended filters or gear (e.g. O-III, Moon filter, solar filter, red light).",\n'
        '      "observing_tip": "Practical technique (e.g. averted vision, thermal cooldown, best viewing angle)."\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1500,
            "responseMimeType": "application/json"
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
                    raw_json_str = text_parts[0]["text"].strip()
                    parsed = json.loads(raw_json_str)
                    if isinstance(parsed, dict) and "executive_briefing" in parsed:
                        return parsed
            raise RuntimeError("Empty or invalid candidate response from Gemini API.")
    except Exception as err:
        raise RuntimeError(f"Gemini API request failed: {err}") from err


def generate_llm_explanation(
    verified_context: str,
    api_key: Optional[str] = None
) -> str:
    """Legacy helper: generate natural-language string summary using Gemini."""
    try:
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("No Gemini API key supplied.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": f"Summarize observation plan clearly: {verified_context}"}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600}
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and "text" in parts[0]:
                    return parts[0]["text"].strip()
        return verified_context
    except Exception:
        return verified_context


def explain_pipeline_output(
    pipeline_output: Dict[str, Any],
    use_llm: bool = False,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Produce a complete explanation and optical equipment advisory package for the recommendation pipeline.

    Dual-Mode Architecture:
        - Deterministic explanations and equipment guides are ALWAYS generated as ground truth.
        - If use_llm=True, calls Gemini 1.5 Flash to synthesize the briefing and optical equipment advice.
        - Gracefully falls back to deterministic advisory if Gemini fails or is disabled.
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

    # Baseline deterministic advisory
    det_advisory = generate_deterministic_observation_advisory(pipeline_output)

    response_package: Dict[str, Any] = {
        "mode": "deterministic",
        "schedule_summary": schedule_summary,
        "event_explanations": event_explanations,
        "executive_briefing": det_advisory["executive_briefing"],
        "target_advisories": det_advisory["target_advisories"],
        "llm_used": False,
        "fallback_reason": None,
    }

    if use_llm:
        try:
            llm_advisory = generate_llm_observation_advisory(pipeline_output, api_key=api_key)
            response_package["mode"] = "llm"
            response_package["executive_briefing"] = llm_advisory.get("executive_briefing") or det_advisory["executive_briefing"]
            response_package["target_advisories"] = llm_advisory.get("target_advisories") or det_advisory["target_advisories"]
            response_package["llm_summary"] = response_package["executive_briefing"]
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