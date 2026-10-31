import {
  Activity,
  CalendarDays,
  Compass,
  LayoutDashboard,
  LogOut,
  ShieldCheck,
  Sparkles,
  UserCircle,
  X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import BrandLogo from "./BrandLogo";
import { useAuth } from "../context/AuthContext";

const navigation = [
  { label: "Dashboard", path: "/", icon: LayoutDashboard },
  { label: "Explore Cosmos", path: "/explore", icon: Compass },
  { label: "Observation Planner", path: "/planner", icon: CalendarDays },
  { label: "Visibility Intelligence", path: "/visibility", icon: Activity },
  { label: "Catalog Recommendations", path: "/recommendations", icon: Sparkles },
  { label: "Profile", path: "/profile", icon: UserCircle },
];

export default function Sidebar({
  activePath,
  onNavigate,
  open,
  onClose,
  isAdmin = false,
}) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    onClose();
    navigate("/login", { replace: true });
  }

  return (
    <>
      {open && (
        <button className="sidebar-backdrop" onClick={onClose} aria-label="Close menu" />
      )}

      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="brand">
          <BrandLogo size="nav" />
          <button className="mobile-close" onClick={onClose} aria-label="Close menu">
            <X size={19} />
          </button>
        </div>

        <div className="sidebar-section-label">WORKSPACE</div>

        <nav className="sidebar-nav">
          {navigation.map(({ label, path, icon: Icon }) => (
            <button
              key={path}
              className={`nav-item ${activePath === path ? "active" : ""}`}
              onClick={() => {
                onNavigate(path);
                onClose();
              }}
            >
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        {isAdmin && (
          <>
            <div className="sidebar-section-label secondary-label">SYSTEM</div>
            <nav className="sidebar-nav">
              <button
                className={`nav-item ${activePath === "/admin" ? "active" : ""}`}
                onClick={() => {
                  onNavigate("/admin");
                  onClose();
                }}
              >
                <ShieldCheck size={18} strokeWidth={1.8} />
                <span>Administration</span>
              </button>
            </nav>
          </>
        )}

        <div className="sidebar-bottom">
          <BrandLogo size="sm" />
          <div className="sidebar-bottom-title">Observe with intelligence.</div>
          <div className="sidebar-bottom-text">
            Discover celestial events and plan sessions from live AstroOS APIs.
          </div>
          <button className="sidebar-logout" onClick={handleLogout}>
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>
    </>
  );
}
