"""Light pollution service and provider interface.

Adheres to scientific data standards:
- World Atlas of Artificial Night Sky Brightness (Falchi et al., 2016; Lorenz 2024 model)
- Does not scrape map tiles or invent APIs.
- Returns explicit 'unavailable' status when dataset is not configured.
- Supports grid lookup with spatial bounds checking and nearest-cell querying.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import math
from pathlib import Path
from typing import Any, Mapping
from pydantic import BaseModel, Field

from app.core.config import LIGHT_POLLUTION_DATA_PATH


class LightPollutionResult(BaseModel):
    """Normalized light-pollution assessment result for a geographic coordinate."""

    status: str = Field(
        ...,
        description="Assessment status: 'success', 'unavailable', 'out_of_coverage', or 'error'",
    )
    bortle_class: int | None = Field(
        default=None,
        ge=1,
        le=9,
        description="Estimated Bortle class from 1 (excellent dark sky) to 9 (inner-city sky)",
    )
    artificial_brightness_mcd: float | None = Field(
        default=None,
        ge=0,
        description="Artificial night sky brightness in mcd/m²",
    )
    sqm: float | None = Field(
        default=None,
        description="Estimated Sky Quality Meter reading in mag/arcsec²",
    )
    ratio_to_natural_sky: float | None = Field(
        default=None,
        ge=0,
        description="Ratio of artificial brightness to natural night sky background",
    )
    source: str = Field(
        default="unavailable",
        description="Data source and provenance",
    )
    dataset_year: int | None = Field(
        default=None,
        description="Publication or reference year of the dataset",
    )
    spatial_resolution: str | None = Field(
        default=None,
        description="Spatial resolution of the grid (e.g., '30 arcsec (~1 km)')",
    )
    attribution: str | None = Field(
        default=None,
        description="License and legal attribution requirements",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Limitations, caveats, or missing data explanations",
    )


def artificial_brightness_to_bortle(art_mcd: float) -> int:
    """Convert artificial sky brightness (mcd/m²) to an approximate Bortle class.

    Based on Falchi et al. (2016) and Cinzano thresholds:
    Natural dark sky zenith luminance is approximately 0.174 mcd/m² (~22.0 mag/arcsec²).
    - Bortle 1: < 0.0017 mcd/m² (ratio < 0.01)
    - Bortle 2: 0.0017 - 0.019 mcd/m²
    - Bortle 3: 0.019 - 0.09 mcd/m²
    - Bortle 4: 0.09 - 0.27 mcd/m²
    - Bortle 4.5/5: 0.27 - 0.87 mcd/m²
    - Bortle 6: 0.87 - 2.6 mcd/m²
    - Bortle 7: 2.6 - 7.8 mcd/m²
    - Bortle 8: 7.8 - 23 mcd/m²
    - Bortle 9: >= 23 mcd/m²
    """
    if art_mcd < 0.002:
        return 1
    elif art_mcd < 0.02:
        return 2
    elif art_mcd < 0.09:
        return 3
    elif art_mcd < 0.27:
        return 4
    elif art_mcd < 0.87:
        return 5
    elif art_mcd < 2.6:
        return 6
    elif art_mcd < 7.8:
        return 7
    elif art_mcd < 23.0:
        return 8
    else:
        return 9


def artificial_brightness_to_sqm(art_mcd: float) -> float:
    """Convert artificial brightness (mcd/m²) to approximate SQM (mag/arcsec²).

    Natural sky is ~0.174 mcd/m² (22.0 mag/arcsec²).
    Total sky brightness = Natural (0.174) + Artificial.
    SQM = 22.0 - 2.5 * log10(1 + art_mcd / 0.174)
    """
    natural_mcd = 0.174
    total_ratio = 1.0 + max(0.0, art_mcd) / natural_mcd
    sqm = 22.0 - 2.5 * math.log10(total_ratio)
    return round(max(16.0, min(22.0, sqm)), 2)


class BaseLightPollutionProvider(ABC):
    """Abstract interface for light pollution data providers."""

    @abstractmethod
    def get_light_pollution(
        self,
        latitude: float,
        longitude: float,
    ) -> LightPollutionResult:
        """Query light pollution at the specified coordinates."""
        raise NotImplementedError


class UnavailableLightPollutionProvider(BaseLightPollutionProvider):
    """Provider used when no light pollution dataset is configured or accessible.

    Complies with project rules:
    - Never fabricates fake light pollution numbers.
    - Explicitly returns status="unavailable".
    - Documents setup instructions.
    """

    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason or (
            "Light-pollution dataset is not configured. To enable point queries, "
            "download the World Atlas dataset (GFZ Data Services, DOI: 10.5880/GFZ.1.4.2016.001) "
            "or Lorenz atlas raster, and configure LIGHT_POLLUTION_DATA_PATH in .env."
        )

    def get_light_pollution(
        self,
        latitude: float,
        longitude: float,
    ) -> LightPollutionResult:
        if not -90 <= latitude <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")

        return LightPollutionResult(
            status="unavailable",
            bortle_class=None,
            artificial_brightness_mcd=None,
            sqm=None,
            ratio_to_natural_sky=None,
            source="unavailable",
            dataset_year=None,
            spatial_resolution=None,
            attribution=None,
            limitations=[self.reason],
        )


class GridLightPollutionProvider(BaseLightPollutionProvider):
    """Grid-based light pollution provider querying nearest valid cell.

    Can be initialized with a grid dictionary or a JSON file defining:
    - lat_min, lat_max, lon_min, lon_max
    - resolution_deg (or lat_step, lon_step)
    - values: 2D array [lat_idx][lon_idx] of artificial brightness in mcd/m²
    - metadata (provenance, year, spatial resolution, attribution)
    """

    def __init__(
        self,
        grid_data: Mapping[str, Any] | None = None,
        file_path: str | Path | None = None,
    ) -> None:
        if grid_data is not None:
            self._init_from_dict(grid_data)
        elif file_path is not None:
            path = Path(file_path)
            if not path.is_file():
                raise FileNotFoundError(f"Light pollution grid file not found: {path}")
            suffix = path.suffix.lower()
            if suffix in (".asc", ".grd"):
                self._init_from_esri_asc(path)
            elif suffix in (".tif", ".tiff"):
                self._init_from_geotiff(path)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._init_from_dict(data)
        else:
            raise ValueError("Either grid_data or file_path must be provided")

    def _init_from_dict(self, data: Mapping[str, Any]) -> None:
        self.lat_min = float(data["lat_min"])
        self.lat_max = float(data["lat_max"])
        self.lon_min = float(data["lon_min"])
        self.lon_max = float(data["lon_max"])
        self.lat_step = float(data.get("lat_step") or data.get("resolution_deg", 0.008333))
        self.lon_step = float(data.get("lon_step") or data.get("resolution_deg", 0.008333))
        self.values = data["values"]  # list of lists
        self.row_order = str(data.get("row_order", "south_to_north")).lower()
        self.source = str(data.get("source", "The New World Atlas of Artificial Night Sky Brightness"))
        self.dataset_year = int(data.get("dataset_year", 2016))
        self.spatial_resolution = str(data.get("spatial_resolution", "30 arcsec (~1 km)"))
        self.attribution = str(
            data.get(
                "attribution",
                "Falchi et al. (2016) / GFZ Data Services under CC BY 4.0",
            )
        )

    def _init_from_esri_asc(self, path: Path) -> None:
        """Parse standard ESRI ASCII raster grid (.asc / .grd)."""
        header: dict[str, float] = {}
        values: list[list[float | None]] = []
        esri_keywords = {
            "ncols",
            "nrows",
            "xllcorner",
            "yllcorner",
            "xllcenter",
            "yllcenter",
            "cellsize",
            "nodata_value",
            "nodata",
        }
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                parts = line_str.split()
                if len(parts) == 2 and parts[0].lower() in esri_keywords:
                    header[parts[0].lower()] = float(parts[1])
                else:
                    nodata = header.get("nodata_value", -9999.0)
                    row = [
                        None if math.isclose(float(v), nodata, rel_tol=1e-5) or float(v) < 0 else float(v)
                        for v in parts
                    ]
                    values.append(row)

        ncols = int(header.get("ncols", len(values[0]) if values else 0))
        nrows = int(header.get("nrows", len(values)))
        cellsize = header.get("cellsize", 0.008333333333333)

        if "xllcorner" in header:
            self.lon_min = header["xllcorner"]
        elif "xllcenter" in header:
            self.lon_min = header["xllcenter"] - cellsize / 2.0
        else:
            self.lon_min = -180.0

        if "yllcorner" in header:
            self.lat_min = header["yllcorner"]
        elif "yllcenter" in header:
            self.lat_min = header["yllcenter"] - cellsize / 2.0
        else:
            self.lat_min = -90.0

        self.lon_max = self.lon_min + ncols * cellsize
        self.lat_max = self.lat_min + nrows * cellsize
        self.lat_step = cellsize
        self.lon_step = cellsize
        self.values = values
        self.row_order = "north_to_south"
        self.source = "ESRI ASCII Raster Grid (Falchi et al., 2016 / World Atlas)"
        self.dataset_year = 2016
        self.spatial_resolution = f"{cellsize * 3600:.0f} arcsec"
        self.attribution = "Falchi et al. (2016) / GFZ Data Services under CC BY-NC 4.0"

    def _init_from_geotiff(self, path: Path) -> None:
        """Attempt to read GeoTIFF using rasterio if installed."""
        try:
            import rasterio
        except ImportError as exc:
            raise RuntimeError(
                f"Reading GeoTIFF files requires 'rasterio'. Please install rasterio or "
                f"export the regional dataset to an ESRI ASCII grid (.asc) or regional JSON grid: {exc}"
            ) from exc

        with rasterio.open(path) as src:
            bounds = src.bounds
            self.lon_min = bounds.left
            self.lon_max = bounds.right
            self.lat_min = bounds.bottom
            self.lat_max = bounds.top
            self.lon_step = src.res[0]
            self.lat_step = src.res[1]
            band = src.read(1)
            nodata = src.nodata
            self.values = [
                [
                    None if (nodata is not None and math.isclose(float(v), float(nodata), rel_tol=1e-5)) or float(v) < 0 else float(v)
                    for v in row
                ]
                for row in band
            ]
            self.row_order = "north_to_south"
            self.source = "GeoTIFF (World Atlas / Falchi et al., 2016)"
            self.dataset_year = 2016
            self.spatial_resolution = f"{self.lat_step * 3600:.0f} arcsec"
            self.attribution = "Falchi et al. (2016) / GFZ Data Services under CC BY-NC 4.0"

    def get_light_pollution(
        self,
        latitude: float,
        longitude: float,
    ) -> LightPollutionResult:
        if not -90 <= latitude <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")

        # Check coverage
        if not (self.lat_min <= latitude <= self.lat_max and self.lon_min <= longitude <= self.lon_max):
            return LightPollutionResult(
                status="out_of_coverage",
                bortle_class=None,
                artificial_brightness_mcd=None,
                sqm=None,
                ratio_to_natural_sky=None,
                source=self.source,
                dataset_year=self.dataset_year,
                spatial_resolution=self.spatial_resolution,
                attribution=self.attribution,
                limitations=[
                    f"Coordinates ({latitude}, {longitude}) are outside the grid coverage "
                    f"[{self.lat_min}, {self.lat_max}] lat, [{self.lon_min}, {self.lon_max}] lon."
                ],
            )

        # Nearest neighbor index based on row ordering
        row_order = getattr(self, "row_order", "south_to_north")
        if row_order == "north_to_south":
            row_idx = int(round((self.lat_max - latitude) / self.lat_step))
        else:
            row_idx = int(round((latitude - self.lat_min) / self.lat_step))

        col_idx = int(round((longitude - self.lon_min) / self.lon_step))

        row_idx = max(0, min(len(self.values) - 1, row_idx))
        row = self.values[row_idx]
        col_idx = max(0, min(len(row) - 1, col_idx))

        raw_val = row[col_idx]
        if raw_val is None or raw_val < 0:
            return LightPollutionResult(
                status="unavailable",
                bortle_class=None,
                artificial_brightness_mcd=None,
                sqm=None,
                ratio_to_natural_sky=None,
                source=self.source,
                dataset_year=self.dataset_year,
                spatial_resolution=self.spatial_resolution,
                attribution=self.attribution,
                limitations=["No valid data at the nearest grid cell."],
            )

        art_mcd = float(raw_val)
        natural_mcd = 0.174
        ratio = round(art_mcd / natural_mcd, 3)
        bortle = artificial_brightness_to_bortle(art_mcd)
        sqm = artificial_brightness_to_sqm(art_mcd)

        return LightPollutionResult(
            status="success",
            bortle_class=bortle,
            artificial_brightness_mcd=round(art_mcd, 4),
            sqm=sqm,
            ratio_to_natural_sky=ratio,
            source=self.source,
            dataset_year=self.dataset_year,
            spatial_resolution=self.spatial_resolution,
            attribution=self.attribution,
            limitations=[],
        )


def get_light_pollution_provider(
    data_path: str | Path | None = None,
) -> BaseLightPollutionProvider:
    """Return active light pollution provider based on configuration.

    Priority:
    1. GridLightPollutionProvider if a valid data file is configured.
    2. DarkSkySitesLightPollutionProvider if DARKSKYSITES_API_KEY is set.
    3. UnavailableLightPollutionProvider as fallback.
    """
    target_path = data_path if data_path is not None else LIGHT_POLLUTION_DATA_PATH
    if target_path:
        path = Path(target_path)
        if path.is_file():
            try:
                return GridLightPollutionProvider(file_path=path)
            except Exception as exc:
                return UnavailableLightPollutionProvider(
                    reason=f"Failed to load light pollution grid from {path}: {exc}"
                )
        return UnavailableLightPollutionProvider(
            reason=f"Configured light pollution data file not found at: {path}"
        )

    # Try DarkSkySites API if key is available
    from app.core.config import DARKSKYSITES_API_KEY  # local import avoids circular deps

    if DARKSKYSITES_API_KEY:
        return DarkSkySitesLightPollutionProvider(api_key=DARKSKYSITES_API_KEY)

    return UnavailableLightPollutionProvider()


# ─────────────────────────────────────────────────────────────────────────────
# DarkSkySites API provider
# ─────────────────────────────────────────────────────────────────────────────

class DarkSkySitesError(Exception):
    """Base exception for DarkSkySites provider errors."""


class DarkSkySitesAuthError(DarkSkySitesError):
    """Raised on HTTP 401 / 403 — key missing, invalid, or access revoked."""


class DarkSkySitesRateLimitError(DarkSkySitesError):
    """Raised on HTTP 429 — request rate or monthly allowance reached."""


class DarkSkySitesUnavailableError(DarkSkySitesError):
    """Raised on HTTP 503 — API temporarily unavailable."""


class DarkSkySitesTimeoutError(DarkSkySitesError):
    """Raised when the request times out."""


class DarkSkySitesDataError(DarkSkySitesError):
    """Raised when the response body cannot be parsed or is missing required fields."""


def _sqm_to_artificial_brightness_mcd(sqm: float) -> float:
    """Convert SQM (mag/arcsec²) to approximate artificial brightness (mcd/m²).

    Inverse of artificial_brightness_to_sqm():
        SQM = 22.0 - 2.5 * log10(1 + art_mcd / 0.174)
    Solving for art_mcd:
        art_mcd = 0.174 * (10^((22.0 - SQM) / 2.5) - 1)
    """
    natural_mcd = 0.174
    art_mcd = natural_mcd * (10 ** ((22.0 - sqm) / 2.5) - 1.0)
    return round(max(0.0, art_mcd), 4)


class DarkSkySitesLightPollutionProvider(BaseLightPollutionProvider):
    """Light pollution provider backed by the DarkSkySites API (GET /api/sqm).

    Documentation: https://www.darkskysites.com/api-access
    Endpoint: GET https://darkskysites.com/api/sqm?lat=<lat>&lng=<lng>
    Auth header: x-api-key: <key>   (never sent in URL)
    Rate limits (Free tier): 30,000 zenith requests / month, 10 req/s, 3 active keys.
    Attribution requirement: display "DarkSkySites.com" adjacent to the data,
      linked to https://darkskysites.com wherever hyperlinks are supported.

    Response JSON shape (documented):
        {
          "latitude": float,
          "longitude": float,
          "sqm": float,              # mag/arcsec², higher = darker
          "bortleClass": int,        # 1–9
          "bortleDescription": str,
          "dataset": {
            "id": str,               # MM_YYYY
            "year": int,
            "month": int,
            "requestedDate": str|null,
            "fallbackUsed": bool,
            "fallbackFrom": str|null,
            "fallbackReason": str|null,
            "datasetsChecked": int
          },
          "quality": {
            "status": str,           # "screened" | "unverified_zero" | "unavailable"
            "method": str,
            "coverageVerified": bool,
            "flags": list[str]
          },
          "attribution": str         # Required: "darkskysites.com"
        }

    Error codes:
        400 — invalid coordinates or date
        401 — missing or invalid API key
        403 — project suspended / access revoked
        404 — no usable dataset within search bounds
        429 — rate/monthly limit reached
        503 — temporary service unavailability
    """

    #: Required attribution text from the API response (must be preserved).
    REQUIRED_ATTRIBUTION = "darkskysites.com"
    #: Attribution URL for link-capable contexts.
    ATTRIBUTION_URL = "https://darkskysites.com"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float | None = None,
        cache_ttl: int | None = None,
        client: Any | None = None,  # httpx.Client or compatible
    ) -> None:
        import httpx as _httpx

        if not api_key:
            raise ValueError("api_key must not be empty")

        from app.core.config import (
            DARKSKYSITES_BASE_URL,
            DARKSKYSITES_CACHE_TTL_SECONDS,
            DARKSKYSITES_TIMEOUT_SECONDS,
        )

        self._api_key = api_key
        self._base_url = (base_url or DARKSKYSITES_BASE_URL).rstrip("/")
        self._timeout = timeout if timeout is not None else DARKSKYSITES_TIMEOUT_SECONDS
        self._cache_ttl = cache_ttl if cache_ttl is not None else DARKSKYSITES_CACHE_TTL_SECONDS
        self._external_client = client
        # In-memory TTL cache: (lat_rounded, lng_rounded) -> (monotonic_ts, LightPollutionResult)
        self._cache: dict[tuple[float, float], tuple[float, "LightPollutionResult"]] = {}
        self._httpx = _httpx

    def clear_cache(self) -> None:
        """Clear all cached results."""
        self._cache.clear()

    def _get_client(self) -> Any:
        if self._external_client is not None:
            return self._external_client
        return self._httpx.Client(timeout=self._timeout)

    def get_light_pollution(
        self,
        latitude: float,
        longitude: float,
    ) -> "LightPollutionResult":
        """Query DarkSkySites API for zenith SQM and Bortle class.

        Returns LightPollutionResult with status='success' on a valid response.
        Returns status='unavailable' for all network/auth/data failure paths
        without fabricating any brightness values.
        """
        import time as _time

        if not -90 <= latitude <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")

        cache_key = (round(latitude, 4), round(longitude, 4))
        now_mono = _time.monotonic()
        if cache_key in self._cache:
            cached_at, cached_result = self._cache[cache_key]
            if now_mono - cached_at < self._cache_ttl:
                return cached_result

        result = self._fetch(latitude, longitude)
        if result.status == "success":
            self._cache[cache_key] = (now_mono, result)
        return result

    def _fetch(self, latitude: float, longitude: float) -> "LightPollutionResult":
        """Perform the live API request. Returns LightPollutionResult."""
        params = {"lat": latitude, "lng": longitude}
        headers = {"x-api-key": self._api_key}

        # Perform request with a single non-blocking retry for transient network errors
        attempts = 0
        max_attempts = 2
        while attempts < max_attempts:
            attempts += 1
            try:
                client = self._get_client()
                if self._external_client is not None:
                    response = client.get(self._base_url, params=params, headers=headers)
                else:
                    with client:
                        response = client.get(self._base_url, params=params, headers=headers)
                # Handle HTTP 429 rate limiting without blocking sleep
                if response.status_code == 429:
                    return self._unavailable(
                        "DarkSkySites API rate limit exceeded (HTTP 429). Retry later."
                    )
            except self._httpx.TimeoutException as exc:
                if attempts >= max_attempts:
                    return self._unavailable(
                        f"DarkSkySites API request timed out after {self._timeout}s: {exc}"
                    )
                # Immediate retry on transient timeout without blocking sleep
                continue
            except self._httpx.RequestError as exc:
                # Do not retry on request errors that likely won't succeed (e.g., DNS)
                return self._unavailable(
                    f"DarkSkySites API network error: {exc}"
                )
            # Successful HTTP exchange – break out of retry loop
            break
        else:
            # Should not reach here; safety fallback
            return self._unavailable("DarkSkySites API request failed after retries")

        status_code = response.status_code

        if status_code == 401:
            return self._unavailable(
                "DarkSkySites API key is missing or invalid (HTTP 401). "
                "Check DARKSKYSITES_API_KEY in .env."
            )
        if status_code == 403:
            return self._unavailable(
                "DarkSkySites API access is suspended or revoked (HTTP 403). "
                "Contact DarkSkySites support."
            )
        # HTTP 429 handling moved into retry loop above
        if status_code == 400:
            return self._unavailable(
                f"DarkSkySites API rejected the request (HTTP 400): {response.text[:200]}"
            )
        if status_code == 404:
            return self._unavailable(
                "DarkSkySites API found no usable dataset for these coordinates (HTTP 404)."
            )
        if status_code == 503:
            return self._unavailable(
                "DarkSkySites API is temporarily unavailable (HTTP 503). Retry later."
            )
        if status_code != 200:
            return self._unavailable(
                f"DarkSkySites API returned unexpected HTTP {status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
        except Exception as exc:
            return self._unavailable(
                f"DarkSkySites API returned malformed JSON: {exc}"
            )

        return self._parse_response(data, latitude, longitude)

    def _parse_response(
        self,
        data: dict[str, Any],
        latitude: float,
        longitude: float,
    ) -> "LightPollutionResult":
        """Map documented DarkSkySites JSON response to LightPollutionResult."""
        if not isinstance(data, dict):
            return self._unavailable("DarkSkySites response is not a JSON object.")

        sqm = data.get("sqm")
        bortle = data.get("bortleClass")
        bortle_desc = data.get("bortleDescription", "")

        if sqm is None:
            return self._unavailable(
                "DarkSkySites response missing required field 'sqm'."
            )
        try:
            sqm_float = float(sqm)
        except (TypeError, ValueError):
            return self._unavailable(
                f"DarkSkySites 'sqm' field is not numeric: {sqm!r}"
            )
        if not (16.0 <= sqm_float <= 22.0):
            return self._unavailable(
                f"DarkSkySites 'sqm' value {sqm_float} is outside the expected range [16, 22]."
            )

        try:
            bortle_int = int(bortle) if bortle is not None else artificial_brightness_to_bortle(
                _sqm_to_artificial_brightness_mcd(sqm_float)
            )
        except (TypeError, ValueError):
            bortle_int = artificial_brightness_to_bortle(
                _sqm_to_artificial_brightness_mcd(sqm_float)
            )

        # DarkSkySites may return direct artificialBrightness/naturalSkyRatio or only SQM/bortle
        direct_art = data.get("artificialBrightness")
        direct_ratio = data.get("naturalSkyRatio")
        art_mcd: float | None = None
        ratio: float | None = None

        if direct_art is not None:
            try:
                art_mcd = round(float(direct_art), 4)
            except (TypeError, ValueError):
                art_mcd = None

        if direct_ratio is not None:
            try:
                ratio = round(float(direct_ratio), 3)
            except (TypeError, ValueError):
                ratio = None

        # Dataset provenance & Quality
        dataset: dict[str, Any] = data.get("dataset") or {}
        quality: dict[str, Any] = data.get("quality") or {}
        api_attribution = str(data.get("attribution") or self.REQUIRED_ATTRIBUTION)

        dataset_id = dataset.get("id", "unknown")
        dataset_year = dataset.get("year")
        fallback_used = bool(dataset.get("fallbackUsed", False))
        fallback_reason = dataset.get("fallbackReason")
        quality_status = quality.get("status", "unknown")
        quality_method = quality.get("method")
        coverage_verified = quality.get("coverageVerified")
        quality_flags: list[str] = quality.get("flags") or []

        # Build limitations from dataset/quality metadata
        limitations: list[str] = [
            "SQM value is a modeled estimate, not a live sky measurement.",
            f"Attribution: {api_attribution} ({self.ATTRIBUTION_URL})",
        ]
        if coverage_verified is False:
            limitations.append("Coverage is unverified by ground stations (coverageVerified: false).")
        if quality_method:
            limitations.append(f"Modeling method: {quality_method}.")
        if fallback_used and fallback_reason:
            limitations.append(
                f"Dataset fallback applied: {fallback_reason} (returned dataset: {dataset_id})"
            )
        if quality_status == "unverified_zero":
            limitations.append(
                "Quality status is 'unverified_zero': genuine darkness cannot be confirmed. "
                "Do not present as confirmed pristine sky."
            )
        if quality_flags:
            limitations.append(f"Quality screening flags: {', '.join(quality_flags)}")
        if bortle_desc:
            limitations.append(f"Bortle description: {bortle_desc}")

        fallback_from = dataset.get("fallbackFrom")
        source_label = (
            f"DarkSkySites API — dataset {dataset_id}"
            + (f" (fallback from {fallback_from})" if fallback_used else "")
        )

        return LightPollutionResult(
            status="success",
            bortle_class=max(1, min(9, bortle_int)),
            artificial_brightness_mcd=art_mcd,
            sqm=round(sqm_float, 2),
            ratio_to_natural_sky=ratio,
            source=source_label,
            dataset_year=int(dataset_year) if dataset_year is not None else None,
            spatial_resolution="Modeled (physics-based, sub-km scale)",
            attribution=(
                f"Light pollution data: {api_attribution} — {self.ATTRIBUTION_URL}. "
                f"Quality: {quality_status}. Dataset: {dataset_id}."
            ),
            limitations=limitations,
        )

    @staticmethod
    def _unavailable(reason: str) -> "LightPollutionResult":
        return LightPollutionResult(
            status="unavailable",
            bortle_class=None,
            artificial_brightness_mcd=None,
            sqm=None,
            ratio_to_natural_sky=None,
            source="unavailable",
            dataset_year=None,
            spatial_resolution=None,
            attribution=None,
            limitations=[reason],
        )

