
from typing import Any


# Initial development rules. Tune these with the team later.
GOAL_CATEGORY_PREFERENCES = {
    "moon_observation": {"moon", "lunar"},
    "planet_observation": {"planet", "planetary"},
    "meteor_shower": {"meteor_shower", "meteor"},
    "deep_sky": {"comet", "asteroid"},
    "general_observation": set(),
}


def calculate_preference_score(
    event: dict[str, Any],
    observation_goal: str = "general_observation",
    preferences: dict[str, Any] | None = None,
) -> float:
    """
    Return a preference score between 0 and 100.

    These are initial heuristic rules, not a trained AI model.
    """
    preferences = preferences or {}

    score = 70.0
    goal = observation_goal.strip().lower()

    event_type = str(event.get("event_type", "")).strip().lower()
    category = str(event.get("category", "")).strip().lower()
    event_name = str(event.get("name", event.get("object_name", ""))).strip().lower()

    preferred_categories = GOAL_CATEGORY_PREFERENCES.get(goal)

    if preferred_categories is None:
        # Unknown goals receive neutral treatment.
        preferred_categories = set()

    if preferred_categories:
        if category in preferred_categories or event_type in preferred_categories:
            score += 20
        else:
            score -= 15

    preferred_types = preferences.get("preferred_event_types", [])
    if isinstance(preferred_types, list) and preferred_types:
        normalized_types = {
            str(value).strip().lower() for value in preferred_types
        }
        if event_type in normalized_types or category in normalized_types:
            score += 10
        else:
            score -= 10

    preferred_names = preferences.get("preferred_objects", [])
    if isinstance(preferred_names, list) and preferred_names:
        normalized_names = {
            str(value).strip().lower() for value in preferred_names
        }
        if event_name in normalized_names:
            score += 10

    avoided_types = preferences.get("avoided_event_types", [])
    if isinstance(avoided_types, list):
        normalized_avoided = {
            str(value).strip().lower() for value in avoided_types
        }
        if event_type in normalized_avoided or category in normalized_avoided:
            score -= 30

    return max(0.0, min(100.0, score))
