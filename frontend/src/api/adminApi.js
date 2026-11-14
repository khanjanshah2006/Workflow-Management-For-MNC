import { apiClient } from "./client";
import mockData from "../features/admin/mockData.json";

/**
 * Security Operations & Administration API Module (US-45, US-46, US-49 / Issue #81)
 *
 * Provides typed methods for:
 * - System Parameters (GET /api/v1/admin/system-params, PUT /api/v1/admin/system-params/{key})
 * - Time-Bound Elevated Access (POST /api/v1/admin/elevated-access, GET /api/v1/admin/elevated-access/active)
 * - User Account Directory (GET /api/v1/admin/users)
 * - Security Anomaly Alerts (GET /api/v1/admin/anomaly-alerts)
 */

export const adminApi = {
  /**
   * Fetch all operational system parameters (US-46).
   * Endpoint: GET /api/v1/admin/system-params
   * @returns {Promise<Array<{key: string, value: string, value_type: string, description?: string, updated_at: string, updated_by?: string}>>}
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
   * @param {string} key Parameter key name (e.g. 'session_timeout_minutes')
   * @param {string|number|boolean} value Parameter value
   * @returns {Promise<Object>} Updated SystemParameterResponse
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
   * Alias for updating system parameters to support varied call signatures.
   */
  updateSystemParams: async (keyOrPayload, maybeValue) => {
    if (typeof keyOrPayload === "string") {
      return adminApi.updateSystemParam(keyOrPayload, maybeValue);
    }
    if (keyOrPayload?.key && keyOrPayload?.value !== undefined) {
      return adminApi.updateSystemParam(keyOrPayload.key, keyOrPayload.value);
    }
    throw new Error("Invalid parameters provided for updateSystemParams");
  },

  /**
   * Fetch user accounts to populate the target user selection (US-43).
   * Endpoint: GET /api/v1/admin/users
   * @param {{ page?: number, limit?: number, is_active?: boolean, search?: string }} [params]
   * @returns {Promise<{ items: Array<Object>, total: number }>}
   */
  getUsers: async (params = {}) => {
    const query = new URLSearchParams({
      page: String(params.page || 1),
      limit: String(params.limit || 50),
      ...(params.is_active !== undefined ? { is_active: String(params.is_active) } : {}),
      ...(params.search ? { search: params.search } : {}),
    }).toString();

    try {
      const response = await apiClient.get(`/api/v1/admin/users?${query}`);
      return response;
    } catch (err) {
      if (err?.status === 0 && import.meta.env?.DEV) {
        return { items: mockData.users, total: mockData.users.length };
      }
      throw err;
    }
  },

  /**
   * Grant temporary elevated role privilege (US-45).
   * Endpoint: POST /api/v1/admin/elevated-access
   * @param {{ user_id: string, granted_role: string, expires_at: string, reason: string }} payload
   * @returns {Promise<Object>} Created ElevatedAccessGrantResponse
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
   * @returns {Promise<Array<Object>>} List of active elevated access grants
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
   * Attempt to revoke an active elevated access grant.
   * Note: Verified against backend router.py — the current backend exposes
   * repository.revoke_elevated_grant but does not yet declare a router endpoint for revoke.
   * When the endpoint returns 404/405 or fails, this throws a clear error so the UI
   * does NOT falsely report a successful revocation.
   * @param {number|string} grantId
   * @returns {Promise<Object>}
   */
  revokeElevatedGrant: async (grantId) => {
    try {
      return await apiClient.delete(`/api/v1/admin/elevated-access/${encodeURIComponent(grantId)}`);
    } catch (err) {
      if (err?.status === 404 || err?.status === 405) {
        // Backend router endpoint is not yet wired
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
   * Priority: GET /api/v1/admin/anomaly-alerts
   * Strictly DEV-only fallback when backend endpoint is in progress.
   * In production builds, strictly throws so the UI surfaces the telemetry error state.
   * @returns {Promise<Array<Object>>} List of anomaly alerts
   */
  getAnomalyAlerts: async () => {
    try {
      const response = await apiClient.get("/api/v1/admin/anomaly-alerts");
      return Array.isArray(response) ? response : [];
    } catch (err) {
      // In development mode only, if backend endpoint is unavailable or 404,
      // fallback to mockData alerts so the UI layout can be evaluated locally without crashing
      if (import.meta.env?.DEV && (err?.status === 404 || err?.status === 0)) {
        console.warn("Backend anomaly-alerts unavailable (404/offline); using dev mock data:", err.message);
        return mockData.anomalyAlerts;
      }
      // In production builds, strictly throw the error so the UI displays the error state
      throw err;
    }
  },
};

export default adminApi;

