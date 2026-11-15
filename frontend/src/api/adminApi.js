import { apiClient } from "./client";
import mockData from "../features/admin/mockData.json";

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
 * - System Parameters (GET /api/v1/admin/system-params, PUT /api/v1/admin/system-params/{key})
 * - Time-Bound Elevated Access (POST /api/v1/admin/elevated-access, GET /api/v1/admin/elevated-access/active)
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

    try {
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
    } catch (err) {
      if (err?.status === 0 && import.meta.env?.DEV) {
        let filtered = [...mockData.users];
        if (params.search) {
          const s = params.search.toLowerCase();
          filtered = filtered.filter(
            (u) => u.email?.toLowerCase().includes(s) || u.account_id?.toLowerCase().includes(s)
          );
        }
        if (params.user_type && params.user_type !== "ALL") {
          filtered = filtered.filter((u) => u.user_type === params.user_type);
        }
        if (params.is_active !== undefined && params.is_active !== "") {
          const activeBool = String(params.is_active) === "true";
          filtered = filtered.filter((u) => Boolean(u.is_active) === activeBool);
        }
        return {
          items: filtered,
          total: filtered.length,
          page: params.page || 1,
          limit: params.limit || 20,
          pages: Math.max(1, Math.ceil(filtered.length / (params.limit || 20))),
        };
      }
      throw err;
    }
  },

  /**
   * Create a new user account (US-43).
   * Endpoint: POST /api/v1/admin/users
   * @param {{ email: string, password?: string, user_type: string, full_name?: string }} payload
   * @returns {Promise<Object>} Created user account
   */
  createUser: async (payload) => {
    try {
      return await apiClient.post("/api/v1/admin/users", payload);
    } catch (err) {
      if (err?.status === 0 && import.meta.env?.DEV) {
        const newUser = {
          account_id: `usr-${Date.now().toString(36)}`,
          email: payload.email,
          user_type: payload.user_type || "EMPLOYEE",
          is_active: true,
          created_at: new Date().toISOString(),
        };
        mockData.users.unshift(newUser);
        return newUser;
      }
      throw err;
    }
  },

  /**
   * Activate or deactivate a user account (US-43, US-48).
   * Endpoint: PATCH /api/v1/admin/users/{account_id}/status
   * @param {string} accountId User account ID
   * @param {boolean} isActive Target active status
   * @returns {Promise<Object>} Updated user account
   */
  updateUserStatus: async (accountId, isActive) => {
    try {
      return await apiClient.patch(`/api/v1/admin/users/${encodeURIComponent(accountId)}/status`, {
        is_active: isActive,
      });
    } catch (err) {
      if (err?.status === 0 && import.meta.env?.DEV) {
        const target = mockData.users.find((u) => u.account_id === accountId);
        if (target) {
          target.is_active = isActive;
        }
        return { account_id: accountId, is_active: isActive };
      }
      throw err;
    }
  },

  /**
   * Assign a new role to a user account (US-44).
   * Endpoint: PATCH /api/v1/admin/users/{account_id}/role
   * @param {string} accountId User account ID
   * @param {string} userType Target user type / role
   * @returns {Promise<Object>} Updated user account
   */
  updateUserRole: async (accountId, userType) => {
    try {
      return await apiClient.patch(`/api/v1/admin/users/${encodeURIComponent(accountId)}/role`, {
        user_type: userType,
      });
    } catch (err) {
      if (err?.status === 0 && import.meta.env?.DEV) {
        const target = mockData.users.find((u) => u.account_id === accountId);
        if (target) {
          target.user_type = userType;
        }
        return { account_id: accountId, user_type: userType };
      }
      throw err;
    }
  },

  /**
   * Admin triggered password reset (US-48).
   * Endpoint: POST /api/v1/admin/users/{account_id}/reset-password
   * @param {string} accountId User account ID
   * @param {string} newPassword New password string
   * @returns {Promise<Object>} Response confirmation
   */
  resetUserPassword: async (accountId, newPassword) => {
    try {
      return await apiClient.post(
        `/api/v1/admin/users/${encodeURIComponent(accountId)}/reset-password`,
        {
          new_password: newPassword,
        }
      );
    } catch (err) {
      if (err?.status === 0 && import.meta.env?.DEV) {
        return {
          message: "Password reset successful (DEV simulation)",
          account_id: accountId,
        };
      }
      throw err;
    }
  },

  /**
   * Fetch all operational system parameters (US-46).
   * Endpoint: GET /api/v1/admin/system-params
   */
  getSystemParams: async () => {
    try {
      const response = await apiClient.get("/api/v1/admin/system-params");
      return Array.isArray(response) ? response : [];
    } catch (err) {
      if (err?.status === 0 && import.meta.env?.DEV) {
        console.warn("Backend system-params unreachable; using mockData fallback in DEV mode:", err.message);
        return mockData.systemParams;
      }
      throw err;
    }
  },

  /**
   * Update an operational system parameter value (US-46).
   * Endpoint: PUT /api/v1/admin/system-params/{key}
   */
  updateSystemParam: async (key, value) => {
    const encodedKey = encodeURIComponent(key);
    try {
      return await apiClient.put(`/api/v1/admin/system-params/${encodedKey}`, {
        value: String(value),
      });
    } catch (err) {
      if (err?.status === 0 && import.meta.env?.DEV) {
        console.warn(`Backend update system-param '${key}' unreachable; mocking successful update in DEV mode`);
        return {
          key,
          value: String(value),
          value_type: "string",
          updated_at: new Date().toISOString(),
        };
      }
      throw err;
    }
  },

  /**
   * Grant temporary elevated role privilege (US-45).
   * Endpoint: POST /api/v1/admin/elevated-access
   */
  grantElevatedAccess: async (payload) => {
    try {
      return await apiClient.post("/api/v1/admin/elevated-access", payload);
    } catch (err) {
      if (err?.status === 0 && import.meta.env?.DEV) {
        console.warn("Backend elevated-access unreachable; mocking successful grant in DEV mode:", payload);
        return {
          id: Date.now(),
          ...payload,
          granted_at: new Date().toISOString(),
          revoked_at: null,
        };
      }
      throw err;
    }
  },

  /**
   * Fetch all unexpired, unrevoked elevated access grants (US-45).
   * Endpoint: GET /api/v1/admin/elevated-access/active
   */
  getActiveElevatedGrants: async () => {
    try {
      const response = await apiClient.get("/api/v1/admin/elevated-access/active");
      return Array.isArray(response) ? response : [];
    } catch (err) {
      if (err?.status === 0 && import.meta.env?.DEV) {
        console.warn("Backend active elevated grants unreachable; using mockData in DEV mode:", err.message);
        return mockData.activeGrants;
      }
      throw err;
    }
  },

  /**
   * Revoke an active elevated access grant.
   */
  revokeElevatedGrant: async (grantId) => {
    try {
      return await apiClient.delete(`/api/v1/admin/elevated-access/${encodeURIComponent(grantId)}`);
    } catch (err) {
      if (err?.status === 404 || err?.status === 405) {
        throw new Error(
          "Backend revoke endpoint (DELETE /api/v1/admin/elevated-access/:id) is not yet exposed by the backend router. Manual grant revocation requires backend Wave 2 implementation."
        );
      }
      throw new Error(
        err?.message || "Failed to revoke elevated access grant. Backend endpoint unavailable."
      );
    }
  },

  /**
   * Fetch real-time security anomaly alerts (US-49).
   */
  getAnomalyAlerts: async () => {
    try {
      const response = await apiClient.get("/api/v1/admin/anomaly-alerts");
      return Array.isArray(response) ? response : [];
    } catch (err) {
      if (import.meta.env?.DEV && (err?.status === 404 || err?.status === 0)) {
        console.warn("Backend anomaly-alerts unavailable (404/offline); using dev mock data:", err.message);
        return mockData.anomalyAlerts;
      }
      throw err;
    }
  },
};

export default adminApi;
