"""
Synthetic assessment provider for AstroOS development.

These values are test fixtures, not real weather forecasts
or verified astronomical visibility calculations.
"""

from typing import Any


TEST_ASSESSMENTS: dict[str, dict[str, Any]] = {
    "moon": {
        "visibility_score": 90,
        "weather_score": 85,
    },
    "planet": {
        "visibility_score": 80,
        "weather_score": 85,
    },
    "meteor_shower": {
        "visibility_score": 75,
        "weather_score": 80,
    },
    "eclipse": {
        "visibility_score": 95,
        "weather_score": 85,
    },
    "satellite": {
        "visibility_score": 70,
        "weather_score": 80,
    },
    "comet": {
        "visibility_score": 65,
        "weather_score": 80,
    },
    "asteroid": {
        "visibility_score": 50,
        "weather_score": 80,
    },
    # Deep-sky objects (Messier/NGC/IC catalog targets)
    "deep_sky": {
        "visibility_score": 72,
        "weather_score": 80,
    },
}




def get_test_assessment(event):
    """Return synthetic scores for supported database event types."""

    event_type = str(
        getattr(event, "event_type", "") or ""
    ).strip().lower()

    category = str(
        getattr(event, "category", "") or ""
    ).strip().lower()

    aliases = {
        "lunar": "moon",
        "full_moon": "moon",
        "new_moon": "moon",
        "moon_phase": "moon",
        "planetary": "planet",
        "meteor": "meteor_shower",
        "iss": "satellite",
        # Eclipse variants
        "solar_eclipse": "eclipse",
        "lunar_eclipse": "eclipse",
        # Deep-sky aliases
        "dso": "deep_sky",
        "deep-sky object": "deep_sky",
        "deep sky object": "deep_sky",
        "deep sky": "deep_sky",
    }

    key = aliases.get(event_type, event_type)

    if key not in TEST_ASSESSMENTS:
        key = aliases.get(category, category)

    assessment = TEST_ASSESSMENTS.get(key)

    if assessment is None:
        return {
            "visibility_score": None,
            "weather_score": None,
            "data_mode": "synthetic_test",
            "source": "test_assessment_provider",
            "status": "unavailable",
        }

    return {
        **assessment,
        "data_mode": "synthetic_test",
        "source": "test_assessment_provider",
        "status": "success",
    }
