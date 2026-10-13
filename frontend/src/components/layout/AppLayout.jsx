import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import NotificationBell from "../common/NotificationBell";

const navigation = [
  { path: "/dashboard", label: "Dashboard", icon: "▦" },
  { path: "/projects", label: "Projects", icon: "◇" },
  { path: "/tasks", label: "Tasks", icon: "✓" },
  { path: "/profile", label: "My Profile", icon: "○" },
];

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  const currentPage =
    navigation.find((item) => item.path === location.pathname)?.label ??
    "Dashboard";

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
            <NotificationBell />
            <div className="user-avatar" title="Demo profile">
              U
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
