import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getTaskDetail, getProgressFillClass } from "../../api/tasksApi";
import RejectionFeedbackBanner from "./components/RejectionFeedbackBanner";
import SubmitTaskModal from "./components/SubmitTaskModal";
import ResubmitTaskModal from "./components/ResubmitTaskModal";
import TaskCommentThread from "./components/TaskCommentThread";

/**
 * Formats an ISO date/timestamp into a readable string.
 * @param {string|null} dateStr
 * @param {boolean} [includeTime=false]
 * @returns {string}
 */
function formatDateTime(dateStr, includeTime = false) {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const options = {
      month: "short",
      day: "numeric",
      year: "numeric",
    };
    if (includeTime) {
      options.hour = "2-digit";
      options.minute = "2-digit";
    }
    return d.toLocaleDateString("en-US", options);
  } catch {
    return dateStr;
  }
}

/**
 * Checks if a task is overdue.
 * @param {string|null} dueDateStr
 * @param {string} status
 * @returns {boolean}
 */
function isOverdue(dueDateStr, status) {
  if (!dueDateStr || status === "DONE") return false;
  try {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const [year, month, day] = dueDateStr.split("-");
    const due = new Date(Number(year), Number(month) - 1, Number(day));
    return due < today;
  } catch {
    return false;
  }
}

/**
 * WorkSphere Priority Badge
 */
function PriorityBadge({ priority }) {
  const p = (priority || "MEDIUM").toUpperCase();
  const classes = {
    CRITICAL: "badge-priority-critical",
    HIGH: "badge-priority-high",
    MEDIUM: "badge-priority-medium",
    LOW: "badge-priority-low",
  };
  return (
    <span className={`badge-priority ${classes[p] || classes.MEDIUM}`}>
      {p}
    </span>
  );
}

/**
 * WorkSphere Status Badge
 */
function StatusBadge({ status }) {
  const s = (status || "TODO").toUpperCase();
  const formatted = s.replace("_", " ");
  const statusKey = s.toLowerCase();
  return (
    <span className={`badge-status badge-status-${statusKey}`}>
      <span className="badge-dot" aria-hidden="true" />
      {formatted}
    </span>
  );
}

/**
 * TaskDetailDrawer Component (US-32)
 *
 * Slide-out drawer displaying comprehensive task details:
 * - Title, description, status, priority, and progress
 * - Blocker information and warning banner when flagged BLOCKED
 * - Rejection count and feedback from prior reviews
 * - Project and milestone context
 * - Assignee and creator profiles
 * - Start date, due date, completion timestamp, and audit timestamps
 * - Integration boundary for Issue #80 (TaskCommentThread)
 *
 * @param {Object} props
 * @param {number|null} props.taskId Active task ID to display (or null to hide)
 * @param {() => void} props.onClose Callback to close drawer
 * @param {(task: Object) => void} props.onUpdateProgress Callback to launch progress modal
 * @param {(updatedTask: Object) => void} [props.onTaskUpdated] Callback when task status/details change
 */
export default function TaskDetailDrawer({
  taskId,
  onClose,
  onUpdateProgress,
  onTaskUpdated,
}) {
  const queryClient = useQueryClient();
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);
  const [isResubmitModalOpen, setIsResubmitModalOpen] = useState(false);
  const [actionToast, setActionToast] = useState(null);

  // Auto-dismiss transient action toast
  useEffect(() => {
    if (!actionToast) return;
    const timer = setTimeout(() => setActionToast(null), 4000);
    return () => clearTimeout(timer);
  }, [actionToast]);

  // Close drawer on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    if (taskId) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [taskId, onClose]);

  // TanStack Query for full task details
  const {
    data: task,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["task-detail", taskId],
    queryFn: () => getTaskDetail(taskId),
    enabled: Boolean(taskId),
    retry: 1,
  });

  if (!taskId) return null;

  const overdue = task ? isOverdue(task.due_date, task.status) : false;
  const canUpdateProgress =
    task &&
    (task.status === "TODO" ||
      task.status === "IN_PROGRESS" ||
      task.status === "BLOCKED");

  return (
    <div
      className="drawer-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="drawer-task-title"
    >
      <div
        className="task-drawer"
        onClick={(e) => e.stopPropagation()}
        tabIndex={-1}
      >
        {/* Loading State */}
        {isLoading && (
          <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="skeleton-box" style={{ height: 32, width: "40%" }} />
            <div className="skeleton-box" style={{ height: 24, width: "80%" }} />
            <div className="skeleton-box" style={{ height: 80, width: "100%" }} />
            <div className="skeleton-box" style={{ height: 160, width: "100%" }} />
          </div>
        )}

        {/* Error State */}
        {!isLoading && isError && (
          <div style={{ padding: 32, textAlign: "center" }}>
            <span style={{ fontSize: 32 }}>⚠️</span>
            <h3 style={{ margin: "12px 0 6px", color: "#991b1b" }}>
              Unable to load task details
            </h3>
            <p style={{ fontSize: 13, color: "#64748b", marginBottom: 16 }}>
              {error?.message || "An unexpected error occurred while fetching the task."}
            </p>
            <button
              type="button"
              className="btn-retry"
              onClick={() => refetch()}
            >
              Retry
            </button>
            <button
              type="button"
              className="btn-secondary"
              style={{ marginLeft: 8 }}
              onClick={onClose}
            >
              Close
            </button>
          </div>
        )}

        {/* Loaded Detail Content */}
        {!isLoading && !isError && task && (
          <>
            {/* Drawer Header */}
            <header className="drawer-header">
              <div className="drawer-title-block">
                <span className="drawer-task-id-badge">
                  Task #{task.task_id}
                </span>
                <h2 id="drawer-task-title" className="drawer-title">
                  {task.title}
                </h2>
                <div className="drawer-badges-row">
                  <StatusBadge status={task.status} />
                  <PriorityBadge priority={task.priority} />
                  {task.project?.name && (
                    <span
                      style={{
                        fontSize: 11.5,
                        fontWeight: 600,
                        color: "#475569",
                        background: "#f1f5f9",
                        padding: "2.5px 8px",
                        borderRadius: 6,
                      }}
                    >
                      📁 {task.project.name}
                    </span>
                  )}
                </div>
              </div>
              <button
                type="button"
                className="btn-drawer-close"
                onClick={onClose}
                aria-label="Close task details drawer"
              >
                ✕
              </button>
            </header>

            {/* Drawer Action Bar */}
            <div className="drawer-action-bar">
              <div style={{ fontSize: 12, color: "#64748b" }}>
                <span>Team #{task.team_id}</span>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                {canUpdateProgress && (
                  <button
                    type="button"
                    className="btn-drawer-primary"
                    onClick={() => onUpdateProgress(task)}
                  >
                    <span aria-hidden="true">⚡</span> Update Progress
                  </button>
                )}

                {/* Submit Task for Review (US-11: visible strictly for IN_PROGRESS) */}
                {task.status === "IN_PROGRESS" && (
                  <button
                    type="button"
                    className="btn-drawer-submit"
                    onClick={() => setIsSubmitModalOpen(true)}
                    aria-label="Submit task deliverable for review"
                  >
                    <span aria-hidden="true">📤</span> Submit for Review
                  </button>
                )}

                {/* Revise and Resubmit Task (US-13: visible strictly for REJECTED) */}
                {task.status === "REJECTED" && (
                  <button
                    type="button"
                    className="btn-drawer-resubmit"
                    onClick={() => setIsResubmitModalOpen(true)}
                    aria-label="Revise and resubmit rejected task"
                  >
                    <span aria-hidden="true">🔄</span> Revise &amp; Resubmit
                  </button>
                )}
              </div>
            </div>

            {/* Drawer Body */}
            <div className="drawer-body">
              {/* Action Feedback Toast */}
              {actionToast && (
                <div
                  className={`tasks-toast ${
                    actionToast.type === "error" ? "toast-error" : "toast-success"
                  }`}
                  style={{ position: "static", marginBottom: 12, width: "100%" }}
                  role="status"
                >
                  <span aria-hidden="true">
                    {actionToast.type === "error" ? "⚠️" : "✓"}
                  </span>
                  <span>{actionToast.message}</span>
                </div>
              )}

              {/* Blocker Alert Banner */}
              {(task.status === "BLOCKED" || task.blocker_reason) && (
                <div className="drawer-alert drawer-alert-blocked" role="alert">
                  <span className="drawer-alert-icon" aria-hidden="true">
                    🚨
                  </span>
                  <div className="drawer-alert-content">
                    <div className="drawer-alert-title">Task is Blocked</div>
                    <div>
                      {task.blocker_reason || "No blocker details provided."}
                    </div>
                  </div>
                </div>
              )}

              {/* Rejection Feedback Banner (US-13: visible strictly on REJECTED) */}
              <RejectionFeedbackBanner
                task={task}
                onOpenResubmit={() => setIsResubmitModalOpen(true)}
              />

              {/* Historical Review Feedback for non-REJECTED tasks that had prior rejections */}
              {task.status !== "REJECTED" &&
                (task.rejection_count > 0 || task.rejection_feedback) && (
                  <div className="drawer-alert drawer-alert-rejected" role="alert">
                    <span className="drawer-alert-icon" aria-hidden="true">
                      ↩
                    </span>
                    <div className="drawer-alert-content">
                      <div className="drawer-alert-title">
                        Prior Review Feedback · Returned ({task.rejection_count}{" "}
                        {task.rejection_count === 1 ? "time" : "times"})
                      </div>
                      <div>
                        {task.rejection_feedback ||
                          "Changes requested by reviewer before sign-off."}
                      </div>
                    </div>
                  </div>
                )}

              {/* Progress Section */}
              <div className="drawer-section">
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <h3 className="drawer-section-title">Current Progress</h3>
                  <span style={{ fontSize: 12.5, fontWeight: 700, color: "#1e293b" }}>
                    {task.progress_pct}%
                  </span>
                </div>
                <div className="progress-track" style={{ height: 8 }}>
                  <div
                    className={`progress-fill ${getProgressFillClass(task.status)}`}
                    style={{ width: `${task.progress_pct}%` }}
                  />
                </div>
              </div>

              {/* Task Description */}
              <div className="drawer-section">
                <h3 className="drawer-section-title">Description</h3>
                <p className="drawer-description-text">
                  {task.description && task.description.trim()
                    ? task.description
                    : "No detailed description provided for this task."}
                </p>
              </div>

              {/* Project & Milestone Context */}
              <div className="drawer-section">
                <h3 className="drawer-section-title">Project & Context</h3>
                <div className="drawer-meta-grid">
                  <div className="drawer-meta-item">
                    <span className="meta-label">Project</span>
                    <span className="meta-value">
                      {task.project ? task.project.name : `Project #${task.project_id}`}
                    </span>
                  </div>
                  <div className="drawer-meta-item">
                    <span className="meta-label">Milestone</span>
                    <span className="meta-value">
                      {task.milestone
                        ? task.milestone.title
                        : task.milestone_id
                        ? `Milestone #${task.milestone_id}`
                        : "None specified"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Assignment & Creator Details */}
              <div className="drawer-section">
                <h3 className="drawer-section-title">People</h3>
                <div className="drawer-meta-grid">
                  <div className="drawer-meta-item">
                    <span className="meta-label">Assigned To</span>
                    {task.assignee ? (
                      <div className="meta-user-chip">
                        <span className="meta-user-name">
                          {task.assignee.full_name}
                        </span>
                        <span className="meta-user-role">
                          {task.assignee.designation || task.assignee.email}
                        </span>
                      </div>
                    ) : (
                      <span className="meta-value" style={{ color: "#94a3b8" }}>
                        Unassigned
                      </span>
                    )}
                  </div>

                  <div className="drawer-meta-item">
                    <span className="meta-label">Created By</span>
                    {task.creator ? (
                      <div className="meta-user-chip">
                        <span className="meta-user-name">
                          {task.creator.full_name}
                        </span>
                        <span className="meta-user-role">
                          {task.creator.designation || task.creator.email}
                        </span>
                      </div>
                    ) : (
                      <span className="meta-value" style={{ color: "#94a3b8" }}>
                        System / Unknown
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Dates & Timeline */}
              <div className="drawer-section">
                <h3 className="drawer-section-title">Dates & Timeline</h3>
                <div className="drawer-meta-grid">
                  <div className="drawer-meta-item">
                    <span className="meta-label">Start Date</span>
                    <span className="meta-value">
                      {formatDateTime(task.start_date)}
                    </span>
                  </div>
                  <div className="drawer-meta-item">
                    <span className="meta-label">Target Due Date</span>
                    <span
                      className="meta-value"
                      style={{ color: overdue ? "#dc2626" : undefined }}
                    >
                      {formatDateTime(task.due_date)}
                      {overdue && " (Overdue)"}
                    </span>
                  </div>
                  {task.completed_at && (
                    <div className="drawer-meta-item">
                      <span className="meta-label">Completed At</span>
                      <span className="meta-value" style={{ color: "#16a34a" }}>
                        {formatDateTime(task.completed_at, true)}
                      </span>
                    </div>
                  )}
                  <div className="drawer-meta-item">
                    <span className="meta-label">Created At</span>
                    <span className="meta-value">
                      {formatDateTime(task.created_at, true)}
                    </span>
                  </div>
                  <div className="drawer-meta-item">
                    <span className="meta-label">Last Updated</span>
                    <span className="meta-value">
                      {formatDateTime(task.updated_at, true)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Task Comments Discussion Thread (US-33) */}
              <div className="drawer-comments-section" aria-label="Task Discussion">
                <TaskCommentThread taskId={taskId} />
              </div>
            </div>

            {/* Modals for Task Submission & Resubmission (US-11 & US-13) */}
            {isSubmitModalOpen && (
              <SubmitTaskModal
                task={task}
                onClose={() => setIsSubmitModalOpen(false)}
                onSuccess={(result) => {
                  queryClient.invalidateQueries({ queryKey: ["task-detail", taskId] });
                  queryClient.invalidateQueries({ queryKey: ["my-tasks"] });
                  refetch();
                  setActionToast({
                    type: "success",
                    message:
                      result?.message ||
                      "Task deliverable submitted for review! Status updated to IN_REVIEW.",
                  });
                  if (onTaskUpdated) {
                    onTaskUpdated({
                      ...task,
                      status: "IN_REVIEW",
                    });
                  }
                }}
              />
            )}

            {isResubmitModalOpen && (
              <ResubmitTaskModal
                task={task}
                onClose={() => setIsResubmitModalOpen(false)}
                onSuccess={(result) => {
                  // Confirm returned status is IN_REVIEW from TaskResubmitResponse
                  const updatedStatus =
                    result?.status === "IN_REVIEW" ? result.status : "IN_REVIEW";
                  queryClient.invalidateQueries({ queryKey: ["task-detail", taskId] });
                  queryClient.invalidateQueries({ queryKey: ["my-tasks"] });
                  refetch();
                  setActionToast({
                    type: "success",
                    message:
                      result?.message ||
                      "Revised task resubmitted for review! Status updated to IN_REVIEW.",
                  });
                  if (onTaskUpdated) {
                    // TaskResubmitResponse does not include project, milestone, assignee, or creator objects.
                    // Preserve original task details and update status cleanly.
                    onTaskUpdated({
                      ...task,
                      status: updatedStatus,
                    });
                  }
                }}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
