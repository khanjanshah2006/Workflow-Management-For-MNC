import React from "react";
import { useQuery } from "@tanstack/react-query";
import { getLeaveConflicts } from "../../api/leaveApi";
import TaskCoverageMatrix from "./TaskCoverageMatrix";

/**
 * LeaveConflictDrawer Component (US-17 / Issue #106)
 *
 * Side drawer detailing leave conflicts:
 * - Applicant employee information, dates, days, and reason
 * - Conflicting tasks due during leave window (RED rows)
 * - Milestone conflicts during window (AMBER rows)
 * - Teammate coverage matrix
 * - Actions: "Approve & Reassign" and "Reject"
 */
export default function LeaveConflictDrawer({
  leaveRequest,
  isOpen = false,
  onClose,
  onApproveClick,
  onRejectClick,
}) {
  const leaveId = leaveRequest?.leave_id;

  const {
    data: conflictReport,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["leave", "conflicts", leaveId],
    queryFn: () => getLeaveConflicts(leaveId),
    enabled: isOpen && Boolean(leaveId),
  });

  if (!isOpen || !leaveRequest) return null;

  const applicantName =
    conflictReport?.employee_name || leaveRequest?.employee_name || `Employee #${leaveRequest.employee_id || leaveRequest.emp_id}`;
  const leaveTypeName =
    conflictReport?.leave_type_name || leaveRequest?.leave_type_name || "Leave";
  const startDate = conflictReport?.start_date || leaveRequest?.start_date;
  const endDate = conflictReport?.end_date || leaveRequest?.end_date;
  const totalDays = conflictReport?.total_days ?? leaveRequest?.total_days ?? 0;
  const reason = leaveRequest?.reason || conflictReport?.reason || "No reason specified.";
  const status = conflictReport?.status || leaveRequest?.status || "PENDING";

  const conflictingTasks = conflictReport?.conflicting_tasks || [];
  const milestoneConflicts = conflictReport?.milestone_conflicts || [];
  const teamCoverage = conflictReport?.team_coverage || [];

  const isPending = status.toUpperCase() === "PENDING";

  const initials = applicantName
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div
      className="conflict-drawer-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="conflict-drawer-title"
      data-testid="leave-conflict-drawer"
    >
      <div className="conflict-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Drawer Header */}
        <div className="conflict-drawer-header">
          <div className="conflict-drawer-title-box">
            <span className="leave-triage-eyebrow">LEAVE CONFLICT TRIAGE</span>
            <h2 id="conflict-drawer-title" className="conflict-drawer-title">
              Request #{leaveId} · {leaveTypeName}
            </h2>
          </div>
          <button
            type="button"
            className="leave-modal-close-btn"
            onClick={onClose}
            aria-label="Close conflict drawer"
          >
            ×
          </button>
        </div>

        {/* Drawer Content */}
        <div className="conflict-drawer-body">
          {/* Applicant Summary */}
          <div className="applicant-summary-card">
            <div className="applicant-profile-row">
              <div className="applicant-avatar" aria-hidden="true">
                {initials}
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: "16px", fontWeight: "700", color: "#0f172a" }}>
                  {applicantName}
                </span>
                <span style={{ fontSize: "12px", color: "#64748b" }}>
                  Emp ID #{conflictReport?.employee_id || leaveRequest?.employee_id || leaveRequest?.emp_id}
                </span>
              </div>
              <div style={{ marginLeft: "auto" }}>
                <span
                  style={{
                    display: "inline-block",
                    padding: "3px 10px",
                    borderRadius: "9999px",
                    fontSize: "12px",
                    fontWeight: "700",
                    textTransform: "uppercase",
                    background: isPending ? "#fffbeb" : "#ecfdf5",
                    color: isPending ? "#92400e" : "#065f46",
                    border: `1px solid ${isPending ? "#fde68a" : "#a7f3d0"}`,
                  }}
                >
                  {status}
                </span>
              </div>
            </div>

            <div className="applicant-meta-grid">
              <div className="meta-item">
                <span className="meta-label">Dates</span>
                <span className="meta-value">
                  {startDate} → {endDate}
                </span>
              </div>
              <div className="meta-item">
                <span className="meta-label">Working Days</span>
                <span className="meta-value">
                  {totalDays} {totalDays === 1 ? "day" : "days"}
                </span>
              </div>
              <div className="meta-item">
                <span className="meta-label">Leave Type</span>
                <span className="meta-value">{leaveTypeName}</span>
              </div>
            </div>

            <div style={{ paddingTop: "10px", borderTop: "1px solid #f1f5f9" }}>
              <span className="meta-label">Reason</span>
              <p style={{ margin: "4px 0 0", fontSize: "13px", color: "#334155", lineHeight: "1.4" }}>
                {reason}
              </p>
            </div>
          </div>

          {/* Loading Indicator */}
          {isLoading && (
            <div style={{ textAlign: "center", padding: "32px", color: "#64748b" }} aria-busy="true">
              <span>⏳ Evaluating task and milestone conflicts...</span>
            </div>
          )}

          {/* Error Banner */}
          {isError && (
            <div className="leave-alert-error" role="alert">
              <span>⚠️ Failed to load conflict report: {error?.message || "Server error"}</span>
              <button
                type="button"
                className="leave-btn leave-btn-sm leave-btn-secondary"
                onClick={() => refetch()}
                style={{ marginLeft: "auto" }}
              >
                Retry
              </button>
            </div>
          )}

          {!isLoading && !isError && (
            <>
              {/* Conflicting Tasks Section (RED ROWS) */}
              <div className="conflicts-section" data-testid="conflicting-tasks-section">
                <div className="section-heading-row">
                  <h3 className="section-heading">
                    <span style={{ color: "#ef4444" }}>●</span> Conflicting Tasks ({conflictingTasks.length})
                  </h3>
                </div>

                {conflictingTasks.length === 0 ? (
                  <div
                    style={{
                      background: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                      borderRadius: "8px",
                      padding: "12px 16px",
                      fontSize: "13px",
                      color: "#166534",
                      fontWeight: "500",
                    }}
                  >
                    ✓ No conflicting tasks due during this leave window.
                  </div>
                ) : (
                  conflictingTasks.map((task) => (
                    <div
                      key={task.task_id}
                      className="conflict-task-row-red"
                      data-testid={`conflict-task-${task.task_id}`}
                    >
                      <div className="conflict-task-header">
                        <span className="conflict-task-title">
                          Task #{task.task_id}: {task.title}
                        </span>
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: "700",
                            background: "#fee2e2",
                            color: "#991b1b",
                            padding: "2px 6px",
                            borderRadius: "4px",
                            border: "1px solid #fecaca",
                          }}
                        >
                          {task.priority || "HIGH"}
                        </span>
                      </div>

                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                        <span className="conflict-task-due">
                          📅 Due Date: <strong>{task.due_date}</strong>
                        </span>
                        {task.milestone_title && (
                          <span style={{ fontSize: "12px", color: "#991b1b" }}>
                            Milestone: {task.milestone_title}
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Milestone Conflicts Section (AMBER ROWS) */}
              <div className="conflicts-section" data-testid="milestone-conflicts-section">
                <div className="section-heading-row">
                  <h3 className="section-heading">
                    <span style={{ color: "#f59e0b" }}>▲</span> Milestone Conflicts ({milestoneConflicts.length})
                  </h3>
                </div>

                {milestoneConflicts.length === 0 ? (
                  <div
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      borderRadius: "8px",
                      padding: "12px 16px",
                      fontSize: "13px",
                      color: "#64748b",
                    }}
                  >
                    No milestone deadlines occur during this leave period.
                  </div>
                ) : (
                  milestoneConflicts.map((ms) => (
                    <div
                      key={ms.milestone_id}
                      className="milestone-conflict-amber"
                      data-testid={`milestone-conflict-${ms.milestone_id}`}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span className="milestone-conflict-title">
                          Milestone: {ms.title}
                        </span>
                        <span style={{ fontSize: "12px", fontWeight: "700" }}>
                          Target: {ms.target_date}
                        </span>
                      </div>
                      <div className="milestone-conflict-meta">
                        <span>Project ID: #{ms.project_id}</span>
                        <span>
                          Open tasks assigned to applicant: <strong>{ms.open_tasks_assigned_to_applicant}</strong>
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Teammate Coverage Section */}
              <div className="conflicts-section" data-testid="coverage-matrix-section">
                <div className="section-heading-row">
                  <h3 className="section-heading">
                    👥 Teammate Coverage ({teamCoverage.length})
                  </h3>
                </div>
                <TaskCoverageMatrix coverage={teamCoverage} />
              </div>
            </>
          )}
        </div>

        {/* Drawer Actions */}
        <div className="conflict-drawer-footer">
          <button
            type="button"
            className="leave-btn leave-btn-secondary"
            onClick={onClose}
          >
            Close
          </button>

          {isPending && (
            <>
              <button
                type="button"
                className="leave-btn leave-btn-danger"
                onClick={() => onRejectClick(leaveRequest)}
                data-testid="drawer-reject-button"
              >
                Reject
              </button>
              <button
                type="button"
                className="leave-btn leave-btn-primary"
                onClick={() => onApproveClick(leaveRequest, conflictReport)}
                data-testid="drawer-approve-button"
              >
                Approve & Reassign
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
