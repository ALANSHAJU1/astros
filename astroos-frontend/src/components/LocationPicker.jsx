import { useEffect, useRef, useState } from "react";
import {
  Compass,
  Edit3,
  LoaderCircle,
  LocateFixed,
  MapPin,
  Search,
  Sparkles,
  Telescope,
  X,
} from "lucide-react";
import {
  formatCoordinates,
  getCurrentGpsLocation,
  PRESET_OBSERVATORIES,
  POPULAR_LOCATIONS,
  searchLocations,
} from "../services/geocodingService";

export default function LocationPicker({
  latitude,
  longitude,
  locationName = "",
  onChange,
  label = "Observing Location & Station",
  showPresets = true,
}) {
  const [query, setQuery] = useState(locationName || "");
  const [suggestions, setSuggestions] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [locating, setLocating] = useState(false);
  const [showManualCoords, setShowManualCoords] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  const containerRef = useRef(null);
  const searchTimeoutRef = useRef(null);

  // Sync internal search query if parent locationName updates
  useEffect(() => {
    if (locationName && !dropdownOpen) {
      setQuery(locationName);
    }
  }, [locationName, dropdownOpen]);

  // Handle outside click to dismiss suggestion dropdown
  useEffect(() => {
    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Debounced geocoding search
  function handleQueryChange(e) {
    const value = e.target.value;
    setQuery(value);
    setStatusMessage("");

    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    if (!value.trim()) {
      setSuggestions([]);
      setDropdownOpen(false);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    setDropdownOpen(true);

    searchTimeoutRef.current = setTimeout(async () => {
      try {
        const results = await searchLocations(value);
        setSuggestions(results);
      } catch {
        setSuggestions([]);
      } finally {
        setIsSearching(false);
      }
    }, 280);
  }

  function handleSelectLocation(loc) {
    setQuery(loc.name);
    setDropdownOpen(false);
    setStatusMessage("");
    if (onChange) {
      onChange({
        latitude: loc.latitude,
        longitude: loc.longitude,
        name: loc.name,
      });
    }
  }

  async function handleUseGps() {
    setLocating(true);
    setStatusMessage("");
    try {
      const gps = await getCurrentGpsLocation();
      setQuery(gps.name);
      if (onChange) {
        onChange({
          latitude: gps.latitude,
          longitude: gps.longitude,
          name: gps.name,
        });
      }
      setStatusMessage("📍 GPS position acquired successfully.");
      setTimeout(() => setStatusMessage(""), 4000);
    } catch (err) {
      setStatusMessage(err.message || "Failed to acquire GPS position.");
    } finally {
      setLocating(false);
    }
  }

  function handleManualLatChange(val) {
    const num = Number(val);
    if (onChange) {
      onChange({
        latitude: num,
        longitude,
        name: query || `Lat: ${val}, Lon: ${longitude}`,
      });
    }
  }

  function handleManualLonChange(val) {
    const num = Number(val);
    if (onChange) {
      onChange({
        latitude,
        longitude: num,
        name: query || `Lat: ${latitude}, Lon: ${val}`,
      });
    }
  }

  return (
    <div className="location-picker-container" ref={containerRef}>
      <div className="location-picker-top">
        <label className="location-picker-label">
          <MapPin size={14} className="text-gold" />
          <span>{label}</span>
        </label>

        <button
          type="button"
          className="location-manual-toggle"
          onClick={() => setShowManualCoords(!showManualCoords)}
        >
          <Edit3 size={12} />
          <span>{showManualCoords ? "Hide coordinates" : "Edit coordinates manually"}</span>
        </button>
      </div>

      {/* Main Location Search Input */}
      <div className="location-search-wrapper">
        <div className="location-search-input-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            className="location-search-input"
            placeholder="Type city or observatory (e.g. Thrissur, London, Mauna Kea...)"
            value={query}
            onChange={handleQueryChange}
            onFocus={() => {
              if (query.trim().length >= 2 && suggestions.length > 0) {
                setDropdownOpen(true);
              }
            }}
            aria-label="Enter observing location name or city"
          />

          {query && (
            <button
              type="button"
              className="location-clear-btn"
              onClick={() => {
                setQuery("");
                setSuggestions([]);
                setDropdownOpen(false);
              }}
              aria-label="Clear location input"
            >
              <X size={14} />
            </button>
          )}

          <button
            type="button"
            className="location-gps-btn"
            onClick={handleUseGps}
            disabled={locating}
            title="Use current device GPS location"
          >
            {locating ? (
              <LoaderCircle size={14} className="loading-spinner" />
            ) : (
              <LocateFixed size={14} />
            )}
            <span>{locating ? "Locating..." : "Use GPS"}</span>
          </button>
        </div>

        {/* Autocomplete Dropdown List */}
        {dropdownOpen && (
          <div className="location-dropdown" role="listbox">
            {isSearching && (
              <div className="location-dropdown-loading">
                <LoaderCircle size={14} className="loading-spinner" />
                <span>Searching astronomical locations & cities...</span>
              </div>
            )}

            {!isSearching && suggestions.length === 0 && (
              <div className="location-dropdown-empty">
                No matching locations found. You can enter custom coordinates below.
              </div>
            )}

            {!isSearching &&
              suggestions.map((loc, idx) => (
                <button
                  type="button"
                  key={`${loc.name}-${idx}`}
                  className="location-dropdown-item"
                  onClick={() => handleSelectLocation(loc)}
                >
                  <div className="dropdown-item-left">
                    {loc.isObservatory ? (
                      <Telescope size={15} className="text-accent" />
                    ) : (
                      <MapPin size={15} className="text-muted" />
                    )}
                    <div>
                      <div className="dropdown-item-name">
                        {loc.shortName || loc.name}
                        {loc.isObservatory && (
                          <span className="observatory-badge">Observatory</span>
                        )}
                      </div>
                      <div className="dropdown-item-details">{loc.name}</div>
                    </div>
                  </div>

                  <div className="dropdown-item-coords">
                    {formatCoordinates(loc.latitude, loc.longitude)}
                  </div>
                </button>
              ))}
          </div>
        )}
      </div>

      {/* Preset Quick Chips */}
      {showPresets && (
        <div className="location-preset-row">
          <span className="preset-label">Quick stations:</span>
          <div className="preset-chips-scroll">
            <button
              type="button"
              className="preset-chip"
              onClick={() =>
                handleSelectLocation({
                  name: "Kakkanad, Kochi, Kerala, India",
                  shortName: "Kakkanad",
                  latitude: 10.0159,
                  longitude: 76.3419,
                })
              }
            >
              📍 Kakkanad (Kochi)
            </button>
            <button
              type="button"
              className="preset-chip"
              onClick={() =>
                handleSelectLocation({
                  name: "Thrissur, Kerala, India",
                  shortName: "Thrissur",
                  latitude: 10.5276,
                  longitude: 76.2144,
                })
              }
            >
              📍 Thrissur
            </button>
            <button
              type="button"
              className="preset-chip"
              onClick={() =>
                handleSelectLocation(PRESET_OBSERVATORIES[0]) // Hanle
              }
            >
              🔭 Hanle (IAO)
            </button>
            <button
              type="button"
              className="preset-chip"
              onClick={() =>
                handleSelectLocation(PRESET_OBSERVATORIES[2]) // Mauna Kea
              }
            >
              🔭 Mauna Kea
            </button>
            <button
              type="button"
              className="preset-chip"
              onClick={() =>
                handleSelectLocation(PRESET_OBSERVATORIES[3]) // Atacama / Paranal
              }
            >
              🔭 Atacama
            </button>
            <button
              type="button"
              className="preset-chip"
              onClick={() =>
                handleSelectLocation({
                  name: "Bengaluru, Karnataka, India",
                  shortName: "Bengaluru",
                  latitude: 12.9716,
                  longitude: 77.5946,
                })
              }
            >
              🏙️ Bengaluru
            </button>
            <button
              type="button"
              className="preset-chip"
              onClick={() =>
                handleSelectLocation({
                  name: "London, England, United Kingdom",
                  shortName: "London",
                  latitude: 51.5074,
                  longitude: -0.1278,
                })
              }
            >
              🏙️ London
            </button>
            <button
              type="button"
              className="preset-chip"
              onClick={() =>
                handleSelectLocation({
                  name: "Tokyo, Japan",
                  shortName: "Tokyo",
                  latitude: 35.6762,
                  longitude: 139.6503,
                })
              }
            >
              🏙️ Tokyo
            </button>
          </div>
        </div>
      )}

      {/* Coordinate Preview & Status */}
      <div className="location-active-strip">
        <div className="active-coords-tag">
          <Compass size={12} className="text-gold" />
          <span>Active Station Coordinates:</span>
          <strong>{formatCoordinates(latitude, longitude)}</strong>
        </div>

        {statusMessage && (
          <span className="location-status-text">{statusMessage}</span>
        )}
      </div>

      {/* Manual Coordinate Inputs (Expandable) */}
      {showManualCoords && (
        <div className="manual-coordinates-panel">
          <div className="manual-grid">
            <label>
              Latitude (°N / °S)
              <input
                type="number"
                step="0.0001"
                min="-90"
                max="90"
                required
                value={latitude}
                onChange={(e) => handleManualLatChange(e.target.value)}
                placeholder="e.g. 10.5276"
              />
            </label>
            <label>
              Longitude (°E / °W)
              <input
                type="number"
                step="0.0001"
                min="-180"
                max="180"
                required
                value={longitude}
                onChange={(e) => handleManualLonChange(e.target.value)}
                placeholder="e.g. 76.2144"
              />
            </label>
          </div>
          <small className="manual-note">
            Decimal coordinates are passed directly into the AstroOS ephemeris and topocentric seeing calculations.
          </small>
        </div>
      )}
    </div>
  );
}

