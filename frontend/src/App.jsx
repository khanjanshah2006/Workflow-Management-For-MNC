
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  NavLink,
  Outlet,
  useLocation,
} from "react-router-dom";
import { useState } from "react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import "./App.css";

const queryClient = new QueryClient();

const navigation = [
  { path: "/dashboard", label: "Dashboard", icon: "▦" },
  { path: "/projects", label: "Projects", icon: "◇" },
  { path: "/tasks", label: "Tasks", icon: "✓" },
  { path: "/profile", label: "My Profile", icon: "○" },
];

function AppLayout() {
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

function PagePlaceholder({ title, description }) {
  return (
    <section className="page">
      <div className="page-eyebrow">WORKSPACE</div>
      <h1>{title}</h1>
      <p className="page-description">{description}</p>

      <div className="placeholder-panel">
        <div className="placeholder-symbol">✳</div>
        <h2>{title} page</h2>
        <p>
          The shared layout and routing are ready. Feature-specific content
          will be added in the relevant development task.
        </p>
        <span className="status-label">Foundation in progress</span>
      </div>
    </section>
  );
}

function LoginPlaceholder() {
  return (
    <div className="login-placeholder">
      <div className="brand-mark login-brand-mark">W</div>
      <p className="page-eyebrow">WORKSPHERE</p>
      <h1>Login page placeholder</h1>
      <p>
        The shared application foundation is ready. Login UI will be
        implemented in the authentication issue.
      </p>
      <NavLink className="back-link" to="/dashboard">
        View dashboard foundation →
      </NavLink>
    </div>
  );
}

function NotFound() {
  return (
    <PagePlaceholder
      title="Page not found"
      description="The requested route does not exist."
    />
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPlaceholder />} />
          <Route element={<AppLayout />}>
            <Route
              path="/"
              element={<Navigate to="/dashboard" replace />}
            />
            <Route
              path="/dashboard"
              element={
                <PagePlaceholder
                  title="Dashboard"
                  description="Welcome to your WorkSphere workspace."
                />
              }
            />
            <Route
              path="/projects"
              element={
                <PagePlaceholder
                  title="Projects"
                  description="Your project workspace will appear here."
                />
              }
            />
            <Route
              path="/tasks"
              element={
                <PagePlaceholder
                  title="Tasks"
                  description="Your task workspace will appear here."
                />
              }
            />
            <Route
              path="/profile"
              element={
                <PagePlaceholder
                  title="My Profile"
                  description="Your profile information will appear here."
                />
              }
            />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
