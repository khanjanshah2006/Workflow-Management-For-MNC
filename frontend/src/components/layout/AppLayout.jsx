import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import NotificationBell from "../common/NotificationBell";
import { useAuth } from "../../context/AuthContext";

const navigation = [
  { path: "/dashboard", label: "Dashboard", icon: "▦" },
  { path: "/projects", label: "Projects", icon: "◇" },
  { path: "/team", label: "Team Roster", icon: "👥" },
  { path: "/tasks", label: "Tasks", icon: "✓" },
  { path: "/support", label: "IT Support", icon: "🛠" },
  { path: "/profile", label: "My Profile", icon: "○" },
];

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, role, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const currentPage =
    navigation.find((item) => item.path === location.pathname)?.label ??
    (location.pathname.startsWith("/team")
      ? "Team Roster"
      : location.pathname.startsWith("/projects")
      ? "Projects"
      : location.pathname.startsWith("/support") || location.pathname.startsWith("/it-support")
      ? "IT Support"
      : "Dashboard");

  return (
    <div
      className={`app-shell ${collapsed ? "sidebar-collapsed" : ""} ${
        mobileOpen ? "mobile-nav-open" : ""
      }`}
    >
      {mobileOpen && (
        <button
          className="mobile-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">W</div>
          <span className="brand-name">WorkSphere</span>
          <button
            className="collapse-button"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? "→" : "←"}
          </button>
        </div>

        <div className="workspace-label">WORKSPACE</div>

        <nav className="navigation" aria-label="Main navigation">
          {navigation.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                `nav-link ${isActive ? "nav-link-active" : ""}`
              }
              onClick={() => setMobileOpen(false)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="help-card">
            <div className="help-dot">i</div>
            <div className="help-copy">
              <strong>Need help?</strong>
              <span>Contact your administrator</span>
            </div>
          </div>
          <div className="sidebar-version">WorkSphere · UI foundation</div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <button
            className="mobile-menu-button"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
          >
            ☰
          </button>

          <div className="breadcrumb">
            <span>Workspace</span>
            <span className="breadcrumb-separator">/</span>
            <strong>{currentPage}</strong>
          </div>

          <div className="topbar-right">
            <span className="environment-label">Development</span>
            {user && (
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "12px", fontWeight: "600", color: "#334155" }}>
                  {user.full_name || user.email}
                </span>
                <span
                  style={{
                    fontSize: "11px",
                    background: "#e0e7ff",
                    color: "#3730a3",
                    padding: "2px 6px",
                    borderRadius: "4px",
                    fontWeight: "600",
                  }}
                >
                  {role || "User"}
                </span>
                <button
                  onClick={handleLogout}
                  style={{
                    background: "#fee2e2",
                    color: "#991b1b",
                    border: "1px solid #fecaca",
                    borderRadius: "6px",
                    padding: "4px 8px",
                    fontSize: "12px",
                    fontWeight: "600",
                    cursor: "pointer",
                  }}
                >
                  Logout
                </button>
              </div>
            )}
            <NotificationBell />
            <div className="user-avatar" title={user?.full_name || "Demo profile"}>
              {user?.full_name
                ? user.full_name.charAt(0).toUpperCase()
                : user?.email
                ? user.email.charAt(0).toUpperCase()
                : "U"}
            </div>
          </div>
        </header>

        <main className="main-content">
          <Outlet />
        </main>

        <footer className="app-footer">
          <span>WorkSphere</span>
          <span>Enterprise Workflow Management</span>
        </footer>
      </div>
    </div>
  );
}
