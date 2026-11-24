import { apiClient } from "./client.js";

/**
 * WorkSphere Employee Profile & Skills API Client (US-03, US-34 / Issues #39, #161)
 * Provides methods to retrieve profile data, employee skills, and manage skill proposals & review queue.
 */

/**
 * Fetch the authenticated employee's organizational profile.
 * Endpoint: GET /api/v1/profile/me
 * @returns {Promise<Object>} ProfileResponse
 */
export async function getMyProfile() {
  return await apiClient.get("/api/v1/profile/me");
}

/**
 * Update the authenticated employee's self-service contact details.
 * Endpoint: PUT /api/v1/profile/me
 * @param {{ phone?: string, emergency_contact?: string, bio?: string }} payload
 * @returns {Promise<Object>} Updated ProfileResponse
 */
export async function updateMyProfile(payload) {
  return await apiClient.put("/api/v1/profile/me", payload);
}

/**
 * Fetch the authenticated employee's assigned skills.
 * Endpoint: GET /api/v1/profile/me/skills
 * @returns {Promise<Array<Object>>} List of SkillResponse items
 */
export async function getMySkills() {
  return await apiClient.get("/api/v1/profile/me/skills");
}

/**
 * Submit a skill change proposal (ADD, UPDATE, or REMOVE) (US-34).
 * Endpoint: POST /api/v1/profile/me/skill-requests
 * @param {{ action: string, skill_id?: number, proposed_skill_name?: string, proficiency?: string, years_of_experience?: number, justification: string }} payload
 * @returns {Promise<Object>} Created SkillChangeRequestOut
 */
export async function proposeSkillChange(payload) {
  return await apiClient.post("/api/v1/profile/me/skill-requests", payload);
}

/**
 * Fetch all skill change requests submitted by the current employee, newest first (US-34).
 * Endpoint: GET /api/v1/profile/me/skill-requests
 * @returns {Promise<Array<Object>>} List of SkillChangeRequestOut items
 */
export async function getMySkillRequests() {
  return await apiClient.get("/api/v1/profile/me/skill-requests");
}

/**
 * Fetch paginated skill proposals review queue for HR and Team Leads (US-34).
 * Scoped by role: HR sees all; Team Leads see requests from active team members.
 * Endpoint: GET /api/v1/skill-requests
 * @param {{ status?: string, page?: number, limit?: number }} [params]
 * @returns {Promise<{ items: Array<Object>, total: number, page: number, limit: number }>}
 */
export async function getSkillRequestQueue(params = {}) {
  const query = new URLSearchParams();
  if (params?.status && String(params.status).trim() !== "") {
    query.set("status", String(params.status).trim());
  }
  if (params?.page !== undefined && params?.page !== null) {
    query.set("page", String(params.page));
  }
  if (params?.limit !== undefined && params?.limit !== null) {
    query.set("limit", String(params.limit));
  }
  const queryString = query.toString();
  const endpoint = `/api/v1/skill-requests${queryString ? `?${queryString}` : ""}`;
  return await apiClient.get(endpoint);
}

/**
 * Approve a pending skill change request and apply changes to employee profile (US-34).
 * Endpoint: PUT /api/v1/skill-requests/{id}/approve
 * @param {number|string} id Request ID
 * @param {string} [remarks] Optional approval remarks
 * @returns {Promise<Object>} Updated SkillChangeRequestOut
 */
export async function approveSkillRequest(id, remarks) {
  const body = {};
  if (remarks !== undefined && remarks !== null && String(remarks).trim() !== "") {
    body.remarks = String(remarks).trim();
    body.review_remarks = String(remarks).trim();
  }
  return await apiClient.put(`/api/v1/skill-requests/${id}/approve`, body);
}

/**
 * Reject a pending skill change request with mandatory remarks (US-34).
 * Endpoint: PUT /api/v1/skill-requests/{id}/reject
 * @param {number|string} id Request ID
 * @param {string} remarks Mandatory rejection remarks (min 5 chars)
 * @returns {Promise<Object>} Updated SkillChangeRequestOut
 */
export async function rejectSkillRequest(id, remarks) {
  const cleanRemarks = remarks !== undefined && remarks !== null ? String(remarks).trim() : "";
  const body = {
    remarks: cleanRemarks,
    review_remarks: cleanRemarks,
  };
  return await apiClient.put(`/api/v1/skill-requests/${id}/reject`, body);
}

export const profileApi = {
  getMyProfile,
  updateMyProfile,
  getMySkills,
  proposeSkillChange,
  getMySkillRequests,
  getSkillRequestQueue,
  approveSkillRequest,
  rejectSkillRequest,
};

export default profileApi;
