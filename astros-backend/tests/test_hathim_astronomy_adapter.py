from types import SimpleNamespace
from datetime import datetime, timezone
import pytest

from app.services.hathim_astronomy_adapter import HathimAstronomyAdapter


def test_solar_eclipse_routing():
    adapter = HathimAstronomyAdapter()
    event = {
        "id": "evt-eclipse-solar",
        "category": "eclipse",
        "event_type": "solar_eclipse",
        "name": "Total Solar Eclipse",
        "additional_data": {
            "eclipse_id": "SE_2026_Aug_12",
            "eclipse_type": "Total Solar Eclipse",
            "magnitude": 1.079,
            "gamma": 0.896,
            "partial_visibility_latitudes": (15.0, 82.0),
            "peak_timestamp_utc": "2026-08-12T17:47:00Z",
        },
    }
    # Observer in Europe / North Atlantic where Sun is above horizon
    res = adapter.evaluate_celestial_event(event, latitude=64.1, longitude=-21.9)
    assert res.is_calculable is True
    assert res.astronomical_score is not None
    assert res.astronomical_score > 0.0
    assert res.factors["category"] == "eclipse"
    assert "Solar" in res.factors["eclipse_type"]


def test_lunar_eclipse_routing():
    adapter = HathimAstronomyAdapter()
    event = SimpleNamespace(
        id="evt-eclipse-lunar",
        category="lunar_eclipse",
        event_type="lunar_eclipse",
        name="Total Lunar Eclipse",
        additional_data={
            "eclipse_type": "Total Lunar Eclipse",
            "umbral_magnitude": 1.178,
            "peak_timestamp_utc": "2025-03-14T06:59:00Z",
        },
    )
    # Observer in Americas where Moon is above horizon at peak
    res = adapter.evaluate_celestial_event(event, latitude=40.7, longitude=-74.0)
    assert res.is_calculable is True
    assert res.astronomical_score is not None
    assert res.astronomical_score >= 70.0
    assert res.factors["category"] == "lunar_eclipse"


def test_deep_sky_routing():
    adapter = HathimAstronomyAdapter()
    event = {
        "id": "evt-m31",
        "category": "deep_sky",
        "event_type": "galaxy",
        "name": "M31 (Andromeda Galaxy)",
        "additional_data": {
            "object_id": "M31",
            "target_altitude_deg": 55.0,
            "sun_elevation_deg": -25.0,
            "moon_elevation_deg": -10.0,
        },
    }
    res = adapter.evaluate_celestial_event(event, latitude=35.0, longitude=-111.0)
    assert res.is_calculable is True
    assert res.astronomical_score is not None
    assert res.astronomical_score > 50.0
    assert res.factors["target"] == "M31"


def test_meteor_shower_routing():
    adapter = HathimAstronomyAdapter()
    event = {
        "id": "evt-perseids",
        "category": "meteor_shower",
        "event_type": "meteor_shower",
        "name": "Perseids",
        "additional_data": {
            "shower_id": "perseids",
            "radiant_elevation_deg": 50.0,
            "activity_factor": 1.0,
            "sun_elevation_deg": -24.0,
            "moon_elevation_deg": -5.0,
        },
    }
    res = adapter.evaluate_celestial_event(event, latitude=45.0, longitude=10.0)
    assert res.is_calculable is True
    assert res.astronomical_score is not None
    assert res.astronomical_score > 0.0
    assert res.factors.get("target") == "Perseids"
    assert res.factors.get("display_name") == "Perseid Meteor Shower"
    assert res.factors.get("shower_id") == "perseids"


def test_missing_required_inputs_unscorable():
    adapter = HathimAstronomyAdapter()

    # Eclipse missing timestamp/catalog date
    event_eclipse_no_time = {
        "category": "eclipse",
        "event_type": "solar_eclipse",
        "name": "Solar Eclipse",
        "additional_data": {},
    }
    res_e = adapter.evaluate_celestial_event(event_eclipse_no_time, 0.0, 0.0)
    assert res_e.is_calculable is False
    assert res_e.astronomical_score is None

    # Deep-sky unresolved and without magnitude
    event_dso_unknown = {
        "category": "deep_sky",
        "name": "Unknown_Uncataloged_Object",
        "additional_data": {},
    }
    res_d = adapter.evaluate_celestial_event(event_dso_unknown, 0.0, 0.0)
    assert res_d.is_calculable is False
    assert res_d.astronomical_score is None

    # Meteor shower missing radiant altitude
    event_meteor_no_alt = {
        "category": "meteor_shower",
        "name": "Perseids",
        "additional_data": {},
    }
    res_m = adapter.evaluate_celestial_event(event_meteor_no_alt, 0.0, 0.0)
    assert res_m.is_calculable is False
    assert res_m.astronomical_score is None

    # Deep-sky missing solar elevation and observation timestamp
    event_dso_no_solar = {
        "category": "deep_sky",
        "name": "M31",
        "additional_data": {
            "object_id": "M31",
            "target_altitude_deg": 50.0,
        },
    }
    res_ds_no_solar = adapter.evaluate_celestial_event(event_dso_no_solar, 35.0, -111.0)
    assert res_ds_no_solar.is_calculable is False
    assert res_ds_no_solar.astronomical_score is None
    assert any("solar elevation or observation timestamp" in item for item in res_ds_no_solar.limitations)

    # Meteor shower missing solar elevation and observation timestamp
    event_meteor_no_solar = {
        "category": "meteor_shower",
        "name": "Perseids",
        "additional_data": {
            "shower_id": "perseids",
            "radiant_elevation_deg": 50.0,
        },
    }
    res_met_no_solar = adapter.evaluate_celestial_event(event_meteor_no_solar, 45.0, 10.0)
    assert res_met_no_solar.is_calculable is False
    assert res_met_no_solar.astronomical_score is None
    assert any("solar elevation or observation timestamp" in item for item in res_met_no_solar.limitations)


def test_solar_elevation_timestamp_calculation():
    adapter = HathimAstronomyAdapter()

    # Deep-sky with valid nighttime timestamp (calculates dark solar elevation)
    dso_event_with_time = {
        "category": "deep_sky",
        "name": "M31",
        "additional_data": {
            "object_id": "M31",
            "target_altitude_deg": 50.0,
            "observed_at": "2026-10-22T08:00:00Z",  # Local midnight in Arizona (-111.0)
        },
    }
    res_dso = adapter.evaluate_celestial_event(dso_event_with_time, 35.0, -111.0)
    assert res_dso.is_calculable is True
    assert res_dso.astronomical_score is not None
    assert res_dso.astronomical_score > 0.0

    # Meteor shower with valid nighttime timestamp
    meteor_event_with_time = {
        "category": "meteor_shower",
        "name": "Perseids",
        "additional_data": {
            "shower_id": "perseids",
            "radiant_elevation_deg": 45.0,
            "observed_at": "2026-08-12T01:00:00Z",  # Nighttime in Europe
        },
    }
    res_met = adapter.evaluate_celestial_event(meteor_event_with_time, 45.0, 10.0)
    assert res_met.is_calculable is True
    assert res_met.astronomical_score is not None
    assert res_met.astronomical_score > 0.0


def test_unknown_category_unscorable():
    adapter = HathimAstronomyAdapter()
    event = {
        "category": "satellite",
        "name": "ISS Visible Pass",
        "additional_data": {"target_altitude_deg": 60.0},
    }
    res = adapter.evaluate_celestial_event(event, 0.0, 0.0)
    assert res.is_calculable is False
    assert res.astronomical_score is None


def test_precomputed_derived_score_shortcut():
    adapter = HathimAstronomyAdapter()
    event = {
        "category": "deep_sky",
        "name": "Custom Target",
        "additional_data": {"computed_visibility_score": 88.5},
    }
    res = adapter.evaluate_celestial_event(event, 0.0, 0.0)
    assert res.is_calculable is True
    assert res.astronomical_score == 88.5
    assert res.adapter_source == "hathim_astronomy_adapter_v1_derived"


def test_regression_lunar_and_planetary():
    adapter = HathimAstronomyAdapter()

    # Lunar event with altitude 45.0 deg (authoritative score: (45-15)/75 * 80 + 15 = 47.0)
    lunar_event = {
        "category": "lunar",
        "event_type": "full_moon",
        "name": "Full Moon",
        "additional_data": {"target_altitude_deg": 45.0},
    }
    res_lunar = adapter.evaluate_celestial_event(lunar_event, 10.0, 76.0)
    assert res_lunar.is_calculable is True
    assert res_lunar.astronomical_score == 47.0

    # Planetary event with altitude 40.0 deg and magnitude -2.0 (authoritative score: 23.3 + 21.7 = 45.0)
    planet_event = {
        "category": "planet",
        "event_type": "opposition",
        "name": "Jupiter",
        "additional_data": {
            "target_altitude_deg": 40.0,
            "apparent_magnitude": -2.0,
        },
    }
    res_planet = adapter.evaluate_celestial_event(planet_event, 10.0, 76.0)
    assert res_planet.is_calculable is True
    assert res_planet.astronomical_score == 45.0


def test_deep_sky_compound_name_and_catalog_id_resolution():
    adapter = HathimAstronomyAdapter()

    # 1. Compound name with space (e.g. "M31 Andromeda")
    event1 = {
        "category": "deep_sky",
        "name": "M31 Andromeda",
        "additional_data": {
            "altitude": 60.0,
            "sun_elevation_deg": -30.0,
        },
    }
    res1 = adapter.evaluate_celestial_event(event1, 10.0, 76.0)
    assert res1.is_calculable is True
    assert res1.astronomical_score is not None
    assert res1.factors["target"] == "M31"

    # 2. Compound name with parentheses (e.g. "M42 (Orion Nebula)")
    event2 = {
        "category": "deep_sky",
        "name": "M42 (Orion Nebula)",
        "additional_data": {
            "altitude": 55.0,
            "mean_sun_elevation_deg": -30.0,
        },
    }
    res2 = adapter.evaluate_celestial_event(event2, 10.0, 76.0)
    assert res2.is_calculable is True
    assert res2.astronomical_score is not None
    assert res2.factors["target"] == "M42"

    # 3. Explicit catalog_id in additional_data / metadata
    event3 = {
        "category": "deep_sky",
        "name": "Custom User Label",
        "additional_data": {
            "catalog_id": "M51",
            "altitude": 50.0,
            "mean_sun_elevation_deg": -30.0,
        },
    }
    res3 = adapter.evaluate_celestial_event(event3, 10.0, 76.0)
    assert res3.is_calculable is True
    assert res3.astronomical_score is not None
    assert res3.factors["target"] == "M51"


