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
