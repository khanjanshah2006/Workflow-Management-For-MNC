import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getTaskDetail, getProgressFillClass } from "../../api/tasksApi";

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
 */
export default function TaskDetailDrawer({
  taskId,
  onClose,
  onUpdateProgress,
}) {
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
              {canUpdateProgress && (
                <button
                  type="button"
                  className="btn-drawer-primary"
                  onClick={() => onUpdateProgress(task)}
                >
                  <span aria-hidden="true">⚡</span> Update Progress
                </button>
              )}
            </div>

            {/* Drawer Body */}
            <div className="drawer-body">
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

              {/* Review Rejection Banner */}
              {(task.rejection_count > 0 || task.rejection_feedback) && (
                <div className="drawer-alert drawer-alert-rejected" role="alert">
                  <span className="drawer-alert-icon" aria-hidden="true">
                    ↩
                  </span>
                  <div className="drawer-alert-content">
                    <div className="drawer-alert-title">
                      Review Feedback · Returned ({task.rejection_count}{" "}
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

              {/* Task Comments Boundary (Clean integration point for Issue #80 TaskCommentThread) */}
              <div className="drawer-comments-boundary" aria-label="Task Discussion">
                <div className="comments-boundary-header">
                  <h3 className="comments-boundary-title">
                    <span aria-hidden="true">💬</span> Task Discussion
                  </h3>
                  <span className="comments-boundary-badge">Issue #80 Integration</span>
                </div>
                <p className="comments-boundary-notice">
                  The threaded discussion feed and file attachment preview are managed by{" "}
                  <strong>TaskCommentThread</strong> (Issue #80). When Issue #80 is merged,
                  the comment thread will mount directly into this conversation container.
                </p>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
