import BrandLogo from "../components/BrandLogo";
import { useAuth } from "../context/AuthContext";
import { formatDateTime } from "../utils/datetime";

export default function Profile() {
  const { user } = useAuth();

  if (!user) return null;

  return (
    <div className="page-content">
      <section className="explore-hero">
        <div className="explore-hero-content">
          <div className="eyebrow">OBSERVER PROFILE</div>
          <h1>Your AstroOS <span>identity.</span></h1>
          <p>
            Profile fields are returned by GET /api/v1/auth/me. Password hashes
            and tokens are never displayed.
          </p>
        </div>
        <BrandLogo size="panel" />
      </section>

      <div className="panel profile-panel">
        <dl className="profile-grid">
          <div>
            <dt>Name</dt>
            <dd>{user.full_name || "Not provided"}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{user.email}</dd>
          </div>
          <div>
            <dt>Role</dt>
            <dd>{user.role}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{user.is_active ? "Active" : "Inactive"}</dd>
          </div>
          <div>
            <dt>Account created</dt>
            <dd>{formatDateTime(user.created_at)}</dd>
          </div>
          <div>
            <dt>User ID</dt>
            <dd className="mono">{user.id}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
