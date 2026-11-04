import { apiClient } from "./client.js";

/**
 * Team Management API Service (US-37)
 * Implements frontend integration with the team members endpoint.
 */
export const teamApi = {
  /**
   * Fetch members of a team.
   * Priority: GET /api/v1/teams/{teamId}/members (Issue #43 specification)
   * Fallback: GET /api/v1/projects/{projectId}/teams/{teamId}/members
   *
   * @param {number|string} teamId - Team identifier
   * @param {number|string|null} projectId - Optional project context
   * @returns {Promise<Array>} List of raw team member records
   */
  getTeamMembers: async (teamId, projectId = null) => {
    try {
      // Primary API endpoint specified in Issue #43
      const response = await apiClient.get(`/api/v1/teams/${teamId}/members`);
      return response || [];
    } catch (err) {
      // If primary endpoint is not found (404) and project ID is provided, try project-scoped endpoint
      if (err.status === 404 && projectId) {
        try {
          const fallbackResponse = await apiClient.get(
            `/api/v1/projects/${projectId}/teams/${teamId}/members`
          );
          return fallbackResponse || [];
        } catch {
          // Re-throw original error if fallback also fails
          throw err;
        }
      }
      throw err;
    }
  },

  /**
   * Fetch detailed employee profile by emp_id.
   * Used to enrich minimal member records (which only include emp_id).
   *
   * @param {number|string} empId
   * @returns {Promise<Object>}
   */
  getEmployeeById: async (empId) => {
    return apiClient.get(`/api/v1/employees/${empId}`);
  },

  /**
   * Normalizes member records from various API shapes into a unified UI model.
   *
   * @param {Object} raw - Raw API response item
   * @param {Object} [employeeDetail] - Optional enriched employee details
   * @returns {Object} Normalized member object
   */
  normalizeMember: (raw, employeeDetail = null) => {
    const detail = employeeDetail || {};
    return {
      id: raw.team_member_id || raw.id || raw.emp_id,
      emp_id: raw.emp_id || raw.id,
      name:
        detail.full_name ||
        raw.full_name ||
        raw.name ||
        raw.employee_name ||
        `Employee #${raw.emp_id || raw.id}`,
      role:
        detail.designation ||
        raw.role ||
        raw.designation ||
        raw.role_in_team ||
        "Team Member",
      email:
        detail.email ||
        raw.email ||
        raw.employee_email ||
        (raw.emp_id ? `emp${raw.emp_id}@enterprise.com` : "N/A"),
      status: (detail.status || raw.status || "ACTIVE").toUpperCase(),
      joined_on: raw.joined_on || detail.date_of_joining || null,
    };
  },
};
