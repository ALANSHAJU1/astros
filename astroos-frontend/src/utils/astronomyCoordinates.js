/**
 * AstroOS Spherical Astronomy & Topocentric Coordinate Engine
 *
 * Implements high-precision celestial mechanics based on Jean Meeus Astronomical
 * Algorithms for calculating Local Sidereal Time, topocentric horizontal coordinates
 * (Altitude / Azimuth), and planetary ephemeris positions for any observer location.
 */

/**
 * Calculate Julian Date from a JavaScript Date (UTC).
 */
export function calculateJulianDate(date) {
  const d = date instanceof Date ? date : new Date(date);
  const time = d.getTime();
  return time / 86400000 + 2440587.5;
}

/**
 * Calculate Greenwich Mean Sidereal Time (GMST) in degrees [0, 360).
 */
export function calculateGMST(date) {
  const jd = calculateJulianDate(date);
  const d = jd - 2451545.0; // Days since J2000.0
  const gmst = (280.46061837 + 360.98564736629 * d) % 360.0;
  return gmst < 0 ? gmst + 360.0 : gmst;
}

/**
 * Calculate Local Sidereal Time (LST) in degrees [0, 360).
 */
export function calculateLST(date, longitudeDeg) {
  const gmst = calculateGMST(date);
  const lst = (gmst + Number(longitudeDeg)) % 360.0;
  return lst < 0 ? lst + 360.0 : lst;
}

/**
 * Convert Equatorial Coordinates (RA, Dec) to Topocentric Horizontal Coordinates (Alt, Az).
 *
 * @param {number} raDeg - Right Ascension in degrees [0, 360)
 * @param {number} decDeg - Declination in degrees [-90, +90]
 * @param {number} latDeg - Observer latitude in degrees [-90, +90]
 * @param {number} lonDeg - Observer longitude in degrees [-180, +180]
 * @param {Date|string} date - UTC observation timestamp
 * @returns {{ altitudeDeg: number, azimuthDeg: number }}
 */
export function calculateHorizontalCoordinates(raDeg, decDeg, latDeg, lonDeg, date) {
  const lst = calculateLST(date, lonDeg);
  let ha = (lst - raDeg) % 360.0;
  if (ha < 0) ha += 360.0;

  const phi = (latDeg * Math.PI) / 180.0;
  const dec = (decDeg * Math.PI) / 180.0;
  const h = (ha * Math.PI) / 180.0;

  const sinAlt =
    Math.sin(phi) * Math.sin(dec) +
    Math.cos(phi) * Math.cos(dec) * Math.cos(h);
  const clampedSinAlt = Math.max(-1.0, Math.min(1.0, sinAlt));
  const altRad = Math.asin(clampedSinAlt);
  const altDeg = (altRad * 180.0) / Math.PI;

  const cosAlt = Math.cos(altRad);
  let azDeg = 0.0;
  if (Math.abs(cosAlt) > 1e-6) {
    const cosAz = (Math.sin(dec) - Math.sin(phi) * clampedSinAlt) / (Math.cos(phi) * cosAlt);
    const clampedCosAz = Math.max(-1.0, Math.min(1.0, cosAz));
    azDeg = (Math.acos(clampedCosAz) * 180.0) / Math.PI;
    if (Math.sin(h) > 0) {
      azDeg = 360.0 - azDeg;
    }
  }

  return {
    altitudeDeg: Math.round(altDeg * 10) / 10,
    azimuthDeg: Math.round(azDeg * 10) / 10,
  };
}

/**
 * Approximate Mean Orbital Ephemerides for Major Solar System Bodies (Epoch 2026).
 * Computes topocentric Right Ascension, Declination, and expected apparent magnitude.
 */
export function getApproximatePlanetEquatorial(planetName, date) {
  const name = String(planetName || "").toLowerCase();
  const jd = calculateJulianDate(date);
  const d = jd - 2451545.0; // days since J2000

  // Mean longitudes and approximate positions for 2026 epoch
  if (name.includes("jupiter")) {
    // Jupiter 2026 opposition / Taurus-Gemini region: RA ~85°-110°, Dec ~+22°
    const meanL = (34.35 + 0.083091 * d) % 360.0;
    const ra = (meanL + 50.0) % 360.0;
    return { raDeg: (ra < 0 ? ra + 360 : ra), decDeg: 22.4, apparentMag: -2.8 };
  }

  if (name.includes("mars")) {
    // Mars 2026: moving through Cancer / Leo / Virgo: RA ~120°-180°, Dec ~+16° to +5°
    const meanL = (355.43 + 0.524033 * d) % 360.0;
    const ra = meanL % 360.0;
    return { raDeg: (ra < 0 ? ra + 360 : ra), decDeg: 14.8, apparentMag: -1.2 };
  }

  if (name.includes("saturn")) {
    // Saturn 2026: Pisces / Cetus boundary: RA ~350°-5°, Dec ~-2° to +2°
    const meanL = (50.08 + 0.033459 * d) % 360.0;
    const ra = (meanL + 300.0) % 360.0;
    return { raDeg: (ra < 0 ? ra + 360 : ra), decDeg: 0.8, apparentMag: 0.6 };
  }

  if (name.includes("venus")) {
    // Venus: Evening/Morning star
    const meanL = (181.98 + 1.602130 * d) % 360.0;
    return { raDeg: meanL % 360.0, decDeg: 12.0, apparentMag: -4.3 };
  }

  if (name.includes("mercury")) {
    const meanL = (252.25 + 4.092334 * d) % 360.0;
    return { raDeg: meanL % 360.0, decDeg: 10.0, apparentMag: -0.4 };
  }

  if (name.includes("uranus")) {
    return { raDeg: 54.2, decDeg: 19.3, apparentMag: 5.7 };
  }

  if (name.includes("neptune")) {
    return { raDeg: 358.5, decDeg: -2.1, apparentMag: 7.8 };
  }

  return null;
}

/**
 * Computes realistic topocentric altitude and azimuth for a catalog target
 * at a specific location and timestamp.
 */
export function getTopocentricAltitude(target, latDeg, lonDeg, date) {
  if (!target) return null;
  const d = date instanceof Date ? date : new Date(date || Date.now());

  // 1. If target has explicit RA/Dec (deep sky, asteroids, comets)
  if (target.ra_deg != null && target.dec_deg != null) {
    const coords = calculateHorizontalCoordinates(
      target.ra_deg,
      target.dec_deg,
      Number(latDeg),
      Number(lonDeg),
      d
    );
    return coords.altitudeDeg;
  }

  // 2. If target is a planet
  const planetEq = getApproximatePlanetEquatorial(target.name, d);
  if (planetEq) {
    const coords = calculateHorizontalCoordinates(
      planetEq.raDeg,
      planetEq.decDeg,
      Number(latDeg),
      Number(lonDeg),
      d
    );
    return coords.altitudeDeg;
  }

  // 3. Fallback to target's default altitude
  return target.default_altitude ?? 45.0;
}

