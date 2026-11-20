import { apiClient, setStoredToken } from "./client";
import { clearSession } from "../auth/session";

export const DEMO_USERS = {
  "admin@worksphere.com": {
    account_id: "usr-admin-01",
    email: "admin@worksphere.com",
    user_type: "SYSTEM_ADMIN",
    role: "SYSTEM_ADMIN",
    full_name: "System Administrator",
    is_active: true,
  },
  "pm@worksphere.com": {
    account_id: "usr-pm-01",
    email: "pm@worksphere.com",
    user_type: "PROJECT_MANAGER",
    role: "PROJECT_MANAGER",
    full_name: "David Miller (PM)",
    is_active: true,
  },
  "employee@worksphere.com": {
    account_id: "usr-emp-01",
    email: "employee@worksphere.com",
    user_type: "EMPLOYEE",
    role: "EMPLOYEE",
    full_name: "Sarah Connor",
    is_active: true,
  },
  "hr@worksphere.com": {
    account_id: "usr-hr-01",
    email: "hr@worksphere.com",
    user_type: "HR",
    role: "HR",
    full_name: "Elena Rostova",
    is_active: true,
  },
  "client@worksphere.com": {
    account_id: "usr-client-01",
    email: "client@worksphere.com",
    user_type: "CLIENT",
    role: "CLIENT",
    full_name: "Robert Vance",
    is_active: true,
  },
  // Wave 3 Demo Accounts (backend/scripts/seed_wave3_demo.py)
  "john.teamlead@company.com": {
    account_id: "usr-w3-tl-01",
    email: "john.teamlead@company.com",
    user_type: "TEAM_LEAD",
    role: "TEAM_LEAD",
    full_name: "John Doe",
    emp_code: "W3-EMP-001",
    designation: "Team Lead",
    is_active: true,
  },
  "sarah.connor@company.com": {
    account_id: "usr-w3-emp-01",
    email: "sarah.connor@company.com",
    user_type: "EMPLOYEE",
    role: "EMPLOYEE",
    full_name: "Sarah Connor",
    emp_code: "W3-EMP-002",
    designation: "Software Engineer",
    is_active: true,
  },
  "john.matrix@company.com": {
    account_id: "usr-w3-emp-02",
    email: "john.matrix@company.com",
    user_type: "EMPLOYEE",
    role: "EMPLOYEE",
    full_name: "John Matrix",
    emp_code: "W3-EMP-003",
    designation: "Software Engineer",
    is_active: true,
  },
  "kyle.reese@company.com": {
    account_id: "usr-w3-emp-03",
    email: "kyle.reese@company.com",
    user_type: "EMPLOYEE",
    role: "EMPLOYEE",
    full_name: "Kyle Reese",
    emp_code: "W3-EMP-004",
    designation: "QA Engineer",
    is_active: true,
  },
  "pm@company.com": {
    account_id: "usr-w3-pm-01",
    email: "pm@company.com",
    user_type: "PM",
    role: "PM",
    full_name: "Priya Menon",
    emp_code: "W3-PM-001",
    is_active: true,
  },
  "hr@company.com": {
    account_id: "usr-w3-hr-01",
    email: "hr@company.com",
    user_type: "HR",
    role: "HR",
    full_name: "Helen Ross",
    emp_code: "W3-HR-001",
    is_active: true,
  },
  "executive@company.com": {
    account_id: "usr-w3-exec-01",
    email: "executive@company.com",
    user_type: "MNC_EXECUTIVE",
    role: "MNC_EXECUTIVE",
    full_name: "MNC Executive",
    is_active: true,
  },
  "client@acme.com": {
    account_id: "usr-w3-client-01",
    email: "client@acme.com",
    user_type: "CLIENT",
    role: "CLIENT",
    full_name: "Alice Carter",
    company_name: "Acme Corp",
    is_active: true,
  },
};

export const authApi = {
  /**
   * Authenticate with email & password.
   * Calls POST /api/v1/auth/login.
   */
  login: async (credentials) => {
    try {
      const response = await apiClient.post("/api/v1/auth/login", {
        email: credentials.email,
        password: credentials.password,
      });
      return response;
    } catch (err) {
      // In DEV / offline environment, provide instant demo authentication fallback
      const key = credentials?.email?.toLowerCase();
      const demo = DEMO_USERS[key];
      if (demo && (err?.status === 0 || err?.status === 404 || import.meta.env?.DEV)) {
        return {
          access_token: `demo-jwt-token-${demo.account_id}`,
          refresh_token: `demo-refresh-token-${demo.account_id}`,
          token_type: "bearer",
          expires_in: 3600,
          user: demo,
        };
      }
      throw err;
    }
  },

  /**
   * Retrieves verified current user data.
   * Queries GET /api/v1/auth/me.
   */
  getMe: async () => {
    return await apiClient.get("/api/v1/auth/me");
  },

  /**
   * Logs out the current session.
   * Calls POST /api/v1/auth/logout.
   */
  logout: async () => {
    try {
      await apiClient.post("/api/v1/auth/logout");
    } catch {
      // Ignore network errors during logout
    } finally {
      clearSession();
      setStoredToken("");
      if (typeof localStorage !== "undefined") {
        localStorage.removeItem("wms_user");
      }
    }
  },
};

export default authApi;
