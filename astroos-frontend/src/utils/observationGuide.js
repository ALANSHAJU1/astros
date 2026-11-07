/**
 * AstroOS Observation Method & Optical Equipment Guide
 *
 * Provides accurate observational guidance on how human observers can view each celestial target:
 * - Naked Eye
 * - Binoculars (7x50, 10x50)
 * - Small Telescope (60mm - 100mm / 2.4" - 4")
 * - Medium to Large Telescope (150mm+ / 6" - 10"+)
 * - Certified ISO 12312-2 Solar Filter
 * - Astrophotography / Digital Sensor
 */

export function getObservationGuide(name = "", category = "", magnitude = null, additionalData = {}) {
  const n = String(name || "").toLowerCase();
  const cat = String(category || "").toLowerCase();
  const mag = magnitude !== null && !Number.isNaN(Number(magnitude)) ? Number(magnitude) : null;

  // 1. Solar observation / Solar eclipses (SAFETY CRITICAL)
  if (
    n.includes("sun") ||
    cat.includes("sun") ||
    cat.includes("solar") ||
    n.includes("solar eclipse") ||
    cat.includes("solar eclipse")
  ) {
    return {
      method: "Solar Filter Required",
      badge: "Solar Filter Required",
      iconType: "sun",
      equipmentDetail: "ISO 12312-2 Certified Solar Eclipse Glasses or Full-Aperture Telescope Solar Filter",
      magnification: "1x (Glasses) or 30x–80x with full-aperture telescope filter",
      accessories: [
        "ISO 12312-2 Certified Solar Viewing Glasses",
        "Full-Aperture Baader Solar Filter for Telescope/Binoculars",
        "Solar Projection Screen or Dedicated H-alpha Solar Scope",
      ],
      howToSee:
        "CRITICAL SAFETY WARNING: Never observe the Sun with the naked eye, binoculars, or an unfiltered telescope! Permanent eye damage or blindness will occur. Use only certified ISO 12312-2 eclipse glasses or a full-aperture solar filter mounted securely at the front of your telescope. Look for partial bite marks during eclipses, or dark sunspots and faculae across the solar photosphere.",
      difficulty: "Easy with certified safety filtration",
      bestSkyCondition: "Clear daytime skies away from passing high cirrus clouds",
    };
  }

  // 2. Meteor Showers
  if (cat.includes("meteor") || n.includes("meteor") || n.includes("shower") || n.includes("perseid") || n.includes("geminid") || n.includes("orionid")) {
    return {
      method: "Naked Eye",
      badge: "Naked Eye",
      iconType: "eye",
      equipmentDetail: "Unaided Human Eye (Wide-Angle Peripheral Vision)",
      magnification: "1x (Do NOT use a telescope or binoculars)",
      accessories: [
        "Reclining Lawn Chair or Sleeping Mat",
        "Warm Blanket / Sleeping Bag",
        "Red LED Flashlight (preserves scotopic dark adaptation)",
        "Sky Map or Planetarium App (night mode)",
      ],
      howToSee:
        "Best viewed with the unaided eye! Telescopes and binoculars restrict your field of view too severely to catch rapid meteor streaks. Lie back on a reclining chair facing roughly 45° to 60° away from the radiant point. Allow 20–30 minutes in total darkness for your eyes to fully dark-adapt. Watch for fast white streaks and occasional lingering ion trains.",
      difficulty: "Easy",
      bestSkyCondition: "Dark skies (Bortle 1–4), after midnight when radiant culminates, moonless sky",
    };
  }

  // 3. Lunar Eclipses (Totality & Partial Blood Moon)
  if (
    (cat.includes("lunar") && cat.includes("eclipse")) ||
    (n.includes("lunar") && n.includes("eclipse")) ||
    cat.includes("lunar_eclipse") ||
    n.includes("blood moon")
  ) {
    return {
      method: "Naked Eye & Binoculars",
      badge: "Naked Eye / Binoculars",
      iconType: "eye",
      equipmentDetail: "Unaided Eye, 7x50 / 10x50 Binoculars, or Small Telescope (60mm+)",
      magnification: "1x (Naked Eye panoramic), 7x–10x (Binocular umbra details), 30x–70x (Telescope)",
      accessories: [
        "10x50 Wide-Field Binoculars or Small Refractor Telescope",
        "Tripod Mount for steady viewing during totality",
        "Camera on Tripod for long-exposure Blood Moon photography",
        "Comfortable Reclining Observation Chair",
      ],
      howToSee:
        "100% safe to observe directly with the naked eye! No filters are required. As Earth moves directly between the Sun and Moon, watch the dark curved bite of Earth's umbral shadow creep across the lunar face. During totality, the Moon transforms into an ethereal copper-red 'Blood Moon', illuminated by the collective glow of all the sunrises and sunsets around Earth's rim.",
      difficulty: "Very Easy",
      bestSkyCondition: "Clear skies during full moon phase; visible from cities and dark sky sites alike",
    };
  }

  // 4. Moon (General Lunar Observation)
  if (n.includes("moon") || cat.includes("moon") || cat.includes("lunar")) {
    return {
      method: "Naked Eye & Any Optical Aid",
      badge: "Naked Eye / Binoculars / Scope",
      iconType: "eye",
      equipmentDetail: "Naked Eye, 7x50 Binoculars, or any Small Telescope (60mm+)",
      magnification: "1x (Naked Eye), 7x–10x (Binoculars), 30x–150x (Telescope)",
      accessories: [
        "Neutral Density Lunar Filter (cuts dazzling glare at high magnification)",
        "25mm & 10mm Eyepieces",
        "Lunar Map or Moon Atlas",
      ],
      howToSee:
        "Vividly visible naked eye from any location, even brightly lit cities. Focus along the 'terminator' line (the boundary between lunar day and night) where low-angle sunlight casts long shadows, dramatically highlighting craters (Tycho, Copernicus), mountain chains (Apennines), and deep rilles. During a lunar eclipse, watch the Moon blush copper-red naked-eye as Earth's shadow engulfs it.",
      difficulty: "Very Easy",
      bestSkyCondition: "Any clear night from urban or rural skies; best at crescent and gibbous phases",
    };
  }

  // 4. Planets: Jupiter
  if (n.includes("jupiter")) {
    return {
      method: "Naked Eye & Telescope",
      badge: "Naked Eye (Locate) / Telescope (Details)",
      iconType: "telescope",
      equipmentDetail: "Naked Eye to spot; 70mm–150mm Telescope to resolve Galilean moons and cloud bands",
      magnification: "1x (Locate beacon), 7x–10x (Four Moons), 75x–150x (Cloud Belts & Red Spot)",
      accessories: [
        "Color Planetary Filter (Light Blue #80A or Light Orange #21)",
        "2x Achromatic Barlow Lens",
        "Sturdy Altitude-Azimuth or Equatorially Tracking Mount",
      ],
      howToSee:
        "Visible to the naked eye as a brilliant, steady cream-white beacon outshining all nearby stars. Steady 10x50 binoculars easily reveal the four Galilean moons (Io, Europa, Ganymede, Callisto) lined up in orbital planes. A 70mm+ telescope at 50x–100x magnification reveals Jupiter's dark equatorial cloud belts and the Great Red Spot.",
      difficulty: "Very Easy naked eye; Moderate for fine atmospheric detail",
      bestSkyCondition: "When high in the sky (>30° altitude) under steady atmospheric seeing with low turbulence",
    };
  }

  // 5. Planets: Saturn
  if (n.includes("saturn")) {
    return {
      method: "Naked Eye & Small Telescope",
      badge: "Small Telescope (Rings)",
      iconType: "telescope",
      equipmentDetail: "Naked Eye to locate; 60mm–100mm+ Telescope for majestic rings and Titan",
      magnification: "30x minimum to resolve rings; 80x–180x for Cassini division & ring shadow",
      accessories: [
        "9mm–15mm Plössl or Wide-Field Eyepiece",
        "2x Barlow Lens",
        "Yellow-Green Planetary Filter (#11) for subtle atmospheric banding",
      ],
      howToSee:
        "Appears to the naked eye as a steady golden-yellow star. Any small telescope (60mm / 2.4-inch or larger) at 30x–50x magnification will instantly separate Saturn's breathtaking rings from its globe. Higher magnifications (100x+) show the Cassini Division (dark gap in the rings), the shadow of the planet across the rings, and giant moon Titan.",
      difficulty: "Easy to spot; Rewarding with any backyard telescope",
      bestSkyCondition: "High altitude culmination during steady, transparent skies",
    };
  }

  // 6. Planets: Mars
  if (n.includes("mars")) {
    return {
      method: "Naked Eye & Medium Telescope",
      badge: "Naked Eye / Medium Scope",
      iconType: "telescope",
      equipmentDetail: "Naked Eye for orange-red color; 4-inch to 8-inch Telescope for surface details",
      magnification: "100x–200x on nights of calm atmospheric seeing",
      accessories: [
        "Red (#23A) or Orange (#21) Filter to boost surface contrast",
        "High-magnification eyepiece (6mm–9mm)",
        "Motorized tracking mount for steady high-power inspection",
      ],
      howToSee:
        "Easily spotted with the naked eye by its unmistakable fiery orange-red hue. Resolving surface features requires a 4-inch or larger telescope when Mars is near opposition (closest approach to Earth). Look for the dazzling white polar ice caps and subtle dark volcanic albedo regions like Syrtis Major.",
      difficulty: "Easy naked eye; Challenging for small telescope surface features",
      bestSkyCondition: "Opposition period under calm seeing with minimal atmospheric scintillation",
    };
  }

  // 7. Planets: Venus & Mercury
  if (n.includes("venus") || n.includes("mercury")) {
    const isVenus = n.includes("venus");
    return {
      method: "Naked Eye & Small Telescope",
      badge: "Naked Eye / Small Scope",
      iconType: "telescope",
      equipmentDetail: isVenus
        ? "Naked Eye in evening/morning twilight; 60mm+ Telescope for crescent phases"
        : "Naked Eye/Binoculars during peak elongation twilight along clear horizon",
      magnification: "20x–60x to resolve changing planetary phases",
      accessories: [
        "Variable Polarizing Filter (reduces overpowering Venusian glare)",
        "Compass or unobstructed western/eastern horizon view",
      ],
      howToSee: isVenus
        ? "Venus is the 'Morning Star' or 'Evening Star', dazzling brightly in twilight skies. A small telescope or 10x binoculars reveals that Venus exhibits phases just like the Moon—from a slender delicate crescent to a gibbous disk."
        : "Mercury stays close to the Sun, appearing low on the horizon in dusk or dawn twilight. Use binoculars to pinpoint it against the twilight glow, then switch to a small telescope to observe its phase.",
      difficulty: "Easy for Venus; Moderate for Mercury due to low horizon altitude",
      bestSkyCondition: "30–60 minutes after sunset or before sunrise along a clear horizon",
    };
  }

  // 8. Planets: Uranus & Neptune
  if (n.includes("uranus") || n.includes("neptune")) {
    const isUranus = n.includes("uranus");
    return {
      method: isUranus ? "Binoculars / Small Telescope" : "Small to Medium Telescope",
      badge: isUranus ? "Binoculars / Scope" : "Medium Telescope",
      iconType: "telescope",
      equipmentDetail: isUranus
        ? "7x50 or 10x50 Binoculars to locate; 80mm+ Telescope to see pale cyan disk"
        : "100mm–150mm Telescope and detailed star chart to resolve tiny azure disk",
      magnification: isUranus ? "10x (starlike in binoculars); 100x+ (disk in scope)" : "120x–200x",
      accessories: [
        "Detailed Finder Star Chart / Star-Hopping Guide",
        "Red LED Flashlight",
        "High-power eyepiece",
      ],
      howToSee: isUranus
        ? "Uranus (mag ~5.7) can be spotted with binoculars in dark skies as a tiny greenish-cyan star. A 4-inch telescope at 100x magnification shows a distinct, non-twinkling planetary disk."
        : "Neptune (mag ~7.8) requires a telescope and star chart to distinguish its tiny, deep-blue disk from surrounding background stars. At 150x magnification in a 6-inch scope, its blue color and disc shape become apparent.",
      difficulty: "Moderate to Challenging (Requires star-hopping)",
      bestSkyCondition: "Dark rural skies (Bortle 1–4), new moon, zenith culmination",
    };
  }

  // 9. Bright Asteroids: 1 Ceres, 4 Vesta
  if (n.includes("vesta") || n.includes("ceres") || (cat.includes("asteroid") && mag !== null && mag < 8.5)) {
    const isVesta = n.includes("vesta");
    return {
      method: "Binoculars / Small Telescope",
      badge: "Binoculars / Small Scope",
      iconType: "binoculars",
      equipmentDetail: "10x50 Binoculars or 70mm–100mm Telescope with a star-hopping chart",
      magnification: "10x to 50x wide-field",
      accessories: [
        "AstroOS / JPL Horizons Ephemeris Finder Chart",
        "Binocular Tripod Adapter for rock-steady tracking",
        "Field Notebook or Sketchpad",
      ],
      howToSee: isVesta
        ? "4 Vesta is the brightest asteroid in the solar system (mag 5.5–6.5) and can be seen with ordinary binoculars. It looks like a steady star. Sketch the star field across two consecutive nights to watch Vesta noticeably change position against background stars!"
        : "1 Ceres (mag 7.5–8.5) is the largest asteroid belt body and dwarf planet. Readily observable with 10x50 binoculars or any small telescope. Track its nightly movement across several days to confirm its orbital motion.",
      difficulty: "Moderate (Requires star-hopping to identify among stars)",
      bestSkyCondition: "Moonless nights under suburban to dark rural skies",
    };
  }

  // 10. Faint Near-Earth Asteroids (Apophis, Eros, Bennu)
  if (cat.includes("asteroid") || n.includes("apophis") || n.includes("eros") || n.includes("bennu")) {
    return {
      method: "Medium to Large Telescope / Astrophotography",
      badge: "Large Scope / Camera",
      iconType: "camera",
      equipmentDetail: "6-inch to 10-inch Telescope or Digital Astrophotography Rig (CMOS/CCD)",
      magnification: "Long-exposure stacked imaging (30s–120s sub-exposures) or 150x+",
      accessories: [
        "GoTo Computerized Equatorial Mount",
        "Cooled Astronomy Camera / DSLR",
        "Plate-Solving & Stacking Software (DSS / PixInsight)",
      ],
      howToSee:
        "Near-Earth Objects are typically faint (magnitude 12–16+ except during close flybys). They are best recorded by stacking multiple digital exposures: while background stars remain stationary pinpoints, the asteroid draws a distinct moving streak of light across the sensor frames.",
      difficulty: "Advanced (Astrophotography or large aperture required)",
      bestSkyCondition: "Pristine dark skies (Bortle 1–3) with no moonlight or light pollution",
    };
  }

  // 11. Comets (Halley, NEOWISE, generic comets)
  if (cat.includes("comet") || n.includes("comet") || n.includes("halley") || n.includes("neowise")) {
    const isBright = mag !== null && mag <= 6.0;
    return {
      method: isBright ? "Naked Eye & Binoculars" : "Binoculars & Wide-Field Telescope",
      badge: isBright ? "Naked Eye / Binoculars" : "Binoculars / Telescope",
      iconType: "binoculars",
      equipmentDetail: "7x50 or 10x50 Binoculars; Wide-Field Telescope (f/4 to f/6) with low magnification",
      magnification: "7x to 35x (Wide field of view preserves delicate tail structure)",
      accessories: [
        "Wide-Field Eyepiece (30mm–32mm)",
        "Deep-Sky Light Pollution Filter",
        "Dark Sky Site with clean horizon",
      ],
      howToSee:
        "Comets appear as soft, diffuse fuzzy patches with a brighter stellar nucleus, often accompanied by an elongated dust or gas tail sweeping away from the Sun. Use binoculars to scan the horizon. In a telescope, use low power and 'averted vision' (looking slightly off to the side) to trace faint tail wisps.",
      difficulty: "Moderate",
      bestSkyCondition: "Dark skies with transparent horizon; avoid twilight and urban skyglow",
    };
  }

  // 12. Deep-Sky Objects: Pleiades M45, Orion Nebula M42, Andromeda M31
  if (n.includes("pleiades") || n.includes("m45") || n.includes("seven sisters")) {
    return {
      method: "Naked Eye & Binoculars",
      badge: "Binoculars (Optimal) / Eye",
      iconType: "binoculars",
      equipmentDetail: "Naked Eye under dark skies; 7x50 or 10x50 Binoculars (Best view)",
      magnification: "7x–10x (Telescopes have too narrow a field for this large cluster)",
      accessories: ["Binoculars", "Reclining Chair", "Warm Layers"],
      howToSee:
        "Naked eye reveals 6 to 7 glittering blue-white stars in a tiny dipper shape. 10x50 binoculars reveal dozens of diamond-like stars wrapped in faint bluish reflection nebulosity under dark skies.",
      difficulty: "Very Easy",
      bestSkyCondition: "Suburban to dark rural skies; autumn and winter evenings",
    };
  }

  if (n.includes("orion") || n.includes("m42")) {
    return {
      method: "Binoculars & Any Telescope",
      badge: "Binoculars / Telescope",
      iconType: "telescope",
      equipmentDetail: "Visible naked eye in Orion's sword; spectacular in any 60mm+ Telescope",
      magnification: "20x–60x for cosmic cloud structure; 100x for Trapezium cluster stars",
      accessories: [
        "UHC (Ultra High Contrast) or O-III Nebula Filter",
        "Wide-Field Eyepiece",
      ],
      howToSee:
        "Look at the center of Orion's Sword hanging below the Belt. A fuzzy star to the naked eye blooms into glowing wings of cosmic gas in binoculars. A small telescope resolves the 'Trapezium'—four infant stars illuminating the nebula from within.",
      difficulty: "Easy & spectacular",
      bestSkyCondition: "Winter skies; visible even from suburban light pollution",
    };
  }

  if (n.includes("andromeda") || n.includes("m31")) {
    return {
      method: "Naked Eye & Binoculars",
      badge: "Binoculars / Small Scope",
      iconType: "binoculars",
      equipmentDetail: "Naked eye in dark skies (Bortle 1–4); 10x50 Binoculars or 80mm+ Telescope",
      magnification: "7x to 25x wide-angle",
      accessories: [
        "Binoculars on Tripod",
        "Low-power wide-field eyepiece",
        "Dark Sky Site",
      ],
      howToSee:
        "Our neighboring spiral galaxy spanning 2.5 million light-years away. In dark skies, it is the most distant object visible to the unaided human eye as a ghostly smudge. Binoculars reveal its elongated cosmic disk and bright stellar core.",
      difficulty: "Easy under dark skies; Moderate in suburban skies",
      bestSkyCondition: "Moonless night under dark country skies (Bortle 1–4)",
    };
  }

  // M13 Great Globular Cluster in Hercules
  if (n.includes("hercules") || n.includes("m13")) {
    return {
      method: "Binoculars & Small Telescope",
      badge: "Binoculars / Telescope",
      iconType: "telescope",
      equipmentDetail: "10x50 Binoculars to locate; 100mm–200mm Telescope to resolve outer stars",
      magnification: "10x in binoculars; 75x–150x in telescope to resolve stellar grains",
      accessories: [
        "Medium-power Eyepiece (10mm–15mm)",
        "Sturdy Tripod or Dobsonian Mount",
        "Star Chart of the Hercules Keystone",
      ],
      howToSee:
        "Look along the western side of the Hercules 'Keystone' quadrilateral. Binoculars reveal a distinct hazy cosmic snowball. An 8-inch telescope at 100x magnification resolves thousands of shimmering stellar pinpoints across its dense core.",
      difficulty: "Easy to find with binoculars; Rewarding in a telescope",
      bestSkyCondition: "Spring and summer skies at high culmination, moonless night",
    };
  }

  // M57 Ring Nebula in Lyra
  if (n.includes("ring nebula") || n.includes("m57")) {
    return {
      method: "Small to Medium Telescope",
      badge: "Small Telescope (Smoke Ring)",
      iconType: "telescope",
      equipmentDetail: "70mm–100mm+ Telescope (Too small to resolve in binoculars)",
      magnification: "80x–180x high magnification",
      accessories: [
        "UHC or O-III Nebula Filter",
        "High-magnification eyepiece (6mm–9mm)",
        "2x Barlow Lens",
      ],
      howToSee:
        "Point your telescope halfway between Beta and Gamma Lyrae in the constellation Lyra. At 100x magnification, it reveals an unmistakable, delicate smoke-ring floating in deep space with a slightly darker interior.",
      difficulty: "Moderate (requires locating between stars and high magnification)",
      bestSkyCondition: "Summer to autumn nights under steady transparent seeing",
    };
  }

  // M27 Dumbbell Nebula in Vulpecula
  if (n.includes("dumbbell") || n.includes("m27")) {
    return {
      method: "Binoculars & Small Telescope",
      badge: "Binoculars / Scope",
      iconType: "telescope",
      equipmentDetail: "10x50 Binoculars to spot; 80mm+ Telescope for hourglass shape",
      magnification: "10x (fuzzy patch) to 50x–100x (lobed structure)",
      accessories: [
        "O-III or UHC Filter",
        "Wide-Field Eyepiece",
      ],
      howToSee:
        "The first planetary nebula ever discovered. Readily spotted in binoculars as an oval glow. In a 4-inch or larger telescope with a UHC filter, its double-lobed apple-core or dumbbell shape stands out dramatically.",
      difficulty: "Moderate",
      bestSkyCondition: "Summer Milky Way skies away from urban light domes",
    };
  }

  // M8 Lagoon Nebula in Sagittarius
  if (n.includes("lagoon") || n.includes("m8")) {
    return {
      method: "Binoculars & Telescope",
      badge: "Binoculars / Telescope",
      iconType: "telescope",
      equipmentDetail: "7x50 or 10x50 Binoculars; 80mm–150mm Telescope with wide-field eyepiece",
      magnification: "10x to 45x wide-angle",
      accessories: [
        "H-Beta or UHC Filter",
        "Low-power 2-inch wide-field eyepiece",
      ],
      howToSee:
        "Located in the rich star clouds of the Sagittarius Milky Way. Binoculars show an elongated glowing cloud bifurcated by a dark interstellar dust lane (the 'lagoon') with embedded open cluster NGC 6530 sparkling inside.",
      difficulty: "Easy under dark southern horizons",
      bestSkyCondition: "Summer nights along clear southern horizon without obstruction",
    };
  }

  // M51 Whirlpool Galaxy in Canes Venatici
  if (n.includes("whirlpool") || n.includes("m51")) {
    return {
      method: "4-inch to 8-inch Telescope",
      badge: "Medium Telescope (Spiral Arms)",
      iconType: "telescope",
      equipmentDetail: "100mm–200mm Reflector / Dobsonian Telescope under dark skies",
      magnification: "50x–120x",
      accessories: [
        "Dark Sky Site (Bortle 1–3 essential for spiral arms)",
        "25mm & 12mm Wide-Field Eyepieces",
      ],
      howToSee:
        "Located just off Alkaid at the tip of the Big Dipper's handle. In small scopes, you will see two bright cores (M51 and companion NGC 5195). An 8-inch scope in dark skies reveals the stunning spiral bridge connecting both galaxies.",
      difficulty: "Moderate to Challenging (Requires dark skies to trace arms)",
      bestSkyCondition: "Pristine dark rural sky (Bortle 1–3), no moonlight",
    };
  }

  // M81 / M82 Bode's & Cigar Galaxies in Ursa Major
  if (n.includes("bode") || n.includes("m81") || n.includes("cigar") || n.includes("m82")) {
    return {
      method: "Binoculars & Small Telescope",
      badge: "Binoculars / Small Scope",
      iconType: "telescope",
      equipmentDetail: "10x50 Binoculars or 70mm–150mm Telescope",
      magnification: "10x to 60x (Wide field fits both galaxies in one eyepiece view!)",
      accessories: [
        "Wide-Field Eyepiece (fits both in same ~1.5° field)",
        "Star-Hopping Chart from Dubhe in Ursa Major",
      ],
      howToSee:
        "A celebrated celestial pair! At low power (30x–50x), both galaxies fit into the same telescopic field of view: M81 appears as a smooth bright oval spiral, while M82 (the Cigar Galaxy) appears as a thin, edge-on needle mottled with dark dust filaments.",
      difficulty: "Easy to Moderate",
      bestSkyCondition: "Clear northern spring sky away from light pollution",
    };
  }

  // M44 Beehive Cluster / Praesepe in Cancer
  if (n.includes("beehive") || n.includes("m44") || n.includes("praesepe")) {
    return {
      method: "Naked Eye & Binoculars",
      badge: "Binoculars (Best) / Eye",
      iconType: "binoculars",
      equipmentDetail: "Naked Eye under suburban/dark skies; 7x50 or 10x50 Binoculars (Optimal)",
      magnification: "1x (faint cloud) to 7x–10x (dozens of resolved stars)",
      accessories: ["Binoculars on Tripod", "Comfortable Lounger"],
      howToSee:
        "Visible to the naked eye as a hazy smudge in the faint constellation Cancer. 10x50 binoculars transform the smudge into a glorious open swarm of over 50 sparkling stars resembling a busy swarm of bees.",
      difficulty: "Very Easy",
      bestSkyCondition: "Winter and spring skies, moonless night",
    };
  }

  // M1 Crab Nebula in Taurus
  if (n.includes("crab nebula") || n.includes("m1")) {
    return {
      method: "Small to Medium Telescope",
      badge: "Telescope (Supernova Remnant)",
      iconType: "telescope",
      equipmentDetail: "80mm–150mm Telescope; star chart to locate near Zeta Tauri",
      magnification: "50x–100x",
      accessories: [
        "Deep-Sky / O-III Filter",
        "Red Headlamp for dark adaptation",
      ],
      howToSee:
        "The remnant of the supernova seen by astronomers in 1054 AD. Located near Zeta Tauri. In a 4-inch telescope it appears as a faint, elongated oval ghost. An 8-inch scope reveals subtle filamentary texture with averted vision.",
      difficulty: "Moderate (faint diffuse contrast)",
      bestSkyCondition: "Transparent winter skies without moonlight or haze",
    };
  }

  // 13. Generic Deep-Sky Objects
  if (cat.includes("deep sky") || cat.includes("galaxy") || cat.includes("nebula") || cat.includes("cluster") || cat.includes("dso")) {
    const isBinocTarget = mag !== null && mag <= 6.5;
    return {
      method: isBinocTarget ? "Binoculars / Small Telescope" : "4-inch to 8-inch Telescope",
      badge: isBinocTarget ? "Binoculars / Small Scope" : "Medium Telescope",
      iconType: "telescope",
      equipmentDetail: isBinocTarget
        ? "10x50 Binoculars or 70mm–100mm Telescope"
        : "4-inch to 8-inch Reflector/Dobsonian Telescope",
      magnification: "30x to 100x",
      accessories: [
        "Deep-Sky / UHC Nebula Filter",
        "25mm Plössl Eyepiece",
        "Red LED Flashlight",
      ],
      howToSee:
        "Allow your eyes 20 minutes to adapt to darkness. Use low magnification to locate the target field. Use averted vision (looking 10° away from center) to let the eye's sensitive rod cells pick up subtle spiral arms, nebulosity, and resolved star clusters.",
      difficulty: "Moderate",
      bestSkyCondition: "New Moon period under dark skies with no light pollution",
    };
  }

  // Default fallback
  return {
    method: "Naked Eye / Binoculars / Small Telescope",
    badge: "Binoculars / Scope",
    iconType: "telescope",
    equipmentDetail: "Unaided Eye, 10x50 Binoculars, or Small Backyard Telescope",
    magnification: "1x to 50x",
    accessories: ["Planisphere or Planetarium App", "Red Flashlight"],
    howToSee:
      "Locate the target constellation using a star chart or planetarium app. Observe when the target is highest in the sky away from horizon haze and city light domes.",
    difficulty: "Easy to Moderate",
    bestSkyCondition: "Clear, transparent skies away from city light pollution",
  };
}

