/**
 * AstroOS Geocoding & Astronomical Location Service
 *
 * Converts human-friendly location names (cities, towns, landmarks, observatories)
 * into precise topocentric coordinates (latitude & longitude) for the AstroOS
 * intelligence and ephemeris engine.
 */

export const PRESET_OBSERVATORIES = [
  {
    name: "Indian Astronomical Observatory (IAO), Hanle",
    shortName: "Hanle (IAO)",
    latitude: 32.7794,
    longitude: 78.9642,
    country: "India",
    admin1: "Ladakh",
    isObservatory: true,
  },
  {
    name: "Vainu Bappu Observatory (VBO), Kavalur",
    shortName: "Kavalur (VBO)",
    latitude: 12.5767,
    longitude: 78.8286,
    country: "India",
    admin1: "Tamil Nadu",
    isObservatory: true,
  },
  {
    name: "Mauna Kea Observatories, Hawaii",
    shortName: "Mauna Kea",
    latitude: 19.8207,
    longitude: -155.4681,
    country: "United States",
    admin1: "Hawaii",
    isObservatory: true,
  },
  {
    name: "Paranal Observatory (VLT / ESO), Atacama",
    shortName: "Paranal (Atacama)",
    latitude: -24.6272,
    longitude: -70.4042,
    country: "Chile",
    admin1: "Antofagasta",
    isObservatory: true,
  },
  {
    name: "Roque de los Muchachos Observatory, La Palma",
    shortName: "La Palma (ORM)",
    latitude: 28.7567,
    longitude: -17.885,
    country: "Spain",
    admin1: "Canary Islands",
    isObservatory: true,
  },
  {
    name: "Royal Observatory, Greenwich",
    shortName: "Greenwich",
    latitude: 51.4769,
    longitude: 0.0005,
    country: "United Kingdom",
    admin1: "London",
    isObservatory: true,
  },
  {
    name: "South African Astronomical Observatory (SALT), Sutherland",
    shortName: "SALT, Sutherland",
    latitude: -32.3783,
    longitude: 20.8108,
    country: "South Africa",
    admin1: "Northern Cape",
    isObservatory: true,
  },
  {
    name: "Kitt Peak National Observatory, Arizona",
    shortName: "Kitt Peak",
    latitude: 31.9583,
    longitude: -111.5967,
    country: "United States",
    admin1: "Arizona",
    isObservatory: true,
  },
  {
    name: "Griffith Observatory, Los Angeles",
    shortName: "Griffith Obs",
    latitude: 34.1184,
    longitude: -118.3004,
    country: "United States",
    admin1: "California",
    isObservatory: true,
  },
  {
    name: "Pic du Midi Observatory, Pyrenees",
    shortName: "Pic du Midi",
    latitude: 42.9369,
    longitude: 0.1411,
    country: "France",
    admin1: "Occitanie",
    isObservatory: true,
  },
];

export const POPULAR_LOCATIONS = [
  { name: "Kakkanad, Kochi, Kerala, India", shortName: "Kakkanad", latitude: 10.0159, longitude: 76.3419, admin1: "Kerala", country: "India" },
  { name: "Thrissur, Kerala, India", shortName: "Thrissur", latitude: 10.5276, longitude: 76.2144, admin1: "Kerala", country: "India" },
  { name: "Kochi, Kerala, India", shortName: "Kochi", latitude: 9.9312, longitude: 76.2673, admin1: "Kerala", country: "India" },
  { name: "Munnar, Kerala, India", shortName: "Munnar (Dark Sky)", latitude: 10.0889, longitude: 77.0595, admin1: "Kerala", country: "India" },
  { name: "Thiruvananthapuram, Kerala, India", shortName: "Trivandrum", latitude: 8.5241, longitude: 76.9366, admin1: "Kerala", country: "India" },
  { name: "Kozhikode, Kerala, India", shortName: "Calicut", latitude: 11.2588, longitude: 75.7804, admin1: "Kerala", country: "India" },
  { name: "Bengaluru, Karnataka, India", shortName: "Bengaluru", latitude: 12.9716, longitude: 77.5946, admin1: "Karnataka", country: "India" },
  { name: "Chennai, Tamil Nadu, India", shortName: "Chennai", latitude: 13.0827, longitude: 80.2707, admin1: "Tamil Nadu", country: "India" },
  { name: "Mumbai, Maharashtra, India", shortName: "Mumbai", latitude: 19.076, longitude: 72.8777, admin1: "Maharashtra", country: "India" },
  { name: "New Delhi, Delhi, India", shortName: "New Delhi", latitude: 28.6139, longitude: 77.209, admin1: "Delhi", country: "India" },
  { name: "Hyderabad, Telangana, India", shortName: "Hyderabad", latitude: 17.385, longitude: 78.4867, admin1: "Telangana", country: "India" },
  { name: "Kolkata, West Bengal, India", shortName: "Kolkata", latitude: 22.5726, longitude: 88.3639, admin1: "West Bengal", country: "India" },
  { name: "Pune, Maharashtra, India", shortName: "Pune", latitude: 18.5204, longitude: 73.8567, admin1: "Maharashtra", country: "India" },
  { name: "Ahmedabad, Gujarat, India", shortName: "Ahmedabad", latitude: 23.0225, longitude: 72.5714, admin1: "Gujarat", country: "India" },
  { name: "London, England, United Kingdom", shortName: "London", latitude: 51.5074, longitude: -0.1278, admin1: "England", country: "United Kingdom" },
  { name: "New York, NY, United States", shortName: "New York", latitude: 40.7128, longitude: -74.006, admin1: "New York", country: "United States" },
  { name: "San Francisco, CA, United States", shortName: "San Francisco", latitude: 37.7749, longitude: -122.4194, admin1: "California", country: "United States" },
  { name: "Tokyo, Japan", shortName: "Tokyo", latitude: 35.6762, longitude: 139.6503, admin1: "Tokyo", country: "Japan" },
  { name: "Paris, Île-de-France, France", shortName: "Paris", latitude: 48.8566, longitude: 2.3522, admin1: "Île-de-France", country: "France" },
  { name: "Berlin, Germany", shortName: "Berlin", latitude: 52.52, longitude: 13.405, admin1: "Berlin", country: "Germany" },
  { name: "Sydney, NSW, Australia", shortName: "Sydney", latitude: -33.8688, longitude: 151.2093, admin1: "New South Wales", country: "Australia" },
  { name: "Dubai, United Arab Emirates", shortName: "Dubai", latitude: 25.2048, longitude: 55.2708, admin1: "Dubai", country: "United Arab Emirates" },
  { name: "Singapore", shortName: "Singapore", latitude: 1.3521, longitude: 103.8198, admin1: "", country: "Singapore" },
  { name: "Toronto, Ontario, Canada", shortName: "Toronto", latitude: 43.6532, longitude: -79.3832, admin1: "Ontario", country: "Canada" },
];

/**
 * Format latitude and longitude into navigational notation (e.g., 10.53° N, 76.21° E)
 */
export function formatCoordinates(lat, lon) {
  if (lat == null || lon == null || !Number.isFinite(Number(lat)) || !Number.isFinite(Number(lon))) {
    return "Coordinates unassigned";
  }
  const latNum = Number(lat);
  const lonNum = Number(lon);
  const latDir = latNum >= 0 ? "N" : "S";
  const lonDir = lonNum >= 0 ? "E" : "W";
  return `${Math.abs(latNum).toFixed(4)}° ${latDir}, ${Math.abs(lonNum).toFixed(4)}° ${lonDir}`;
}

/**
 * Search locations by query string.
 * Checks instant local catalog of observatories and cities first,
 * and supplements with Open-Meteo Geocoding API if online.
 */
export async function searchLocations(query = "") {
  const q = String(query).trim().toLowerCase();
  if (!q) {
    return [
      ...PRESET_OBSERVATORIES.slice(0, 4),
      ...POPULAR_LOCATIONS.slice(0, 4),
    ];
  }

  // 1. Instant local matching
  const localMatches = [];
  for (const obs of PRESET_OBSERVATORIES) {
    if (
      obs.name.toLowerCase().includes(q) ||
      obs.shortName.toLowerCase().includes(q) ||
      obs.country.toLowerCase().includes(q)
    ) {
      localMatches.push(obs);
    }
  }

  for (const loc of POPULAR_LOCATIONS) {
    if (
      loc.name.toLowerCase().includes(q) ||
      loc.shortName.toLowerCase().includes(q) ||
      loc.country.toLowerCase().includes(q) ||
      loc.admin1.toLowerCase().includes(q)
    ) {
      localMatches.push(loc);
    }
  }

  // 2. Query Open-Meteo Geocoding API if query is 2+ characters
  if (q.length >= 2) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3500);

      const response = await fetch(
        `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(
          query
        )}&count=8&language=en&format=json`,
        { signal: controller.signal }
      );
      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data.results)) {
          for (const item of data.results) {
            const lat = Number(Number(item.latitude).toFixed(4));
            const lon = Number(Number(item.longitude).toFixed(4));

            // Check if already in local matches
            const exists = localMatches.some(
              (m) => Math.abs(m.latitude - lat) < 0.05 && Math.abs(m.longitude - lon) < 0.05
            );

            if (!exists) {
              const parts = [item.name, item.admin1, item.country].filter(Boolean);
              localMatches.push({
                name: parts.join(", "),
                shortName: item.name,
                latitude: lat,
                longitude: lon,
                country: item.country || "",
                admin1: item.admin1 || "",
                elevation: item.elevation,
                isObservatory: false,
              });
            }
          }
        }
      }
    } catch {
      // Offline or network error: return local matches
    }
  }

  return localMatches.slice(0, 10);
}

/**
 * Retrieve user's current GPS location via HTML5 Geolocation API
 */
export function getCurrentGpsLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation is not supported by your browser."));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = Number(pos.coords.latitude.toFixed(4));
        const lon = Number(pos.coords.longitude.toFixed(4));
        resolve({
          name: `Current Location (${formatCoordinates(lat, lon)})`,
          shortName: "My Location",
          latitude: lat,
          longitude: lon,
          accuracy: pos.coords.accuracy,
        });
      },
      (err) => {
        let msg = "Could not retrieve current location.";
        if (err.code === 1) msg = "Location permission denied by user.";
        else if (err.code === 2) msg = "Position unavailable from GPS sensors.";
        else if (err.code === 3) msg = "Location request timed out.";
        reject(new Error(msg));
      },
      { timeout: 8000, enableHighAccuracy: true }
    );
  });
}

/**
 * Assess realistic topocentric light pollution and Bortle class based on
 * astronomical observation benchmarks, geographical boundaries, and urban light domes.
 */
export function getLightPollution(latitude, longitude, locationName = "") {
  const lat = Number(latitude);
  const lon = Number(longitude);
  const name = String(locationName || "").toLowerCase();

  // 1. Specific Named Location Lookups
  if (name.includes("kakkanad") || name.includes("infopark") || name.includes("smartcity")) {
    return {
      status: "success",
      bortle_class: 7,
      sqm: 18.5,
      artificial_brightness_mcd: 4.8,
      zone: "Kakkanad / Kochi IT Corridor",
      classification: "Urban / Suburban Transition (Heavy Light Dome)",
      limitingMagnitude: 4.5,
      description: "Severe urban light pollution from Infopark, streetlights, and commercial complexes.",
    };
  }

  if (name.includes("kochi") || name.includes("cochin") || name.includes("ernakulam")) {
    return {
      status: "success",
      bortle_class: 8,
      sqm: 18.1,
      artificial_brightness_mcd: 8.5,
      zone: "Kochi Metropolitan City",
      classification: "City Sky (Intense Skyglow)",
      limitingMagnitude: 4.0,
      description: "Dense coastal city lighting. High artificial sky brightness washing out faint stars.",
    };
  }

  if (name.includes("hanle") || name.includes("iao")) {
    return {
      status: "success",
      bortle_class: 1,
      sqm: 21.9,
      artificial_brightness_mcd: 0.001,
      zone: "Indian Astronomical Observatory (Hanle, Ladakh)",
      classification: "Pristine Dark Sky",
      limitingMagnitude: 7.6,
      description: "World-class dark sky site with near-zero artificial light pollution.",
    };
  }

  if (name.includes("mauna kea")) {
    return {
      status: "success",
      bortle_class: 1,
      sqm: 21.9,
      artificial_brightness_mcd: 0.001,
      zone: "Mauna Kea Summit, Hawaii",
      classification: "Pristine Dark Sky",
      limitingMagnitude: 7.8,
      description: "Premier international observatory site above low cloud inversion layer.",
    };
  }

  if (name.includes("paranal") || name.includes("atacama")) {
    return {
      status: "success",
      bortle_class: 1,
      sqm: 22.0,
      artificial_brightness_mcd: 0.0,
      zone: "Atacama Desert, Chile",
      classification: "Pristine Dark Sky",
      limitingMagnitude: 7.9,
      description: "Extremely dry and dark high-altitude desert observatory.",
    };
  }

  if (name.includes("munnar") || name.includes("wayanad") || name.includes("idukki")) {
    return {
      status: "success",
      bortle_class: 3,
      sqm: 21.4,
      artificial_brightness_mcd: 0.08,
      zone: "High-Altitude Western Ghats, Kerala",
      classification: "Rural Dark Sky",
      limitingMagnitude: 6.8,
      description: "Mountain dark sky favorable for deep-sky and milky way observation.",
    };
  }

  if (name.includes("thrissur")) {
    return {
      status: "success",
      bortle_class: 6,
      sqm: 19.3,
      artificial_brightness_mcd: 1.8,
      zone: "Thrissur Urban / Suburban",
      classification: "Bright Suburban Sky",
      limitingMagnitude: 5.2,
      description: "Suburban light pollution with moderate milky way obscuration.",
    };
  }

  if (name.includes("bengaluru") || name.includes("bangalore")) {
    return {
      status: "success",
      bortle_class: 8,
      sqm: 18.0,
      artificial_brightness_mcd: 9.0,
      zone: "Bengaluru Metropolitan Region",
      classification: "City Sky",
      limitingMagnitude: 4.1,
      description: "Dense metropolitan light pollution dome.",
    };
  }

  if (name.includes("mumbai") || name.includes("delhi") || name.includes("tokyo")) {
    return {
      status: "success",
      bortle_class: 9,
      sqm: 17.5,
      artificial_brightness_mcd: 16.0,
      zone: "Mega-City Inner Core",
      classification: "Inner-City Sky",
      limitingMagnitude: 3.5,
      description: "Extreme urban illumination; only bright planets and the Moon are visible.",
    };
  }

  // 2. Coordinate boundary checks for Kakkanad / Greater Kochi specifically
  if (lat >= 9.97 && lat <= 10.06 && lon >= 76.31 && lon <= 76.39) {
    return {
      status: "success",
      bortle_class: 7,
      sqm: 18.5,
      artificial_brightness_mcd: 4.8,
      zone: "Kakkanad / Kochi Urban Sector",
      classification: "Urban / Suburban Transition (Heavy Light Dome)",
      limitingMagnitude: 4.5,
      description: "Heavy commercial and residential artificial light dome in Kakkanad.",
    };
  }

  if (lat >= 9.85 && lat <= 10.15 && lon >= 76.20 && lon <= 76.45) {
    return {
      status: "success",
      bortle_class: 7,
      sqm: 18.4,
      artificial_brightness_mcd: 5.5,
      zone: "Greater Kochi Metropolitan Area",
      classification: "Urban Sky (Heavy Skyglow)",
      limitingMagnitude: 4.3,
      description: "Metropolitan coastal city lighting washing out faint celestial targets.",
    };
  }

  // 3. Coordinate boundary check for Thrissur area
  if (lat >= 10.45 && lat <= 10.60 && lon >= 76.15 && lon <= 76.30) {
    return {
      status: "success",
      bortle_class: 6,
      sqm: 19.3,
      artificial_brightness_mcd: 1.8,
      zone: "Thrissur Region",
      classification: "Bright Suburban Sky",
      limitingMagnitude: 5.2,
      description: "Suburban light pollution with moderate milky way obscuration.",
    };
  }

  // 4. Coordinate boundary check for Western Ghats dark skies
  if (lat >= 9.5 && lat <= 11.9 && lon >= 76.7 && lon <= 77.5) {
    return {
      status: "success",
      bortle_class: 3,
      sqm: 21.4,
      artificial_brightness_mcd: 0.08,
      zone: "Western Ghats Dark Sky Corridor",
      classification: "Rural Dark Sky",
      limitingMagnitude: 6.8,
      description: "Mountain dark sky favorable for deep-sky observation.",
    };
  }

  // Default fallback for general observer coordinates
  return {
    status: "assessed",
    bortle_class: 5,
    sqm: 20.0,
    artificial_brightness_mcd: 0.6,
    zone: "Suburban Observer Station",
    classification: "Suburban Sky",
    limitingMagnitude: 5.7,
    description: "Moderate suburban artificial brightness.",
  };
}

/**
 * Calculates target-specific light pollution attenuation.
 * In heavy urban skies (Bortle 7-8 like Kakkanad), faint diffuse objects (nebulae,
 * galaxies, meteors) are drastically degraded, while high-surface-brightness
 * planets (Jupiter, Saturn, Venus) remain observable.
 */
export function calculateLightPollutionEffect(category = "", bortleClass = 5, apparentMagnitude = null) {
  const cat = String(category || "").toLowerCase();
  const bortle = Math.max(1, Math.min(9, Number(bortleClass) || 5));

  let penalty = 0;
  let limitation = null;

  if (cat.includes("planet") || cat.includes("planetary")) {
    // High surface brightness: readily cuts through urban light pollution
    if (bortle >= 7) {
      penalty = (bortle - 6) * 6; // Bortle 7: -6 pts, Bortle 8: -12 pts
      limitation = `Urban light pollution (Bortle ${bortle}) slightly softens subtle planetary atmospheric contrast, but major planets remain well observable.`;
    }
  } else if (cat.includes("moon") || cat.includes("lunar")) {
    // Moon has extreme surface brightness, almost unaffected by city lights
    if (bortle >= 8) {
      penalty = 4;
      limitation = `Very high city glare (Bortle ${bortle}) slightly impairs naked-eye earthshine contrast.`;
    }
  } else if (
    cat.includes("deep_sky") ||
    cat.includes("deep sky") ||
    cat.includes("deep-sky") ||
    cat.includes("galaxy") ||
    cat.includes("nebula") ||
    cat.includes("cluster") ||
    cat.includes("messier") ||
    cat.includes("dso")
  ) {
    // Extended deep-sky objects (galaxies, nebulae, star clusters)
    if (bortle <= 3) {
      penalty = 0;
      limitation = null;
    } else if (bortle >= 7) {
      penalty = Math.min(30, (bortle - 5) * 12); // Bortle 7: -24 pts, Bortle 8: -30 pts
      limitation = `Urban skyglow (Bortle ${bortle}) reduces contrast on faint outer nebulosity. Use a narrowband UHC/O-III filter or visit a dark sky site for maximum visual depth.`;
    } else if (bortle >= 5) {
      penalty = (bortle - 4) * 8; // Bortle 5: -8 pts, Bortle 6: -16 pts
      limitation = `Suburban skyglow (Bortle ${bortle}) slightly softens faint outer spiral structure.`;
    }
  } else if (cat.includes("meteor")) {
    // Faint meteor streaks are severely obscured
    if (bortle >= 6) {
      penalty = (bortle - 5) * 15; // Bortle 7: -30 pts, Bortle 8: -45 pts
      limitation = `Urban light dome (Bortle ${bortle}) conceals up to 80% of faint meteor passes. Only occasional bright fireballs will penetrate city skyglow.`;
    }
  } else if (cat.includes("comet") || cat.includes("asteroid")) {
    // Faint point/diffuse targets
    if (bortle >= 6) {
      penalty = (bortle - 5) * 12; // Bortle 7: -24 pts, Bortle 8: -36 pts
      limitation = `Faint target in city sky (Bortle ${bortle}); requires telescope tracking (100mm-150mm+) to resolve through background skyglow.`;
    }
  }

  return {
    penalty: Math.min(60, penalty),
    limitation,
  };
}


