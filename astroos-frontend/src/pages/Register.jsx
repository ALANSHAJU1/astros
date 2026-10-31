import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Eye, EyeOff, LockKeyhole, Mail, User } from "lucide-react";

import BrandLogo from "../components/BrandLogo";
import { useAuth } from "../context/AuthContext";
import { getApiErrorMessage } from "../utils/apiErrors";

export default function Register() {
  const navigate = useNavigate();
  const { register, isAuthenticated, ready } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (ready && isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match. Please re-enter.");
      return;
    }

    setLoading(true);

    try {
      await register({
        email,
        password,
        full_name: fullName.trim() || null,
      });
      navigate("/login", {
        replace: true,
        state: { registered: true },
      });
    } catch (err) {
      setError(
        getApiErrorMessage(
          err,
          "Registration failed. Public registration may be disabled on this backend."
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

        <div className="eyebrow">NEW OBSERVER</div>
        <h1>Create your account.</h1>
        <p className="login-subtitle">
          Registration provisions a new account with the observer role.
          Passphrases are hashed securely with Argon2id on the backend.
        </p>

        <form onSubmit={handleSubmit}>
          <label htmlFor="register-name">Full name</label>
          <div className="login-input">
            <User size={17} />
            <input
              id="register-name"
              type="text"
              autoComplete="name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Observer display name"
            />
          </div>

          <label htmlFor="register-email">Email address</label>
          <div className="login-input">
            <Mail size={17} />
            <input
              id="register-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
            />
          </div>

          <label htmlFor="register-password">Password</label>
          <div className="login-input">
            <LockKeyhole size={17} />
            <input
              id="register-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
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

          <label htmlFor="register-confirm-password">Confirm password</label>
          <div className="login-input">
            <LockKeyhole size={17} />
            <input
              id="register-confirm-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={8}
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="Repeat your password"
            />
          </div>

          {error && <div className="login-error">{error}</div>}

          <button className="login-submit" type="submit" disabled={loading}>
            {loading ? "Creating account..." : "Create AstroOS account"}
          </button>
        </form>

        <p className="auth-switch">
          Already have an observer account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </main>
  );
}
