"""Pure, testable visibility scoring engine for AstroOS.

Decoupled from HTTP and database layers.
Separates:
1. Environmental suitability score
2. Astronomical visibility score
3. Observation suitability decision and quality label
4. Data confidence and provenance
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Mapping
from pydantic import BaseModel, Field

from app.services.astronomy_adapter import (
    AstronomicalAssessment,
    BaseAstronomyAdapter,
    CelestialEventAstronomyAdapter,
)
from app.services.light_pollution_service import LightPollutionResult


class EnvironmentalSuitability(BaseModel):
    """Result of pure environmental suitability scoring."""

    score: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Heuristic environmental score (0-100), or None if required data is absent.",
    )
    status: str = Field(
        ...,
        description="'success', 'partial_success', 'unavailable', or 'error'",
    )
    quality_label: str = Field(
        default="Unavailable",
        description="'Optimal', 'Good', 'Fair', 'Poor', 'Unusable', or 'Unavailable'",
    )
    decision: str = Field(
        default="Not evaluable",
        description="Suitability recommendation summary",
    )
    factors: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    confidence: str = Field(
        default="unknown",
        description="'high', 'medium', 'low', or 'unreliable'",
    )


class FullVisibilityAssessment(BaseModel):
    """Complete explainable visibility assessment record."""

    event_id: str
    status: str  # 'success', 'partial_success', 'unavailable', 'error'
    visibility_score: float | None = None  # None when assessment is unavailable (0-100 when available)
    environmental_score: float | None = None
    astronomical_score: float | None = None
    quality_label: str
    decision: str
    viewing_window_start: datetime
    viewing_window_end: datetime
    factors: dict[str, Any]
    limitations: list[str]
    source: str
    assessed_at: datetime
    light_pollution: dict[str, Any]
    confidence: str


def score_to_quality_and_decision(score: float | None) -> tuple[str, str]:
    """Map numeric score (0-100) to human-readable quality label and decision."""
    if score is None:
        return "Unavailable", "Conditions could not be evaluated"
    if score >= 80.0:
        return "Optimal", "Highly recommended"
    elif score >= 65.0:
        return "Good", "Recommended"
    elif score >= 45.0:
        return "Fair", "Marginal conditions"
    elif score >= 25.0:
        return "Poor", "Unfavorable conditions"
    else:
        return "Unusable", "Observation not recommended"


def calculate_environmental_suitability(
    weather_data: Any,
    *,
    now: datetime | None = None,
) -> EnvironmentalSuitability:
    """Calculate environmental suitability from weather observation or forecast.

    Rules:
    - Never substitutes missing cloud cover with 0 or perfect conditions.
    - Cloud cover is the primary determinant.
    - Precipitation induces heavy penalties; active rain renders observing unusable.
    - High humidity (>85%) introduces optical dewing penalty.
    - Strong winds (>35 km/h) penalize telescope stability.
    - Weather-model visibility is reported with explicit caveat.
    """
    if weather_data is None:
        return EnvironmentalSuitability(
            score=None,
            status="unavailable",
            quality_label="Unavailable",
            decision="No environmental data available",
            factors={},
            limitations=["Environmental observation/forecast is missing."],
            confidence="unreliable",
        )

    current_time = now or datetime.now(timezone.utc)

    # Extract attributes whether from Pydantic model, ORM model, or dict
    def get_attr(key: str) -> Any:
        if isinstance(weather_data, dict):
            val = weather_data.get(key)
            if val is None and "additional_data" in weather_data:
                val = weather_data["additional_data"].get(key)
            return val
        val = getattr(weather_data, key, None)
        if val is None:
            extra = getattr(weather_data, "additional_data", {}) or {}
            val = extra.get(key)
        return val

    cloud_cover = get_attr("cloud_cover")
    cloud_low = get_attr("cloud_cover_low")
    cloud_mid = get_attr("cloud_cover_mid")
    cloud_high = get_attr("cloud_cover_high")
    temp = get_attr("temperature_celsius")
    humidity = get_attr("humidity")
    dew_point = get_attr("dew_point_celsius")
    precip_mm = get_attr("precipitation_mm") or get_attr("precipitation")
    precip_prob = get_attr("precipitation_probability")
    wind_speed = get_attr("wind_speed_kmh") or get_attr("wind_speed_10m")
    visibility_m = get_attr("visibility_meters") or get_attr("visibility")
    expires_at = get_attr("expires_at")
    observed_at = get_attr("observed_at")
    recorded_at = get_attr("recorded_at")

    limitations: list[str] = []

    # 1. Check for expired forecast
    if expires_at is not None:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is not None and expires_at <= current_time:
            return EnvironmentalSuitability(
                score=None,
                status="unavailable",
                quality_label="Unavailable",
                decision="Forecast expired",
                factors={"expires_at": expires_at.isoformat()},
                limitations=["Environmental forecast has expired."],
                confidence="unreliable",
            )

    # 2. Check essential input: cloud cover
    if cloud_cover is None:
        return EnvironmentalSuitability(
            score=None,
            status="unavailable",
            quality_label="Unavailable",
            decision="Cloud cover unavailable",
            factors={"temperature_celsius": temp, "humidity": humidity},
            limitations=["Cloud cover data is missing; cannot calculate environmental suitability."],
            confidence="unreliable",
        )

    try:
        cloud_val = float(cloud_cover)
    except (ValueError, TypeError):
        return EnvironmentalSuitability(
            score=None,
            status="error",
            quality_label="Unavailable",
            decision="Invalid cloud cover format",
            factors={},
            limitations=["Invalid cloud cover value."],
            confidence="unreliable",
        )

    if not 0 <= cloud_val <= 100:
        return EnvironmentalSuitability(
            score=None,
            status="error",
            quality_label="Unavailable",
            decision="Cloud cover out of range",
            factors={"cloud_cover": cloud_val},
            limitations=["Cloud cover must be between 0 and 100."],
            confidence="unreliable",
        )

    # Determine base score from cloud cover
    if cloud_low is not None and cloud_mid is not None and cloud_high is not None:
        try:
            eff_cloud = (
                0.5 * float(cloud_low)
                + 0.3 * float(cloud_mid)
                + 0.2 * float(cloud_high)
            )
        except (ValueError, TypeError):
            eff_cloud = cloud_val
    else:
        eff_cloud = cloud_val

    base_score = 100.0 - eff_cloud
    penalties = 0.0

    # Precipitation penalty
    rain_active = False
    if precip_mm is not None:
        try:
            p_val = float(precip_mm)
            if p_val >= 1.0:
                rain_active = True
                penalties += 80.0
                limitations.append(f"Active precipitation ({p_val:.1f} mm) detected.")
            elif p_val > 0.0:
                penalties += 40.0 + p_val * 20.0
                limitations.append(f"Light precipitation ({p_val:.1f} mm) detected.")
        except (ValueError, TypeError):
            pass

    if not rain_active and precip_prob is not None:
        try:
            prob_val = float(precip_prob)
            if prob_val >= 50.0:
                penalties += (prob_val - 40.0) * 0.8
                limitations.append(f"High precipitation probability ({prob_val:.0f}%).")
        except (ValueError, TypeError):
            pass

    # Humidity / Dewing penalty
    if humidity is not None:
        try:
            h_val = float(humidity)
            if h_val > 85.0:
                h_penalty = min(20.0, (h_val - 85.0) * 1.5)
                penalties += h_penalty
                limitations.append(f"High relative humidity ({h_val:.0f}%) risks optical dewing.")
        except (ValueError, TypeError):
            pass

    # Wind penalty
    if wind_speed is not None:
        try:
            w_val = float(wind_speed)
            if w_val > 35.0:
                w_penalty = min(25.0, (w_val - 35.0) * 1.0)
                penalties += w_penalty
                limitations.append(f"High wind speeds ({w_val:.1f} km/h) cause telescope vibration.")
        except (ValueError, TypeError):
            pass

    # Ground visibility caveat
    if visibility_m is not None:
        try:
            v_val = float(visibility_m)
            if v_val < 3000.0:
                penalties += 20.0
                limitations.append(f"Low surface visibility ({v_val:.0f}m - fog/mist).")
        except (ValueError, TypeError):
            pass

    final_score = round(max(0.0, min(100.0, base_score - penalties)), 1)
    if rain_active:
        final_score = min(final_score, 5.0)

    quality, decision = score_to_quality_and_decision(final_score)

    factors_dict = {
        "cloud_cover": cloud_val,
        "effective_cloud_cover": round(eff_cloud, 1),
        "temperature_celsius": temp,
        "humidity": humidity,
        "dew_point_celsius": dew_point,
        "precipitation_probability": precip_prob,
        "precipitation_mm": precip_mm,
        "wind_speed_kmh": wind_speed,
        "visibility_meters": visibility_m,
        "visibility_caveat": (
            "Weather-model visibility estimates horizontal ground visibility, "
            "not astronomical transparency."
        ),
        "applied_penalties": round(penalties, 1),
    }

    confidence = "high"
    if observed_at and recorded_at:
        # Check staleness
        try:
            if isinstance(recorded_at, str):
                recorded_at = datetime.fromisoformat(recorded_at)
            if recorded_at.tzinfo and (current_time - recorded_at).total_seconds() > 7200:
                confidence = "medium"
                limitations.append("Forecast was generated more than 2 hours ago.")
        except Exception:
            pass

    status = "success" if not limitations else "partial_success"

    return EnvironmentalSuitability(
        score=final_score,
        status=status,
        quality_label=quality,
        decision=decision,
        factors=factors_dict,
        limitations=limitations,
        confidence=confidence,
    )


def evaluate_event_visibility(
    event: Any,
    environmental_data: Any | None,
    latitude: float,
    longitude: float,
    light_pollution: LightPollutionResult | None = None,
    astronomy_adapter: BaseAstronomyAdapter | None = None,
    viewing_window_start: datetime | None = None,
    viewing_window_end: datetime | None = None,
    *,
    now: datetime | None = None,
) -> FullVisibilityAssessment:
    """Evaluate visibility for a single event.

    The function now validates that any provided ``environmental_data`` actually
    covers the event's observation window. If the observation timestamp does not
    fall within the event's ``window_start`` / ``window_end`` interval, the
    environmental data is ignored (treated as ``None``) so the final visibility
    score falls back to the astronomical score alone. This prevents the earlier
    situation where a session‑level forecast (e.g., for the whole user session)
    was incorrectly combined with an event that occurs outside that forecast
    window, yielding a blended score like ``0.6*env + 0.4*astro`` even though the
    environment was effectively unavailable for the event.
    """
    def _get_val(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    raw_start = (
        viewing_window_start
        or _get_val(event, "window_start")
        or _get_val(event, "start_time")
    )
    raw_end = (
        viewing_window_end
        or _get_val(event, "window_end")
        or _get_val(event, "end_time")
    )

    has_explicit_window = raw_start is not None
    window_start = raw_start or now or datetime.now(timezone.utc)
    window_end = raw_end or window_start

    if isinstance(window_start, str):
        window_start = datetime.fromisoformat(window_start)
    if isinstance(window_end, str):
        window_end = datetime.fromisoformat(window_end)
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=timezone.utc)
    if window_end.tzinfo is None:
        window_end = window_end.replace(tzinfo=timezone.utc)

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    # If environmental data is provided and event has an explicit window,
    # ensure its observation timestamp overlaps or is reasonably adjacent to the event window.
    if environmental_data is not None and has_explicit_window:
        observed_at = getattr(environmental_data, "observed_at", None)
        if observed_at is None and isinstance(environmental_data, dict):
            observed_at = environmental_data.get("observed_at")
        if observed_at is not None:
            if isinstance(observed_at, str):
                observed_at = datetime.fromisoformat(observed_at)
            # Normalize timezones for comparison
            def _to_utc(dt: datetime) -> datetime:
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            obs_utc = _to_utc(observed_at)
            w_start_utc = _to_utc(window_start)
            w_end_utc = _to_utc(window_end)
            # If the observation is more than 60 minutes outside the event window, discard it.
            if obs_utc < w_start_utc - timedelta(minutes=60) or obs_utc > w_end_utc + timedelta(minutes=60):
                environmental_data = None

    event_id = str(_get_val(event, "id") or _get_val(event, "event_id") or "unknown_event")
    adapter = astronomy_adapter or CelestialEventAstronomyAdapter()

    # 1. Environmental evaluation
    env_result = calculate_environmental_suitability(environmental_data, now=now)

    # 2. Light pollution context
    lp_dict: dict[str, Any] = {}
    bortle: int | None = None
    if light_pollution is not None:
        lp_dict = light_pollution.model_dump()
        bortle = light_pollution.bortle_class
    else:
        lp_dict = {"status": "unavailable", "bortle_class": None}

    # 3. Astronomical evaluation
    astro_result = adapter.evaluate_celestial_event(
        event=event,
        latitude=latitude,
        longitude=longitude,
        bortle_class=bortle,
    )

    combined_limitations: list[str] = []
    combined_limitations.extend(env_result.limitations)
    if light_pollution:
        combined_limitations.extend(light_pollution.limitations)
    combined_limitations.extend(astro_result.limitations)

    # Calculate overall visibility score
    if env_result.score is None and (not astro_result.is_calculable or astro_result.astronomical_score is None):
        visibility_score = None
        overall_status = "unavailable"
        quality_label = "Unavailable"
        decision = "Not evaluable"
    elif env_result.score is None and astro_result.is_calculable and astro_result.astronomical_score is not None:
        visibility_score = astro_result.astronomical_score
        overall_status = "partial_success"
        quality_label, decision = score_to_quality_and_decision(visibility_score)
        combined_limitations.append(
            "Overall visibility score reflects astronomical ephemeris only; "
            "environmental observation/forecast was unavailable."
        )
    elif env_result.score is not None and astro_result.is_calculable and astro_result.astronomical_score is not None:
        # Genuine combination of environmental + astronomical score
        visibility_score = round(
            0.60 * env_result.score + 0.40 * astro_result.astronomical_score,
            1,
        )
        overall_status = "success"
        quality_label, decision = score_to_quality_and_decision(visibility_score)
    else:
        # Only environmental score is available; astronomical score cannot be fabricated
        visibility_score = env_result.score
        overall_status = "partial_success"
        quality_label, decision = score_to_quality_and_decision(visibility_score)
        combined_limitations.append(
            "Overall visibility score reflects environmental suitability only; "
            "astronomical ephemeris could not be calculated."
        )

    all_factors = {
        "environmental_score": env_result.score,
        "astronomical_score": astro_result.astronomical_score,
        "environmental_factors": env_result.factors,
        "astronomical_factors": astro_result.factors,
        "light_pollution": lp_dict,
        "scoring_method": (
            "heuristic_v1_uncalibrated (not scientifically calibrated probabilities)"
        ),
    }

    return FullVisibilityAssessment(
        event_id=event_id,
        status=overall_status,
        visibility_score=visibility_score,
        environmental_score=env_result.score,
        astronomical_score=astro_result.astronomical_score,
        quality_label=quality_label,
        decision=decision,
        viewing_window_start=window_start,
        viewing_window_end=window_end,
        factors=all_factors,
        limitations=combined_limitations,
        source="AstroOS Environmental & Visibility Scoring Engine v1",
        assessed_at=current_time,
        light_pollution=lp_dict,
        confidence=env_result.confidence,
    )
