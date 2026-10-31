from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest

from app.services.light_pollution_service import LightPollutionResult
from app.services.visibility_scoring_engine import (
    calculate_environmental_suitability,
    evaluate_event_visibility,
)


def test_clear_vs_heavily_clouded_conditions():
    # 0% cloud cover
    clear_weather = {
        "cloud_cover": 0,
        "temperature_celsius": 20.0,
        "humidity": 50,
        "wind_speed_kmh": 5.0,
    }
    res_clear = calculate_environmental_suitability(clear_weather)
    assert res_clear.status == "success"
    assert res_clear.score == 100.0
    assert res_clear.quality_label == "Optimal"
    assert res_clear.decision == "Highly recommended"

    # 90% cloud cover
    cloudy_weather = {
        "cloud_cover": 90,
        "temperature_celsius": 20.0,
        "humidity": 60,
    }
    res_cloudy = calculate_environmental_suitability(cloudy_weather)
    assert res_cloudy.status == "success"
    assert res_cloudy.score == 10.0
    assert res_cloudy.quality_label == "Unusable"
    assert res_cloudy.decision == "Observation not recommended"


def test_precipitation_penalties():
    # Active rain (2.5 mm)
    rainy_weather = {
        "cloud_cover": 40,
        "precipitation_mm": 2.5,
    }
    res_rain = calculate_environmental_suitability(rainy_weather)
    assert res_rain.score <= 5.0
    assert res_rain.quality_label == "Unusable"
    assert any("Active precipitation" in item for item in res_rain.limitations)


def test_high_humidity_and_wind_penalties():
    weather = {
        "cloud_cover": 10,
        "humidity": 95,      # >85% penalty
        "wind_speed_kmh": 45, # >35 km/h penalty
    }
    res = calculate_environmental_suitability(weather)
    assert res.score < 90.0  # Base 90 minus dewing and wind penalties
    assert any("dewing" in item.lower() for item in res.limitations)
    assert any("wind" in item.lower() for item in res.limitations)


def test_missing_cloud_cover_returns_unavailable():
    weather_missing_clouds = {
        "temperature_celsius": 22.0,
        "humidity": 60,
        "cloud_cover": None,
    }
    res = calculate_environmental_suitability(weather_missing_clouds)
    assert res.status == "unavailable"
    assert res.score is None
    assert any("missing" in item.lower() for item in res.limitations)


def test_expired_forecast_returns_unavailable():
    now = datetime(2026, 10, 27, 20, 0, tzinfo=timezone.utc)
    weather_expired = {
        "cloud_cover": 10,
        "expires_at": now - timedelta(minutes=5),
    }
    res = calculate_environmental_suitability(weather_expired, now=now)
    assert res.status == "unavailable"
    assert res.score is None
    assert any("expired" in item.lower() for item in res.limitations)


def test_invalid_cloud_cover_values():
    assert calculate_environmental_suitability({"cloud_cover": 150}).status == "error"
    assert calculate_environmental_suitability({"cloud_cover": -10}).status == "error"
    assert calculate_environmental_suitability({"cloud_cover": "not-a-number"}).status == "error"


def test_evaluate_event_visibility_without_astronomical_ephemeris():
    # Event has no ephemeris; should produce partial_success with environmental score only
    event = SimpleNamespace(
        id="evt-001",
        category="planet",
        event_type="opposition",
        start_time=datetime(2026, 10, 27, 19, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 27, 21, tzinfo=timezone.utc),
        additional_data={},
    )
    weather = {"cloud_cover": 20}
    assessment = evaluate_event_visibility(
        event=event,
        environmental_data=weather,
        latitude=10.0,
        longitude=76.0,
    )

    assert assessment.status == "partial_success"
    assert assessment.environmental_score == 80.0
    assert assessment.astronomical_score is None
    assert assessment.visibility_score == 80.0
    assert any("reflects environmental suitability only" in item for item in assessment.limitations)


def test_evaluate_event_visibility_with_genuine_astronomy():
    # Event has valid altitude input
    event = SimpleNamespace(
        id="evt-002",
        category="planet",
        event_type="opposition",
        start_time=datetime(2026, 10, 27, 19, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 27, 21, tzinfo=timezone.utc),
        additional_data={"target_altitude_deg": 50.0},
    )
    weather = {"cloud_cover": 10}
    lp = LightPollutionResult(
        status="success",
        bortle_class=4,
        artificial_brightness_mcd=0.15,
        sqm=21.3,
    )
    assessment = evaluate_event_visibility(
        event=event,
        environmental_data=weather,
        latitude=10.0,
        longitude=76.0,
        light_pollution=lp,
    )

    assert assessment.status == "success"
    assert assessment.environmental_score == 90.0
    assert assessment.astronomical_score == 100.0
    # Combined score = 0.6 * 90 + 0.4 * 100 = 94.0
    assert assessment.visibility_score == 94.0
    assert assessment.quality_label == "Optimal"
