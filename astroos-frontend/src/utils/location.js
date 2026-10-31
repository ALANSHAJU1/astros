export const LOCATION_STORAGE_KEY = "astroos_observer_location";

export const DEFAULT_LOCATION = {
  latitude: 10.5276,
  longitude: 76.2144,
};

export function loadObserverLocation() {
  try {
    const raw = localStorage.getItem(LOCATION_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_LOCATION };
    const parsed = JSON.parse(raw);
    const latitude = Number(parsed.latitude);
    const longitude = Number(parsed.longitude);
    if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
      return { latitude, longitude };
    }
  } catch {
    // Keep the default observer location if storage is unavailable.
  }
  return { ...DEFAULT_LOCATION };
}

export function saveObserverLocation(location) {
  localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify(location));
}
