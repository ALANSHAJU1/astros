import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Check,
  LogOut,
  MapPin,
  Save,
  UserCheck,
} from "lucide-react";

import BrandLogo from "../components/BrandLogo";
import { useAuth } from "../context/AuthContext";
import { formatDateTime } from "../utils/datetime";
import { loadObserverLocation, saveObserverLocation } from "../utils/location";

export default function Profile() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [location, setLocation] = useState(() => loadObserverLocation());
  const [savedMessage, setSavedMessage] = useState(false);

  if (!user) return null;

  function handleSaveLocation(e) {
    e.preventDefault();
    const lat = Number(location.latitude);
    const lon = Number(location.longitude);
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      saveObserverLocation({ latitude: lat, longitude: lon });
      setSavedMessage(true);
      setTimeout(() => setSavedMessage(false), 3000);
    }
  }

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="page-content profile-page">
      <section className="explore-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">
            <span className="live-dot" /> OBSERVER IDENTITY & SESSION
          </div>
          <h1>Your AstroOS <span>profile.</span></h1>
          <p>
            Authenticated observer account details retrieved from the AstroOS
            backend via GET /api/v1/auth/me. Sensitive credentials and password
            hashes are never exposed.
          </p>
        </div>
        <BrandLogo size="panel" />
      </section>

      <div className="dashboard-grid">
        {/* Core Profile Attributes */}
        <div className="panel profile-panel">
          <div className="panel-header">
            <div>
              <div className="eyebrow">ACCOUNT INFORMATION</div>
              <h3>Observer credentials</h3>
            </div>
            <div className="system-status">
              <UserCheck size={16} /> {user.role.toUpperCase()}
            </div>
          </div>

          <dl className="profile-grid">
            <div>
              <dt>Display name</dt>
              <dd>{user.full_name || "Observer"}</dd>
            </div>
            <div>
              <dt>Email address</dt>
              <dd>{user.email}</dd>
            </div>
            <div>
              <dt>Authorization role</dt>
              <dd>
                <span className={`score-pill ${user.role === "admin" ? "optimal" : "good"}`}>
                  {user.role}
                </span>
              </dd>
            </div>
            <div>
              <dt>Account status</dt>
              <dd>
                <span className="score-pill good">
                  {user.is_active ? "Active" : "Inactive"}
                </span>
              </dd>
            </div>
            <div>
              <dt>Member since</dt>
              <dd>{formatDateTime(user.created_at)}</dd>
            </div>
            <div>
              <dt>System user UUID</dt>
              <dd className="mono" style={{ fontSize: "11px", wordBreak: "break-all" }}>
                {user.id}
              </dd>
            </div>
          </dl>

          <p className="condition-note" style={{ marginTop: "16px" }}>
            Profile identity fields are authoritative and cryptographically signed.
            Profile edits and role changes require administrator privileges.
          </p>
        </div>

        {/* Observer Station & Session Preferences */}
        <div className="panel station-panel">
          <div className="panel-header">
            <div>
              <div className="eyebrow">OBSERVER STATION</div>
              <h3>Default observing location</h3>
              <p>Coordinates used by default in observation planning and visibility queries.</p>
            </div>
            <MapPin size={20} className="text-gold" />
          </div>

          <form onSubmit={handleSaveLocation} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div className="planner-grid" style={{ marginBottom: 0 }}>
              <label>
                Default latitude
                <input
                  type="number"
                  step="0.0001"
                  min="-90"
                  max="90"
                  required
                  value={location.latitude}
                  onChange={(e) =>
                    setLocation((prev) => ({ ...prev, latitude: e.target.value }))
                  }
                />
              </label>
              <label>
                Default longitude
                <input
                  type="number"
                  step="0.0001"
                  min="-180"
                  max="180"
                  required
                  value={location.longitude}
                  onChange={(e) =>
                    setLocation((prev) => ({ ...prev, longitude: e.target.value }))
                  }
                />
              </label>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "4px" }}>
              <button className="primary-action" type="submit" style={{ padding: "8px 16px" }}>
                {savedMessage ? (
                  <>
                    <Check size={15} /> Coordinates saved
                  </>
                ) : (
                  <>
                    <Save size={15} /> Save default station
                  </>
                )}
              </button>
              {savedMessage && (
                <span className="text-emerald" style={{ fontSize: "12px" }}>
                  Saved to browser storage
                </span>
              )}
            </div>
          </form>

          <div style={{ marginTop: "24px", paddingTop: "16px", borderTop: "1px solid var(--border)" }}>
            <div className="eyebrow">SESSION SECURITY</div>
            <div className="condition-row">
              <span>Authentication method:</span>
              <strong>Argon2id + JWT Bearer</strong>
            </div>
            <div className="condition-row">
              <span>Token rotation:</span>
              <strong>Opaque family replay detection</strong>
            </div>
            <div className="condition-row">
              <span>CORS Policy:</span>
              <strong>Configured origin boundary</strong>
            </div>

            <button
              className="secondary-action"
              style={{ marginTop: "16px", width: "100%", justifyContent: "center" }}
              onClick={handleLogout}
            >
              <LogOut size={15} /> End observer session (Sign out)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
