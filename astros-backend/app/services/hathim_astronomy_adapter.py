from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure the sibling 'astros-intelligence' package is on the import path
# The project layout is:
#   AstroOS/
#     astros-backend/
#     astros-intelligence/
# This file lives in astros-backend/app/services, so we go up three levels to the workspace root.
ROOT_PATH = Path(__file__).resolve().parents[3]
INTEL_PATH = ROOT_PATH / "astros-intelligence"
# Add both the intelligence source directory and the workspace root to sys.path
if str(INTEL_PATH) not in sys.path:
    sys.path.append(str(INTEL_PATH))
if str(ROOT_PATH) not in sys.path:
    sys.path.append(str(ROOT_PATH))

from typing import Any, Mapping
from datetime import datetime, timezone

# Import detailed scoring functions from installed astros-intelligence package (astronomy module)
try:
    from astronomy.event_adapter import (
        calculate_lunar_visibility_score,
        calculate_planetary_visibility_score,
        DEFAULT_MIN_ELEVATION_DEG,
        parse_horizons_timestamp,
    )
except ImportError:
    # Graceful fallback to dynamic load if not yet installed in environment
    import importlib.util
    EVENT_ADAPTER_PATH = INTEL_PATH / "astronomy" / "event_adapter.py"
    spec = importlib.util.spec_from_file_location("astronomy.event_adapter", EVENT_ADAPTER_PATH)
    _event_adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_event_adapter)
    calculate_lunar_visibility_score = _event_adapter.calculate_lunar_visibility_score
    calculate_planetary_visibility_score = _event_adapter.calculate_planetary_visibility_score
    DEFAULT_MIN_ELEVATION_DEG = _event_adapter.DEFAULT_MIN_ELEVATION_DEG
    parse_horizons_timestamp = _event_adapter.parse_horizons_timestamp

try:
    from astronomy.eclipse_engine import (
        calculate_eclipse_visibility_score,
        resolve_eclipse_target,
        ECLIPSE_CATALOG,
        _parse_dt_utc,
    )
except ImportError:
    import importlib.util
    ECLIPSE_PATH = INTEL_PATH / "astronomy" / "eclipse_engine.py"
    spec = importlib.util.spec_from_file_location("astronomy.eclipse_engine", ECLIPSE_PATH)
    _eclipse_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_eclipse_mod)
    calculate_eclipse_visibility_score = _eclipse_mod.calculate_eclipse_visibility_score
    resolve_eclipse_target = _eclipse_mod.resolve_eclipse_target
    ECLIPSE_CATALOG = _eclipse_mod.ECLIPSE_CATALOG
    _parse_dt_utc = _eclipse_mod._parse_dt_utc

try:
    from astronomy.deep_sky_engine import (
        calculate_deep_sky_visibility_score,
        resolve_deep_sky_object,
        calculate_horizontal_coordinates as calculate_dso_horizontal_coordinates,
        approximate_solar_elevation_deg as approximate_dso_solar_elevation_deg,
        DEEP_SKY_CATALOG,
        DEEP_SKY_ALIASES,
    )
except ImportError:
    import importlib.util
    DSO_PATH = INTEL_PATH / "astronomy" / "deep_sky_engine.py"
    spec = importlib.util.spec_from_file_location("astronomy.deep_sky_engine", DSO_PATH)
    _dso_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_dso_mod)
    calculate_deep_sky_visibility_score = _dso_mod.calculate_deep_sky_visibility_score
    resolve_deep_sky_object = _dso_mod.resolve_deep_sky_object
    calculate_dso_horizontal_coordinates = _dso_mod.calculate_horizontal_coordinates
    approximate_dso_solar_elevation_deg = _dso_mod.approximate_solar_elevation_deg
    DEEP_SKY_CATALOG = _dso_mod.DEEP_SKY_CATALOG
    DEEP_SKY_ALIASES = _dso_mod.DEEP_SKY_ALIASES

try:
    from astronomy.meteor_shower_engine import (
        calculate_meteor_shower_visibility_score,
        check_shower_activity,
        resolve_meteor_shower,
        calculate_horizontal_coordinates as calculate_meteor_horizontal_coordinates,
        approximate_solar_elevation_deg as approximate_meteor_solar_elevation_deg,
        METEOR_SHOWER_CATALOG,
    )
except ImportError:
    import importlib.util
    METEOR_PATH = INTEL_PATH / "astronomy" / "meteor_shower_engine.py"
    spec = importlib.util.spec_from_file_location("astronomy.meteor_shower_engine", METEOR_PATH)
    _meteor_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_meteor_mod)
    calculate_meteor_shower_visibility_score = _meteor_mod.calculate_meteor_shower_visibility_score
    check_shower_activity = _meteor_mod.check_shower_activity
    resolve_meteor_shower = _meteor_mod.resolve_meteor_shower
    calculate_meteor_horizontal_coordinates = _meteor_mod.calculate_horizontal_coordinates
    approximate_meteor_solar_elevation_deg = _meteor_mod.approximate_solar_elevation_deg
    METEOR_SHOWER_CATALOG = _meteor_mod.METEOR_SHOWER_CATALOG


from app.services.astronomy_adapter import (
    BaseAstronomyAdapter,
    AstronomicalAssessment,
)


class HathimAstronomyAdapter(BaseAstronomyAdapter):
    """Thin wrapper around Hathim's detailed astronomy calculations.

    It extracts the required fields from a CelestialEvent (or compatible dict)
    and delegates to the authoritative scoring functions provided by the
    `astros_intelligence` package. The adapter conforms to the same interface
    as :class:`CelestialEventAstronomyAdapter` used elsewhere in the backend.
    """

    def _parse_dt(self, val: Any) -> datetime | None:
        """Parse string or datetime to timezone-aware UTC datetime."""
        if val is None:
            return None
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        if isinstance(val, str):
            val_str = val.strip()
            if val_str.endswith("Z"):
                val_str = val_str[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(val_str)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception:
                try:
                    return parse_horizons_timestamp(val)
                except Exception:
                    return None
        return None

    def _extract_extra(self, event: Any) -> Mapping[str, Any]:
        """Return the ``additional_data`` mapping or event dict itself.

        Supports both ORM objects with an ``additional_data`` attribute and
        plain dictionaries.
        """
        if isinstance(event, dict):
            extra = event.get("additional_data")
            if isinstance(extra, dict) and extra:
                combined = dict(event)
                combined.update(extra)
            else:
                combined = dict(event)
            meta = event.get("metadata")
            if isinstance(meta, dict):
                derived = meta.get("derived_astronomical_values")
                if isinstance(derived, dict):
                    for k, v in derived.items():
                        combined.setdefault(k, v)
                facts = meta.get("nasa_horizons_facts")
                if isinstance(facts, dict):
                    for k, v in facts.items():
                        combined.setdefault(k, v)
            return combined
        extra = getattr(event, "additional_data", None)
        if isinstance(extra, dict):
            return extra
        return {}

    def evaluate_celestial_event(
        self,
        event: Any,
        latitude: float,
        longitude: float,
        bortle_class: int | None = None,
    ) -> AstronomicalAssessment:
        extra = self._extract_extra(event)
        if isinstance(event, dict):
            category = str(event.get("category", "")).strip().lower()
            event_type = str(event.get("event_type") or event.get("type") or "").strip().lower()
            name = str(event.get("name", "")).strip().lower()
        else:
            category = str(getattr(event, "category", "")).strip().lower()
            event_type = str(getattr(event, "event_type", None) or getattr(event, "type", "")).strip().lower()
            name = str(getattr(event, "name", "")).strip().lower()

        target_id_str = str(extra.get("target_id", "")).strip()

        # Check for pre-computed authoritative visibility score (e.g. from JPL derived values)
        derived_score = extra.get("computed_visibility_score")
        if derived_score is not None:
            try:
                return AstronomicalAssessment(
                    is_calculable=True,
                    astronomical_score=float(derived_score),
                    factors={
                        "category": category,
                        "event_type": event_type,
                        "peak_elevation_deg": extra.get("target_altitude_deg") or extra.get("altitude") or extra.get("peak_elevation_deg"),
                        "bortle_class": bortle_class,
                    },
                    limitations=[],
                    adapter_source="hathim_astronomy_adapter_v1_derived",
                )
            except (ValueError, TypeError):
                pass

        is_eclipse = (
            category in ("eclipse", "solar_eclipse", "lunar_eclipse")
            or "eclipse" in event_type
            or "eclipse" in category
            or "eclipse" in name
        )
        is_meteor = (
            category in ("meteor_shower", "meteor")
            or "meteor" in event_type
            or "meteor" in category
            or "meteor" in name
        )
        is_deep_sky = (
            category in ("deep_sky", "dso", "messier", "ngc", "ic")
            or "deep_sky" in event_type
            or "dso" in event_type
            or target_id_str.lower() in DEEP_SKY_ALIASES
            or target_id_str.lower().replace(" ", "") in DEEP_SKY_ALIASES
            or (name and name.lower() in DEEP_SKY_ALIASES)
            or (name and name.lower().replace(" ", "") in DEEP_SKY_ALIASES)
        )
        is_lunar = (
            not is_eclipse
            and not is_meteor
            and not is_deep_sky
            and (
                category in ("lunar", "moon")
                or "moon" in event_type
                or "lunar" in event_type
                or "moon" in name
                or target_id_str.startswith("301")
            )
        )
        is_planetary = (
            not is_eclipse
            and not is_meteor
            and not is_deep_sky
            and (
                category in ("planet", "planetary")
                or "planet" in event_type
                or "planetary" in event_type
                or target_id_str in ("199", "299", "499", "599", "699", "799", "899")
            )
        )

        factors: dict[str, Any] = {
            "category": category,
            "event_type": event_type,
            "bortle_class": bortle_class,
        }

        if is_eclipse:
            target_key = extra.get("eclipse_id") or extra.get("target_id") or name or event_type
            catalog_entry: dict[str, Any] | None = None
            if target_key:
                try:
                    resolved = resolve_eclipse_target(target_key)
                    if isinstance(resolved, dict) and "eclipse_type" in resolved:
                        catalog_entry = resolved
                except Exception:
                    pass

            eclipse_dict: dict[str, Any] = dict(catalog_entry) if catalog_entry else {}
            for k, v in extra.items():
                if v is not None:
                    eclipse_dict[k] = v

            if not eclipse_dict.get("eclipse_type"):
                if "solar" in category or "solar" in event_type or "solar" in name:
                    eclipse_dict["eclipse_type"] = "Partial Solar Eclipse"
                elif "lunar" in category or "lunar" in event_type or "lunar" in name:
                    eclipse_dict["eclipse_type"] = "Partial Lunar Eclipse"
                else:
                    eclipse_dict["eclipse_type"] = "Total Solar Eclipse"

            peak_dt = (
                self._parse_dt(extra.get("peak_dt_utc"))
                or self._parse_dt(extra.get("peak_timestamp_utc"))
                or self._parse_dt(extra.get("peak_time_utc"))
                or self._parse_dt(extra.get("window_start"))
                or self._parse_dt(extra.get("start_time"))
            )
            if peak_dt is None and eclipse_dict.get("date_utc") and eclipse_dict.get("peak_time_utc"):
                try:
                    peak_dt = _parse_dt_utc(str(eclipse_dict["date_utc"]), str(eclipse_dict["peak_time_utc"]))
                except Exception:
                    peak_dt = None

            if peak_dt is None:
                return AstronomicalAssessment(
                    is_calculable=False,
                    astronomical_score=None,
                    factors=factors,
                    limitations=["Eclipse event lacks required peak timestamp or catalog date for scoring."],
                    adapter_source="hathim_astronomy_adapter_v1",
                )

            try:
                score, expl = calculate_eclipse_visibility_score(
                    eclipse=eclipse_dict,
                    observer_latitude=float(latitude),
                    observer_longitude=float(longitude),
                    peak_dt_utc=peak_dt,
                )
                factors.update({
                    "eclipse_type": eclipse_dict.get("eclipse_type"),
                    "magnitude": eclipse_dict.get("magnitude") or eclipse_dict.get("umbral_magnitude"),
                    "explanation": expl,
                    "peak_dt_utc": peak_dt.isoformat(),
                })
                return AstronomicalAssessment(
                    is_calculable=True,
                    astronomical_score=float(score),
                    factors=factors,
                    limitations=[] if score > 0 else [expl],
                    adapter_source="hathim_astronomy_adapter_v1",
                )
            except Exception as err:
                return AstronomicalAssessment(
                    is_calculable=False,
                    astronomical_score=None,
                    factors=factors,
                    limitations=[f"Eclipse calculation failed: {err}"],
                    adapter_source="hathim_astronomy_adapter_v1",
                )

        elif is_deep_sky:
            dso_query = (
                extra.get("catalog_id")
                or extra.get("object_id")
                or extra.get("target_id")
                or extra.get("target")
                or name
                or event_type
            )
            obj_data: dict[str, Any] | None = None
            if dso_query:
                # 1. Direct resolution
                try:
                    obj_data = dict(resolve_deep_sky_object(dso_query))
                except Exception:
                    pass

                # 2. Compound name fallback (e.g. "M31 Andromeda", "M42 (Orion Nebula)")
                if obj_data is None and isinstance(dso_query, str):
                    clean_query = dso_query.replace("(", " ").replace(")", " ").strip()
                    parts = clean_query.split()
                    if len(parts) > 1:
                        # Try first part (e.g. "M31", "M42")
                        try:
                            obj_data = dict(resolve_deep_sky_object(parts[0]))
                        except Exception:
                            pass
                        # If first part was NGC or IC, try "NGC 7000"
                        if obj_data is None and len(parts) >= 2 and parts[0].upper() in ("NGC", "IC"):
                            try:
                                obj_data = dict(resolve_deep_sky_object(f"{parts[0].upper()} {parts[1]}"))
                            except Exception:
                                pass
                        # Try the remaining phrase (e.g. "Andromeda Galaxy", "Orion Nebula")
                        if obj_data is None:
                            try:
                                obj_data = dict(resolve_deep_sky_object(" ".join(parts[1:])))
                            except Exception:
                                pass

            if obj_data is None:
                if extra.get("apparent_magnitude") is not None or extra.get("magnitude") is not None:
                    obj_data = {
                        "object_id": str(dso_query or "DSO"),
                        "name": name or str(dso_query or "DSO"),
                        "object_type": extra.get("object_type", "Deep-Sky Object"),
                        "apparent_magnitude": float(extra.get("apparent_magnitude") or extra.get("magnitude")),
                        "ra_deg": float(extra.get("ra_deg", 0.0)),
                        "dec_deg": float(extra.get("dec_deg", 0.0)),
                    }

            if obj_data is None:
                return AstronomicalAssessment(
                    is_calculable=False,
                    astronomical_score=None,
                    factors=factors,
                    limitations=["Deep-sky target could not be resolved from catalog and lacks required optical parameters."],
                    adapter_source="hathim_astronomy_adapter_v1",
                )

            obs_dt = (
                self._parse_dt(extra.get("observed_at"))
                or self._parse_dt(extra.get("window_start"))
                or self._parse_dt(extra.get("start_time"))
                or self._parse_dt(extra.get("peak_timestamp_utc"))
            )

            peak_elevation = extra.get("target_altitude_deg") or extra.get("altitude") or extra.get("peak_elevation_deg")
            if peak_elevation is None and obs_dt is not None and "ra_deg" in obj_data and "dec_deg" in obj_data:
                try:
                    peak_elevation, _ = calculate_dso_horizontal_coordinates(
                        float(obj_data["ra_deg"]),
                        float(obj_data["dec_deg"]),
                        float(latitude),
                        float(longitude),
                        obs_dt,
                    )
                except Exception:
                    peak_elevation = None

            if peak_elevation is None:
                factors["target"] = obj_data.get("name") or obj_data.get("object_id")
                return AstronomicalAssessment(
                    is_calculable=False,
                    astronomical_score=None,
                    factors=factors,
                    limitations=["Deep-sky event missing altitude/elevation data for scoring."],
                    adapter_source="hathim_astronomy_adapter_v1",
                )

            sun_el = extra.get("sun_elevation_deg")
            if sun_el is None:
                sun_el = extra.get("solar_elevation_deg")
            if sun_el is None:
                sun_el = extra.get("mean_sun_elevation_deg")

            if sun_el is not None:
                try:
                    sun_el = float(sun_el)
                except (ValueError, TypeError):
                    sun_el = None

            if sun_el is None and obs_dt is not None:
                try:
                    sun_el = approximate_dso_solar_elevation_deg(obs_dt, float(latitude), float(longitude))
                except (ValueError, TypeError, OverflowError):
                    sun_el = None

            if sun_el is None:
                factors["target"] = obj_data.get("name") or obj_data.get("object_id")
                return AstronomicalAssessment(
                    is_calculable=False,
                    astronomical_score=None,
                    factors=factors,
                    limitations=["Deep-sky observation requires valid solar elevation or observation timestamp to verify dark skies."],
                    adapter_source="hathim_astronomy_adapter_v1",
                )

            moon_illum = extra.get("moon_illumination_percent")
            if moon_illum is not None:
                try:
                    moon_illum = float(moon_illum)
                    if moon_illum > 1.0:
                        moon_illum = moon_illum / 100.0
                except (ValueError, TypeError):
                    moon_illum = None
            elif extra.get("moon_illumination") is not None:
                try:
                    moon_illum = float(extra.get("moon_illumination"))
                except (ValueError, TypeError):
                    moon_illum = None

            moon_el = extra.get("moon_elevation_deg") or extra.get("moon_altitude_deg")
            if moon_el is not None:
                try:
                    moon_el = float(moon_el)
                except (ValueError, TypeError):
                    moon_el = None

            try:
                score, expl = calculate_deep_sky_visibility_score(
                    obj_data=obj_data,
                    peak_elevation_deg=float(peak_elevation),
                    mean_sun_elevation_deg=float(sun_el),
                    moon_illumination=moon_illum,
                    moon_elevation_deg=moon_el,
                )
                factors.update({
                    "target": obj_data.get("name") or obj_data.get("object_id"),
                    "peak_elevation_deg": float(peak_elevation),
                    "apparent_magnitude": obj_data.get("apparent_magnitude"),
                    "explanation": expl,
                })
                return AstronomicalAssessment(
                    is_calculable=True,
                    astronomical_score=float(score),
                    factors=factors,
                    limitations=[] if score > 0 else [expl],
                    adapter_source="hathim_astronomy_adapter_v1",
                )
            except Exception as err:
                return AstronomicalAssessment(
                    is_calculable=False,
                    astronomical_score=None,
                    factors=factors,
                    limitations=[f"Deep-sky scoring failed: {err}"],
                    adapter_source="hathim_astronomy_adapter_v1",
                )

        elif is_meteor:
            shower_query = extra.get("shower_id") or extra.get("target_id") or extra.get("target") or name or event_type
            shower_config: dict[str, Any] | None = None
            if shower_query:
                try:
                    shower_config = resolve_meteor_shower(shower_query)
                except Exception:
                    pass

            obs_dt = (
                self._parse_dt(extra.get("observed_at"))
                or self._parse_dt(extra.get("window_start"))
                or self._parse_dt(extra.get("start_time"))
                or self._parse_dt(extra.get("peak_timestamp_utc"))
            )

            radiant_el = (
                extra.get("radiant_elevation_deg")
                or extra.get("target_altitude_deg")
                or extra.get("altitude")
                or extra.get("peak_elevation_deg")
            )
            if radiant_el is None and shower_config and obs_dt:
                try:
                    radiant_el, _ = calculate_meteor_horizontal_coordinates(
                        float(shower_config["radiant_ra_deg"]),
                        float(shower_config["radiant_dec_deg"]),
                        float(latitude),
                        float(longitude),
                        obs_dt,
                    )
                except Exception:
                    radiant_el = None

            if radiant_el is None:
                return AstronomicalAssessment(
                    is_calculable=False,
                    astronomical_score=None,
                    factors=factors,
                    limitations=["Meteor shower event missing radiant altitude data for scoring."],
                    adapter_source="hathim_astronomy_adapter_v1",
                )

            activity_factor = extra.get("activity_factor")
            if activity_factor is None and shower_config and obs_dt:
                try:
                    act_info = check_shower_activity(shower_config, obs_dt)
                    activity_factor = act_info.get("activity_factor", 1.0)
                except Exception:
                    activity_factor = 1.0
            if activity_factor is None:
                activity_factor = 1.0

            sun_el = extra.get("sun_elevation_deg")
            if sun_el is None:
                sun_el = extra.get("solar_elevation_deg")
            if sun_el is None:
                sun_el = extra.get("mean_sun_elevation_deg")

            if sun_el is not None:
                try:
                    sun_el = float(sun_el)
                except (ValueError, TypeError):
                    sun_el = None

            if sun_el is None and obs_dt is not None:
                try:
                    sun_el = approximate_meteor_solar_elevation_deg(float(latitude), float(longitude), obs_dt)
                except (ValueError, TypeError, OverflowError):
                    sun_el = None

            if sun_el is None:
                shower_name = shower_config.get("name") if shower_config else (name or str(shower_query))
                factors["target"] = shower_name
                return AstronomicalAssessment(
                    is_calculable=False,
                    astronomical_score=None,
                    factors=factors,
                    limitations=["Meteor shower observation requires valid solar elevation or observation timestamp to verify dark skies."],
                    adapter_source="hathim_astronomy_adapter_v1",
                )

            moon_el = extra.get("moon_elevation_deg") or extra.get("moon_altitude_deg")
            moon_illum = extra.get("moon_illumination_percent")
            if moon_illum is not None:
                try:
                    moon_illum = float(moon_illum)
                    if moon_illum > 1.0:
                        moon_illum = moon_illum / 100.0
                except (ValueError, TypeError):
                    moon_illum = None
            elif extra.get("moon_illumination") is not None:
                try:
                    moon_illum = float(extra.get("moon_illumination"))
                except (ValueError, TypeError):
                    moon_illum = None

            try:
                score = calculate_meteor_shower_visibility_score(
                    radiant_elevation_deg=float(radiant_el),
                    activity_factor=float(activity_factor),
                    sun_elevation_deg=float(sun_el) if sun_el is not None else None,
                    moon_elevation_deg=float(moon_el) if moon_el is not None else None,
                    moon_illumination_fraction=moon_illum,
                )
                target_short = shower_config.get("name") if shower_config else (name or str(shower_query))
                display_name = shower_config.get("display_name") if shower_config else target_short
                shower_id = shower_config.get("shower_id") if shower_config else str(shower_query or "")
                factors.update({
                    "target": target_short,
                    "display_name": display_name,
                    "shower_id": shower_id,
                    "radiant_elevation_deg": float(radiant_el),
                    "activity_factor": float(activity_factor),
                })
                return AstronomicalAssessment(
                    is_calculable=True,
                    astronomical_score=float(score),
                    factors=factors,
                    limitations=[] if score > 0 else ["Radiant below horizon, daytime twilight, or shower inactive."],
                    adapter_source="hathim_astronomy_adapter_v1",
                )
            except Exception as err:
                return AstronomicalAssessment(
                    is_calculable=False,
                    astronomical_score=None,
                    factors=factors,
                    limitations=[f"Meteor shower scoring failed: {err}"],
                    adapter_source="hathim_astronomy_adapter_v1",
                )

        elif is_lunar:
            peak_elevation = extra.get("target_altitude_deg") or extra.get("altitude") or extra.get("peak_elevation_deg")
            phase_angle = extra.get("phase_angle_deg")
            if peak_elevation is None:
                # Fallback to pre-computed visibility score from JPL derived values if present
                derived_score = extra.get("computed_visibility_score")
                if derived_score is not None:
                    try:
                        return AstronomicalAssessment(
                            is_calculable=True,
                            astronomical_score=float(derived_score),
                            factors={"category": category, "event_type": event_type, "bortle_class": bortle_class},
                            limitations=[],
                            adapter_source="hathim_astronomy_adapter_v1_derived",
                        )
                    except (ValueError, TypeError):
                        pass
                return AstronomicalAssessment(
                    is_calculable=False,
                    astronomical_score=None,
                    factors={"category": category, "event_type": event_type},
                    limitations=["Lunar event lacks required altitude information for scoring."],
                    adapter_source="hathim_astronomy_adapter_v1",
                )
            score = calculate_lunar_visibility_score(
                float(peak_elevation),
                phase_angle_deg=phase_angle,
                min_elevation_deg=DEFAULT_MIN_ELEVATION_DEG,
            )
        elif is_planetary:
            peak_elevation = extra.get("target_altitude_deg") or extra.get("altitude") or extra.get("peak_elevation_deg")
            visual_mag = extra.get("apparent_magnitude") or extra.get("magnitude") or extra.get("visual_magnitude")
            if peak_elevation is None:
                # Fallback to pre-computed visibility score from JPL derived values if present
                derived_score = extra.get("computed_visibility_score")
                if derived_score is not None:
                    try:
                        return AstronomicalAssessment(
                            is_calculable=True,
                            astronomical_score=float(derived_score),
                            factors={"category": category, "event_type": event_type, "bortle_class": bortle_class},
                            limitations=[],
                            adapter_source="hathim_astronomy_adapter_v1_derived",
                        )
                    except (ValueError, TypeError):
                        pass
                return AstronomicalAssessment(
                    is_calculable=False,
                    astronomical_score=None,
                    factors={"category": category, "event_type": event_type},
                    limitations=["Planetary event missing altitude data for scoring."],
                    adapter_source="hathim_astronomy_adapter_v1",
                )
            score = calculate_planetary_visibility_score(
                float(peak_elevation),
                visual_magnitude=visual_mag,
                min_elevation_deg=DEFAULT_MIN_ELEVATION_DEG,
            )
        else:
            # Fallback for any other event type if pre-computed score is present
            derived_score = extra.get("computed_visibility_score")
            if derived_score is not None:
                try:
                    return AstronomicalAssessment(
                        is_calculable=True,
                        astronomical_score=float(derived_score),
                        factors={"category": category, "event_type": event_type, "bortle_class": bortle_class},
                        limitations=[],
                        adapter_source="hathim_astronomy_adapter_v1_derived",
                    )
                except (ValueError, TypeError):
                    pass
            return AstronomicalAssessment(
                is_calculable=False,
                astronomical_score=None,
                factors={"category": category, "event_type": event_type},
                limitations=["Hathim adapter currently supports only lunar and planetary events."],
                adapter_source="hathim_astronomy_adapter_v1",
            )

        return AstronomicalAssessment(
            is_calculable=True,
            astronomical_score=score,
            factors={
                "category": category,
                "event_type": event_type,
                "peak_elevation_deg": peak_elevation,
                "bortle_class": bortle_class,
            },
            limitations=[],
            adapter_source="hathim_astronomy_adapter_v1",
        )
