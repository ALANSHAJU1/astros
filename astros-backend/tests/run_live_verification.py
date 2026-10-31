"""Verification runner executing all test cases and capturing actual JSON response."""

import json
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.models.environmental_observation import EnvironmentalObservation
from app.services.environmental_service import EnvironmentalService
from app.services.light_pollution_service import LightPollutionResult


def run_full_environmental_verification():
    client = TestClient(app)

    # 1. Setup mock observations representing hourly forecasts
    # 18:00 (outside window) -> 100% overcast
    # 20:00 (inside window)  -> 15% clear sky
    obs_outside = EnvironmentalObservation(
        observed_at=datetime.fromisoformat("2026-10-26T18:00:00+05:30"),
        cloud_cover=100.0,
        temperature_celsius=21.0,
    )
    obs_inside = EnvironmentalObservation(
        observed_at=datetime.fromisoformat("2026-10-26T20:00:00+05:30"),
        cloud_cover=15.0,
        temperature_celsius=25.0,
        humidity=65.0,
        additional_data={
            "cloud_cover_low": 10.0,
            "cloud_cover_mid": 5.0,
            "cloud_cover_high": 0.0,
            "precipitation_mm": 0.0,
            "wind_speed_kmh": 10.0,
            "visibility_meters": 10000.0,
        },
    )

    import app.api.routes.observation_plans as routes_mod

    original_get_or_fetch = EnvironmentalService.get_or_fetch_forecast_observations
    original_get_lp = EnvironmentalService.get_light_pollution

    try:
        EnvironmentalService.get_or_fetch_forecast_observations = (
            lambda self, db, latitude, longitude, start_time, end_time, **kwargs: [obs_outside, obs_inside]
        )
        EnvironmentalService.get_light_pollution = (
            lambda self, latitude, longitude: LightPollutionResult(
                status="success",
                bortle_class=4,
                sqm=21.15,
                source="DarkSkySites API",
            )
        )

        payload = {
            "session": {
                "latitude": 10.5276,
                "longitude": 76.2144,
                "session_start": "2026-10-26T19:00:00+05:30",
                "session_end": "2026-10-26T22:00:00+05:30",
                "available_duration_minutes": 120,
                "preference_score": 80.0,
            },
            "events": [
                {
                    "event_id": "target_event_01",
                    "name": "Moon Observation Pass",
                    "category": "lunar",
                    "event_type": "moon",
                    "window_start": "2026-10-26T19:30:00+05:30",
                    "window_end": "2026-10-26T21:00:00+05:30",
                    "duration_minutes": 45,
                    "additional_data": {
                        "target_altitude_deg": 55.0,
                        "phase_angle_deg": 28.0,
                    },
                }
            ],
        }

        response = client.post("/api/v1/observation-plans/generate", json=payload)
        return response.status_code, response.json()
    finally:
        EnvironmentalService.get_or_fetch_forecast_observations = original_get_or_fetch
        EnvironmentalService.get_light_pollution = original_get_lp


if __name__ == "__main__":
    code, body = run_full_environmental_verification()
    print("STATUS:", code)
    print("RESPONSE:")
    print(json.dumps(body, indent=2))

