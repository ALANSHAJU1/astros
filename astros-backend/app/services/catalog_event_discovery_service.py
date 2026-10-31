"""
AstroOS11 — Catalog Event Discovery Service
============================================

Discovers catalog-backed celestial events (eclipses, meteor showers, deep-sky
objects) for a given observation session window.

The discovery layer bridges the gap between the existing JPL Horizons auto-fetch
(planets / Moon) and the three new intelligence-engine categories added in
Stage 1.  It produces event dicts in the same backend shape used by
``observation_plans.py`` so they can be merged, environmentally assessed, and
ranked without any further normalisation.

Design constraints
------------------
* No live network calls — all data comes from static intelligence-layer
  catalogs (eclipse, meteor-shower, and deep-sky catalogs).
* Returns an empty list when no catalog candidates qualify; never fabricates
  events.
* Produces stable, deterministic event IDs suitable for deduplication.
* All ``window_start`` / ``window_end`` values are timezone-aware ISO-8601
  strings so that the existing ``_parse_ts`` helper in ``observation_plans.py``
  parses them correctly.
"""

from __future__ import annotations

import sys
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intelligence-layer import path setup (mirrors hathim_astronomy_adapter.py)
# ---------------------------------------------------------------------------
ROOT_PATH = Path(__file__).resolve().parents[3]
INTEL_PATH = ROOT_PATH / "astros-intelligence"

if str(INTEL_PATH) not in sys.path:
    sys.path.append(str(INTEL_PATH))
if str(ROOT_PATH) not in sys.path:
    sys.path.append(str(ROOT_PATH))

# ---------------------------------------------------------------------------
# Engine imports — lazy-import style with explicit error reporting
# ---------------------------------------------------------------------------

try:
    from astronomy.eclipse_engine import (
        generate_unassessed_eclipse_passes,
        list_upcoming_eclipses,
    )
    _eclipse_available = True
except Exception as _exc:  # pragma: no cover
    logger.warning("catalog_event_discovery: eclipse engine unavailable: %s", _exc)
    _eclipse_available = False

try:
    from astronomy.meteor_shower_engine import (
        generate_unassessed_meteor_shower_passes,
        check_shower_activity,
    )
    from astronomy.models import METEOR_SHOWER_CATALOG
    _meteor_available = True
except Exception as _exc:  # pragma: no cover
    logger.warning("catalog_event_discovery: meteor-shower engine unavailable: %s", _exc)
    _meteor_available = False

try:
    from astronomy.deep_sky_engine import (
        generate_unassessed_deep_sky_passes,
        DEEP_SKY_CATALOG,
    )
    from astronomy.event_adapter import UnobservableEventError
    _dso_available = True
except Exception as _exc:  # pragma: no cover
    logger.warning("catalog_event_discovery: deep-sky engine unavailable: %s", _exc)
    _dso_available = False

# DSO targets to attempt discovery for when no specific target list is supplied.
# Ordered roughly by brightness / observability popularity (Messier highlights).
_DEFAULT_DSO_TARGETS: list[str] = [
    "M31", "M42", "M45", "M13", "M51", "M57",
    "M81", "M82", "M27", "M1",  "M35", "M44",
    "M11", "M15", "M92", "M5",  "M3",  "M47",
    "M41", "M67", "M36", "M37", "M38", "M50",
]

# Maximum number of DSO candidates returned per discovery call so we keep the
# response bounded for typical 2–4 hour sessions.
_MAX_DSO_CANDIDATES = 8


def _ensure_utc_aware(dt: datetime) -> datetime:
    """Return *dt* as a timezone-aware UTC datetime."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def discover_eclipse_candidates(
    latitude: float,
    longitude: float,
    session_start: datetime,
    session_end: datetime,
    available_duration_minutes: float | None = None,
) -> list[dict[str, Any]]:
    """Return unassessed eclipse passes overlapping the session window.

    Parameters
    ----------
    latitude, longitude:
        Observer geodetic coordinates in degrees.
    session_start, session_end:
        Timezone-aware session boundary datetimes.
    available_duration_minutes:
        Desired minimum observable duration.  Passed to the engine so
        eclipses whose observable overlap is shorter than this are filtered
        out early.

    Returns
    -------
    list[dict]
        Zero or more unassessed eclipse event dicts ready for environmental
        assessment.  ``weather_score`` and ``preference_score`` are absent;
        ``assessment_status`` is ``'pending'``.
    """
    if not _eclipse_available:
        return []

    session_start = _ensure_utc_aware(session_start)
    session_end = _ensure_utc_aware(session_end)

    try:
        passes = generate_unassessed_eclipse_passes(
            session_start=session_start,
            session_end=session_end,
            observer_latitude=latitude,
            observer_longitude=longitude,
            eclipse_kind="eclipse",          # both solar and lunar
            required_duration_minutes=available_duration_minutes,
            min_visibility_score=1.0,        # reject completely invisible eclipses
        )
        for p in passes:
            p.setdefault("category", "eclipse")
        logger.info(
            "catalog_event_discovery: %d eclipse candidate(s) found for session %s to %s",
            len(passes), session_start.isoformat(), session_end.isoformat(),
        )
        return passes
    except Exception as exc:
        logger.warning("catalog_event_discovery: eclipse discovery failed: %s", exc)
        return []


def discover_meteor_shower_candidates(
    latitude: float,
    longitude: float,
    session_start: datetime,
    session_end: datetime,
    available_duration_minutes: float | None = None,
) -> list[dict[str, Any]]:
    """Return unassessed meteor-shower passes whose activity window overlaps the session.

    Only showers that are *active* (per the catalog activity window) during any
    part of the session are attempted.  Showers where the radiant is never
    above the horizon under dark skies during the session are silently skipped.

    Parameters
    ----------
    latitude, longitude:
        Observer geodetic coordinates in degrees.
    session_start, session_end:
        Timezone-aware session boundary datetimes.
    available_duration_minutes:
        Passed as ``required_duration_minutes`` to the engine.

    Returns
    -------
    list[dict]
        Zero or more unassessed meteor-shower event dicts.
    """
    if not _meteor_available:
        return []

    session_start = _ensure_utc_aware(session_start)
    session_end = _ensure_utc_aware(session_end)

    # Check every catalog shower for activity overlap with the session window.
    # We probe the session midpoint as a representative timestamp.
    session_mid = session_start + (session_end - session_start) / 2

    candidates: list[dict[str, Any]] = []

    for shower_id, shower_config in METEOR_SHOWER_CATALOG.items():
        try:
            activity = check_shower_activity(shower_config, session_mid)
        except Exception:
            continue

        if not activity.get("is_active"):
            # Not active at session midpoint — also check start & end to catch
            # edge cases where the session straddles the activity boundary.
            active_at_start = False
            active_at_end = False
            try:
                active_at_start = check_shower_activity(shower_config, session_start).get("is_active", False)
                active_at_end = check_shower_activity(shower_config, session_end).get("is_active", False)
            except Exception:
                pass
            if not (active_at_start or active_at_end):
                continue

        # Shower is active — attempt pass generation.
        try:
            passes = generate_unassessed_meteor_shower_passes(
                shower_target=shower_id,
                latitude=latitude,
                longitude=longitude,
                start_time=session_start,
                stop_time=session_end,
                twilight_mode="nautical",
                required_duration_minutes=available_duration_minutes,
            )
            for p in passes:
                p.setdefault("category", "meteor_shower")
                for field in ("window_start", "window_end"):
                    val = p.get(field)
                    if isinstance(val, str) and val.strip():
                        cleaned = val.strip()
                        if cleaned.endswith("Z") or cleaned.endswith("z"):
                            cleaned = cleaned[:-1] + "+00:00"
                        try:
                            dt_val = datetime.fromisoformat(cleaned)
                            if dt_val.tzinfo is None:
                                dt_val = dt_val.replace(tzinfo=timezone.utc)
                            p[field] = dt_val.isoformat()
                        except ValueError:
                            pass
                    elif isinstance(val, datetime):
                        if val.tzinfo is None:
                            val = val.replace(tzinfo=timezone.utc)
                        p[field] = val.isoformat()
            candidates.extend(passes)
            logger.info(
                "catalog_event_discovery: %d meteor-shower pass(es) for '%s'",
                len(passes), shower_config.get("name", shower_id),
            )
        except Exception as exc:
            # UnobservableEventError or other: radiant below horizon / session
            # too short — acceptable, just skip.
            logger.debug(
                "catalog_event_discovery: meteor shower '%s' not observable: %s",
                shower_id, exc,
            )

    return candidates


def discover_deep_sky_candidates(
    latitude: float,
    longitude: float,
    session_start: datetime,
    session_end: datetime,
    available_duration_minutes: float | None = None,
    dso_targets: list[str] | None = None,
    max_candidates: int = _MAX_DSO_CANDIDATES,
) -> list[dict[str, Any]]:
    """Return unassessed deep-sky object passes observable during the session.

    Iterates a bounded list of DSO targets, attempts pass generation for each,
    and returns up to *max_candidates* results ordered by visibility score.

    Parameters
    ----------
    latitude, longitude:
        Observer geodetic coordinates in degrees.
    session_start, session_end:
        Timezone-aware session boundary datetimes.
    available_duration_minutes:
        Desired observation duration (minutes).  Defaults to 45 when omitted.
    dso_targets:
        Explicit list of DSO designations (e.g. ``["M31", "NGC 869"]``).
        When *None*, a default curated list of popular Messier objects is used.
    max_candidates:
        Upper bound on returned candidates.

    Returns
    -------
    list[dict]
        Unassessed DSO event dicts sorted by visibility score descending.
    """
    if not _dso_available:
        return []

    session_start = _ensure_utc_aware(session_start)
    session_end = _ensure_utc_aware(session_end)

    req_dur = float(available_duration_minutes) if available_duration_minutes else 45.0
    targets = dso_targets if dso_targets is not None else _DEFAULT_DSO_TARGETS

    scored_candidates: list[tuple[float, dict[str, Any]]] = []

    for dso_id in targets:
        if len(scored_candidates) >= max_candidates * 3:
            # We have plenty to sort and trim — stop early.
            break
        try:
            passes = generate_unassessed_deep_sky_passes(
                dso_target=dso_id,
                latitude=latitude,
                longitude=longitude,
                start_time=session_start,
                stop_time=session_end,
                required_duration_minutes=req_dur,
                twilight_mode="astronomical",
            )
            for p in passes:
                score = float(p.get("visibility_score") or 0.0)
                scored_candidates.append((score, p))
        except Exception as exc:
            logger.debug(
                "catalog_event_discovery: DSO '%s' not observable: %s", dso_id, exc
            )

    if not scored_candidates:
        return []

    # Sort by visibility score descending, pick best pass per DSO (by event_id prefix)
    scored_candidates.sort(key=lambda t: t[0], reverse=True)

    # Deduplicate by DSO: keep highest-score pass per object_id prefix
    seen_dso: set[str] = set()
    result: list[dict[str, Any]] = []
    for score, ev in scored_candidates:
        # event_id format: "pass_{object_id}_{block_idx}"
        ev_id = ev.get("event_id", "")
        parts = ev_id.split("_")
        dso_key = "_".join(parts[:2]) if len(parts) >= 2 else ev_id
        if dso_key not in seen_dso:
            seen_dso.add(dso_key)
            ev.setdefault("category", "deep_sky")
            result.append(ev)
        if len(result) >= max_candidates:
            break

    logger.info(
        "catalog_event_discovery: %d DSO candidate(s) found (from %d targets attempted)",
        len(result), len(targets),
    )
    return result


def discover_catalog_events(
    latitude: float,
    longitude: float,
    session_start: datetime,
    session_end: datetime,
    categories: list[str] | None = None,
    available_duration_minutes: float | None = None,
    dso_targets: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Discover all catalog-backed events for the given session.

    This is the primary entry point consumed by ``observation_plans.py``.
    It aggregates eclipse, meteor-shower, and deep-sky candidates into one
    list, normalised to the existing backend event shape.

    Parameters
    ----------
    latitude, longitude:
        Observer geodetic coordinates in degrees.
    session_start, session_end:
        Timezone-aware session boundary datetimes.
    categories:
        Optional subset filter: one or more of ``"eclipse"``,
        ``"meteor_shower"``, ``"deep_sky"``.  When *None* all three categories
        are discovered.
    available_duration_minutes:
        Observation duration budget forwarded to each engine.
    dso_targets:
        Explicit DSO list; forwarded to :func:`discover_deep_sky_candidates`.

    Returns
    -------
    list[dict]
        Zero or more unassessed event dicts with:
        - ``event_id``:        stable, deterministic string
        - ``name``:            human-readable target name
        - ``event_type``:      e.g. ``"solar_eclipse"``, ``"Meteor Shower"``, ``"Deep-Sky Object"``
        - ``window_start``:    timezone-aware ISO-8601 string
        - ``window_end``:      timezone-aware ISO-8601 string
        - ``duration_minutes``: float
        - ``visibility_score``: float (astronomical score only; weather/preference pending)
        - ``source``:          catalog provenance string
        - ``metadata``:        nested catalog metadata dict
    """
    discover_all = categories is None
    cats = set(c.lower() for c in categories) if categories else set()

    results: list[dict[str, Any]] = []

    if discover_all or "eclipse" in cats:
        results.extend(
            discover_eclipse_candidates(
                latitude=latitude,
                longitude=longitude,
                session_start=session_start,
                session_end=session_end,
                available_duration_minutes=available_duration_minutes,
            )
        )

    if discover_all or "meteor_shower" in cats or "meteor" in cats:
        results.extend(
            discover_meteor_shower_candidates(
                latitude=latitude,
                longitude=longitude,
                session_start=session_start,
                session_end=session_end,
                available_duration_minutes=available_duration_minutes,
            )
        )

    if discover_all or "deep_sky" in cats or "dso" in cats:
        results.extend(
            discover_deep_sky_candidates(
                latitude=latitude,
                longitude=longitude,
                session_start=session_start,
                session_end=session_end,
                available_duration_minutes=available_duration_minutes,
                dso_targets=dso_targets,
            )
        )

    logger.info(
        "catalog_event_discovery: total %d catalog candidate(s) for session %s → %s",
        len(results),
        session_start.isoformat() if hasattr(session_start, "isoformat") else str(session_start),
        session_end.isoformat() if hasattr(session_end, "isoformat") else str(session_end),
    )
    return results

