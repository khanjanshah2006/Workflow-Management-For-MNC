import React, { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { reallocateLeaveTasks, approveLeave } from "../../api/leaveApi";
import { buildReallocationPayload, coverageLabel } from "./leaveTriageUtils";

/**
 * Calculates tomorrow relative to a due date string (YYYY-MM-DD).
 * @param {string} dateStr
 * @returns {string}
 */
function getMinExtensionDate(dateStr) {
  if (!dateStr) return "";
  const match = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return "";
  const year = parseInt(match[1], 10);
  const month = parseInt(match[2], 10) - 1;
  const day = parseInt(match[3], 10);
  const nextDay = new Date(Date.UTC(year, month, day + 1));
  return nextDay.toISOString().split("T")[0];
}

/**
 * ApproveLeaveModal Component (US-14, US-16 / Issue #106)
 *
 * Implements the atomic Approve & Reassign sequence:
 * Step 1: Call POST /reallocate-tasks first if any conflicting tasks have actions.
 *         On 400, display message next to task identified by task_id and DO NOT approve.
 * Step 2: Call PUT /approve only after successful reallocation.
 *         If approval fails after reallocation succeeds, display:
 *         "Tasks were reallocated, but the leave is still pending: {reason}".
 * Step 3: Success toast (e.g. "Leave approved · Task #42 reassigned to John Matrix").
 */
export default function ApproveLeaveModal({
  isOpen = false,
  leaveRequest,
  conflictReport,
  onClose,
  onSuccess,
}) {
  const queryClient = useQueryClient();

  // Task decisions state: { [taskId]: { action, newAssigneeId, newDueDate, reason } }
  const [taskDecisions, setTaskDecisions] = useState({});
  const [reviewRemarks, setReviewRemarks] = useState("");

  // Error handling states
  const [taskErrors, setTaskErrors] = useState({});
  const [globalError, setGlobalError] = useState(null);
  const [partialApprovalError, setPartialApprovalError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen || !leaveRequest) return null;

  const conflictingTasks = conflictReport?.conflicting_tasks || [];
  const teamCoverage = conflictReport?.team_coverage || [];
  const applicantName =
    conflictReport?.employee_name || leaveRequest.employee_name || `Employee #${leaveRequest.employee_id || leaveRequest.emp_id}`;

  const handleActionChange = (taskId, action) => {
    setTaskDecisions((prev) => {
      const current = prev[taskId] || {};
      const updated = { ...current, action };

      // Initialize default assignee if switching to REASSIGN
      if (action === "REASSIGN" && !updated.newAssigneeId) {
        const firstAvailable = teamCoverage.find((m) => m.is_available_for_reassignment);
        if (firstAvailable) {
          updated.newAssigneeId = String(firstAvailable.emp_id);
        }
      }

      // Initialize default date if switching to EXTEND_DEADLINE
      if (action === "EXTEND_DEADLINE" && !updated.newDueDate) {
        const task = conflictingTasks.find((t) => t.task_id === taskId);
        if (task?.due_date) {
          updated.newDueDate = getMinExtensionDate(task.due_date);
        }
      }

      return {
        ...prev,
        [taskId]: updated,
      };
    });

    // Clear error for this task
    setTaskErrors((prev) => {
      const next = { ...prev };
      delete next[taskId];
      return next;
    });
    setGlobalError(null);
  };

  const handleDecisionFieldChange = (taskId, field, value) => {
    setTaskDecisions((prev) => ({
      ...prev,
      [taskId]: {
        ...(prev[taskId] || {}),
        [field]: value,
      },
    }));

    setTaskErrors((prev) => {
      const next = { ...prev };
      delete next[taskId];
      return next;
    });
    setGlobalError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setTaskErrors({});
    setGlobalError(null);
    setPartialApprovalError(null);
    setIsSubmitting(true);

    try {
      // Step 1: Reallocate tasks first if at least one task has action
      const reallocationPayload = buildReallocationPayload(taskDecisions);
      const hasReallocations = reallocationPayload.actions.length > 0;
      let reallocationResult = null;

      if (hasReallocations) {
        try {
          reallocationResult = await reallocateLeaveTasks(leaveRequest.leave_id, reallocationPayload);
        } catch (err) {
          // Reallocation failed with HTTP 400 or validation error
          const taskId = err?.data?.task_id || err?.task_id;
          const detailMsg = err?.data?.detail || err?.message || "Reallocation failed";
          if (taskId) {
            setTaskErrors((prev) => ({ ...prev, [taskId]: detailMsg }));
          } else {
            setGlobalError(detailMsg);
          }
          setIsSubmitting(false);
          // Do NOT proceed with leave approval!
          return;
        }
      }

      // Step 2: Approve leave only after successful reallocation
      try {
        await approveLeave(leaveRequest.leave_id, {
          review_remarks: reviewRemarks.trim() || undefined,
        });
      } catch (approvalErr) {
        // If approval fails after reallocation succeeded
        if (hasReallocations) {
          const reason =
            approvalErr?.data?.detail ||
            approvalErr?.message ||
            "Approval decision rejected by server";
          setPartialApprovalError(`Tasks were reallocated, but the leave is still pending: ${reason}`);
        } else {
          setGlobalError(approvalErr?.data?.detail || approvalErr?.message || "Failed to approve leave request.");
        }
        setIsSubmitting(false);
        return;
      }

      // Step 3: Successful completion toast
      let toastMessage = `Leave approved for ${applicantName}`;
      if (reallocationResult?.reassigned?.length > 0) {
        const first = reallocationResult.reassigned[0];
        const targetMember = teamCoverage.find((m) => m.emp_id === first.to_emp_id);
        const assigneeName = targetMember?.full_name || `Teammate #${first.to_emp_id}`;
        toastMessage = `Leave approved · Task #${first.task_id} reassigned to ${assigneeName}`;
      } else if (reallocationResult?.extended?.length > 0) {
        const first = reallocationResult.extended[0];
        toastMessage = `Leave approved · Task #${first.task_id} extended to ${first.new_due_date}`;
      }

      // Refresh cache
      queryClient.invalidateQueries({ queryKey: ["leave"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });

      if (onSuccess) {
        onSuccess({ toastMessage });
      }
      onClose();
    } catch (err) {
      setGlobalError(err?.message || "An unexpected error occurred during leave approval.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="approve-modal-title"
      data-testid="approve-leave-modal"
    >
      <div
        className="leave-modal-dialog"
        style={{ maxWidth: "720px" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="leave-modal-header">
          <div>
            <h2 id="approve-modal-title" className="leave-modal-title">
              Approve Leave & Task Reallocation
            </h2>
            <span style={{ fontSize: "13px", color: "#64748b" }}>
              Request #{leaveRequest.leave_id} · {applicantName} ({leaveRequest.start_date} to {leaveRequest.end_date})
            </span>
          </div>
          <button
            type="button"
            className="leave-modal-close-btn"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close approval modal"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="leave-modal-body">
            {/* Global Error Banner */}
            {globalError && (
              <div className="leave-alert-error" role="alert" data-testid="approve-global-error">
                <span>⚠️ {globalError}</span>
              </div>
            )}

            {/* Critical Partial Approval Failure Banner */}
            {partialApprovalError && (
              <div
                className="leave-alert-error"
                role="alert"
                style={{ background: "#fff1f2", borderColor: "#f43f5e", color: "#9f1239" }}
                data-testid="partial-approval-error"
              >
                <span>⚠️ {partialApprovalError}</span>
              </div>
            )}

            {/* Conflicting Tasks Decisions */}
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, fontSize: "14px", fontWeight: "700", color: "#1e293b" }}>
                  Conflicting Tasks Decision ({conflictingTasks.length})
                </h3>
                <span style={{ fontSize: "12px", color: "#64748b" }}>
                  Choose coverage action for each task
                </span>
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
                  }}
                >
                  ✓ There are no conflicting tasks due during this leave period. You can approve directly.
                </div>
              ) : (
                conflictingTasks.map((task) => {
                  const decision = taskDecisions[task.task_id] || { action: "LEAVE_AS_IS" };
                  const currentAction = decision.action || "LEAVE_AS_IS";
                  const taskError = taskErrors[task.task_id];
                  const minExtensionDate = getMinExtensionDate(task.due_date);

                  return (
                    <div
                      key={task.task_id}
                      className={`task-reallocation-card ${taskError ? "has-error" : ""}`}
                      data-testid={`reallocate-card-${task.task_id}`}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px" }}>
                        <div>
                          <strong style={{ fontSize: "14px", color: "#0f172a" }}>
                            Task #{task.task_id}: {task.title}
                          </strong>
                          <div style={{ fontSize: "12px", color: "#64748b", marginTop: "2px" }}>
                            Current Due Date: <span style={{ fontWeight: "700", color: "#b91c1c" }}>{task.due_date}</span> · Priority: {task.priority}
                          </div>
                        </div>
                      </div>

                      {/* Action Radio Choices: 1. Reassign to, 2. Extend deadline, 3. Leave as is */}
                      <div className="action-selector-group">
                        <label
                          className={`action-radio-label ${currentAction === "LEAVE_AS_IS" ? "selected" : ""}`}
                        >
                          <input
                            type="radio"
                            name={`action-${task.task_id}`}
                            value="LEAVE_AS_IS"
                            checked={currentAction === "LEAVE_AS_IS"}
                            onChange={() => handleActionChange(task.task_id, "LEAVE_AS_IS")}
                            disabled={isSubmitting}
                          />
                          <span>Leave as is</span>
                        </label>

                        <label
                          className={`action-radio-label ${currentAction === "REASSIGN" ? "selected" : ""}`}
                        >
                          <input
                            type="radio"
                            name={`action-${task.task_id}`}
                            value="REASSIGN"
                            checked={currentAction === "REASSIGN"}
                            onChange={() => handleActionChange(task.task_id, "REASSIGN")}
                            disabled={isSubmitting}
                            data-testid={`radio-reassign-${task.task_id}`}
                          />
                          <span>Reassign to</span>
                        </label>

                        <label
                          className={`action-radio-label ${currentAction === "EXTEND_DEADLINE" ? "selected" : ""}`}
                        >
                          <input
                            type="radio"
                            name={`action-${task.task_id}`}
                            value="EXTEND_DEADLINE"
                            checked={currentAction === "EXTEND_DEADLINE"}
                            onChange={() => handleActionChange(task.task_id, "EXTEND_DEADLINE")}
                            disabled={isSubmitting}
                            data-testid={`radio-extend-${task.task_id}`}
                          />
                          <span>Extend deadline</span>
                        </label>
                      </div>

                      {/* Reassign Field Row */}
                      {currentAction === "REASSIGN" && (
                        <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "4px" }}>
                          <label
                            htmlFor={`assignee-select-${task.task_id}`}
                            style={{ fontSize: "12px", fontWeight: "600", color: "#334155" }}
                          >
                            Assign to Teammate *
                          </label>
                          <select
                            id={`assignee-select-${task.task_id}`}
                            className="leave-select"
                            value={decision.newAssigneeId || ""}
                            onChange={(e) => handleDecisionFieldChange(task.task_id, "newAssigneeId", e.target.value)}
                            disabled={isSubmitting}
                            required
                            data-testid={`assignee-select-${task.task_id}`}
                          >
                            <option value="">Select available teammate...</option>
                            {teamCoverage.map((m) => {
                              const label = coverageLabel(m);
                              const isAvail = m.is_available_for_reassignment;
                              return (
                                <option
                                  key={m.emp_id}
                                  value={m.emp_id}
                                  disabled={!isAvail}
                                >
                                  {m.full_name} {isAvail ? `(${label})` : `(Disabled: ${label})`}
                                </option>
                              );
                            })}
                          </select>

                          <input
                            type="text"
                            className="leave-input"
                            placeholder="Reassignment reason (min 10 characters)..."
                            value={decision.reason || ""}
                            onChange={(e) => handleDecisionFieldChange(task.task_id, "reason", e.target.value)}
                            disabled={isSubmitting}
                            data-testid={`reassign-reason-${task.task_id}`}
                          />
                        </div>
                      )}

                      {/* Extend Deadline Field Row */}
                      {currentAction === "EXTEND_DEADLINE" && (
                        <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "4px" }}>
                          <label
                            htmlFor={`extend-date-${task.task_id}`}
                            style={{ fontSize: "12px", fontWeight: "600", color: "#334155" }}
                          >
                            New Due Date * (min: current due date + 1 day)
                          </label>
                          <input
                            id={`extend-date-${task.task_id}`}
                            type="date"
                            className="leave-input"
                            min={minExtensionDate}
                            value={decision.newDueDate || ""}
                            onChange={(e) => handleDecisionFieldChange(task.task_id, "newDueDate", e.target.value)}
                            disabled={isSubmitting}
                            required
                            data-testid={`extend-date-input-${task.task_id}`}
                          />

                          <input
                            type="text"
                            className="leave-input"
                            placeholder="Extension reason (min 10 characters)..."
                            value={decision.reason || ""}
                            onChange={(e) => handleDecisionFieldChange(task.task_id, "reason", e.target.value)}
                            disabled={isSubmitting}
                            data-testid={`extend-reason-${task.task_id}`}
                          />
                        </div>
                      )}

                      {/* Task-specific Error Message */}
                      {taskError && (
                        <div
                          className="reallocation-inline-error"
                          role="alert"
                          data-testid={`task-error-${task.task_id}`}
                        >
                          ⚠️ {taskError}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>

            {/* Optional Approval Remarks */}
            <div className="leave-form-group" style={{ marginTop: "12px" }}>
              <label htmlFor="approve-remarks" className="leave-label">
                Approval Remarks (Optional)
              </label>
              <textarea
                id="approve-remarks"
                className="leave-textarea"
                rows={2}
                placeholder="Add optional notes for the employee..."
                value={reviewRemarks}
                onChange={(e) => setReviewRemarks(e.target.value)}
                disabled={isSubmitting}
                data-testid="approve-remarks-input"
              />
            </div>
          </div>

          <div className="leave-modal-footer">
            <button
              type="button"
              className="leave-btn leave-btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="leave-btn leave-btn-primary"
              disabled={isSubmitting}
              data-testid="confirm-approve-button"
            >
              {isSubmitting ? "Processing..." : "Confirm & Approve"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
