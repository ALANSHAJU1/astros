import { useEffect, useState } from "react";
import { Camera, Sparkles } from "lucide-react";
import { getCelestialImage } from "../../services/celestialImages";

export default function CelestialVisual({
  object = {},
  size = "card", // "card" | "hero"
  symbol = "",
  showCredit = true,
  showScore = true,
}) {
  const [useBackup, setUseBackup] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);

  const imageEntry = getCelestialImage(
    object.name,
    object.category,
    object.additionalData?.target_id || object.target_id
  );

  useEffect(() => {
    setUseBackup(false);
    setLoadFailed(false);
    setIsLoaded(false);
  }, [object.name, object.category, imageEntry.url]);

  const activeSrc = useBackup ? imageEntry.backupUrl : imageEntry.url;
  const scoreVal = object.score !== null && object.score !== undefined ? Math.round(object.score) : null;

  function handleError() {
    if (!useBackup && imageEntry.backupUrl && imageEntry.backupUrl !== imageEntry.url) {
      setUseBackup(true);
    } else {
      setLoadFailed(true);
    }
  }

  const isHero = size === "hero";

  return (
    <div
      className={`celestial-photo-frame ${isHero ? "hero-frame" : "card-frame"}`}
      style={{
        "--accent-color": imageEntry.accent || "#A855F7",
      }}
    >
      {/* Background Photography or Fallback */}
      {!loadFailed ? (
        <img
          src={activeSrc}
          alt={object.name || "Celestial object"}
          className={`celestial-photo-img ${isLoaded ? "loaded" : "loading"}`}
          loading="lazy"
          referrerPolicy="no-referrer"
          onLoad={() => setIsLoaded(true)}
          onError={handleError}
        />
      ) : (
        <div className={`celestial-photo-fallback visual-${object.visual || "galaxy"}`}>
          <div className="fallback-glow" />
          <span className="fallback-symbol">{symbol || "✦"}</span>
        </div>
      )}

      {/* Atmospheric Star Dust & Gradient Vignette */}
      <div className="celestial-photo-vignette" />
      <div className="celestial-photo-atmosphere" />

      {/* Top Bar Badges */}
      <div className="celestial-photo-top-bar">
        {symbol && (
          <span className="celestial-symbol-pill" title={`Astronomical Symbol: ${symbol}`}>
            {symbol}
          </span>
        )}

        {showScore && scoreVal !== null && (
          <div className="celestial-score-chip" title={`Visibility Score: ${scoreVal}/100`}>
            <Sparkles size={11} />
            <span>{scoreVal}</span>
          </div>
        )}
      </div>

      {/* Mission / Photography Provenance Tag */}
      {showCredit && imageEntry.credit && (
        <div className="celestial-photo-credit" title={`Mission Photography: ${imageEntry.credit}`}>
          <Camera size={10} />
          <span>{imageEntry.credit}</span>
        </div>
      )}
    </div>
  );
}

