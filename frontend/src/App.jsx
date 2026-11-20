import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/common/ProtectedRoute";
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
          <Routes>
            {/* Public Login Route */}
            <Route path="/login" element={<LoginPage />} />

            {/* Guarded Application Shell: redirects to /login if unauthenticated */}
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
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

              {/* Projects: Guarded & role permitted */}
              <Route
                path="/projects"
                element={
                  <ProtectedRoute allowedRoles={["PROJECT_MANAGER", "PM", "SYSTEM_ADMIN", "ADMIN"]}>
                    <ProjectListPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/projects/:projectId"
                element={
                  <ProtectedRoute allowedRoles={["PROJECT_MANAGER", "PM", "SYSTEM_ADMIN", "ADMIN"]}>
                    <ProjectDetailPage />
                  </ProtectedRoute>
                }
              />

              <Route path="/team" element={<TeamRosterPage />} />
              <Route path="/team/roster" element={<TeamRosterPage />} />
              <Route path="/teams/:teamId/roster" element={<TeamRosterPage />} />
              <Route path="/tasks" element={<MyTasksPage />} />
              <Route
                path="/team-lead/tasks"
                element={
                  <ProtectedRoute allowedRoles={["TEAM_LEAD", "PM", "PROJECT_MANAGER", "SYSTEM_ADMIN", "ADMIN"]}>
                    <TeamLeadTaskWorkspace />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/team-lead/leave"
                element={
                  <ProtectedRoute allowedRoles={["TEAM_LEAD", "HR", "ADMIN"]}>
                    <TeamLeaveTriagePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/tasks/team"
                element={
                  <ProtectedRoute allowedRoles={["TEAM_LEAD", "PM", "PROJECT_MANAGER", "SYSTEM_ADMIN", "ADMIN"]}>
                    <TeamLeadTaskWorkspace />
                  </ProtectedRoute>
                }
              />
              <Route path="/support" element={<ITSupportDashboard />} />
              <Route path="/support/tickets" element={<ITSupportDashboard />} />
              <Route path="/it-support" element={<ITSupportDashboard />} />
              <Route path="/profile" element={<ProfilePage />} />

              {/* Admin: Guarded & role permitted */}
              <Route
                path="/admin"
                element={
                  <ProtectedRoute allowedRoles={["SYSTEM_ADMIN", "ADMIN"]}>
                    <Navigate to="/admin/users" replace />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/users"
                element={
                  <ProtectedRoute allowedRoles={["SYSTEM_ADMIN", "ADMIN"]}>
                    <UserManagementPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/security"
                element={
                  <ProtectedRoute allowedRoles={["SYSTEM_ADMIN", "ADMIN"]}>
                    <SecurityOpsPage />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
