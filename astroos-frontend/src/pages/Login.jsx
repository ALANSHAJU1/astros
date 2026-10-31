import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";

import BrandLogo from "../components/BrandLogo";
import { useAuth } from "../context/AuthContext";
import { getApiErrorMessage } from "../utils/apiErrors";

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated, ready } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (ready && isAuthenticated) {
    return <Navigate to={location.state?.from || "/"} replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      await login(email, password);
      navigate(location.state?.from || "/", { replace: true });
    } catch (err) {
      setError(
        getApiErrorMessage(
          err,
          "Login failed. Check your credentials and backend connection."
        )
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <div className="login-card">
        <div className="login-brand login-brand-logo">
          <BrandLogo size="hero" />
        </div>

        <div className="eyebrow">OBSERVER ACCESS</div>
        <h1>Welcome back.</h1>
        <p className="login-subtitle">
          Sign in to explore celestial events and generate observation plans
          with AstroOS intelligence.
        </p>

        <form onSubmit={handleSubmit}>
          <label htmlFor="login-email">Email address</label>
          <div className="login-input">
            <Mail size={17} />
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
            />
          </div>

          <label htmlFor="login-password">Password</label>
          <div className="login-input">
            <LockKeyhole size={17} />
            <input
              id="login-password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword((prev) => !prev)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--muted)",
                cursor: "pointer",
                padding: "4px",
                display: "flex",
                alignItems: "center",
              }}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>

          {error && <div className="login-error">{error}</div>}

          <button className="login-submit" type="submit" disabled={loading}>
            {loading ? "Signing in..." : "Sign in to AstroOS"}
          </button>
        </form>

        <p className="auth-switch">
          Need an observer account? <Link to="/register">Create one</Link>
        </p>

        <div className="login-security">
          Credentials are sent to the AstroOS backend. Access tokens are stored
          locally and attached as Bearer tokens on protected requests.
        </div>
      </div>
    </main>
  );
}
