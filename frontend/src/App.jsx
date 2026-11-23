import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
  Outlet,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ProtectedRoute from "./components/common/ProtectedRoute";
import ToastProvider from "./components/common/Toast";
import LoginPage from "./features/auth/LoginPage";
import AppLayout from "./components/layout/AppLayout";
import ProjectListPage from "./features/projects/ProjectListPage";
import ProjectDetailPage from "./features/projects/ProjectDetailPage";
import TeamRosterPage from "./features/team/TeamRosterPage";
import SecurityOpsPage from "./features/admin/SecurityOpsPage";
import UserManagementPage from "./features/admin/UserManagementPage";
import ProfilePage from "./features/profile/ProfilePage";
import ITSupportDashboard from "./features/support/ITSupportDashboard";
import MyTasksPage from "./features/tasks/MyTasksPage";
import TeamLeadTaskWorkspace from "./features/team_lead/TeamLeadTaskWorkspace";
import TeamLeaveTriagePage from "./features/team_lead/TeamLeaveTriagePage";
import LeaveDashboardPage from "./features/leave/LeaveDashboardPage";
import LeavePolicyAdminPage from "./features/hr/LeavePolicyAdminPage";
import PMRiskDashboardPage from "./features/project_manager/PMRiskDashboardPage";
import ExecutiveConsolePage from "./features/executive/ExecutiveConsolePage";
import {
  ROLES,
  INTERNAL_ROLES,
  PLATFORM_ADMINS,
  IT_STAFF,
  getHomeRouteForRole,
} from "./auth/session";
import "./App.css";

const queryClient = new QueryClient();

function RootRedirect() {
  const { isAuthenticated, role, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: "60vh" }}>
        <div style={{ textAlign: "center" }}>
          <div className="placeholder-symbol" style={{ fontSize: "2rem" }}>✳</div>
          <p style={{ marginTop: "12px", color: "#64748b", fontSize: "14px", fontWeight: "500" }}>
            Verifying authentication...
          </p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const requestedFrom = location.state?.from?.pathname || location.state?.from;
  const targetPath =
    requestedFrom && requestedFrom !== "/" && requestedFrom !== "/login"
      ? requestedFrom
      : getHomeRouteForRole(role);

  return <Navigate to={targetPath} replace />;
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
        <AuthProvider>
          <ToastProvider>
            <Routes>
              {/* Public Login Route */}
              <Route path="/login" element={<LoginPage />} />

              {/* Root route: role-based home redirection */}
              <Route path="/" element={<RootRedirect />} />

              {/* Client Portal Route Tree (strictly outside internal AppLayout shell) */}
              {/* S6-FE-1 integration slot: Client Deliverables & Feedback */}
              <Route
                path="/client"
                element={
                  <ProtectedRoute allowedRoles={[ROLES.CLIENT]}>
                    <Outlet />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Navigate to="/client/projects" replace />} />
                <Route
                  path="projects"
                  element={
                    <PagePlaceholder
                      title="Client Projects"
                      description="Client portal workspace for deliverables and project tracking."
                    />
                  }
                />
                <Route path="*" element={<Navigate to="/client/projects" replace />} />
              </Route>

              {/* Guarded Internal Application Shell: requires internal role */}
              <Route
                element={
                  <ProtectedRoute allowedRoles={INTERNAL_ROLES}>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                {/* W3-FE-0 Foundation routes */}
                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute allowedRoles={INTERNAL_ROLES}>
                      <PagePlaceholder
                        title="Dashboard"
                        description="Welcome to your WorkSphere workspace."
                      />
                    </ProtectedRoute>
                  }
                />

                {/* Projects: Guarded & role permitted */}
                <Route
                  path="/projects"
                  element={
                    <ProtectedRoute allowedRoles={[ROLES.PM, ROLES.ADMIN]}>
                      <ProjectListPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/projects/:projectId"
                  element={
                    <ProtectedRoute allowedRoles={[ROLES.PM, ROLES.ADMIN]}>
                      <ProjectDetailPage />
                    </ProtectedRoute>
                  }
                />

                {/* Team Roster: Guarded for internal roles */}
                <Route
                  path="/team"
                  element={
                    <ProtectedRoute allowedRoles={INTERNAL_ROLES}>
                      <TeamRosterPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/team/roster"
                  element={
                    <ProtectedRoute allowedRoles={INTERNAL_ROLES}>
                      <TeamRosterPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/teams/:teamId/roster"
                  element={
                    <ProtectedRoute allowedRoles={INTERNAL_ROLES}>
                      <TeamRosterPage />
                    </ProtectedRoute>
                  }
                />

                {/* S1-FE-2 routes */}
                {/* S1-FE-3 routes */}

                {/* Tasks: Guarded for internal roles */}
                <Route
                  path="/tasks"
                  element={
                    <ProtectedRoute allowedRoles={INTERNAL_ROLES}>
                      <MyTasksPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/team-lead/tasks"
                  element={
                    <ProtectedRoute allowedRoles={[ROLES.TEAM_LEAD, ROLES.PM, ROLES.ADMIN]}>
                      <TeamLeadTaskWorkspace />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tasks/team"
                  element={
                    <ProtectedRoute allowedRoles={[ROLES.TEAM_LEAD, ROLES.PM, ROLES.ADMIN]}>
                      <TeamLeadTaskWorkspace />
                    </ProtectedRoute>
                  }
                />

                {/* Support: Guarded for IT staff */}
                <Route
                  path="/support"
                  element={
                    <ProtectedRoute allowedRoles={IT_STAFF}>
                      <ITSupportDashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/support/tickets"
                  element={
                    <ProtectedRoute allowedRoles={IT_STAFF}>
                      <ITSupportDashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/it-support"
                  element={
                    <ProtectedRoute allowedRoles={IT_STAFF}>
                      <ITSupportDashboard />
                    </ProtectedRoute>
                  }
                />

                {/* S8-FE-3 routes */}

                {/* Profile: Guarded for internal roles */}
                <Route
                  path="/profile"
                  element={
                    <ProtectedRoute allowedRoles={INTERNAL_ROLES}>
                      <ProfilePage />
                    </ProtectedRoute>
                  }
                />

                {/* S2-FE-2 routes */}
                {/* S3-FE-5 routes */}

                {/* Admin: Guarded & role permitted */}
                <Route
                  path="/admin"
                  element={
                    <ProtectedRoute allowedRoles={PLATFORM_ADMINS}>
                      <Navigate to="/admin/users" replace />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin/users"
                  element={
                    <ProtectedRoute allowedRoles={PLATFORM_ADMINS}>
                      <UserManagementPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin/security"
                  element={
                    <ProtectedRoute allowedRoles={PLATFORM_ADMINS}>
                      <SecurityOpsPage />
                    </ProtectedRoute>
                  }
                />

                {/* S9-FE-2 routes */}

                {/* S4-FE-1 routes (Employee Leave Application & History: /leave) */}
                <Route
                  path="/leave"
                  element={
                    <ProtectedRoute allowedRoles={[ROLES.EMPLOYEE, ROLES.TEAM_LEAD]}>
                      <LeaveDashboardPage />
                    </ProtectedRoute>
                  }
                />
                {/* S4-FE-2 routes (Team Lead Leave Triage & Conflict Calendar: /team-lead/leave) */}
                <Route
                  path="/team-lead/leave"
                  element={
                    <ProtectedRoute allowedRoles={[ROLES.TEAM_LEAD, ROLES.HR, ROLES.ADMIN]}>
                      <TeamLeaveTriagePage />
                    </ProtectedRoute>
                  }
                />
                {/* S4-FE-3 routes (HR Leave Policy & Quota Admin: /hr/leave-policies) */}
                <Route
                  path="/hr/leave-policies"
                  element={
                    <ProtectedRoute allowedRoles={[ROLES.HR, ROLES.ADMIN]}>
                      <LeavePolicyAdminPage />
                    </ProtectedRoute>
                  }
                />
                {/* S5-FE-1 routes (PM Risk & Delivery Dashboard: /pm/risk-dashboard) */}
                <Route
                  path="/pm/risk-dashboard"
                  element={
                    <ProtectedRoute allowedRoles={[ROLES.PM, ROLES.ADMIN]}>
                      <PMRiskDashboardPage />
                    </ProtectedRoute>
                  }
                />

                {/* Executive: Guarded & MNC_EXECUTIVE, ADMIN, SYSTEM_ADMIN permitted */}
                {/* S7-FE-1 routes (MNC Executive Dashboard & Export: /executive/console) */}
                <Route
                  path="/executive"
                  element={
                    <ProtectedRoute allowedRoles={[ROLES.MNC_EXECUTIVE, ROLES.ADMIN, ROLES.SYSTEM_ADMIN]}>
                      <Navigate to="/executive/console" replace />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/executive/console"
                  element={
                    <ProtectedRoute allowedRoles={[ROLES.MNC_EXECUTIVE, ROLES.ADMIN, ROLES.SYSTEM_ADMIN]}>
                      <ExecutiveConsolePage />
                    </ProtectedRoute>
                  }
                />

                <Route path="*" element={<NotFound />} />
              </Route>
            </Routes>
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
