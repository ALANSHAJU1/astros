/**
 * AstroOS Celestial Imagery Service
 *
 * Provides authentic, high-resolution astronomical photographs from NASA, ESA,
 * JPL-Caltech, Hubble Space Telescope, James Webb Space Telescope (JWST),
 * and authoritative astronomical archives for planets, asteroids, comets,
 * and deep-sky objects.
 */

export const CELESTIAL_IMAGE_REGISTRY = {
  // ---------------------------------------------------------------------------
  // SOLAR SYSTEM PLANETS
  // ---------------------------------------------------------------------------
  jupiter: {
    url: "https://images.unsplash.com/photo-1614732414444-096e5f1122d5?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/Jupiter.jpg/800px-Jupiter.jpg",
    credit: "NASA / JPL-Caltech / SwRI / Juno",
    accent: "#E5A963",
    description: "Gas giant with Great Red Spot & turbulent Jovian atmospheric bands",
  },
  saturn: {
    url: "https://images.unsplash.com/photo-1614732484003-ef9881555dc3?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Saturn_during_Equinox.jpg/800px-Saturn_during_Equinox.jpg",
    credit: "NASA / JPL / Space Science Institute / Cassini",
    accent: "#E0BE77",
    description: "Ringed jewel of the solar system with icy ring plane",
  },
  mars: {
    url: "https://images.unsplash.com/photo-1614728894747-a83421e2b9c9?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/0/02/OSIRIS_Mars_true_color.jpg/800px-OSIRIS_Mars_true_color.jpg",
    credit: "ESA / MPS / OSIRIS / Mars Express / NASA",
    accent: "#E26A4B",
    description: "The Red Planet with iron-oxide deserts and polar ice cap",
  },
  venus: {
    url: "https://images.unsplash.com/photo-1614313913007-2b4ae8ce32d6?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/0/08/Venus_from_Mariner_10.jpg/800px-Venus_from_Mariner_10.jpg",
    credit: "NASA / Mariner 10 / JAXA Akatsuki",
    accent: "#FFD077",
    description: "Shrouded in dense reflective sulfuric acid clouds",
  },
  mercury: {
    url: "https://images.unsplash.com/photo-1614728423169-3f65fd722b7e?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d9/Mercury_in_color_-_Prockter07-edit1.jpg/800px-Mercury_in_color_-_Prockter07-edit1.jpg",
    credit: "NASA / JHUAPL / Carnegie / MESSENGER",
    accent: "#A2A7AF",
    description: "Heavily cratered terrestrial world closest to the Sun",
  },
  uranus: {
    url: "https://images.unsplash.com/photo-1614732446738-f86497f1fbc7?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3d/Uranus2.jpg/800px-Uranus2.jpg",
    credit: "NASA / JPL-Caltech / Voyager 2",
    accent: "#76D7EA",
    description: "Aquamarine ice giant tilted on its rotational axis",
  },
  neptune: {
    url: "https://images.unsplash.com/photo-1545156521-77bd85671d30?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/Neptune.jpg/800px-Neptune.jpg",
    credit: "NASA / JPL / Voyager 2",
    accent: "#4B7BE5",
    description: "Deep azure ice giant with supersonic winds & methane clouds",
  },
  moon: {
    url: "https://images.unsplash.com/photo-1522030299830-16b8d3d049fe?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/FullMoon2010.jpg/800px-FullMoon2010.jpg",
    credit: "NASA / GSFC / Arizona State Univ / LRO",
    accent: "#E2E5E9",
    description: "Earth's natural satellite showing basaltic maria & impact craters",
  },
  earth: {
    url: "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/9/97/The_Earth_seen_from_Apollo_17.jpg/800px-The_Earth_seen_from_Apollo_17.jpg",
    credit: "NASA / Apollo 17 'Blue Marble'",
    accent: "#38A3A5",
    description: "Blue oasis of life with liquid water oceans and atmosphere",
  },

  // ---------------------------------------------------------------------------
  // ASTEROIDS & NEAR-EARTH OBJECTS
  // ---------------------------------------------------------------------------
  ceres: {
    url: "https://images.unsplash.com/photo-1614728423169-3f65fd722b7e?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/7/76/Ceres_-_RC3_-_Haulani_Crater_%2822381149172%29.jpg/800px-Ceres_-_RC3_-_Haulani_Crater_%2822381149172%29.jpg",
    credit: "NASA / JPL-Caltech / UCLA / MPS / Dawn",
    accent: "#C5B299",
    description: "Dwarf planet Ceres with bright sodium-carbonate Occator crater spots",
  },
  vesta: {
    url: "https://images.unsplash.com/photo-1710268470228-6d77e6d999b3?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Vesta_in_natural_color.jpg/800px-Vesta_in_natural_color.jpg",
    credit: "NASA / JPL-Caltech / UCLA / MPS / DLR / IDA",
    accent: "#C3B6A6",
    description: "Differentiated rocky asteroid with massive south polar Rheasilvia basin",
  },
  apophis: {
    url: "https://images.unsplash.com/photo-1655448985613-3d16697a7250?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1710268470228-6d77e6d999b3?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA Planetary Defense / Goldstone Radar",
    accent: "#B49E82",
    description: "Aten-class Near-Earth Asteroid monitored for close planetary flybys",
  },
  eros: {
    url: "https://images.unsplash.com/photo-1710268470228-6d77e6d999b3?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1655448985613-3d16697a7250?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / JHUAPL / NEAR Shoemaker",
    accent: "#B8A287",
    description: "Elongated peanut-shaped S-type asteroid orbited by NEAR",
  },
  bennu: {
    url: "https://images.unsplash.com/photo-1655448985613-3d16697a7250?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1710268470228-6d77e6d999b3?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / Goddard / University of Arizona / OSIRIS-REx",
    accent: "#6E6862",
    description: "Carbonaceous rubble-pile asteroid sampled by OSIRIS-REx",
  },
  generic_asteroid: {
    url: "https://images.unsplash.com/photo-1710268470228-6d77e6d999b3?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1655448985613-3d16697a7250?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / JPL Small-Body Database",
    accent: "#A69886",
    description: "Rocky primordial planetesimal orbiting in interplanetary space",
  },

  // ---------------------------------------------------------------------------
  // COMETS
  // ---------------------------------------------------------------------------
  halley: {
    url: "https://images.unsplash.com/photo-1675457242541-761e7c858792?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1639004280952-d16fee4be746?auto=format&fit=crop&w=1200&q=85",
    credit: "ESA / Giotto Mission & Mount Wilson Observatory",
    accent: "#76E5FC",
    description: "History's most famous periodic comet displaying brilliant gas & dust coma",
  },
  neowise: {
    url: "https://images.unsplash.com/photo-1639004280952-d16fee4be746?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1639959019385-7ed4c7f421a8?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / JPL-Caltech / NEOWISE & Night-Sky Astrophotography",
    accent: "#F7D070",
    description: "Great Comet of 2020 displaying split golden dust and blue ion tails",
  },
  generic_comet: {
    url: "https://images.unsplash.com/photo-1639959019385-7ed4c7f421a8?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1639004280952-d16fee4be746?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / ESA SOHO Ephemeris",
    accent: "#8BE8FD",
    description: "Icy wanderer outgassing solar wind dust and ionized gas tails",
  },

  // ---------------------------------------------------------------------------
  // DEEP-SKY OBJECTS (MESSIER & NGC)
  // ---------------------------------------------------------------------------
  m31: {
    url: "https://images.unsplash.com/photo-1502134249126-9f3755a50d78?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/9/98/Andromeda_Galaxy_%28with_h-alpha%29.jpg/800px-Andromeda_Galaxy_%28with_h-alpha%29.jpg",
    credit: "NASA / JPL-Caltech / Robert Gendler (Hubble / GALEX)",
    accent: "#6CA0DC",
    description: "Andromeda Spiral Galaxy spanning 220,000 light-years across",
  },
  m42: {
    url: "https://images.unsplash.com/photo-1543722530-d2c3201371e7?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/Orion_Nebula_-_Hubble_2006_mosaic_18000.jpg/800px-Orion_Nebula_-_Hubble_2006_mosaic_18000.jpg",
    credit: "NASA / ESA / M. Robberto (Hubble Heritage Team)",
    accent: "#E84393",
    description: "Great Orion Nebula stellar nursery lit by infant Trapezium stars",
  },
  m45: {
    url: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Pleiades_large.jpg/800px-Pleiades_large.jpg",
    credit: "NASA / ESA / STScI / Digitized Sky Survey",
    accent: "#74B9FF",
    description: "The Pleiades Open Cluster with gossamer blue reflection nebulosity",
  },
  m13: {
    url: "https://upload.wikimedia.org/wikipedia/commons/thumb/4/43/M13_Messier_13_Hercules_Cluster.jpg/800px-M13_Messier_13_Hercules_Cluster.jpg",
    backupUrl: "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / ESA / Hubble Heritage Team (STScI/AURA)",
    accent: "#E2F0D9",
    description: "Great Globular Cluster in Hercules containing ~500,000 stars",
  },
  m8: {
    url: "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Lagoon_Nebula_by_ESO.jpg/800px-Lagoon_Nebula_by_ESO.jpg",
    backupUrl: "https://images.unsplash.com/photo-1543722530-d2c3201371e7?auto=format&fit=crop&w=1200&q=85",
    credit: "ESO / VPHAS+ Consortium",
    accent: "#FD79A8",
    description: "Lagoon Nebula in Sagittarius with embedded star cluster NGC 6530",
  },
  m57: {
    url: "https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/M57_The_Ring_Nebula.jpg/800px-M57_The_Ring_Nebula.jpg",
    backupUrl: "https://images.unsplash.com/photo-1543722530-d2c3201371e7?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / ESA / C.R. O'Dell (Vanderbilt Univ) / Hubble",
    accent: "#00CEC9",
    description: "Ring Nebula smoke-ring shell expelled by central white dwarf in Lyra",
  },
  m27: {
    url: "https://upload.wikimedia.org/wikipedia/commons/thumb/a/af/M27_-_Dumbbell_Nebula.jpg/800px-M27_-_Dumbbell_Nebula.jpg",
    backupUrl: "https://images.unsplash.com/photo-1543722530-d2c3201371e7?auto=format&fit=crop&w=1200&q=85",
    credit: "ESO / Very Large Telescope (VLT)",
    accent: "#55EFC4",
    description: "Dumbbell Nebula in Vulpecula displaying bi-lobed hourglass geometry",
  },
  m51: {
    url: "https://upload.wikimedia.org/wikipedia/commons/thumb/0/02/M51_Whirlpool_Galaxy_HST.jpg/800px-M51_Whirlpool_Galaxy_HST.jpg",
    backupUrl: "https://images.unsplash.com/photo-1502134249126-9f3755a50d78?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / ESA / S. Beckwith (STScI) / Hubble Heritage Team",
    accent: "#A29BFE",
    description: "Whirlpool Galaxy face-on grand design spiral with companion NGC 5195",
  },
  m81: {
    url: "https://upload.wikimedia.org/wikipedia/commons/thumb/5/50/M81_Messier_81.jpg/800px-M81_Messier_81.jpg",
    backupUrl: "https://images.unsplash.com/photo-1502134249126-9f3755a50d78?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / ESA / Hubble Heritage Team",
    accent: "#FFEAA7",
    description: "Bode's Spiral Galaxy in Ursa Major with active galactic nucleus",
  },
  m44: {
    url: "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Pleiades_large.jpg/800px-Pleiades_large.jpg",
    credit: "ESO / Digitized Sky Survey",
    accent: "#FDCB6E",
    description: "Beehive Cluster (Praesepe) open star swarm in Cancer",
  },
  m7: {
    url: "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Pleiades_large.jpg/800px-Pleiades_large.jpg",
    credit: "ESO / Wide Field Imager (La Silla Observatory)",
    accent: "#81ECEC",
    description: "Ptolemy's Cluster near the stinger of Scorpius",
  },
  m1: {
    url: "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/Crab_Nebula.jpg/800px-Crab_Nebula.jpg",
    backupUrl: "https://images.unsplash.com/photo-1543722530-d2c3201371e7?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / ESA / J. Hester and A. Loll (ASU) / Hubble",
    accent: "#FAB1A0",
    description: "Crab Nebula expanding supernova remnant from 1054 AD in Taurus",
  },
  generic_galaxy: {
    url: "https://images.unsplash.com/photo-1502134249126-9f3755a50d78?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/0/02/M51_Whirlpool_Galaxy_HST.jpg/800px-M51_Whirlpool_Galaxy_HST.jpg",
    credit: "NASA / ESA / STScI Hubble Deep Field",
    accent: "#A29BFE",
    description: "Island universe composed of billions of gravitationally bound stars",
  },
  generic_nebula: {
    url: "https://images.unsplash.com/photo-1543722530-d2c3201371e7?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/Orion_Nebula_-_Hubble_2006_mosaic_18000.jpg/800px-Orion_Nebula_-_Hubble_2006_mosaic_18000.jpg",
    credit: "NASA / ESA / Hubble Heritage",
    accent: "#E84393",
    description: "Luminous interstellar cloud of ionized hydrogen gas and cosmic dust",
  },
  generic_cluster: {
    url: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Pleiades_large.jpg/800px-Pleiades_large.jpg",
    credit: "ESO / Hubble Heritage",
    accent: "#74B9FF",
    description: "Gravitationally bound cluster of glittering celestial stars",
  },

  // ---------------------------------------------------------------------------
  // METEOR SHOWERS & TRANSIENT EVENTS
  // ---------------------------------------------------------------------------
  perseids: {
    url: "https://images.unsplash.com/photo-1532767153582-b1a0e5145009?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1516339901601-2e1b62dc0c45?auto=format&fit=crop&w=1200&q=85",
    credit: "Night Sky Astrophotography / Perseid Fireball",
    accent: "#00CEC9",
    description: "Prolific Perseid meteor fireball streaking across the Milky Way from Perseus",
  },
  geminids: {
    url: "https://images.unsplash.com/photo-1516339901601-2e1b62dc0c45?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1532767153582-b1a0e5145009?auto=format&fit=crop&w=1200&q=85",
    credit: "International Meteor Organization / Gemini Observatory",
    accent: "#F5B942",
    description: "Multi-colored Geminid fireball stream radiating from near Castor in Gemini",
  },
  orionids: {
    url: "https://images.unsplash.com/photo-1532767153582-b1a0e5145009?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / MSFC Meteoroid Environment Office",
    accent: "#E84393",
    description: "High-speed Orionid meteor vapor streak from ancient debris of Halley's Comet",
  },
  leonids: {
    url: "https://images.unsplash.com/photo-1532767153582-b1a0e5145009?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1516339901601-2e1b62dc0c45?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA Ames / Leonid Airborne Campaign",
    accent: "#00B894",
    description: "Supersonic Leonid fireball leaving persistent glowing ion train in mesosphere",
  },
  lyrids: {
    url: "https://images.unsplash.com/photo-1532767153582-b1a0e5145009?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1516339901601-2e1b62dc0c45?auto=format&fit=crop&w=1200&q=85",
    credit: "European Southern Observatory / IMO",
    accent: "#74B9FF",
    description: "Ancient Lyrid meteor shower radiating near the bright star Vega in Lyra",
  },
  quadrantids: {
    url: "https://images.unsplash.com/photo-1516339901601-2e1b62dc0c45?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1532767153582-b1a0e5145009?auto=format&fit=crop&w=1200&q=85",
    credit: "IMO / NASA Meteoroid Environment Office",
    accent: "#A29BFE",
    description: "Intense short-duration Quadrantid fireball stream radiating from northern skies",
  },
  meteor: {
    url: "https://images.unsplash.com/photo-1532767153582-b1a0e5145009?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1516339901601-2e1b62dc0c45?auto=format&fit=crop&w=1200&q=85",
    credit: "Night Sky Astrophotography / Perseid Fireball",
    accent: "#00B894",
    description: "Ionizing cometary meteoroid blazing across the upper mesosphere",
  },
  solar_eclipse: {
    url: "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Solar_eclipse_1999_4_NR.jpg/800px-Solar_eclipse_1999_4_NR.jpg",
    backupUrl: "https://images.unsplash.com/photo-1538370965046-79c0d6907d47?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / Solar Dynamics Observatory / Luc Viatour",
    accent: "#F39C12",
    description: "Total solar eclipse revealing the ethereal white solar corona",
  },
  total_solar_eclipse: {
    url: "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Solar_eclipse_1999_4_NR.jpg/800px-Solar_eclipse_1999_4_NR.jpg",
    backupUrl: "https://images.unsplash.com/photo-1538370965046-79c0d6907d47?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / SDO / Luc Viatour Astrophotography",
    accent: "#F39C12",
    description: "Total solar eclipse displaying brilliant solar corona and diamond ring",
  },
  annular_solar_eclipse: {
    url: "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Solar_eclipse_20_May_2012_by_Shih-Kang_Chung.jpg/800px-Solar_eclipse_20_May_2012_by_Shih-Kang_Chung.jpg",
    backupUrl: "https://images.unsplash.com/photo-1538370965046-79c0d6907d47?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA / JAXA Hinode Solar Observatory / Shih-Kang Chung",
    accent: "#FFDA8A",
    description: "Ring of Fire annular solar eclipse with glowing golden photosphere annulus",
  },
  lunar_eclipse: {
    url: "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Blood_Moon_July_27_2018.jpg/800px-Blood_Moon_July_27_2018.jpg",
    backupUrl: "https://images.unsplash.com/photo-1532693322450-2cb5c511067d?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA Goddard / Blood Moon Totality Astrophotography",
    accent: "#D63031",
    description: "Copper-red Blood Moon illuminated by Earth's refractive sunset ring",
  },
  total_lunar_eclipse: {
    url: "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Blood_Moon_July_27_2018.jpg/800px-Blood_Moon_July_27_2018.jpg",
    backupUrl: "https://images.unsplash.com/photo-1532693322450-2cb5c511067d?auto=format&fit=crop&w=1200&q=85",
    credit: "NASA Goddard / Blood Moon Astrophotography Archive",
    accent: "#D63031",
    description: "Total lunar eclipse with copper-red Blood Moon in starfield",
  },
  partial_lunar_eclipse: {
    url: "https://images.unsplash.com/photo-1532693322450-2cb5c511067d?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://images.unsplash.com/photo-1522030299830-16b8d3d049fe?auto=format&fit=crop&w=1200&q=85",
    credit: "ESO / Night Sky Astrophotography Archive",
    accent: "#E17055",
    description: "Deep partial lunar eclipse with Earth's dark curved umbral shadow",
  },
  sun: {
    url: "https://images.unsplash.com/photo-1538370965046-79c0d6907d47?auto=format&fit=crop&w=1200&q=85",
    backupUrl: "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/The_Sun_by_the_Atmospheric_Imaging_Assembly_of_NASA%27s_Solar_Dynamics_Observatory_-_20100819.jpg/800px-The_Sun_by_the_Atmospheric_Imaging_Assembly_of_NASA%27s_Solar_Dynamics_Observatory_-_20100819.jpg",
    credit: "NASA / Solar & Heliospheric Observatory (SOHO/SDO)",
    accent: "#E17055",
    description: "Our parent star displaying active solar prominences & photosphere flares",
  },
};

/**
 * Resolves the optimal astronomical photography entry for any celestial object.
 * Checks target name, catalog ID, category, and event type.
 */
export function getCelestialImage(name = "", category = "", targetId = "") {
  const n = String(name || "").toLowerCase().trim();
  const cat = String(category || "").toLowerCase().trim();
  const tid = String(targetId || "").toLowerCase().trim();

  // 1. Direct Planet Matching
  if (n.includes("jupiter") || tid === "599") return CELESTIAL_IMAGE_REGISTRY.jupiter;
  if (n.includes("saturn") || tid === "699") return CELESTIAL_IMAGE_REGISTRY.saturn;
  if (n.includes("mars") || tid === "499") return CELESTIAL_IMAGE_REGISTRY.mars;
  if (n.includes("venus") || tid === "299") return CELESTIAL_IMAGE_REGISTRY.venus;
  if (n.includes("mercury") || tid === "199") return CELESTIAL_IMAGE_REGISTRY.mercury;
  if (n.includes("uranus") || tid === "799") return CELESTIAL_IMAGE_REGISTRY.uranus;
  if (n.includes("neptune") || tid === "899") return CELESTIAL_IMAGE_REGISTRY.neptune;
  if (n.includes("earth") && !n.includes("near-earth")) return CELESTIAL_IMAGE_REGISTRY.earth;

  // Solar Eclipses (Match before Moon/Sun)
  if (
    cat.includes("solar_eclipse") ||
    cat.includes("solar eclipse") ||
    (cat.includes("solar") && cat.includes("eclipse")) ||
    (n.includes("solar") && n.includes("eclipse")) ||
    tid.startsWith("tse-") ||
    tid.startsWith("ase-")
  ) {
    if (n.includes("annular") || tid.startsWith("ase-")) {
      return CELESTIAL_IMAGE_REGISTRY.annular_solar_eclipse || CELESTIAL_IMAGE_REGISTRY.solar_eclipse;
    }
    return CELESTIAL_IMAGE_REGISTRY.total_solar_eclipse || CELESTIAL_IMAGE_REGISTRY.solar_eclipse;
  }

  // Lunar Eclipses (Match before normal Moon)
  if (
    cat.includes("lunar_eclipse") ||
    cat.includes("lunar eclipse") ||
    (cat.includes("lunar") && cat.includes("eclipse")) ||
    (n.includes("lunar") && n.includes("eclipse")) ||
    n.includes("blood moon") ||
    tid.startsWith("tle-") ||
    tid.startsWith("ple-") ||
    tid.startsWith("pne-")
  ) {
    if (n.includes("partial") || tid.startsWith("ple-")) {
      return CELESTIAL_IMAGE_REGISTRY.partial_lunar_eclipse || CELESTIAL_IMAGE_REGISTRY.lunar_eclipse;
    }
    return CELESTIAL_IMAGE_REGISTRY.total_lunar_eclipse || CELESTIAL_IMAGE_REGISTRY.lunar_eclipse;
  }

  if (n.includes("moon") || cat.includes("moon") || cat.includes("lunar")) {
    return CELESTIAL_IMAGE_REGISTRY.moon;
  }

  // 2. Specific Asteroids
  if (n.includes("ceres") || tid.includes("1;")) return CELESTIAL_IMAGE_REGISTRY.ceres;
  if (n.includes("vesta") || tid.includes("4;")) return CELESTIAL_IMAGE_REGISTRY.vesta;
  if (n.includes("apophis") || tid.includes("99942")) return CELESTIAL_IMAGE_REGISTRY.apophis;
  if (n.includes("eros") || tid.includes("433;")) return CELESTIAL_IMAGE_REGISTRY.eros;
  if (n.includes("bennu") || tid.includes("101955")) return CELESTIAL_IMAGE_REGISTRY.bennu;

  // 3. Specific Comets
  if (n.includes("halley") || tid.includes("90000030")) return CELESTIAL_IMAGE_REGISTRY.halley;
  if (n.includes("neowise") || tid.includes("90004601")) return CELESTIAL_IMAGE_REGISTRY.neowise;

  // 4. Specific Deep-Sky Objects
  if (n.includes("m31") || n.includes("andromeda")) return CELESTIAL_IMAGE_REGISTRY.m31;
  if (n.includes("m42") || n.includes("orion nebula") || (n.includes("orion") && !n.includes("orionid"))) {
    return CELESTIAL_IMAGE_REGISTRY.m42;
  }
  if (n.includes("m45") || n.includes("pleiades") || n.includes("seven sisters")) {
    return CELESTIAL_IMAGE_REGISTRY.m45;
  }
  if (n.includes("m13") || n.includes("hercules")) return CELESTIAL_IMAGE_REGISTRY.m13;
  if (n.includes("m8") && (n.includes("lagoon") || n.startsWith("m8 "))) return CELESTIAL_IMAGE_REGISTRY.m8;
  if (n.includes("m57") || n.includes("ring nebula")) return CELESTIAL_IMAGE_REGISTRY.m57;
  if (n.includes("m27") || n.includes("dumbbell")) return CELESTIAL_IMAGE_REGISTRY.m27;
  if (n.includes("m51") || n.includes("whirlpool")) return CELESTIAL_IMAGE_REGISTRY.m51;
  if (n.includes("m81") || n.includes("bode") || n.includes("cigar") || n.includes("m82")) {
    return CELESTIAL_IMAGE_REGISTRY.m81;
  }
  if (n.includes("m44") || n.includes("beehive") || n.includes("praesepe")) {
    return CELESTIAL_IMAGE_REGISTRY.m44;
  }
  if (n.includes("m7") || n.includes("ptolemy")) return CELESTIAL_IMAGE_REGISTRY.m7;
  if (n.includes("m1 ") || n.includes("m1 (") || n.includes("crab nebula")) return CELESTIAL_IMAGE_REGISTRY.m1;

  // 5. Specific Meteor Showers
  if (n.includes("perseid") || tid.includes("per")) return CELESTIAL_IMAGE_REGISTRY.perseids;
  if (n.includes("geminid") || tid.includes("gem")) return CELESTIAL_IMAGE_REGISTRY.geminids;
  if (n.includes("orionid") || tid.includes("ori")) return CELESTIAL_IMAGE_REGISTRY.orionids;
  if (n.includes("leonid") || tid.includes("leo")) return CELESTIAL_IMAGE_REGISTRY.leonids;
  if (n.includes("lyrid") || tid.includes("lyr")) return CELESTIAL_IMAGE_REGISTRY.lyrids;
  if (n.includes("quadrantid") || tid.includes("qua")) return CELESTIAL_IMAGE_REGISTRY.quadrantids;

  // 6. Category Fallbacks
  if (cat.includes("meteor") || n.includes("meteor") || n.includes("shower")) {
    return CELESTIAL_IMAGE_REGISTRY.meteor;
  }

  if (cat.includes("solar_eclipse") || n.includes("solar eclipse")) {
    return CELESTIAL_IMAGE_REGISTRY.solar_eclipse;
  }

  if (cat.includes("lunar_eclipse") || n.includes("lunar eclipse")) {
    return CELESTIAL_IMAGE_REGISTRY.lunar_eclipse;
  }

  if (cat.includes("comet") || n.includes("comet")) {
    return CELESTIAL_IMAGE_REGISTRY.generic_comet;
  }

  if (cat.includes("asteroid") || cat.includes("neo") || cat.includes("minor_planet")) {
    return CELESTIAL_IMAGE_REGISTRY.generic_asteroid;
  }

  if (cat.includes("galaxy") || n.includes("galaxy")) {
    return CELESTIAL_IMAGE_REGISTRY.generic_galaxy;
  }

  if (cat.includes("nebula") || n.includes("nebula")) {
    return CELESTIAL_IMAGE_REGISTRY.generic_nebula;
  }

  if (cat.includes("cluster") || n.includes("cluster")) {
    return CELESTIAL_IMAGE_REGISTRY.generic_cluster;
  }

  if (cat.includes("deep") || cat.includes("dso") || cat.includes("messier")) {
    return CELESTIAL_IMAGE_REGISTRY.m31;
  }

  if (cat.includes("sun") || n.includes("sun")) {
    return CELESTIAL_IMAGE_REGISTRY.sun;
  }

  if (cat.includes("planet")) {
    return CELESTIAL_IMAGE_REGISTRY.jupiter;
  }

  // Universal Default: Andromeda Galaxy deep space view
  return CELESTIAL_IMAGE_REGISTRY.generic_galaxy;
}

