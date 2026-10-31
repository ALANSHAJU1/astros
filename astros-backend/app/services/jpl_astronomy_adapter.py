from __future__ import annotations

import logging
import sys
from pathlib import Path
import importlib.util

logger = logging.getLogger(__name__)

# Determine workspace root (three levels up from this file)
ROOT_PATH = Path(__file__).resolve().parents[3]
INTEL_PATH = ROOT_PATH / "astros-intelligence"
# Ensure intelligence package is importable
if str(INTEL_PATH) not in sys.path:
    sys.path.append(str(INTEL_PATH))

# Dynamically load the JPL horizons client module
JPL_CLIENT_PATH = INTEL_PATH / "astronomy" / "jpl_horizons_client.py"
spec = importlib.util.spec_from_file_location(
    "astros_intelligence.astronomy.jpl_horizons_client", JPL_CLIENT_PATH
)
_jpl_client = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(_jpl_client)

# Dynamically load the event adapter module for converting ephemeris to events
EVENT_ADAPTER_PATH = INTEL_PATH / "astronomy" / "event_adapter.py"
spec2 = importlib.util.spec_from_file_location(
    "astros_intelligence.astronomy.event_adapter", EVENT_ADAPTER_PATH
)
_event_adapter = importlib.util.module_from_spec(spec2)
assert spec2.loader is not None
spec2.loader.exec_module(_event_adapter)

# Import HorizonsClient lazily inside fetch_events_from_jpl to ensure availability

def fetch_events_from_jpl(
    latitude: float,
    longitude: float,
    start_time_iso: str,
    end_time_iso: str,
    target_ids: list[int] | None = None,
) -> list[dict]:
    """Query JPL Horizons for the given location/time window and adapt results.

    Args:
        latitude: Observer latitude in degrees.
        longitude: Observer longitude in degrees.
        start_time_iso: ISO‑8601 start of observation window.
        end_time_iso: ISO‑8601 end of observation window.
        target_ids: Optional list of integer target IDs (e.g., MOON_TARGET_ID).

    Returns:
        A list of event dictionaries compatible with the rest of the pipeline.
    """

    client = _jpl_client.HorizonsClient()
    try:
        from astronomy.models import EphemerisRequest, ObserverLocation
        from datetime import datetime

        observer = ObserverLocation(latitude=latitude, longitude=longitude, altitude_km=None)

        def _fmt(ts: str) -> str:
            # Parse ISO datetime and convert to UTC for JPL Horizons
            from datetime import timezone
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc)
            # Format as 'YYYY-MMM-DD HH:MM' with uppercase month abbreviation (e.g., '2026-OCT-01 12:00')
            month = dt.strftime('%b').upper()
            return f"{dt.year}-{month}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}"

        request = EphemerisRequest(
            location=observer,
            start_time=_fmt(start_time_iso),
            stop_time=_fmt(end_time_iso),
            quantities=["4"],
        )
        # Use the generic observer ephemeris method provided by HorizonsClient
        response = client.get_observer_ephemeris(request)
    finally:
        if hasattr(client, "close") and callable(client.close):
            client.close()
    # Use the HorizonEventAdapter to convert ephemeris into observation pass events.
    # Weather and preference scores are initialized with placeholder 0.0;
    # the observation plans route resolves actual weather and session preferences.
    try:
        events = _event_adapter.HorizonsEventAdapter.create_observation_passes(
            ephemeris_response=response,
            weather_score=0.0,
            preference_score=0.0,
            target_name=None,
            target_type="auto",
            min_elevation_deg=0.0,
            required_duration_minutes=None,
            custom_visibility_score=None,
            weather_source="External Weather Assessment",
            preference_source="User Profile / Session Preferences",
            is_synthetic=False,
            twilight_mode="none",
            solar_ephemeris=None,
            custom_twilight_max_sun_elevation_deg=None,
        )
    except _event_adapter.UnobservableEventError as exc:
        logger.info(
            "Target is not observable during the requested session: %s",
            exc,
        )
        return []

    return events
