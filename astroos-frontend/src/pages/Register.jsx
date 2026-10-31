import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { LockKeyhole, Mail, User } from "lucide-react";

import BrandLogo from "../components/BrandLogo";
import { useAuth } from "../context/AuthContext";
import { getApiErrorMessage } from "../utils/apiErrors";

export default function Register() {
  const navigate = useNavigate();
  const { register, isAuthenticated, ready } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (ready && isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
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
          Registration is available only when the backend enables public signup.
          New accounts are created with the user role.
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
              placeholder="Optional display name"
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
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
            />
          </div>

          {error && <div className="login-error">{error}</div>}

          <button className="login-submit" type="submit" disabled={loading}>
            {loading ? "Creating account..." : "Create AstroOS account"}
          </button>
        </form>

        <p className="auth-switch">
          Already have access? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </main>
  );
}
