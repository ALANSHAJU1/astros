
from app.services.preference_scoring import calculate_preference_score

moon_event = {
    "name": "Moon",
    "category": "lunar",
    "event_type": "moon",
}

moon_score = calculate_preference_score(
    moon_event,
    observation_goal="moon_observation",
)

planet_score = calculate_preference_score(
    {"name": "Jupiter", "category": "planet", "event_type": "planet"},
    observation_goal="moon_observation",
)

avoided_moon_score = calculate_preference_score(
    moon_event,
    observation_goal="moon_observation",
    preferences={"avoided_event_types": ["moon"]},
)

print("Moon preference score:", moon_score)
print("Planet preference score:", planet_score)
print("Avoided Moon score:", avoided_moon_score)

assert moon_score == 90.0
assert planet_score == 55.0
assert avoided_moon_score == 60.0

print("Preference scoring tests passed.")
