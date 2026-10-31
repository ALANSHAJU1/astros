import pytest
from app.services.light_pollution_service import (
    GridLightPollutionProvider,
    UnavailableLightPollutionProvider,
    artificial_brightness_to_bortle,
    artificial_brightness_to_sqm,
    get_light_pollution_provider,
)


@pytest.fixture
def sample_grid():
    return {
        "lat_min": 10.0,
        "lat_max": 11.0,
        "lon_min": 76.0,
        "lon_max": 77.0,
        "lat_step": 0.5,
        "lon_step": 0.5,
        "source": "World Atlas 2015 (Falchi et al., 2016)",
        "dataset_year": 2016,
        "spatial_resolution": "30 arcsec (~1 km)",
        "attribution": "Falchi et al. (2016) / GFZ Data Services under CC BY 4.0",
        "values": [
            [0.05, 0.25, 1.2],
            [0.02, 0.15, 0.8],
            [0.001, 0.04, 3.5],
        ],
    }


def test_unavailable_provider_default():
    provider = UnavailableLightPollutionProvider()
    result = provider.get_light_pollution(10.5276, 76.2144)

    assert result.status == "unavailable"
    assert result.bortle_class is None
    assert result.artificial_brightness_mcd is None
    assert result.sqm is None
    assert len(result.limitations) == 1
    assert "not configured" in result.limitations[0]


def test_factory_returns_unavailable_when_path_is_none(monkeypatch):
    import app.core.config
    monkeypatch.setattr(app.core.config, "DARKSKYSITES_API_KEY", None)
    provider = get_light_pollution_provider(None)
    assert isinstance(provider, UnavailableLightPollutionProvider)


def test_factory_returns_unavailable_when_file_not_found(tmp_path):
    missing_file = tmp_path / "nonexistent.json"
    provider = get_light_pollution_provider(missing_file)
    assert isinstance(provider, UnavailableLightPollutionProvider)
    result = provider.get_light_pollution(10.0, 76.0)
    assert result.status == "unavailable"
    assert "not found" in result.limitations[0]


def test_valid_grid_lookup(sample_grid):
    provider = GridLightPollutionProvider(grid_data=sample_grid)
    result = provider.get_light_pollution(10.0, 76.0)

    assert result.status == "success"
    assert result.artificial_brightness_mcd == 0.05
    assert result.bortle_class == 3
    assert result.sqm == 21.73
    assert result.dataset_year == 2016
    assert result.spatial_resolution == "30 arcsec (~1 km)"
    assert "Falchi et al." in result.attribution
    assert result.limitations == []


def test_out_of_coverage_coordinates(sample_grid):
    provider = GridLightPollutionProvider(grid_data=sample_grid)
    # Outside latitude 10.0 - 11.0
    result = provider.get_light_pollution(15.0, 76.5)

    assert result.status == "out_of_coverage"
    assert result.bortle_class is None
    assert len(result.limitations) == 1
    assert "outside the grid coverage" in result.limitations[0]


def test_invalid_coordinates_raise_value_error():
    provider = UnavailableLightPollutionProvider()
    with pytest.raises(ValueError, match="Latitude"):
        provider.get_light_pollution(95.0, 76.0)

    with pytest.raises(ValueError, match="Longitude"):
        provider.get_light_pollution(10.0, 200.0)


def test_bortle_and_sqm_calculations():
    # Pristine dark sky (<0.002 mcd/m²)
    assert artificial_brightness_to_bortle(0.001) == 1
    assert artificial_brightness_to_sqm(0.0) == 22.0

    # Suburban sky (~0.5 mcd/m²)
    assert artificial_brightness_to_bortle(0.5) == 5

    # Inner city (>23 mcd/m²)
    assert artificial_brightness_to_bortle(25.0) == 9
    assert artificial_brightness_to_sqm(25.0) < 18.0


def test_read_esri_asc_grid_file(tmp_path):
    """Test reading an authentic ESRI ASCII raster grid file format."""
    asc_content = """ncols         3
nrows         3
xllcorner     76.0
yllcorner     10.0
cellsize      0.5
NODATA_value  -9999
0.80 0.50 0.10
0.40 0.25 0.05
0.20 0.10 0.01
"""
    asc_file = tmp_path / "kerala_sample.asc"
    asc_file.write_text(asc_content, encoding="utf-8")

    provider = GridLightPollutionProvider(file_path=asc_file)

    # In ESRI ASCII, row 0 is top (North: lat 11.5), row 2 is bottom (South: lat 10.0)
    # Query near South-East (lat 10.0, lon 77.0) -> row 2, col 2 -> value 0.01
    res_se = provider.get_light_pollution(10.0, 77.0)
    assert res_se.status == "success"
    assert res_se.artificial_brightness_mcd == 0.01
    assert res_se.bortle_class == 2

    # Query near North-West (lat 11.5, lon 76.0) -> row 0, col 0 -> value 0.80
    res_nw = provider.get_light_pollution(11.5, 76.0)
    assert res_nw.status == "success"
    assert res_nw.artificial_brightness_mcd == 0.80
    assert res_nw.bortle_class == 5


def test_geotiff_handling_without_rasterio(tmp_path):
    """Test informative error when GeoTIFF is specified without rasterio installed."""
    tif_file = tmp_path / "sample.tif"
    tif_file.write_bytes(b"II*\x00mock_geotiff_header")

    with pytest.raises(RuntimeError, match="requires 'rasterio'"):
        GridLightPollutionProvider(file_path=tif_file)


def test_darkskysites_provider_success():
    from unittest.mock import MagicMock
    from app.services.light_pollution_service import DarkSkySitesLightPollutionProvider

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "dataset": {"id": "09_2026", "year": 2026, "fallbackUsed": False},
        "sqm": 19.47,
        "bortleClass": 7,
        "bortleDescription": "Suburban/urban transition",
        "quality": {
            "status": "screened",
            "method": "seasonal_temporal_v1",
            "coverageVerified": False,
            "flags": ["seasonal_variation"],
        },
        "attribution": "darkskysites.com",
    }
    mock_client.get.return_value = mock_response

    provider = DarkSkySitesLightPollutionProvider(
        api_key="test_api_key",
        client=mock_client,
    )
    res = provider.get_light_pollution(10.5276, 76.2144)

    assert res.status == "success"
    assert res.sqm == 19.47
    assert res.bortle_class == 7
    # When artificialBrightness/ratio are omitted, keep null
    assert res.artificial_brightness_mcd is None
    assert res.ratio_to_natural_sky is None
    assert "DarkSkySites API" in res.source
    assert res.dataset_year == 2026
    assert any("coverageVerified: false" in l for l in res.limitations)
    assert any("seasonal_temporal_v1" in l for l in res.limitations)
    assert any("seasonal_variation" in l for l in res.limitations)


def test_darkskysites_provider_with_direct_brightness():
    from unittest.mock import MagicMock
    from app.services.light_pollution_service import DarkSkySitesLightPollutionProvider

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "dataset": {"id": "2024", "year": 2024},
        "sqm": 20.85,
        "bortleClass": 4,
        "artificialBrightness": 0.35,
        "naturalSkyRatio": 2.01,
        "attribution": "darkskysites.com",
    }
    mock_client.get.return_value = mock_response

    provider = DarkSkySitesLightPollutionProvider(
        api_key="test_api_key",
        client=mock_client,
    )
    res = provider.get_light_pollution(10.5276, 76.2144)

    assert res.status == "success"
    assert res.artificial_brightness_mcd == 0.35
    assert res.ratio_to_natural_sky == 2.01



def test_darkskysites_provider_auth_error():
    from unittest.mock import MagicMock
    from app.services.light_pollution_service import DarkSkySitesLightPollutionProvider

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_client.get.return_value = mock_response

    provider = DarkSkySitesLightPollutionProvider(
        api_key="invalid_key",
        client=mock_client,
    )
    res = provider.get_light_pollution(10.5276, 76.2144)

    assert res.status == "unavailable"
    assert any("401" in limit for limit in res.limitations)



