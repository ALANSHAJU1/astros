from datetime import datetime, timezone
from typing import Any

from app.models.environmental_observation import EnvironmentalObservation
from app.services.environmental_freshness import (
    classify_observation_freshness,
)


def build_environmental_context(
    observation: EnvironmentalObservation | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a transparent environmental context for visibility assessment.

    This function does not calculate visibility scores. It reports which
    environmental information is available and its reliability status.
    """
    current_time = now or datetime.now(timezone.utc)

    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("now must include a timezone")

    if observation is None:
        return {
            "environmental_data_available": False,
            "freshness_status": "unknown",
            "source": None,
            "is_synthetic": False,
            "factors": {},
            "limitations": [
                "No environmental observation is available."
            ],
        }

    freshness = classify_observation_freshness(
        observation,
        now=current_time,
    )

    source = observation.source
    additional_data = observation.additional_data or {}

    is_synthetic = (
        "synthetic" in source.lower()
        or additional_data.get("data_type") == "synthetic_test"
    )

    factors = {
        "temperature_celsius": observation.temperature_celsius,
        "humidity": observation.humidity,
        "cloud_cover": observation.cloud_cover,
        "conditions": observation.conditions,
        "environmental_observed_at": (
            observation.observed_at.isoformat()
        ),
    }

    limitations = []

    if freshness != "fresh":
        limitations.append(
            f"Environmental observation freshness is {freshness}."
        )

    if is_synthetic:
        limitations.append(
            "Environmental data is synthetic and must not be "
            "presented as live weather."
        )

    if observation.cloud_cover is None:
        limitations.append("Cloud-cover data is unavailable.")

    return {
        "environmental_data_available": True,
        "freshness_status": freshness,
        "source": source,
        "is_synthetic": is_synthetic,
        "factors": factors,
        "limitations": limitations,
    }
