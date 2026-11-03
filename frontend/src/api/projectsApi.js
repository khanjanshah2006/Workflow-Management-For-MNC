import { apiClient } from "./client";

export const projectsApi = {
  /**
   * List projects scoped to user role.
   */
  getProjects: async (params = {}) => {
    const query = new URLSearchParams(params).toString();
    const endpoint = `/api/v1/projects${query ? `?${query}` : ""}`;
    return apiClient.get(endpoint);
  },

  /**
   * Get single project details.
   */
  getProject: async (projectId) => {
    return apiClient.get(`/api/v1/projects/${projectId}`);
  },

  /**
   * List current employee assignments for project roster (US-07).
   */
  getProjectAssignments: async (projectId) => {
    return apiClient.get(`/api/v1/projects/${projectId}/assignments`);
  },

  /**
   * Fetch eligible employees for project staffing with workload badges (US-07).
   */
  getEligibleEmployees: async (projectId) => {
    return apiClient.get(`/api/v1/projects/${projectId}/eligible-employees`);
  },

  /**
   * Assign an employee to project roster (US-07).
   * @param {number|string} projectId
   * @param {{ emp_id: number, role_in_project: string }} payload
   */
  assignEmployee: async (projectId, payload) => {
    return apiClient.post(`/api/v1/projects/${projectId}/assign`, payload);
  },
};
