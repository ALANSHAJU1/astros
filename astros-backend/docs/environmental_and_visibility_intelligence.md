# AstroOS — Environmental and Visibility Intelligence

## Overview

The **Environmental and Visibility Intelligence** module provides AstroOS with real-time and forecasted weather condition analysis, light-pollution context, and celestial event visibility evaluation.

The system is designed with strict adherence to astronomical data principles:
- **Separation of Concerns**: Environmental suitability (meteorological conditions) is strictly separated from astronomical visibility (target ephemeris, altitude, magnitude, geometry).
- **No Fabricated Data**: If astronomical coordinates, target altitudes, or ephemeris data are missing, the system produces transparent partial assessments explaining the limitation, rather than inventing synthetic visibility scores.
- **Uncalibrated Heuristics Disclosure**: All initial scores are deterministic, transparent heuristics, explicitly documented as not being scientifically calibrated statistical probabilities.
- **Provenance Tracking**: Preserves provider attribution, retrieval timestamps, valid forecast timestamps, and distinguishes forecasts from measured historical observations.

---

## Architecture & Components

```
+-----------------------------------------------------------------------------------+
|                               FastAPI API Layer                                   |
|   /api/v1/visibility-assessments/calculate  |  /api/v1/environmental-observations |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        Visibility Assessment Service                              |
|   Orchestrates event lookup, weather retrieval, light pollution, scoring, and DB  |
+-----------------------------------------------------------------------------------+
        |                                                   |
        v                                                   v
+----------------------------+             +----------------------------------------+
|   Environmental Service    |             |       Visibility Scoring Engine        |
| - Open-Meteo Forecasts     |             | - Pure, deterministic heuristic rules  |
| - In-memory cache & TTL    |             | - Environmental suitability (0-100)    |
| - DB duplicate prevention  |             | - Quality label & observation decision |
| - Light Pollution Provider |             | - Astronomy Adapter (Celestial Events) |
+----------------------------+             +----------------------------------------+
        |                                                   |
        +-------------------------+-------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------------+
|                            PostgreSQL / SQLAlchemy                                |
|   environmental_observations  |  visibility_assessments  |  celestial_events      |
+-----------------------------------------------------------------------------------+
```

---

## 1. Weather Data Provider (Open-Meteo)

- **Provider**: [Open-Meteo](https://open-meteo.com)
- **Endpoint**: `https://api.open-meteo.com/v1/forecast`
- **License / Attribution**: "Weather data by Open-Meteo.com under CC BY 4.0".
- **Variables Requested**:
  `temperature_2m`, `relative_humidity_2m`, `dew_point_2m`, `precipitation_probability`, `precipitation`, `cloud_cover`, `cloud_cover_low`, `cloud_cover_mid`, `cloud_cover_high`, `visibility`, `wind_speed_10m`, `weather_code`.
- **Implementation**: `app/services/weather_provider.py` (`OpenMeteoWeatherProvider`)
- **Key Features**:
  - Request timeouts configured via `WEATHER_REQUEST_TIMEOUT_SECONDS` (default: 10.0s).
  - Handles network timeouts (`WeatherProviderTimeoutError`), HTTP 429 rate limits (`WeatherProviderRateLimitError`), HTTP errors (`WeatherProviderHTTPError`), and malformed responses (`WeatherProviderDataError`).
  - In-memory cache with configurable TTL (`WEATHER_CACHE_TTL_SECONDS`, default: 1800s) keyed by geographic cell and date range to avoid redundant external network calls.
  - Normalizes timestamps to timezone-aware UTC ISO 8601 datetimes.
  - WMO Weather interpretation code mapping for human-readable condition descriptions.
  - Stores explicit caveat on weather-model visibility: *"Weather-model visibility estimates horizontal ground visibility, not astronomical transparency."*

---

## 2. Light-Pollution Provider & Dataset Research

### Investigation of World Atlas & Lorenz Models:
- **David J. Lorenz Atlas** (`djlorenz.github.io/astronomy/lp/index.html`): Serves raster map tiles and web overlays based on VIIRS DNB radiance calculations. It does not provide a public point-query REST API. Scraping map tiles or reverse-engineering tile endpoints is explicitly avoided.
- **Falchi et al. (2016) World Atlas of Artificial Night Sky Brightness**: Hosted at GFZ Data Services (DOI: `10.5880/GFZ.1.4.2016.001`). The raw dataset is a ~2.9 GB GeoTIFF (`World_Atlas_2015.zip`) with 30-arcsecond (~1 km) spatial resolution.

### Implementation:
- **Implementation**: `app/services/light_pollution_service.py`
- **`BaseLightPollutionProvider`**: Abstract interface for point queries.
- **`UnavailableLightPollutionProvider`**: When no local grid dataset is configured or present, returns `status="unavailable"`, setting `bortle_class=None`, `artificial_brightness_mcd=None`, and documenting the setup requirement.
- **`GridLightPollutionProvider`**: Supports querying nearest valid grid cell from a configured raster/grid data file (bounding box checking, spatial resolution metadata, and Falchi/Cinzano zenith luminance to Bortle class and SQM conversion).
- **Configuration**: Set `LIGHT_POLLUTION_DATA_PATH` in `.env`.

---

## 3. Environmental Data Service & Persistence

- **Implementation**: `app/services/environmental_service.py` (`EnvironmentalService`)
- **Persistence**: Persists forecasts using existing repository (`create_observation`) into `environmental_observations` table.
- **Forecast vs Measured Observation Semantics**:
  - Distinguishes forecasts from measured historical observations by populating `additional_data`:
    `{"is_forecast": true, "data_type": "forecast", "provider": "Open-Meteo", "retrieved_at": "...", "raw_units": {...}}`.
  - Sets `expires_at` to the end of the forecast valid hour.
  - Avoids duplicate database insertions if fresh forecast observations already exist for the coordinate cell and observing window.
  - Graceful fallback: If external weather provider is temporarily unreachable, reuses existing database observations and marks freshness accordingly.

---

## 4. Visibility Scoring Engine

- **Implementation**: `app/services/visibility_scoring_engine.py`
- **Pure Scoring Rules**:
  - **Cloud Cover**: Primary factor (`base_score = 100 - effective_cloud_cover`). If low/mid/high cloud breakdown is available, weights them (`0.5*low + 0.3*mid + 0.2*high`). Missing cloud cover returns `status="unavailable"` without assuming 0% cloud cover.
  - **Precipitation Penalties**: Active rain (>= 1.0 mm) caps visibility at 5.0 ("Unusable"). Precipitation probability >= 50% introduces progressive penalties.
  - **Humidity / Dewing**: Relative humidity > 85% introduces an optical dewing penalty.
  - **Wind**: Wind speed > 35 km/h introduces telescope vibration/instability penalty.
  - **Expired / Stale Forecasts**: Expired forecasts return `status="unavailable"` and are excluded from being presented as current.
- **Quality Labels & Decisions**:
  - Score >= 80: "Optimal" ("Highly recommended")
  - 65 - 79: "Good" ("Recommended")
  - 45 - 64: "Fair" ("Marginal conditions")
  - 25 - 44: "Poor" ("Unfavorable conditions")
  - < 25: "Unusable" ("Observation not recommended")

---

## 5. Event-Specific Astronomy Adapter

- **Implementation**: `app/services/astronomy_adapter.py` (`CelestialEventAstronomyAdapter`)
- **Event Categories Supported**:
  - **Moon**: Altitude penalty (<10° severe dispersion), illumination.
  - **Planets**: Low-altitude penalties (<15°), apparent magnitude.
  - **Meteor Showers**: Moonlight interference (>50% illumination penalty), high light pollution (Bortle >= 6 penalty), radiant altitude.
  - **Satellites**: Earth shadow check (sunlit vs eclipsed).
  - **Eclipses**: Horizon check during eclipse maximum.
- **Absence of Ephemeris**: When ephemeris calculations are not available, returns `is_calculable=False`, `astronomical_score=None`, and discloses that the overall score reflects environmental suitability only.

---

## 6. API Endpoints

### 1. `POST /api/v1/visibility-assessments/calculate`
Calculates visibility assessment for a celestial event and coordinates.
- **Request Body**:
```json
{
  "event_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "latitude": 10.5276,
  "longitude": 76.2144,
  "viewing_window_start": "2026-10-27T19:00:00+05:30",
  "viewing_window_end": "2026-10-27T21:00:00+05:30",
  "persist": true
}
```
- **Response**:
```json
{
  "id": "7ca6476e-52eb-4581-be61-267980b1e16f",
  "event_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "success",
  "visibility_score": 94.0,
  "environmental_score": 90.0,
  "astronomical_score": 100.0,
  "quality_label": "Optimal",
  "decision": "Highly recommended",
  "viewing_window_start": "2026-10-27T19:00:00+05:30",
  "viewing_window_end": "2026-10-27T21:00:00+05:30",
  "factors": { ... },
  "limitations": [ ... ],
  "source": "AstroOS Environmental & Visibility Scoring Engine v1",
  "assessed_at": "2026-10-22T17:40:00+00:00",
  "light_pollution": { ... },
  "confidence": "high",
  "is_persisted": true
}
```

### 2. `POST /api/v1/environmental-observations/forecast`
Retrieves, normalizes, and optionally persists hourly forecasts for a location.
- **Request Body**:
```json
{
  "latitude": 10.5276,
  "longitude": 76.2144,
  "start_time": "2026-10-27T19:00:00+05:30",
  "end_time": "2026-10-27T22:00:00+05:30",
  "force_refresh": false,
  "persist": true
}
```

---

## 7. Recommendation Integration

- **Implementation**: `app/services/database_recommendation_service.py`
- Coordinates with `EnvironmentalService.build_session_environmental_context` using the agreed field `"environmental_context"`.
- Preserves explicit session start and session end (`SESSION_END`).
- Preserves observing time budget (`available_duration_minutes`).
- Transparently discloses synthetic assessments when test fixtures are used (`data_mode: "synthetic_test"`).
- Automatically includes environmental data quality context even for empty-event responses.

---

## 8. Verification & Test Execution

Run the complete test suite:
```bash
$env:PYTHONPATH="."
.\venv\Scripts\pytest.exe
```

Run Alembic schema check:
```bash
$env:PYTHONPATH="."
.\venv\Scripts\alembic.exe check
```
