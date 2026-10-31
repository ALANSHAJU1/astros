import BrandLogo from "./BrandLogo";

export default function LoadingScreen({ message = "Preparing celestial intelligence..." }) {
  return (
    <main className="loading-screen" role="status" aria-live="polite">
      <BrandLogo size="lg" />
      <p>{message}</p>
    </main>
  );
}
