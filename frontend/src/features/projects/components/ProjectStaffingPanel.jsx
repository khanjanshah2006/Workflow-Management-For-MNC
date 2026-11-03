import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { projectsApi } from "../../../api/projectsApi";

function getWorkloadBadgeClass(count) {
  if (count === 0) return "badge-workload badge-workload-free";
  if (count <= 1) return "badge-workload badge-workload-low";
  if (count <= 3) return "badge-workload badge-workload-medium";
  return "badge-workload badge-workload-high";
}

function getWorkloadLabel(count) {
  if (count === 1) return "1 active project";
  return `${count} active projects`;
}

export default function ProjectStaffingPanel({ projectId }) {
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState("eligible"); // 'eligible' | 'roster'
  const [searchTerm, setSearchTerm] = useState("");
  const [roleInputs, setRoleInputs] = useState({});
  const [actionMessage, setActionMessage] = useState(null); // { type: 'success' | 'error', text: string }

  // 1. Fetch eligible employees for this project (US-07)
  const {
    data: eligibleEmployees = [],
    isLoading: eligibleLoading,
    isError: eligibleIsError,
    error: eligibleError,
    refetch: refetchEligible,
  } = useQuery({
    queryKey: ["projects", projectId, "eligible-employees"],
    queryFn: () => projectsApi.getEligibleEmployees(projectId),
    enabled: Boolean(projectId),
    retry: 1,
  });

  // 2. Fetch current project team assignments / roster (US-07)
  const {
    data: roster = [],
    isLoading: rosterLoading,
    isError: rosterIsError,
    error: rosterError,
    refetch: refetchRoster,
  } = useQuery({
    queryKey: ["projects", projectId, "assignments"],
    queryFn: () => projectsApi.getProjectAssignments(projectId),
    enabled: Boolean(projectId),
    retry: 1,
  });

  // 3. Mutation: Assign employee to project roster (US-07)
  const assignMutation = useMutation({
    mutationFn: ({ empId, roleInProject }) =>
      projectsApi.assignEmployee(projectId, {
        emp_id: empId,
        role_in_project: roleInProject,
      }),
    onSuccess: (data, variables) => {
      // Refresh both queries immediately
      queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "eligible-employees"],
      });
      queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "assignments"],
      });
      queryClient.invalidateQueries({
        queryKey: ["notifications"],
      });

      // Clear input for this employee
      setRoleInputs((prev) => {
        const next = { ...prev };
        delete next[variables.empId];
        return next;
      });

      setActionMessage({
        type: "success",
        text: `Successfully assigned ${data?.employee_name || "employee"} as "${variables.roleInProject}"!`,
      });

      setTimeout(() => setActionMessage(null), 5000);
    },
    onError: (err) => {
      setActionMessage({
        type: "error",
        text: err?.message || "Failed to assign employee to project.",
      });
      setTimeout(() => setActionMessage(null), 7000);
    },
  });

  const handleRoleChange = (empId, value) => {
    setRoleInputs((prev) => ({
      ...prev,
      [empId]: value,
    }));
  };

  const handleAssign = (employee) => {
    const role = (roleInputs[employee.emp_id] || employee.designation || "Project Contributor").trim();
    if (!role) {
      setActionMessage({
        type: "error",
        text: "Please enter a valid role description.",
      });
      return;
    }

    // Client-side duplicate assignment check
    const isAlreadyAssigned = roster.some(
      (item) => item.emp_id === employee.emp_id && !item.released_on
    );
    if (isAlreadyAssigned) {
      setActionMessage({
        type: "error",
        text: `${employee.full_name} is already assigned to this project.`,
      });
      return;
    }

    assignMutation.mutate({
      empId: employee.emp_id,
      roleInProject: role,
    });
  };

  // Filter eligible employees based on search input
  const filteredEligible = eligibleEmployees.filter((emp) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      emp.full_name?.toLowerCase().includes(term) ||
      emp.emp_code?.toLowerCase().includes(term) ||
      emp.designation?.toLowerCase().includes(term) ||
      emp.department_name?.toLowerCase().includes(term)
    );
  });

  return (
    <div className="staffing-panel-card">
      <div className="staffing-header">
        <div className="staffing-title-area">
          <div className="staffing-badge">US-07</div>
          <h2 className="staffing-title">Project Staffing & Team Management</h2>
          <p className="staffing-subtitle">
            Allocate eligible employees to project roster and monitor team workload.
          </p>
        </div>

        <div className="staffing-tabs">
          <button
            type="button"
            className={`staffing-tab-btn ${activeTab === "eligible" ? "active" : ""}`}
            onClick={() => setActiveTab("eligible")}
          >
            <span>Eligible Employees</span>
            <span className="tab-pill">{eligibleEmployees.length}</span>
          </button>
          <button
            type="button"
            className={`staffing-tab-btn ${activeTab === "roster" ? "active" : ""}`}
            onClick={() => setActiveTab("roster")}
          >
            <span>Active Team Roster</span>
            <span className="tab-pill">{roster.length}</span>
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className={`staffing-alert staffing-alert-${actionMessage.type}`} role="alert">
          <span className="alert-icon">
            {actionMessage.type === "success" ? "✓" : "⚠"}
          </span>
          <span className="alert-text">{actionMessage.text}</span>
          <button
            type="button"
            className="alert-dismiss-btn"
            onClick={() => setActionMessage(null)}
            aria-label="Dismiss notification"
          >
            ×
          </button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 1: ELIGIBLE EMPLOYEES */}
      {/* ========================================================================= */}
      {activeTab === "eligible" && (
        <div className="staffing-content">
          <div className="staffing-filter-bar">
            <div className="search-input-wrapper">
              <span className="search-icon" aria-hidden="true">🔍</span>
              <input
                type="text"
                className="search-input"
                placeholder="Filter by name, designation, or department..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              {searchTerm && (
                <button
                  type="button"
                  className="clear-search-btn"
                  onClick={() => setSearchTerm("")}
                  aria-label="Clear search"
                >
                  ×
                </button>
              )}
            </div>
            <div className="staffing-count-label">
              Showing <strong>{filteredEligible.length}</strong> eligible candidates
            </div>
          </div>

          {eligibleLoading ? (
            <div className="staffing-loading-state">
              <div className="spinner-medium" />
              <p>Scanning employee directory and calculating workloads...</p>
            </div>
          ) : eligibleIsError ? (
            <div className="staffing-error-state">
              <span className="error-symbol">⚠️</span>
              <h4>Unable to load eligible candidates</h4>
              <p>{eligibleError?.message || "An unexpected error occurred while fetching employees."}</p>
              <button
                type="button"
                className="btn-retry"
                onClick={() => refetchEligible()}
              >
                Retry
              </button>
            </div>
          ) : filteredEligible.length === 0 ? (
            <div className="staffing-empty-state">
              <div className="empty-symbol">👥</div>
              <h4>No eligible employees found</h4>
              <p>
                {searchTerm
                  ? `No employees match "${searchTerm}". Try a different search term.`
                  : "All active employees are already assigned to this project or none are available in the organization."}
              </p>
            </div>
          ) : (
            <div className="eligible-table-wrapper">
              <table className="staffing-table">
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Department</th>
                    <th>Current Workload</th>
                    <th>Project Role</th>
                    <th className="th-action">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEligible.map((employee) => {
                    const isAssigningThis =
                      assignMutation.isPending &&
                      assignMutation.variables?.empId === employee.emp_id;
                    const roleValue =
                      roleInputs[employee.emp_id] !== undefined
                        ? roleInputs[employee.emp_id]
                        : employee.designation || "";
                    const workloadCount = employee.workload ?? employee.active_projects_count ?? 0;

                    return (
                      <tr key={employee.emp_id} className="candidate-row">
                        <td className="candidate-info-cell">
                          <div className="candidate-avatar">
                            {employee.full_name?.charAt(0) || "E"}
                          </div>
                          <div className="candidate-details">
                            <span className="candidate-name">{employee.full_name}</span>
                            <span className="candidate-code-email">
                              {employee.emp_code} · {employee.email}
                            </span>
                          </div>
                        </td>
                        <td>
                          <span className="department-tag">
                            {employee.department_name || "General"}
                          </span>
                        </td>
                        <td>
                          <span className={getWorkloadBadgeClass(workloadCount)}>
                            <span className="workload-dot" />
                            {getWorkloadLabel(workloadCount)}
                          </span>
                        </td>
                        <td className="role-input-cell">
                          <input
                            type="text"
                            className="role-input"
                            value={roleValue}
                            placeholder="Enter project role..."
                            disabled={isAssigningThis}
                            onChange={(e) =>
                              handleRoleChange(employee.emp_id, e.target.value)
                            }
                          />
                        </td>
                        <td className="action-cell">
                          <button
                            type="button"
                            className="btn-assign"
                            disabled={assignMutation.isPending}
                            onClick={() => handleAssign(employee)}
                            title={`Assign ${employee.full_name} to project`}
                          >
                            {isAssigningThis ? (
                              <>
                                <span className="btn-spinner" />
                                <span>Adding...</span>
                              </>
                            ) : (
                              <>
                                <span className="btn-plus">+</span>
                                <span>Add to Team</span>
                              </>
                            )}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: CURRENT ROSTER */}
      {/* ========================================================================= */}
      {activeTab === "roster" && (
        <div className="staffing-content">
          {rosterLoading ? (
            <div className="staffing-loading-state">
              <div className="spinner-medium" />
              <p>Loading project roster...</p>
            </div>
          ) : rosterIsError ? (
            <div className="staffing-error-state">
              <span className="error-symbol">⚠️</span>
              <h4>Unable to load project roster</h4>
              <p>{rosterError?.message || "Failed to load assigned employees."}</p>
              <button
                type="button"
                className="btn-retry"
                onClick={() => refetchRoster()}
              >
                Retry
              </button>
            </div>
          ) : roster.length === 0 ? (
            <div className="staffing-empty-state">
              <div className="empty-symbol">📋</div>
              <h4>No team members assigned yet</h4>
              <p>Switch to the "Eligible Employees" tab to assign staff to this project.</p>
              <button
                type="button"
                className="btn-assign-secondary"
                onClick={() => setActiveTab("eligible")}
              >
                Browse Eligible Employees →
              </button>
            </div>
          ) : (
            <div className="eligible-table-wrapper">
              <table className="staffing-table">
                <thead>
                  <tr>
                    <th>Assigned Member</th>
                    <th>Role in Project</th>
                    <th>Assigned On</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {roster.map((assignment) => (
                    <tr key={assignment.assignment_id}>
                      <td className="candidate-info-cell">
                        <div className="candidate-avatar">
                          {(assignment.employee_name || `Emp #${assignment.emp_id}`).charAt(0)}
                        </div>
                        <div className="candidate-details">
                          <span className="candidate-name">
                            {assignment.employee_name || `Employee #${assignment.emp_id}`}
                          </span>
                          <span className="candidate-code-email">
                            {assignment.employee_code || `ID: ${assignment.emp_id}`}
                            {assignment.employee_email ? ` · ${assignment.employee_email}` : ""}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className="role-tag">
                          {assignment.role_in_project}
                        </span>
                      </td>
                      <td className="assigned-date-cell">
                        {assignment.assigned_on || "Recent"}
                      </td>
                      <td>
                        <span className="status-badge-active">
                          <span className="status-dot-active" />
                          {assignment.released_on ? "Released" : "Active Roster"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
