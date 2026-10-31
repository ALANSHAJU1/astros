import { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { LogOut, Menu, UserCircle } from "lucide-react";

import Sidebar from "./Sidebar";
import { useAuth } from "../context/AuthContext";

const pageNames = {
  "/": "Dashboard",
  "/explore": "Explore Cosmos",
  "/planner": "Observation Planner",
  "/visibility": "Visibility Intelligence",
  "/recommendations": "Catalog Recommendations",
  "/profile": "Observer Profile",
  "/admin": "Administration",
};

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const title = pageNames[location.pathname] || "AstroOS";

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="app-shell">
      <Sidebar
        activePath={location.pathname}
        onNavigate={navigate}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        isAdmin={user?.role === "admin"}
      />

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open menu"
            >
              <Menu size={21} />
            </button>

            <div className="breadcrumb">
              ASTROOS <span>/</span> {title.toUpperCase()}
            </div>
          </div>

          <div className="topbar-actions">
            <div className="system-status">
              <span className="live-dot" /> OBSERVER SESSION
            </div>

            <button
              className="profile-button"
              onClick={() => navigate("/profile")}
              aria-label="Open profile"
            >
              <UserCircle size={22} />
              <span>{user?.full_name || user?.email || "Observer"}</span>
            </button>

            <button className="logout-chip" onClick={handleLogout}>
              <LogOut size={14} />
              Logout
            </button>
          </div>
        </header>

        <Outlet />
      </main>
    </div>
  );
}
