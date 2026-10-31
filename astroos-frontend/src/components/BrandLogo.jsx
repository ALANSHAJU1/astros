export default function BrandLogo({
  size = "md",
  className = "",
  alt = "AstroOS",
}) {
  return (
    <img
      src="/assets/astroos-logo.png"
      alt={alt}
      className={`brand-logo brand-logo-${size} ${className}`.trim()}
    />
  );
}
