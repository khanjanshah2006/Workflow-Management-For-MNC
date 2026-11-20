import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getDepartmentDrilldown } from "../../api/executiveApi.js";
import { formatVelocity } from "./executiveUtils.js";

/**
 * DepartmentDetailPanel
 * Lazily loads and renders granular projects, teams, and resource allocation for a department.
 * Guarantees zero individual employee PII is rendered.
 */
function DepartmentDetailPanel({ deptId, deptName }) {
  const isUnassigned = deptId === null || deptId === undefined;

  const { data, isLoading, error } = useQuery({
    queryKey: ["executive", "department", deptId],
    queryFn: () => getDepartmentDrilldown(deptId),
    enabled: !isUnassigned,
    staleTime: 5 * 60 * 1000,
  });

  if (isUnassigned) {
    return (
      <div className="exec-drilldown-content exec-drilldown-empty">
        <p className="exec-empty-text">
          ℹ️ Granular drilldown details are unavailable for projects without department attribution.
        </p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="exec-drilldown-content exec-drilldown-loading">
        <div className="exec-spinner" aria-hidden="true" />
        <p>Loading {deptName} department analytics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="exec-drilldown-content exec-drilldown-error">
        <p className="exec-error-text">
          ⚠️ Failed to load drilldown for {deptName}: {error.message || "Unknown error"}
        </p>
      </div>
    );
  }

  const projects = data?.projects || [];
  const teams = data?.teams || [];
  const allocation = data?.resource_allocation || {
    total_employees: 0,
    allocated_employees: 0,
    unallocated_employees: 0,
    headcount_by_designation: {},
  };

  const designations = Object.entries(allocation.headcount_by_designation || {});

  return (
    <div className="exec-drilldown-content" data-testid={`drilldown-${deptId}`}>
      {/* 1. Projects Section */}
      <div className="exec-drilldown-section">
        <h4 className="exec-drilldown-heading">Department Projects ({projects.length})</h4>
        {projects.length === 0 ? (
          <p className="exec-empty-subtext">No projects attributed to this department.</p>
        ) : (
          <div className="exec-table-responsive">
            <table className="exec-subtable">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Project Name</th>
                  <th>Status</th>
                  <th>Task Progress</th>
                  <th>Milestones</th>
                  <th>Teams</th>
                  <th>Assigned Staff</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((proj) => (
                  <tr key={proj.project_id}>
                    <td>
                      <span className="exec-code-badge">{proj.project_code}</span>
                    </td>
                    <td className="exec-font-semibold">{proj.name}</td>
                    <td>
                      <span className={`exec-status-pill status-${proj.status?.toLowerCase()}`}>
                        {proj.status}
                      </span>
                      {proj.is_delayed && (
                        <span className="exec-badge-delayed" title="Overdue pending milestones">
                          Delayed
                        </span>
                      )}
                    </td>
                    <td>
                      <div className="exec-progress-cell">
                        <div className="exec-mini-track">
                          <div
                            className="exec-mini-fill"
                            style={{ width: `${Math.min(100, Math.max(0, proj.task_completion_pct || 0))}%` }}
                          />
                        </div>
                        <span className="exec-progress-label">{proj.task_completion_pct || 0}%</span>
                      </div>
                    </td>
                    <td>
                      {proj.milestones_completed} / {proj.milestones_total}
                    </td>
                    <td>{proj.team_count}</td>
                    <td>{proj.assigned_headcount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 2. Teams Section */}
      <div className="exec-drilldown-section">
        <h4 className="exec-drilldown-heading">Assigned Teams ({teams.length})</h4>
        {teams.length === 0 ? (
          <p className="exec-empty-subtext">No active teams under department projects.</p>
        ) : (
          <div className="exec-table-responsive">
            <table className="exec-subtable">
              <thead>
                <tr>
                  <th>Team Name</th>
                  <th>Project</th>
                  <th>Headcount</th>
                  <th>Open Tasks</th>
                </tr>
              </thead>
              <tbody>
                {teams.map((tm) => (
                  <tr key={tm.team_id}>
                    <td className="exec-font-semibold">{tm.name}</td>
                    <td>{tm.project_name}</td>
                    <td>{tm.member_count}</td>
                    <td>{tm.open_tasks}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 3. Resource Allocation & Designations (Strictly PII-free) */}
      <div className="exec-drilldown-section">
        <h4 className="exec-drilldown-heading">Staffing &amp; Resource Allocation</h4>
        <div className="exec-allocation-summary">
          <div className="exec-allocation-chip">
            <span className="exec-chip-label">Total Department Staff:</span>
            <span className="exec-chip-value">{allocation.total_employees}</span>
          </div>
          <div className="exec-allocation-chip">
            <span className="exec-chip-label">Allocated to Projects:</span>
            <span className="exec-chip-value">{allocation.allocated_employees}</span>
          </div>
          <div className="exec-allocation-chip">
            <span className="exec-chip-label">Available / Unallocated:</span>
            <span className="exec-chip-value">{allocation.unallocated_employees}</span>
          </div>
        </div>

        {designations.length > 0 && (
          <div className="exec-designations-wrapper">
            <h5 className="exec-designations-title">Headcount by Designation:</h5>
            <div className="exec-designation-chips">
              {designations.map(([role, count]) => (
                <div key={role} className="exec-role-pill">
                  <span className="exec-role-name">{role}</span>
                  <span className="exec-role-count">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * DepartmentDrilldownTable
 * Displays expandable list of department summaries with lazy-loaded drilldown details.
 *
 * @param {Object} props
 * @param {Array<Object>} props.departments List of DepartmentSummaryItem objects
 */
export default function DepartmentDrilldownTable({ departments = [] }) {
  const [expandedDeptId, setExpandedDeptId] = useState(null);

  const toggleRow = (deptId) => {
    setExpandedDeptId((current) => (current === deptId ? null : deptId));
  };

  if (!departments || departments.length === 0) {
    return (
      <div className="exec-table-card">
        <h3 className="exec-card-title">Department Summaries</h3>
        <p className="exec-empty-text">No department summary data available.</p>
      </div>
    );
  }

  return (
    <div className="exec-table-card" aria-label="Department Summaries and Drilldown">
      <div className="exec-card-header">
        <div>
          <h3 className="exec-card-title">Department Performance &amp; Rollups</h3>
          <p className="exec-card-subtitle">
            Click any row to view project health, teams, and staffing allocation
          </p>
        </div>
      </div>

      <div className="exec-table-responsive">
        <table className="exec-main-table">
          <thead>
            <tr>
              <th style={{ width: "40px" }} aria-label="Expand toggle" />
              <th>Department</th>
              <th>Total Projects</th>
              <th>Active Projects</th>
              <th>At Risk Projects</th>
              <th>Total Employees</th>
              <th>Milestone Velocity</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {departments.map((dept) => {
              const rowKey = dept.dept_id !== null ? dept.dept_id : "unassigned";
              const isExpanded = expandedDeptId === rowKey;
              const hasRisk = dept.at_risk_projects > 0;

              return (
                <React.Fragment key={rowKey}>
                  <tr
                    className={`exec-row-clickable ${isExpanded ? "exec-row-expanded" : ""}`}
                    onClick={() => toggleRow(rowKey)}
                    tabIndex={0}
                    role="button"
                    aria-expanded={isExpanded}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        toggleRow(rowKey);
                      }
                    }}
                  >
                    <td className="exec-expand-col">
                      <span className="exec-expand-icon" aria-hidden="true">
                        {isExpanded ? "▼" : "▶"}
                      </span>
                    </td>
                    <td className="exec-dept-name">
                      <strong>{dept.dept_name}</strong>
                      {dept.dept_id === null && (
                        <span className="exec-unassigned-tag">Unassigned</span>
                      )}
                    </td>
                    <td>{dept.total_projects}</td>
                    <td>{dept.active_projects}</td>
                    <td>
                      <span className={hasRisk ? "exec-risk-warning" : "exec-risk-normal"}>
                        {dept.at_risk_projects}
                      </span>
                    </td>
                    <td>{dept.total_employees}</td>
                    <td>
                      <span className="exec-velocity-badge">
                        {formatVelocity(dept.milestone_velocity_pct)}
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="exec-drilldown-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleRow(rowKey);
                        }}
                      >
                        {isExpanded ? "Close" : "Drilldown"}
                      </button>
                    </td>
                  </tr>

                  {isExpanded && (
                    <tr className="exec-drilldown-row">
                      <td colSpan={8}>
                        <DepartmentDetailPanel
                          deptId={dept.dept_id}
                          deptName={dept.dept_name}
                        />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
