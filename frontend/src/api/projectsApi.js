import { apiClient } from "./client";

/**
 * List projects scoped to user role.
 */
export async function getProjects(params = {}) {
  const query = new URLSearchParams(params).toString();
  const endpoint = `/api/v1/projects${query ? `?${query}` : ""}`;
  return apiClient.get(endpoint);
}

/**
 * Get single project details (US-06 / US-08).
 * @param {number|string} projectId
 * @returns {Promise<Object>} Project details
 */
export async function getProject(projectId) {
  return apiClient.get(`/api/v1/projects/${projectId}`);
}

/**
 * List current employee assignments for project roster (US-07).
 * @param {number|string} projectId
 */
export async function getProjectAssignments(projectId) {
  return apiClient.get(`/api/v1/projects/${projectId}/assignments`);
}

/**
 * Fetch eligible employees for project staffing with workload badges (US-07).
 * @param {number|string} projectId
 */
export async function getEligibleEmployees(projectId) {
  return apiClient.get(`/api/v1/projects/${projectId}/eligible-employees`);
}

/**
 * Assign an employee to project roster (US-07).
 * @param {number|string} projectId
 * @param {{ emp_id: number, role_in_project: string }} payload
 */
export async function assignEmployee(projectId, payload) {
  return apiClient.post(`/api/v1/projects/${projectId}/assign`, payload);
}

/**
 * List milestones for a project ordered chronologically (US-08).
 * @param {number|string} projectId
 * @returns {Promise<Array<Object>>}
 */
export async function getMilestones(projectId) {
  return apiClient.get(`/api/v1/projects/${projectId}/milestones`);
}

/**
 * Create a milestone in a project (US-08).
 * @param {number|string} projectId
 * @param {{ title: string, description?: string, target_date: string }} payload
 * @returns {Promise<Object>}
 */
export async function createMilestone(projectId, payload) {
  return apiClient.post(`/api/v1/projects/${projectId}/milestones`, payload);
}

/**
 * Transition project lifecycle status (US-36).
 * Documented contract: PUT /api/v1/projects/{id}/status -> { status }
 * @param {number|string} projectId
 * @param {string} status - Target status ('ACTIVE', 'ON_HOLD', 'COMPLETED', 'CANCELLED')
 * @returns {Promise<{ project_id: number, status: string }>}
 */
export async function updateProjectStatus(projectId, status) {
  return apiClient.put(`/api/v1/projects/${projectId}/status`, { status });
}

export const projectsApi = {
  getProjects,
  getProject,
  getProjectAssignments,
  getEligibleEmployees,
  assignEmployee,
  getMilestones,
  createMilestone,
  updateProjectStatus,
};

export default projectsApi;
