import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
  const [activeTab, setActiveTab] = useState("eligible"); // 'eligible' | 'roster'
  const [searchTerm, setSearchTerm] = useState("");

  // Fetch eligible employees for this project (US-07)
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

  // Filter candidates based on search
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
            <span className="tab-pill">0</span>
          </button>
        </div>
      </div>

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
                          <span className="role-tag-preview">
                            {employee.designation || "Project Member"}
                          </span>
                        </td>
                        <td className="action-cell">
                          <button
                            type="button"
                            className="btn-assign"
                            disabled
                            title="Assignment action available in next flow"
                          >
                            <span className="btn-plus">+</span>
                            <span>Add</span>
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

      {activeTab === "roster" && (
        <div className="staffing-content">
          <div className="staffing-empty-state">
            <div className="empty-symbol">📋</div>
            <h4>Active Roster</h4>
            <p>Team members currently assigned to this project will appear here.</p>
          </div>
        </div>
      )}
    </div>
  );
}
