import { apiClient } from "./client";

/**
 * List projects scoped to user role (returns raw project array).
 * Used by ProjectsPage and general consumers.
 *
 * @param {Record<string, string|number>} params
 * @returns {Promise<Array<Object>>}
 */
export async function getProjects(params = {}) {
  const query = new URLSearchParams(params).toString();
  const endpoint = `/api/v1/projects${query ? `?${query}` : ""}`;
  return apiClient.get(endpoint);
}

/**
 * List projects with pagination metadata and X-Total-Count header extraction (US-06).
 * Used by ProjectListPage directory table.
 *
 * @param {{ skip?: number, limit?: number }} params
 * @returns {Promise<{ projects: Array<Object>, totalCount: number }>}
 */
export async function listProjects({ skip = 0, limit = 20 } = {}) {
  const query = new URLSearchParams({
    skip: String(skip),
    limit: String(limit),
  }).toString();

  const endpoint = `/api/v1/projects?${query}`;
  const result = await apiClient.get(endpoint, { includeHeaders: true });

  const rawProjects = result?.data;
  const projects = Array.isArray(rawProjects) ? rawProjects : [];
  const rawTotalHeader = result?.headers?.get?.("X-Total-Count");
  const parsedHeaderCount =
    rawTotalHeader !== null && rawTotalHeader !== undefined
      ? parseInt(rawTotalHeader, 10)
      : NaN;
  const totalCount = !isNaN(parsedHeaderCount) ? parsedHeaderCount : projects.length;

  return {
    projects,
    totalCount,
  };
}

/**
 * Retrieve details for a single project (US-06 / US-08).
 *
 * @param {number|string} projectId
 * @returns {Promise<Object>} Project details
 */
export async function getProject(projectId) {
  return apiClient.get(`/api/v1/projects/${projectId}`);
}

/**
 * Create a new project record (US-06).
 *
 * @param {Object} projectData Form inputs
 * @returns {Promise<Object>} Created ProjectResponse
 */
export async function createProject(projectData) {
  const payload = {
    project_code: projectData.project_code.trim(),
    name: projectData.name.trim(),
    start_date: projectData.start_date,
    client_id: parseInt(projectData.client_id, 10),
    priority: projectData.priority || "MEDIUM",
  };

  if (projectData.description && projectData.description.trim()) {
    payload.description = projectData.description.trim();
  }

  if (projectData.end_date) {
    payload.end_date = projectData.end_date;
  }

  if (
    projectData.pm_id !== undefined &&
    projectData.pm_id !== null &&
    String(projectData.pm_id).trim() !== ""
  ) {
    payload.pm_id = parseInt(projectData.pm_id, 10);
  }

  return apiClient.post("/api/v1/projects", payload);
}

/**
 * List current employee assignments for project roster (US-07).
 *
 * @param {number|string} projectId
 * @returns {Promise<Array<Object>>}
 */
export async function getProjectAssignments(projectId) {
  return apiClient.get(`/api/v1/projects/${projectId}/assignments`);
}

/**
 * Fetch eligible employees for project staffing with workload badges (US-07).
 *
 * @param {number|string} projectId
 * @returns {Promise<Array<Object>>}
 */
export async function getEligibleEmployees(projectId) {
  return apiClient.get(`/api/v1/projects/${projectId}/eligible-employees`);
}

/**
 * Assign an employee to project roster (US-07).
 *
 * @param {number|string} projectId
 * @param {{ emp_id: number, role_in_project: string }} payload
 * @returns {Promise<Object>}
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
  listProjects,
  getProject,
  createProject,
  getProjectAssignments,
  getEligibleEmployees,
  assignEmployee,
  getMilestones,
  createMilestone,
  updateProjectStatus,
};

export default projectsApi;
