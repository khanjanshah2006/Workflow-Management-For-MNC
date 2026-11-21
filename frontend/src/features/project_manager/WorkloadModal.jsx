import React from "react";
import { useQuery } from "@tanstack/react-query";
import { getProjectTeamWorkload } from "../../api/projectsApi";

/**
 * WorkloadModal Component (US-39 / S5)
 *
 * Displays cross-project team member utilization and task load:
 * - Fetches GET /projects/{id}/team-workload
 * - Utilization progress bar per member
 * - "Open here / open everywhere" counts
 * - Cross-project aggregates without leaking other project task titles
 */
export default function WorkloadModal({ isOpen = false, projectId = null, onClose }) {
  const { data: workload = [], isLoading, isError, error } = useQuery({
    queryKey: ["projects", projectId, "team-workload"],
    queryFn: () => getProjectTeamWorkload(projectId),
    enabled: Boolean(isOpen && projectId),
  });

  if (!isOpen) return null;

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="workload-modal-title"
    >
      <div className="modal-dialog pm-workload-modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <h2 id="workload-modal-title">Team Workload & Capacity Allocation</h2>
            <p className="modal-task-subtitle">
              Cross-project task allocations and capacity utilization for staffed team members
            </p>
          </div>
          <button className="btn-modal-close" onClick={onClose} aria-label="Close dialog">
            ✕
          </button>
        </div>

        <div className="modal-body">
          {isLoading ? (
            <div className="pm-loading-state">Loading team workload across projects...</div>
          ) : isError ? (
            <div className="alert-banner alert-banner-danger" role="alert">
              <span>Failed to load team workload: {error?.message || "Internal server error"}</span>
            </div>
          ) : workload.length === 0 ? (
            <div className="pm-empty-state">
              <p className="pm-empty-title">No Staff Assigned</p>
              <p className="pm-empty-desc">
                There are currently no team members with active project assignments on this project.
              </p>
            </div>
          ) : (
            <div className="pm-workload-list">
              {workload.map((member) => {
                const util = Math.round((member.utilization_pct || 0) * 10) / 10;
                let utilTone = "healthy";
                if (util > 100) utilTone = "overload";
                else if (util >= 75) utilTone = "high";

                return (
                  <div key={member.emp_id} className="pm-workload-card">
                    <div className="pm-workload-header">
                      <div className="pm-workload-member-info">
                        <strong className="pm-workload-name">{member.full_name}</strong>
                        <span className="pm-workload-role">· {member.role_in_project || "Staff"}</span>
                      </div>
                      <span className={`pm-util-badge pm-util-${utilTone}`}>
                        {util}% Utilization
                      </span>
                    </div>

                    {/* Utilization Bar */}
                    <div className="pm-util-track" role="progressbar" aria-valuenow={util} aria-valuemin={0} aria-valuemax={100}>
                      <div
                        className={`pm-util-fill pm-util-fill-${utilTone}`}
                        style={{ width: `${Math.min(100, Math.max(0, util))}%` }}
                      />
                    </div>

                    {/* "Open here / open everywhere" counts */}
                    <div className="pm-workload-metrics-row">
                      <div className="pm-workload-stat">
                        <span className="pm-stat-count">{member.open_tasks_in_project}</span>
                        <span className="pm-stat-label">open here</span>
                      </div>
                      <span className="pm-stat-divider">/</span>
                      <div className="pm-workload-stat">
                        <span className="pm-stat-count">{member.open_tasks_all_projects}</span>
                        <span className="pm-stat-label">open everywhere</span>
                      </div>
                      <span className="pm-stat-divider">·</span>
                      <div className="pm-workload-stat">
                        <span className="pm-stat-label">Across</span>
                        <span className="pm-stat-count-sm">{member.active_projects_count}</span>
                        <span className="pm-stat-label">
                          {member.active_projects_count === 1 ? "active project" : "active projects"}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button type="button" className="pm-btn pm-btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
