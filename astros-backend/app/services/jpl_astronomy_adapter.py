from __future__ import annotations

import logging
from app.services.duration_policy import get_default_duration_minutes
import sys
from pathlib import Path
import importlib.util

logger = logging.getLogger(__name__)

ROOT_PATH = Path(__file__).resolve().parents[3]
INTEL_PATH = ROOT_PATH / "astros-intelligence"

if str(INTEL_PATH) not in sys.path:
    sys.path.append(str(INTEL_PATH))


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_jpl_client = _load_module(
    "astros_intelligence.astronomy.jpl_horizons_client",
    INTEL_PATH / "astronomy" / "jpl_horizons_client.py",
)

_event_adapter = _load_module(
    "astros_intelligence.astronomy.event_adapter",
    INTEL_PATH / "astronomy" / "event_adapter.py",
)


def fetch_events_from_jpl(
    latitude: float,
    longitude: float,
    start_time_iso: str,
    end_time_iso: str,
    target_ids: list[str | int] | None = None,
) -> list[dict]:
    """
    Fetch topocentric observation passes from JPL Horizons.

    When target_ids is omitted, preserve the existing Moon-default behavior.
    When target_ids is supplied, query each requested Horizons target.
    """
    from astronomy.models import EphemerisRequest, ObserverLocation
    from datetime import datetime, timezone

    observer = ObserverLocation(
        latitude=latitude,
        longitude=longitude,
        altitude_km=None,
    )

    def _fmt(ts: str) -> str:
        dt = datetime.fromisoformat(ts)

        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)

        month = dt.strftime("%b").upper()
        return f"{dt.year}-{month}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}"

    start_time = _fmt(start_time_iso)
    stop_time = _fmt(end_time_iso)

    # Preserve the current Moon default when no target is specified.
    targets = target_ids if target_ids is not None else [None]

    all_events: list[dict] = []

    for target_id in targets:
        client = _jpl_client.HorizonsClient()

        try:
            request_kwargs = {
                "location": observer,
                "start_time": start_time,
                "stop_time": stop_time,
                "quantities": ["4"],
            }

            if target_id is not None:
                request_kwargs["target"] = str(target_id)

            request = EphemerisRequest(**request_kwargs)

            response = client.get_observer_ephemeris(request)

            try:
                target_type = "moon"

                if target_id is not None:
                    clean_target_id = str(target_id).strip().rstrip(";")

                    if clean_target_id in {"99942", "433", "101955"}:
                            target_type = "neo"
                    else:
                            target_type = "asteroid"
                events = (
                    _event_adapter.HorizonsEventAdapter.create_observation_passes(
                        ephemeris_response=response,
                        weather_score=0.0,
                        preference_score=0.0,
                        target_name=None,
                        target_type=target_type,
                        min_elevation_deg=0.0,
                        required_duration_minutes=get_default_duration_minutes(target_type),
                        custom_visibility_score=None,
                        weather_source="External Weather Assessment",
                        preference_source="User Profile / Session Preferences",
                        is_synthetic=False,
                        twilight_mode="none",
                        solar_ephemeris=None,
                        custom_twilight_max_sun_elevation_deg=None,
                    )
                )
                all_events.extend(events)

            except _event_adapter.UnobservableEventError as exc:
                logger.info(
                    "Horizons target %s is not observable: %s",
                    target_id if target_id is not None else "Moon",
                    exc,
                )

        finally:
            if hasattr(client, "close") and callable(client.close):
                client.close()

    return all_events