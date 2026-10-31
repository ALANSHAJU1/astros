from types import SimpleNamespace

from app.services.test_assessment_provider import get_test_assessment

event = SimpleNamespace(
    category="lunar",
    event_type="moon",
)

# "lunar" is not a configured key, so event_type "moon" is used.
result = get_test_assessment(event)

print(result)

assert result["visibility_score"] == 90
assert result["weather_score"] == 85
assert result["data_mode"] == "synthetic_test"
assert result["status"] == "success"

print("Assessment provider test passed.")
