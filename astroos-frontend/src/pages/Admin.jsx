import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  LoaderCircle,
  RefreshCw,
  Shield,
  UserCheck,
  UserX,
} from "lucide-react";

import BrandLogo from "../components/BrandLogo";
import { useAuth } from "../context/AuthContext";
import { adminService } from "../services/adminService";
import { getApiErrorMessage } from "../utils/apiErrors";
import { formatDateTime } from "../utils/datetime";

export default function Admin() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState(null);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");

  async function loadUsers() {
    setLoading(true);
    setError("");
    try {
      const data = await adminService.listUsers({ skip: 0, limit: 100 });
      setUsers(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(getApiErrorMessage(err, "Unable to load users."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  async function handleToggleStatus(targetUser) {
    if (targetUser.id === currentUser?.id) {
      setError("You cannot deactivate your own account.");
      return;
    }

    setUpdatingId(targetUser.id);
    setError("");
    setFeedback("");

    try {
      const updated = await adminService.updateStatus(
        targetUser.id,
        !targetUser.is_active
      );
      setUsers((prev) =>
        prev.map((u) => (u.id === targetUser.id ? { ...u, is_active: updated.is_active } : u))
      );
      setFeedback(`Status for ${targetUser.email} updated successfully.`);
      setTimeout(() => setFeedback(""), 4000);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to update account status."));
    } finally {
      setUpdatingId(null);
    }
  }

  async function handleToggleRole(targetUser) {
    if (targetUser.id === currentUser?.id) {
      setError("You cannot change your own administrator role.");
      return;
    }

    const newRole = targetUser.role === "admin" ? "user" : "admin";
    setUpdatingId(targetUser.id);
    setError("");
    setFeedback("");

    try {
      const updated = await adminService.updateRole(targetUser.id, newRole);
      setUsers((prev) =>
        prev.map((u) => (u.id === targetUser.id ? { ...u, role: updated.role } : u))
      );
      setFeedback(`Role for ${targetUser.email} changed to ${updated.role}.`);
      setTimeout(() => setFeedback(""), 4000);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to update user role."));
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <div className="page-content admin-page">
      <section className="explore-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">
            <span className="live-dot" /> SYSTEM ADMINISTRATION
          </div>
          <h1>User <span>directory.</span></h1>
          <p>
            Manage observer access, account activation, and role assignments.
            Changes take effect immediately across authenticated sessions.
          </p>
        </div>
        <BrandLogo size="panel" />
      </section>

      {feedback && (
        <div className="inline-alert" style={{ borderColor: "rgba(56, 189, 122, 0.4)", color: "#d8ffe8" }}>
          <CheckCircle2 size={16} /> {feedback}
        </div>
      )}

      {error && (
        <div className="inline-alert">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {loading ? (
        <div className="empty-catalogue">
          <LoaderCircle className="loading-spinner" size={28} />
          <p>Loading observer accounts...</p>
        </div>
      ) : (
        <div className="panel">
          <div className="panel-header">
            <div>
              <div className="eyebrow">USER ACCOUNTS ({users.length})</div>
              <h3>Registered observers</h3>
            </div>
            <button className="text-button" onClick={loadUsers}>
              <RefreshCw size={14} /> Refresh directory
            </button>
          </div>

          <div className="result-table">
            {users.map((u) => {
              const isSelf = u.id === currentUser?.id;
              const isBusy = updatingId === u.id;

              return (
                <article className="result-row" key={u.id}>
                  <div>
                    <strong>{u.full_name || "Observer"}</strong>
                    <span className="mono" style={{ fontSize: "11px" }}>{u.email}</span>
                  </div>

                  <div>
                    <small>Role</small>
                    <span className={`score-pill ${u.role === "admin" ? "optimal" : "good"}`}>
                      {u.role}
                    </span>
                  </div>

                  <div>
                    <small>Status</small>
                    <span className={`score-pill ${u.is_active ? "good" : "poor"}`}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>

                  <div>
                    <small>Registered</small>
                    <span style={{ fontSize: "11px" }}>{formatDateTime(u.created_at)}</span>
                  </div>

                  <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", gridColumn: "span 2" }}>
                    {!isSelf && (
                      <>
                        <button
                          className="secondary-action"
                          style={{ padding: "6px 10px", fontSize: "11px" }}
                          disabled={isBusy}
                          onClick={() => handleToggleRole(u)}
                          title={`Change role to ${u.role === "admin" ? "user" : "admin"}`}
                        >
                          <Shield size={13} /> {u.role === "admin" ? "Make User" : "Make Admin"}
                        </button>
                        <button
                          className="secondary-action"
                          style={{
                            padding: "6px 10px",
                            fontSize: "11px",
                            color: u.is_active ? "#fca5a5" : "#d8ffe8",
                          }}
                          disabled={isBusy}
                          onClick={() => handleToggleStatus(u)}
                        >
                          {u.is_active ? (
                            <>
                              <UserX size={13} /> Deactivate
                            </>
                          ) : (
                            <>
                              <UserCheck size={13} /> Activate
                            </>
                          )}
                        </button>
                      </>
                    )}
                    {isSelf && (
                      <span className="text-muted" style={{ fontSize: "11px", fontStyle: "italic" }}>
                        (Your current account)
                      </span>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
