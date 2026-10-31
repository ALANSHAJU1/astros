"""Astronomy module adapter interface.

Provides an event-specific interface for astronomical calculations
(altitude, target magnitude, lunar illumination, geometry, twilight).
Where astronomical calculations are not provided or verified,
it explicitly avoids fabricating astronomical numbers.
"""

from __future__ import annotations

from typing import Any, Mapping
from pydantic import BaseModel, Field


class AstronomicalAssessment(BaseModel):
    """Event-specific astronomical visibility data and calculable score."""

    is_calculable: bool = Field(
        ...,
        description="True only if sufficient validated astronomical inputs exist.",
    )
    astronomical_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Heuristic astronomical score (0-100), or None if not calculable.",
    )
    factors: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    adapter_source: str = Field(default="astronomy_adapter_v1")


class BaseAstronomyAdapter:
    """Base interface for astronomy adapters (e.g. Hathim's module or future ephemeris)."""

    def evaluate_celestial_event(
        self,
        event: Any,
        latitude: float,
        longitude: float,
        bortle_class: int | None = None,
    ) -> AstronomicalAssessment:
        """Evaluate a celestial event, supporting both object and dict representations.

        The original implementation accessed attributes via ``getattr`` and assumed an ``additional_data`` attribute.
        Tests provide plain dictionaries, so we now detect ``dict`` instances and extract the required fields
        from keys accordingly.
        """
        if isinstance(event, dict):
            # Extract fields from dict structure used in tests
            category = str(event.get("category", "")).strip().lower()
            event_type = str(event.get("event_type", "")).strip().lower()
            extra = event.get("additional_data", {}) or {}
        else:
            category = str(getattr(event, "category", "") or "").strip().lower()
            event_type = str(getattr(event, "event_type", "") or "").strip().lower()
            extra: Mapping[str, Any] = getattr(event, "additional_data", {}) or {}

        # Check if verified astronomical calculations are provided in event metadata
        target_altitude = extra.get("target_altitude_deg") or extra.get("altitude")
        target_magnitude = extra.get("apparent_magnitude") or extra.get("magnitude")
        moon_illumination = extra.get("moon_illumination_percent")
        zhr = extra.get("zenithal_hourly_rate") or extra.get("zhr")
        is_illuminated = extra.get("is_sunlit")

        factors: dict[str, Any] = {
            "category": category,
            "event_type": event_type,
            "target_altitude_deg": target_altitude,
            "apparent_magnitude": target_magnitude,
            "moon_illumination_percent": moon_illumination,
            "bortle_class": bortle_class,
        }

        # If essential astronomical ephemeris (like altitude or magnitude) is missing:
        if target_altitude is None and target_magnitude is None and zhr is None:
            return AstronomicalAssessment(
                is_calculable=False,
                astronomical_score=None,
                factors=factors,
                limitations=[
                    "Astronomical inputs (target altitude, apparent magnitude, or ephemeris geometry) "
                    "are not provided in event data. Astronomical visibility score cannot be calculated."
                ],
                adapter_source="celestial_event_adapter_v1",
            )

        limitations: list[str] = []
        score = 100.0

        # Category-specific heuristic evaluations
        if category in ("lunar", "moon") or "moon" in event_type:
            if target_altitude is not None:
                alt = float(target_altitude)
                if alt < 10.0:
                    score -= 40.0
                    limitations.append(f"Low Moon altitude ({alt:.1f}°); severe atmospheric dispersion.")
                elif alt < 25.0:
                    score -= 15.0

        elif category in ("planet", "planetary") or "planet" in event_type:
            if target_altitude is not None:
                alt = float(target_altitude)
                if alt < 15.0:
                    score -= 35.0
                    limitations.append(f"Planet low above horizon ({alt:.1f}°).")
                elif alt < 30.0:
                    score -= 10.0
            if target_magnitude is not None:
                mag = float(target_magnitude)
                if mag > 5.0:
                    score -= 20.0
                    limitations.append(f"Faint planetary target (mag {mag:.1f}).")

        elif category in ("meteor_shower", "meteor") or "meteor" in event_type:
            if moon_illumination is not None and float(moon_illumination) > 50.0:
                score -= 30.0
                limitations.append(f"Bright moonlight ({moon_illumination}%) reduces faint meteor visibility.")
            if bortle_class is not None and bortle_class >= 6:
                score -= 25.0
                limitations.append(f"High urban light pollution (Bortle {bortle_class}) washes out meteors.")
            if target_altitude is not None and float(target_altitude) < 20.0:
                score -= 20.0
                limitations.append(f"Radiant is low ({target_altitude}°).")

        elif category == "eclipse" or "eclipse" in event_type:
            if target_altitude is not None and float(target_altitude) < 5.0:
                score -= 50.0
                limitations.append("Target near or below horizon during eclipse.")

        elif category in ("satellite", "visible_pass") or "satellite" in event_type:
            if is_illuminated is False:
                score = 0.0
                limitations.append("Satellite is in Earth's shadow (eclipsed).")
            elif target_altitude is not None and float(target_altitude) < 20.0:
                score -= 30.0

        else:
            # General celestial target
            if target_altitude is not None and float(target_altitude) < 15.0:
                score -= 30.0
                limitations.append(f"Target low on horizon ({target_altitude}°).")

        clamped_score = round(max(0.0, min(100.0, score)), 1)
        return AstronomicalAssessment(
            is_calculable=True,
            astronomical_score=clamped_score,
            factors=factors,
            limitations=limitations,
            adapter_source="celestial_event_adapter_v1",
        )


class CelestialEventAstronomyAdapter(BaseAstronomyAdapter):
    """Transparent adapter for CelestialEvent models and dictionaries.

    Inspects available astronomical fields in event.additional_data or event attributes.
    Supports event categories:
    - lunar / moon
    - planet / planetary
    - meteor_shower / meteor
    - eclipse
    - comet / asteroid
    - satellite / visible_pass
    """

    def evaluate_celestial_event(
        self,
        event: Any,
        latitude: float,
        longitude: float,
        bortle_class: int | None = None,
    ) -> AstronomicalAssessment:
        # Support both dict-based test events and object-based models
        if isinstance(event, dict):
            category = str(event.get("category", "")).strip().lower()
            event_type = str(event.get("event_type", "")).strip().lower()
            extra = event.get("additional_data", {}) or {}
        else:
            category = str(getattr(event, "category", "") or "").strip().lower()
            event_type = str(getattr(event, "event_type", "") or "").strip().lower()
            extra: Mapping[str, Any] = getattr(event, "additional_data", {}) or {}

        # Check if verified astronomical calculations are provided in event metadata
        target_altitude = extra.get("target_altitude_deg") or extra.get("altitude")
        target_magnitude = extra.get("apparent_magnitude") or extra.get("magnitude")
        moon_illumination = extra.get("moon_illumination_percent")
        zhr = extra.get("zenithal_hourly_rate") or extra.get("zhr")
        is_illuminated = extra.get("is_sunlit")

        factors: dict[str, Any] = {
            "category": category,
            "event_type": event_type,
            "target_altitude_deg": target_altitude,
            "apparent_magnitude": target_magnitude,
            "moon_illumination_percent": moon_illumination,
            "bortle_class": bortle_class,
        }

        # If essential astronomical ephemeris (like altitude or magnitude) is missing:
        if target_altitude is None and target_magnitude is None and zhr is None:
            return AstronomicalAssessment(
                is_calculable=False,
                astronomical_score=None,
                factors=factors,
                limitations=[
                    "Astronomical inputs (target altitude, apparent magnitude, or ephemeris geometry) "
                    "are not provided in event data. Astronomical visibility score cannot be calculated."
                ],
                adapter_source="celestial_event_adapter_v1",
            )

        limitations: list[str] = []
        score = 100.0

        # Category-specific heuristic evaluations
        if category in ("lunar", "moon") or "moon" in event_type:
            if target_altitude is not None:
                alt = float(target_altitude)
                if alt < 10.0:
                    score -= 40.0
                    limitations.append(f"Low Moon altitude ({alt:.1f}°); severe atmospheric dispersion.")
                elif alt < 25.0:
                    score -= 15.0

        elif category in ("planet", "planetary") or "planet" in event_type:
            if target_altitude is not None:
                alt = float(target_altitude)
                if alt < 15.0:
                    score -= 35.0
                    limitations.append(f"Planet low above horizon ({alt:.1f}°).")
                elif alt < 30.0:
                    score -= 10.0
            if target_magnitude is not None:
                mag = float(target_magnitude)
                if mag > 5.0:
                    score -= 20.0
                    limitations.append(f"Faint planetary target (mag {mag:.1f}).")

        elif category in ("meteor_shower", "meteor") or "meteor" in event_type:
            if moon_illumination is not None and float(moon_illumination) > 50.0:
                score -= 30.0
                limitations.append(f"Bright moonlight ({moon_illumination}%) reduces faint meteor visibility.")
            if bortle_class is not None and bortle_class >= 6:
                score -= 25.0
                limitations.append(f"High urban light pollution (Bortle {bortle_class}) washes out meteors.")
            if target_altitude is not None and float(target_altitude) < 20.0:
                score -= 20.0
                limitations.append(f"Radiant is low ({target_altitude}°).")

        elif category == "eclipse" or "eclipse" in event_type:
            if target_altitude is not None and float(target_altitude) < 5.0:
                score -= 50.0
                limitations.append("Target near or below horizon during eclipse.")

        elif category in ("satellite", "visible_pass") or "satellite" in event_type:
            if is_illuminated is False:
                score = 0.0
                limitations.append("Satellite is in Earth's shadow (eclipsed).")
            elif target_altitude is not None and float(target_altitude) < 20.0:
                score -= 30.0

        else:
            # General celestial target
            if target_altitude is not None and float(target_altitude) < 15.0:
                score -= 30.0
                limitations.append(f"Target low on horizon ({target_altitude}°).")

        clamped_score = round(max(0.0, min(100.0, score)), 1)
        return AstronomicalAssessment(
            is_calculable=True,
            astronomical_score=clamped_score,
            factors=factors,
            limitations=limitations,
            adapter_source="celestial_event_adapter_v1",
        )
