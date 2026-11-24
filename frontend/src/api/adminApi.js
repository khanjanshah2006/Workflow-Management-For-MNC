import { apiClient } from "./client.js";

/**
 * Security Operations & Administration API Module (US-43, US-44, US-45, US-46, US-48, US-49)
 *
 * Provides typed methods for:
 * - User Administration:
 *   - List Users (GET /api/v1/admin/users)
 *   - Create User (POST /api/v1/admin/users)
 *   - Update User Status (PATCH /api/v1/admin/users/{id}/status)
 *   - Update User Role (PATCH /api/v1/admin/users/{id}/role)
 *   - Admin Password Reset (POST /api/v1/admin/users/{id}/reset-password)
 *   - Unlock Account (POST /api/v1/admin/users/{id}/unlock)
 * - System Parameters (GET /api/v1/admin/system-params, PUT /api/v1/admin/system-params/{key})
 * - Time-Bound Elevated Access (POST /api/v1/admin/elevated-access, GET /api/v1/admin/elevated-access/active,
 *   DELETE /api/v1/admin/elevated-access/{grant_id})
 * - Security Anomaly Alerts (GET /api/v1/admin/anomaly-alerts)
 */

export const adminApi = {
  /**
   * Fetch paginated user accounts with optional filtering (US-43).
   * Endpoint: GET /api/v1/admin/users
   * @param {{ page?: number, limit?: number, is_active?: boolean, user_type?: string, search?: string }} [params]
   * @returns {Promise<{ items: Array<Object>, total: number, page: number, limit: number, pages: number }>}
   */
  getUsers: async (params = {}) => {
    const queryObj = {
      page: String(params.page || 1),
      limit: String(params.limit || 20),
    };
    if (params.is_active !== undefined && params.is_active !== "") {
      queryObj.is_active = String(params.is_active);
    }
    if (params.user_type && params.user_type !== "ALL") {
      queryObj.user_type = String(params.user_type);
    }
    if (params.search && params.search.trim() !== "") {
      queryObj.search = params.search.trim();
    }

    const query = new URLSearchParams(queryObj).toString();
    const response = await apiClient.get(`/api/v1/admin/users?${query}`);

    // Standardize response structure for both paginated and list responses
    if (Array.isArray(response)) {
      return {
        items: response,
        total: response.length,
        page: params.page || 1,
        limit: params.limit || 20,
        pages: 1,
      };
    }
    return {
      items: response?.items || response?.data || [],
      total: response?.total ?? (response?.items?.length || 0),
      page: response?.page || params.page || 1,
      limit: response?.limit || params.limit || 20,
      pages: response?.pages || 1,
    };
  },

  /**
   * Create a new user account (US-43).
   * Endpoint: POST /api/v1/admin/users
   * @param {{ email: string, password?: string, user_type: string, full_name?: string }} payload
   * @returns {Promise<Object>} Created user account
   */
  createUser: async (payload) => {
    return await apiClient.post("/api/v1/admin/users", payload);
  },

  /**
   * Activate or deactivate a user account (US-43, US-48).
   * Endpoint: PATCH /api/v1/admin/users/{account_id}/status
   * @param {string} accountId User account ID
   * @param {boolean} isActive Target active status
   * @returns {Promise<Object>} Updated user account
   */
  updateUserStatus: async (accountId, isActive) => {
    return await apiClient.patch(`/api/v1/admin/users/${encodeURIComponent(accountId)}/status`, {
      is_active: isActive,
    });
  },

  /**
   * Assign a new role to a user account (US-44).
   * Endpoint: PATCH /api/v1/admin/users/{account_id}/role
   * @param {string} accountId User account ID
   * @param {string} userType Target user type / role
   * @returns {Promise<Object>} Updated user account
   */
  updateUserRole: async (accountId, userType) => {
    return await apiClient.patch(`/api/v1/admin/users/${encodeURIComponent(accountId)}/role`, {
      user_type: userType,
    });
  },

  /**
   * Admin triggered password reset (US-48).
   * Endpoint: POST /api/v1/admin/users/{account_id}/reset-password
   * @param {string} accountId User account ID
   * @param {string} newPassword New password string
   * @returns {Promise<Object>} Response confirmation
   */
  resetUserPassword: async (accountId, newPassword) => {
    return await apiClient.post(
      `/api/v1/admin/users/${encodeURIComponent(accountId)}/reset-password`,
      {
        new_password: newPassword,
      }
    );
  },

  /**
   * Fetch all operational system parameters (US-46).
   * Endpoint: GET /api/v1/admin/system-params
   */
  getSystemParams: async () => {
    const response = await apiClient.get("/api/v1/admin/system-params");
    return Array.isArray(response) ? response : [];
  },

  /**
   * Update an operational system parameter value (US-46).
   * Endpoint: PUT /api/v1/admin/system-params/{key}
   */
  updateSystemParam: async (key, value) => {
    const encodedKey = encodeURIComponent(key);
    return await apiClient.put(`/api/v1/admin/system-params/${encodedKey}`, {
      value: String(value),
    });
  },

  /**
   * Grant temporary elevated role privilege (US-45).
   * Endpoint: POST /api/v1/admin/elevated-access
   */
  grantElevatedAccess: async (payload) => {
    return await apiClient.post("/api/v1/admin/elevated-access", payload);
  },

  /**
   * Fetch all unexpired, unrevoked elevated access grants (US-45).
   * Endpoint: GET /api/v1/admin/elevated-access/active
   */
  getActiveElevatedGrants: async () => {
    const response = await apiClient.get("/api/v1/admin/elevated-access/active");
    return Array.isArray(response) ? response : [];
  },

  /**
   * Clear the failed-login lockout on an account (US-48).
   * Endpoint: POST /api/v1/admin/users/{account_id}/unlock
   * Rejects with ApiError status 409 when the account is not locked.
   * @param {string} accountId User account ID
   * @returns {Promise<Object>} Updated user account
   */
  unlockAccount: async (accountId) => {
    return await apiClient.post(`/api/v1/admin/users/${encodeURIComponent(accountId)}/unlock`);
  },

  /**
   * Revoke an active elevated access grant (US-45).
   * Endpoint: DELETE /api/v1/admin/elevated-access/{grant_id}
   * Rejects with ApiError status 409 when the grant is already revoked or expired.
   * @param {number|string} grantId
   * @returns {Promise<Object>} The revoked grant
   */
  revokeElevatedGrant: async (grantId) => {
    return await apiClient.delete(`/api/v1/admin/elevated-access/${encodeURIComponent(grantId)}`);
  },

  /**
   * Fetch real-time security anomaly alerts (US-49).
   */
  getAnomalyAlerts: async () => {
    const response = await apiClient.get("/api/v1/admin/anomaly-alerts");
    return Array.isArray(response) ? response : (response?.alerts || []);
  },
};

export default adminApi;
