import { apiClient, setStoredToken, clearSession } from "./client.js";

/**
 * Builds request options that authenticate with an explicit bearer token
 * (e.g. the short-lived mfa_setup token) instead of the stored access token.
 * Such requests never trigger a silent refresh.
 * @param {string|null|undefined} bearerToken
 */
function withBearer(bearerToken) {
  if (!bearerToken) return {};
  return {
    headers: { Authorization: `Bearer ${bearerToken}` },
    skipRefresh: true,
  };
}

export const authApi = {
  /**
   * Authenticate with email & password.
   * Calls POST /api/v1/auth/login.
   * May resolve with { mfa_required | mfa_setup_required, mfa_token } instead of tokens.
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
   * Completes a sign-in that requires a TOTP code (US-31).
   * Calls POST /api/v1/auth/mfa/login with the pending mfa_token.
   * @param {string} mfaToken
   * @param {string} code 6-digit TOTP code
   */
  mfaLogin: async (mfaToken, code) => {
    return await apiClient.post("/api/v1/auth/mfa/login", {
      mfa_token: mfaToken,
      code,
    });
  },

  /**
   * Starts MFA enrolment and returns { secret, provisioning_uri, current_otp? } (US-31).
   * Calls POST /api/v1/auth/mfa/setup. Pass the mfa_setup token for forced enrolment;
   * omit it to enrol the signed-in user with their access token.
   * @param {string} [bearerToken]
   */
  mfaSetup: async (bearerToken) => {
    return await apiClient.post("/api/v1/auth/mfa/setup", undefined, withBearer(bearerToken));
  },

  /**
   * Confirms enrolment with a 6-digit code (US-31).
   * Calls POST /api/v1/auth/mfa/verify. With an mfa_setup token the response also
   * carries access/refresh tokens and completes the sign-in.
   * @param {string} code
   * @param {string} [bearerToken]
   */
  mfaVerify: async (code, bearerToken) => {
    return await apiClient.post("/api/v1/auth/mfa/verify", { code }, withBearer(bearerToken));
  },

  /**
   * Returns { is_mfa_enabled, email } for the signed-in user.
   * Queries GET /api/v1/auth/mfa/status.
   */
  getMfaStatus: async () => {
    return await apiClient.get("/api/v1/auth/mfa/status");
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
