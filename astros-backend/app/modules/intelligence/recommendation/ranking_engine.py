import math
from typing import Any, Dict, List, Optional

# Default heuristic weights (must sum to 1.0)
# Visibility (50%): Celestial altitude, magnitude, and dark-sky clarity
# Weather (30%): Cloud cover, humidity, and atmospheric seeing
# Preference (20%): User's targeted astronomical interests
DEFAULT_WEIGHTS: Dict[str, float] = {
    "visibility": 0.50,
    "weather": 0.30,
    "preference": 0.20,
}

REQUIRED_SCORE_FIELDS = {
    "visibility_score": "visibility",
    "weather_score": "weather",
    "preference_score": "preference",
}


def validate_event(event: Any, allow_missing: bool = False) -> None:
    """
    Validate that an event dictionary has all required fields, valid data types,
    and numerical scores within the valid range [0, 100].

    If allow_missing is True, score fields may be None or omitted.
    If allow_missing is False, all score fields must be present and non-None.

    Raises:
        TypeError: If event is not a dict or if score types are invalid.
        ValueError: If fields are missing, non-finite, or out of range.
    """
    if not isinstance(event, dict):
        raise TypeError(f"Event must be a dictionary, got {type(event).__name__}")

    if "name" not in event or not isinstance(event["name"], str) or not event["name"].strip():
        raise ValueError("Event must contain a non-empty string 'name' field.")

    event_name = event["name"]

    # Check for completely omitted required score keys
    missing_fields = [field for field in REQUIRED_SCORE_FIELDS if field not in event]
    if missing_fields:
        raise ValueError(
            f"Event '{event_name}' is missing required fields: {', '.join(missing_fields)}"
        )

    # Validate each score
    for field in REQUIRED_SCORE_FIELDS:
        value = event[field]
        if value is None:
            if allow_missing:
                continue
            raise TypeError(
                f"Field '{field}' in event '{event_name}' must be an int or float, got NoneType"
            )

        # In Python, bool is a subclass of int (True == 1, False == 0), so explicitly reject bool
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"Field '{field}' in event '{event_name}' must be an int or float, got {type(value).__name__}"
            )

        # Check for non-finite numbers (NaN, +Infinity, -Infinity)
        if math.isnan(value) or math.isinf(value):
            raise ValueError(
                f"Field '{field}' in event '{event_name}' contains a non-finite value ({value})."
            )

        # Check valid score range [0, 100]
        if not (0.0 <= float(value) <= 100.0):
            raise ValueError(
                f"Field '{field}' in event '{event_name}' must be between 0 and 100, got {value}."
            )


def calculate_score(
    event: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None,
) -> Optional[float]:
    """
    Compute the weighted recommendation score for a validated event.

    Policy for missing scores:
        When one or more scores are None (unavailable), weights are dynamically
        renormalized across the available dimensions.
        A score of 0.0 is treated as a genuine numeric value and included.
        If all scores are None, returns None to represent an unassessed candidate.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    available: Dict[str, float] = {}
    for field, dim in REQUIRED_SCORE_FIELDS.items():
        val = event.get(field)
        if val is not None:
            available[dim] = float(val)

    if not available:
        return None

    weight_sum = sum(weights.get(dim, 0.0) for dim in available)
    if weight_sum <= 0:
        return None

    final_score = sum(
        (weights.get(dim, 0.0) / weight_sum) * val
        for dim, val in available.items()
    )
    return round(final_score, 2)


def generate_explanation(
    event: Dict[str, Any],
    final_score: Optional[float],
    weights: Dict[str, float]
) -> str:
    """
    Generate a clear, human-readable explanation of why an event earned its score.
    Transparently reports effective weights when some dimensions are unavailable.
    """
    if final_score is None:
        return "Unassessed candidate (Score: None). No assessment scores available for evaluation."

    available_factors = []
    missing_factors = []
    available_weights_sum = 0.0

    for field, dim in REQUIRED_SCORE_FIELDS.items():
        val = event.get(field)
        if val is not None:
            available_weights_sum += weights.get(dim, 0.0)

    for field, dim in REQUIRED_SCORE_FIELDS.items():
        val = event.get(field)
        if val is not None:
            eff_wt = (weights.get(dim, 0.0) / available_weights_sum) if available_weights_sum > 0 else 0.0
            contrib = round(float(val) * eff_wt, 2)
            available_factors.append((dim, float(val), contrib, eff_wt))
        else:
            missing_factors.append(dim)

    # Assessment tier
    if final_score >= 80:
        tier = "Prime observation candidate"
    elif final_score >= 60:
        tier = "Favorable observation conditions"
    elif final_score >= 40:
        tier = "Challenging conditions / moderate priority"
    else:
        tier = "Unfavorable observation window"

    if not available_factors:
        return f"{tier} (Score: None). No assessment scores available for evaluation."

    available_factors.sort(key=lambda x: x[1], reverse=True)
    best_factor, best_val, _, _ = available_factors[0]
    worst_factor, worst_val, _, _ = available_factors[-1]

    breakdown_parts = [
        f"{dim.capitalize()}: +{contrib} pts ({eff_wt*100:.0f}% wt)"
        for dim, val, contrib, eff_wt in available_factors
    ]
    breakdown_str = ", ".join(breakdown_parts)

    explanation = (
        f"{tier} (Score: {final_score}/100). "
        f"Strongest factor: {best_factor} ({best_val:.1f}/100). "
        f"Limiting factor: {worst_factor} ({worst_val:.1f}/100). "
        f"Score breakdown -> {breakdown_str}."
    )
    if missing_factors:
        missing_names = ", ".join(m.capitalize() for m in missing_factors)
        explanation += f" Note: {missing_names} data was unavailable; weights renormalized."

    return explanation


def rank_events(
    events: List[Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
    allow_missing: bool = True,
) -> List[Dict[str, Any]]:
    """
    Validate, score, explain, and rank a list of celestial events.

    Args:
        events: List of event dictionaries.
        weights: Optional custom dictionary of weights for visibility, weather, and preference.
        allow_missing: If True, missing or None scores will be handled via weight renormalization.

    Returns:
        A list of enriched event dictionaries sorted from highest to lowest score,
        with 'rank', 'recommendation_score', 'explanation', and score metadata added.
    """
    if not isinstance(events, list):
        raise TypeError(f"Expected events to be a list, got {type(events).__name__}")

    if not events:
        return []

    # Use default weights if not provided
    active_weights = weights or DEFAULT_WEIGHTS

    # Validate weight values
    weight_sum = sum(active_weights.values())
    if not math.isclose(weight_sum, 1.0, rel_tol=1e-3):
        raise ValueError(f"Weights must sum to 1.0, current sum is {weight_sum:.3f}")

    processed_events = []

    for event in events:
        # Step 1: Validate input fields and ranges
        validate_event(event, allow_missing=allow_missing)

        # Step 2: Calculate recommendation score
        score = calculate_score(event, active_weights)

        # Step 3: Generate human-readable explanation
        explanation = generate_explanation(event, score, active_weights)

        # Step 4: Enrich event dictionary (creates a clean copy)
        enriched = dict(event)
        enriched["recommendation_score"] = score
        enriched["explanation"] = explanation

        # Metadata tracking missing scores and status (use dimension names)
        missing_dims = [
            dim for field, dim in REQUIRED_SCORE_FIELDS.items()
            if enriched.get(field) is None
        ]
        enriched["missing_scores"] = missing_dims
        if not missing_dims:
            enriched["score_status"] = "complete"
        elif len(missing_dims) < len(REQUIRED_SCORE_FIELDS):
            enriched["score_status"] = "partial"
        else:
            enriched["score_status"] = "unassessed"

        # Effective weights after renormalization
        available_weight_sum = sum(
            active_weights.get(dim, 0.0)
            for field, dim in REQUIRED_SCORE_FIELDS.items()
            if enriched.get(field) is not None
        )
        eff_weights = {}
        for field, dim in REQUIRED_SCORE_FIELDS.items():
            if enriched.get(field) is not None and available_weight_sum > 0:
                eff_weights[dim] = active_weights.get(dim, 0.0) / available_weight_sum
            else:
                eff_weights[dim] = 0.0
        enriched["effective_weights"] = eff_weights

        processed_events.append(enriched)

    # Step 5: Sort descending by recommendation score (None sorts last)
    ranked_events = sorted(
        processed_events,
        key=lambda ev: (ev["recommendation_score"] is not None, ev["recommendation_score"] or 0),
        reverse=True
    )

    # Step 6: Assign rank order (1-based index)
    for index, event in enumerate(ranked_events, start=1):
        event["rank"] = index

    return ranked_events


def get_sample_events() -> List[Dict[str, Any]]:
    """
    Returns illustrative sample celestial events for demonstration and testing.
    Note: These are mock scores for system testing, not live astronomical predictions.
    """
    return [
        {
            "name": "Jupiter Opposition",
            "type": "Planetary",
            "visibility_score": 92.0,
            "preference_score": 85.0,
            "weather_score": 88.0,
        },
        {
            "name": "Perseid Meteor Shower Peak",
            "type": "Meteor Shower",
            "visibility_score": 75.0,
            "preference_score": 95.0,
            "weather_score": 70.0,
        },
        {
            "name": "Comet C/2023 A3 Flyby",
            "type": "Comet",
            "visibility_score": 60.0,
            "preference_score": 90.0,
            "weather_score": 40.0,
        },
        {
            "name": "Lunar Eclipse Partial Phase",
            "type": "Eclipse",
            "visibility_score": 85.0,
            "preference_score": 65.0,
            "weather_score": 90.0,
        },
        {
            "name": "Overcast Sky ISS Pass",
            "type": "Satellite",
            "visibility_score": 50.0,
            "preference_score": 70.0,
            "weather_score": 15.0,
        },
    ]


if __name__ == "__main__":
    print("=" * 80)
    print(" AstrOS Celestial Event Ranking Engine - Demonstration")
    print("=" * 80)

    sample_data = get_sample_events()
    ranked = rank_events(sample_data)

    for item in ranked:
        print(f"\n[Rank #{item['rank']}] {item['name']} ({item['type']})")
        print(f"  Final Score : {item['recommendation_score']} / 100")
        print(f"  Visibility  : {item['visibility_score']} | Weather: {item['weather_score']} | User Preference: {item['preference_score']}")
        print(f"  Explanation : {item['explanation']}")

    print("\n" + "=" * 80)
    print("Demonstration completed successfully.")
    print("=" * 80)