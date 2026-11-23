import { apiClient, setStoredToken, clearSession } from "./client.js";

export const authApi = {
  /**
   * Authenticate with email & password.
   * Calls POST /api/v1/auth/login.
   */
  login: async (credentials) => {
    return await apiClient.post("/api/v1/auth/login", {
      email: credentials.email,
      password: credentials.password,
    });
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
