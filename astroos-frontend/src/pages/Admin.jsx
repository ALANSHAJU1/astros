import { useEffect, useState } from "react";
import { AlertCircle, LoaderCircle } from "lucide-react";

import BrandLogo from "../components/BrandLogo";
import { adminService } from "../services/adminService";
import { getApiErrorMessage } from "../utils/apiErrors";
import { formatDateTime } from "../utils/datetime";

export default function Admin() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    adminService
      .listUsers()
      .then((data) => setUsers(Array.isArray(data) ? data : []))
      .catch((err) => setError(getApiErrorMessage(err, "Unable to load users.")))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-content">
      <section className="explore-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">ADMINISTRATION</div>
          <h1>User <span>directory.</span></h1>
          <p>
            This view is limited to administrators and reads GET /api/v1/admin/users.
          </p>
        </div>
        <BrandLogo size="panel" />
      </section>

      {loading && (
        <div className="empty-catalogue">
          <LoaderCircle className="loading-spinner" size={28} />
          <p>Loading users...</p>
        </div>
      )}

      {error && (
        <div className="inline-alert">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {!loading && !error && (
        <div className="panel">
          <div className="result-table">
            {users.map((user) => (
              <article className="result-row" key={user.id}>
                <div>
                  <strong>{user.full_name || user.email}</strong>
                  <span>{user.email}</span>
                </div>
                <div>
                  <small>Role</small>
                  <strong>{user.role}</strong>
                </div>
                <div>
                  <small>Status</small>
                  <strong>{user.is_active ? "Active" : "Inactive"}</strong>
                </div>
                <div>
                  <small>Created</small>
                  <strong>{formatDateTime(user.created_at)}</strong>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
