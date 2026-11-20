import { apiClient } from "./client.js";
import mockLeaveData from "../features/leave/mockLeaveData.json";

/**
 * WorkSphere Leave Management API Service (S4 / US-16)
 *
 * Provides typed methods interacting with the backend leave endpoints:
 * - GET  /api/v1/leave/balance/me        (Retrieve year-wise balances for current employee)
 * - GET  /api/v1/leave/policies          (Retrieve active leave policies / leave types)
 * - POST /api/v1/leave/requests          (Submit a new leave request)
 * - GET  /api/v1/leave/requests/my       (List paginated leave history for current employee)
 * - PUT  /api/v1/leave/requests/{id}/cancel (Cancel a pending leave request)
 */

/**
 * Fetch the authenticated employee's leave balances.
 * Endpoint: GET /api/v1/leave/balance/me
 *
 * @param {{ year?: number }} [params] Optional calendar year filter
 * @returns {Promise<{ employee_id: number, year: number, balances: Array<Object> }>}
 */
export async function getMyLeaveBalances(params = {}) {
  const query = new URLSearchParams();
  if (params?.year !== undefined && params?.year !== null && String(params.year).trim() !== "") {
    query.set("year", String(params.year));
  }
  const queryString = query.toString();
  const endpoint = `/api/v1/leave/balance/me${queryString ? `?${queryString}` : ""}`;

  try {
    return await apiClient.get(endpoint);
  } catch (err) {
    if (err?.status === 0 && typeof import.meta !== "undefined" && import.meta.env?.DEV) {
      console.warn("Backend /api/v1/leave/balance/me unreachable; serving mock balances in DEV mode:", err.message);
      return {
        employee_id: 12,
        year: params?.year || new Date().getFullYear(),
        balances: mockLeaveData.balances,
      };
    }
    throw err;
  }
}

/**
 * Fetch active leave policies (leave types).
 * Endpoint: GET /api/v1/leave/policies
 *
 * Assumption note: In S4-BE-1, policies router is a stub placeholder awaiting S4-BE-2.
 * When backend returns 404 or is unavailable in DEV mode, this gracefully falls back
 * to standard leave policies from mockLeaveData.
 *
 * @returns {Promise<Array<{ leave_type_id: number, name: string, yearly_quota: number, is_paid: boolean, description: string, is_active: boolean }>>}
 */
export async function getLeavePolicies() {
  try {
    const response = await apiClient.get("/api/v1/leave/policies");
    // If backend returns wrapped object or array
    if (Array.isArray(response)) {
      return response;
    }
    if (Array.isArray(response?.items)) {
      return response.items;
    }
    return response || [];
  } catch (err) {
    // If endpoint is not yet implemented (404/501) or network is unreachable in DEV mode
    if ((err?.status === 404 || err?.status === 501 || err?.status === 0) &&
        typeof import.meta !== "undefined" && import.meta.env?.DEV) {
      console.warn("Backend /api/v1/leave/policies unavailable (S4-BE-2 pending); serving mock policies in DEV mode:", err.message);
      return mockLeaveData.policies;
    }
    throw err;
  }
}

/**
 * Submit a new leave request.
 * Endpoint: POST /api/v1/leave/requests
 *
 * @param {{ leave_type_id: number, start_date: string, end_date: string, reason: string }} payload
 * @returns {Promise<Object>} Created LeaveRequestOut
 */
export async function submitLeaveRequest(payload) {
  if (!payload) {
    throw new Error("Leave request payload is required");
  }

  const normalizedPayload = {
    leave_type_id: Number(payload.leave_type_id),
    start_date: String(payload.start_date || "").trim(),
    end_date: String(payload.end_date || "").trim(),
    reason: String(payload.reason || "").trim(),
  };

  return await apiClient.post("/api/v1/leave/requests", normalizedPayload);
}

/**
 * Fetch paginated leave request history for the authenticated employee.
 * Endpoint: GET /api/v1/leave/requests/my
 *
 * @param {{ status?: string, year?: number, page?: number, limit?: number }} [params]
 * @returns {Promise<{ items: Array<Object>, total: number, page: number, limit: number }>}
 */
export async function getMyLeaveRequests(params = {}) {
  const query = new URLSearchParams();
  if (params?.status && params.status !== "ALL") {
    query.set("status", String(params.status).toUpperCase());
  }
  if (params?.year !== undefined && params?.year !== null && String(params.year).trim() !== "" && params.year !== "ALL") {
    query.set("year", String(params.year));
  }
  if (params?.page !== undefined && params?.page !== null) {
    query.set("page", String(params.page));
  }
  if (params?.limit !== undefined && params?.limit !== null) {
    query.set("limit", String(params.limit));
  }

  const queryString = query.toString();
  const endpoint = `/api/v1/leave/requests/my${queryString ? `?${queryString}` : ""}`;

  try {
    return await apiClient.get(endpoint);
  } catch (err) {
    if (err?.status === 0 && typeof import.meta !== "undefined" && import.meta.env?.DEV) {
      console.warn("Backend /api/v1/leave/requests/my unreachable; serving mock requests in DEV mode:", err.message);
      return mockLeaveData.requests;
    }
    throw err;
  }
}

/**
 * Cancel a pending leave request owned by the authenticated employee.
 * Endpoint: PUT /api/v1/leave/requests/{id}/cancel
 *
 * @param {number|string} leaveId
 * @returns {Promise<Object>} Updated LeaveRequestOut with status CANCELLED
 */
export async function cancelLeaveRequest(leaveId) {
  if (leaveId === undefined || leaveId === null || String(leaveId).trim() === "") {
    throw new Error("Leave ID is required for cancellation");
  }

  const id = encodeURIComponent(String(leaveId).trim());
  return await apiClient.put(`/api/v1/leave/requests/${id}/cancel`, {});
}

export const leaveApi = {
  getMyLeaveBalances,
  getLeavePolicies,
  submitLeaveRequest,
  getMyLeaveRequests,
  cancelLeaveRequest,
};

export default leaveApi;
