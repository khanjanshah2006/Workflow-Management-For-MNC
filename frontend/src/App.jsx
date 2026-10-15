import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  NavLink,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import AppLayout from "./components/layout/AppLayout";
import "./App.css";

const queryClient = new QueryClient();

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
