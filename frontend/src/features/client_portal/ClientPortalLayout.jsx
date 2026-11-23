import React from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import NotificationBell from "../../components/common/NotificationBell";
import { ROUTES } from "../../routes";
import "./clientPortal.css";

/**
 * ClientPortalLayout (US-20, US-21, US-22, US-41)
 *
 * Dedicated minimal application shell for external CLIENT users.
 * Isolated from internal company dashboards, team allocations, and internal routes.
 */
export default function ClientPortalLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      navigate("/login", { replace: true });
    }
  };

  const displayName = user?.full_name || user?.email || "Client User";
  const companyName = user?.company_name || user?.organization || "Contracted Client";

  return (
    <div className="client-portal-layout">
      {/* Minimal Top Bar Navigation */}
      <header className="client-navbar" role="banner">
        <div className="client-navbar-left">
          <Link to="/client/projects" className="client-brand" aria-label="WorkSphere Client Portal">
            <div className="client-brand-logo">W</div>
            <span>WorkSphere</span>
          </Link>

          <span className="client-company-badge" title="Contracted Client Organization">
            🏢 {companyName}
          </span>

          <nav className="client-nav-links" aria-label="Client Portal Navigation">
            <NavLink
              to="/client/projects"
              className={({ isActive }) =>
                `client-nav-item ${isActive ? "active" : ""}`
              }
            >
              My Projects
            </NavLink>
          </nav>
        </div>

        <div className="client-navbar-right">
          <NotificationBell />

          <div className="client-user-info">
            <div className="client-user-avatar" title={displayName}>
              {displayName.charAt(0).toUpperCase()}
            </div>
          </div>

          <Link
            to={ROUTES.ACCOUNT_SECURITY}
            className="account-security-link"
            title="Account security and MFA"
          >
            Security
          </Link>

          <button
            type="button"
            onClick={handleLogout}
            className="client-logout-btn"
            aria-label="Sign out of client portal"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="client-main-content" role="main">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="client-footer">
        <span>© {new Date().getFullYear()} WorkSphere — Client Delivery Portal</span>
      </footer>
    </div>
  );
}
