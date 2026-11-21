import { apiClient } from "./client.js";
import mockLeaveData from "../features/leave/mockLeaveData.json" with { type: "json" };
import mockLeaveTriageData from "../features/team_lead/mockLeaveTriageData.json" with { type: "json" };

/**
 * WorkSphere Leave Management API Service (S4 / US-14, US-16, US-17)
 *
 * Provides typed methods interacting with the backend leave endpoints:
 * - Employee APIs:
 *   - GET  /api/v1/leave/balance/me          (Retrieve year-wise balances for current employee)
 *   - GET  /api/v1/leave/policies            (Retrieve active leave policies / leave types)
 *   - POST /api/v1/leave/requests            (Submit a new leave request)
 *   - GET  /api/v1/leave/requests/my         (List paginated leave history for current employee)
 *   - PUT  /api/v1/leave/requests/{id}/cancel (Cancel a pending leave request)
 * - Team Lead & Admin APIs:
 *   - GET  /api/v1/leave/requests/pending    (Queue of leave requests for team lead review)
 *   - GET  /api/v1/leave/requests/{id}/conflicts (Conflicting tasks, milestones, coverage)
 *   - PUT  /api/v1/leave/requests/{id}/approve   (Approve leave request)
 *   - PUT  /api/v1/leave/requests/{id}/reject    (Reject leave request with remarks)
 *   - POST /api/v1/leave/requests/{id}/reallocate-tasks (Batch reassign/extend tasks)
 */

// ============================================================================
// Employee Self-Service Leave APIs (US-16)
// ============================================================================

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

// ============================================================================
// Team Lead & Reviewer Leave APIs (US-14, US-16, US-17 / Issue #106)
// ============================================================================

/**
 * Fetch pending and reviewed leave requests for Team Lead review triage.
 * Endpoint: GET /api/v1/leave/requests/pending
 *
 * @param {{ status?: string, page?: number, limit?: number }} [params]
 * @returns {Promise<{ items: Array<Object>, total: number, page: number, limit: number }>}
 */
export async function getPendingLeaveRequests(params = {}) {
  const query = new URLSearchParams();
  if (params?.status) {
    query.set("status", String(params.status).toUpperCase());
  }
  if (params?.page !== undefined && params?.page !== null) {
    query.set("page", String(params.page));
  }
  if (params?.limit !== undefined && params?.limit !== null) {
    query.set("limit", String(params.limit));
  }

  const queryString = query.toString();
  const endpoint = `/api/v1/leave/requests/pending${queryString ? `?${queryString}` : ""}`;

  try {
    return await apiClient.get(endpoint);
  } catch (err) {
    if (err?.status === 0 && typeof import.meta !== "undefined" && import.meta.env?.DEV) {
      console.warn("Backend /api/v1/leave/requests/pending unreachable; serving mock in DEV mode:", err.message);
      return mockLeaveTriageData.pendingRequests;
    }
    throw err;
  }
}

/**
 * Retrieve conflict evaluation report for a leave request.
 * Evaluates conflicting tasks due during leave, milestone conflicts, and teammate coverage.
 * Endpoint: GET /api/v1/leave/requests/{id}/conflicts
 *
 * @param {number|string} leaveId
 * @returns {Promise<{
 *   leave_id: number,
 *   employee_id: number,
 *   employee_name: string,
 *   leave_type_name: string,
 *   status: string,
 *   start_date: string,
 *   end_date: string,
 *   total_days: number,
 *   has_conflicts: boolean,
 *   conflicting_tasks: Array<Object>,
 *   milestone_conflicts: Array<Object>,
 *   team_coverage: Array<Object>,
 *   availability_threshold: number
 * }>}
 */
export async function getLeaveConflicts(leaveId) {
  if (leaveId === undefined || leaveId === null || String(leaveId).trim() === "") {
    throw new Error("Leave ID is required to fetch conflict report");
  }

  const id = encodeURIComponent(String(leaveId).trim());
  const endpoint = `/api/v1/leave/requests/${id}/conflicts`;

  try {
    return await apiClient.get(endpoint);
  } catch (err) {
    if (err?.status === 0 && typeof import.meta !== "undefined" && import.meta.env?.DEV) {
      console.warn(`Backend ${endpoint} unreachable; serving mock report in DEV mode:`, err.message);
      const strId = String(leaveId);
      return mockLeaveTriageData.conflictReports[strId] || mockLeaveTriageData.conflictReports["1"];
    }
    throw err;
  }
}

/**
 * Approve a pending leave request.
 * Endpoint: PUT /api/v1/leave/requests/{id}/approve
 *
 * @param {number|string} leaveId
 * @param {{ review_remarks?: string }} [payload={}]
 * @returns {Promise<Object>} Updated LeaveRequestOut
 */
export async function approveLeave(leaveId, payload = {}) {
  if (leaveId === undefined || leaveId === null || String(leaveId).trim() === "") {
    throw new Error("Leave ID is required for approval");
  }

  const id = encodeURIComponent(String(leaveId).trim());
  const endpoint = `/api/v1/leave/requests/${id}/approve`;

  const body = payload?.review_remarks ? { review_remarks: String(payload.review_remarks).trim() } : {};
  return await apiClient.put(endpoint, body);
}

/**
 * Reject a pending leave request with mandatory remarks.
 * Endpoint: PUT /api/v1/leave/requests/{id}/reject
 *
 * @param {number|string} leaveId
 * @param {{ review_remarks: string }} payload
 * @returns {Promise<Object>} Updated LeaveRequestOut
 */
export async function rejectLeave(leaveId, payload = {}) {
  if (leaveId === undefined || leaveId === null || String(leaveId).trim() === "") {
    throw new Error("Leave ID is required for rejection");
  }

  const remarks = String(payload?.review_remarks || "").trim();
  if (remarks.length < 10) {
    throw new Error("Review remarks must contain at least 10 non-whitespace characters.");
  }

  const id = encodeURIComponent(String(leaveId).trim());
  const endpoint = `/api/v1/leave/requests/${id}/reject`;

  return await apiClient.put(endpoint, { review_remarks: remarks });
}

/**
 * Batch reallocate conflicting tasks belonging to leave applicant.
 * Allows reassigning tasks to available teammates or extending due dates.
 * Endpoint: POST /api/v1/leave/requests/{id}/reallocate-tasks
 *
 * @param {number|string} leaveId
 * @param {{ actions: Array<{ task_id: number, action_type: "REASSIGN"|"EXTEND_DEADLINE", new_assignee_id?: number, new_due_date?: string, reason: string }> }} payload
 * @returns {Promise<{ leave_id: number, reallocated_count: number, reassigned: Array<Object>, extended: Array<Object>, warnings: Array<string> }>}
 */
export async function reallocateLeaveTasks(leaveId, payload) {
  if (leaveId === undefined || leaveId === null || String(leaveId).trim() === "") {
    throw new Error("Leave ID is required for task reallocation");
  }

  if (!payload || !Array.isArray(payload.actions) || payload.actions.length === 0) {
    throw new Error("At least one reallocation action is required.");
  }

  const id = encodeURIComponent(String(leaveId).trim());
  const endpoint = `/api/v1/leave/requests/${id}/reallocate-tasks`;

  return await apiClient.post(endpoint, payload);
}

export const leaveApi = {
  getMyLeaveBalances,
  getLeavePolicies,
  submitLeaveRequest,
  getMyLeaveRequests,
  cancelLeaveRequest,
  getPendingLeaveRequests,
  getLeaveConflicts,
  approveLeave,
  rejectLeave,
  reallocateLeaveTasks,
};

export default leaveApi;
