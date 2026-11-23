/**
/**
 * Shared Route Constants (Wave 4)
 * Centralizes all frontend application routes across scenarios S1–S9.
 */
export const ROUTES = Object.freeze({
  LOGIN: "/login",
  DASHBOARD: "/dashboard",
  PROJECTS: "/projects",
  PROJECT_DETAIL: "/projects/:projectId",
  PM_RISK_DASHBOARD: "/pm/risk-dashboard",
  TEAM_ROSTER: "/team",
  MY_TASKS: "/tasks",
  TEAM_LEAD_TASKS: "/team-lead/tasks",
  TEAM_TASKS_ALIAS: "/tasks/team",
  LEAVE: "/leave",
  TEAM_LEAD_LEAVE: "/team-lead/leave",
  HR_LEAVE_POLICIES: "/hr/leave-policies",
  HR_TEAMS: "/hr/teams",
  SKILL_REQUESTS: "/skill-requests",
  IT_SUPPORT: "/it-support",
  SUPPORT: "/support",
  SUPPORT_TICKETS: "/support/tickets",
  PROFILE: "/profile",
  ADMIN: "/admin",
  ADMIN_USERS: "/admin/users",
  ADMIN_SECURITY: "/admin/security",
  ACCOUNT_SECURITY: "/account/security",
  NOTIFICATIONS: "/notifications",
  EXECUTIVE: "/executive",
  EXECUTIVE_CONSOLE: "/executive/console",
  CLIENT: "/client",
  CLIENT_PROJECTS: "/client/projects",
});

export default ROUTES;
