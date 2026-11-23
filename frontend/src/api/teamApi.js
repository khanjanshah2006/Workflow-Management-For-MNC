import { apiClient } from "./client.js";

/**
 * Team Management API Service (US-37, Issue #160)
 * Implements frontend integration with team members, department teams,
 * and employee search endpoints.
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
    // GET /api/v1/teams/{id}/members returns `employee_id`; older shapes used `emp_id`.
    const empId = raw.emp_id || raw.employee_id || raw.id;
    return {
      id: raw.team_member_id || raw.id || empId,
      emp_id: empId,
      name:
        detail.full_name ||
        raw.full_name ||
        raw.name ||
        raw.employee_name ||
        `Employee #${empId}`,
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
        (empId ? `emp${empId}@enterprise.com` : "N/A"),
      status: (detail.status || raw.status || "ACTIVE").toUpperCase(),
      joined_on: raw.joined_on || detail.date_of_joining || null,
    };
  },
};

// ==========================================
// Department Teams API (Issue #160)
// ==========================================

/**
 * Fetch all departments.
 * GET /api/v1/departments?limit=100
 * @returns {Promise<Array>}
 */
export async function getDepartments() {
  return apiClient.get("/api/v1/departments?limit=100");
}

/**
 * Fetch teams for a department.
 * GET /api/v1/departments/{deptId}/teams?include_disbanded={bool}
 * @param {number} deptId
 * @param {{ includeDisbanded?: boolean }} options
 * @returns {Promise<Array>}
 */
export async function getDepartmentTeams(deptId, { includeDisbanded = false } = {}) {
  const qs = includeDisbanded ? "?include_disbanded=true" : "";
  return apiClient.get(`/api/v1/departments/${deptId}/teams${qs}`);
}

/**
 * Create a team under a department.
 * POST /api/v1/departments/{deptId}/teams
 * @param {number} deptId
 * @param {{ name: string, description?: string, lead_emp_id: number, member_emp_ids: number[] }} payload
 * @returns {Promise<Object>}
 */
export async function createDepartmentTeam(deptId, payload) {
  return apiClient.post(`/api/v1/departments/${deptId}/teams`, payload);
}

/**
 * Update a team.
 * PUT /api/v1/teams/{teamId}
 * @param {number} teamId
 * @param {Object} patch - Partial fields: name, description, lead_emp_id, status
 * @returns {Promise<Object>}
 */
export async function updateTeam(teamId, patch) {
  return apiClient.put(`/api/v1/teams/${teamId}`, patch);
}

/**
 * Add members to a team (idempotent).
 * POST /api/v1/teams/{teamId}/members
 * @param {number} teamId
 * @param {number[]} empIds
 * @returns {Promise<Object>}
 */
export async function addTeamMembers(teamId, empIds) {
  return apiClient.post(`/api/v1/teams/${teamId}/members`, { emp_ids: empIds });
}

/**
 * Remove a member from a team.
 * DELETE /api/v1/teams/{teamId}/members/{empId}
 * Returns 409 if employee is the designated lead.
 * @param {number} teamId
 * @param {number} empId
 * @returns {Promise<null>}
 */
export async function removeTeamMember(teamId, empId) {
  return apiClient.delete(`/api/v1/teams/${teamId}/members/${empId}`);
}

/**
 * Search employees by department and optional text query.
 * GET /api/v1/employees?dept_id={deptId}&search={q}&status=ACTIVE&limit=50
 * @param {{ deptId?: number, search?: string }} options
 * @returns {Promise<Array>}
 */
export async function searchEmployees({ deptId, search } = {}) {
  const params = new URLSearchParams();
  params.set("status", "ACTIVE");
  params.set("limit", "50");
  if (deptId) params.set("dept_id", String(deptId));
  if (search && search.trim()) params.set("search", search.trim());
  return apiClient.get(`/api/v1/employees?${params.toString()}`);
}
