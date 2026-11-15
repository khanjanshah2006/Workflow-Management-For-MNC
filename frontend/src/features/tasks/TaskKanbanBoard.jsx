import { useMemo } from "react";
import { getProgressFillClass, groupTasksForKanban } from "../../api/tasksApi";

/**
 * Columns displayed on the WorkSphere Kanban board in lifecycle sequence.
 */
const KANBAN_COLUMNS = [
  { id: "TODO", title: "To Do", dotClass: "col-dot-todo" },
  { id: "IN_PROGRESS", title: "In Progress", dotClass: "col-dot-inprogress" },
  { id: "BLOCKED", title: "Blocked", dotClass: "col-dot-blocked" },
  { id: "IN_REVIEW", title: "In Review", dotClass: "col-dot-review" },
  { id: "DONE", title: "Done", dotClass: "col-dot-done" },
];

/**
 * Format a date string (YYYY-MM-DD) into a human-friendly format.
 * @param {string|null} dateStr
 * @returns {string}
 */
function formatDate(dateStr) {
  if (!dateStr) return "—";
  try {
    const [year, month, day] = dateStr.split("-");
    if (!year || !month || !day) return dateStr;
    const date = new Date(Number(year), Number(month) - 1, Number(day));
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

/**
 * Checks if a task is past its due date and not yet completed.
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
 * Renders a priority badge with standard WorkSphere severity styles.
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
 * Renders a status badge with matching color dot.
 */
function StatusBadge({ status }) {
  const s = (status || "TODO").toUpperCase();
  const formatted = s === "REJECTED" ? "NEEDS REVISION" : s.replace("_", " ");
  const statusKey = s.toLowerCase();
  return (
    <span className={`badge-status badge-status-${statusKey}`}>
      <span className="badge-dot" aria-hidden="true" />
      {formatted}
    </span>
  );
}

/**
 * Visual progress bar component with colored fill.
 */
function ProgressBar({ pct, status }) {
  const clamped = Math.max(0, Math.min(100, Number(pct) || 0));
  const fillClass = getProgressFillClass(status);

  return (
    <div className="progress-bar-container" title={`${clamped}% completed`}>
      <div className="progress-track" aria-hidden="true">
        <div
          className={`progress-fill ${fillClass}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span className="progress-label">{clamped}%</span>
    </div>
  );
}

/**
 * Single task card rendered inside a Kanban column.
 */
function TaskCard({ task, onSelectTask, onUpdateProgress }) {
  const overdue = isOverdue(task.due_date, task.status);
  const canUpdateProgress =
    task.status === "TODO" ||
    task.status === "IN_PROGRESS" ||
    task.status === "BLOCKED";

  const handleKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelectTask(task.task_id);
    }
  };

  return (
    <div
      className="kanban-card"
      tabIndex={0}
      role="button"
      aria-label={`Task: ${task.title}, priority ${task.priority}, status ${task.status}`}
      onClick={() => onSelectTask(task.task_id)}
      onKeyDown={handleKeyDown}
    >
      <div className="kanban-card-top">
        <span className="kanban-card-id">#{task.task_id}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <StatusBadge status={task.status} />
          <PriorityBadge priority={task.priority} />
        </div>
      </div>

      <h3 className="kanban-card-title" title={task.title}>
        {task.title}
      </h3>

      {/* Blocker alert if task is blocked */}
      {task.status === "BLOCKED" && (
        <div className="kanban-blocker-chip">
          <span aria-hidden="true">⚠️</span>
          <span>
            <strong>Blocked:</strong>{" "}
            {task.blocker_reason
              ? task.blocker_reason
              : "Action required to unblock"}
          </span>
        </div>
      )}

      {/* Rejection alert if returned or status is REJECTED */}
      {(task.status === "REJECTED" ||
        (task.rejection_count > 0 && task.status !== "DONE")) && (
        <div className="kanban-rejection-chip">
          <span aria-hidden="true">↩</span>
          <span>
            {task.status === "REJECTED"
              ? "Needs Revision (Rejected)"
              : `Returned for fixes (v${task.rejection_count + 1})`}
          </span>
        </div>
      )}

      {/* Progress Bar */}
      <ProgressBar pct={task.progress_pct} status={task.status} />

      {/* Card Meta Footer */}
      <div className="kanban-card-meta">
        <span className="kanban-card-project" title={`Project ID: ${task.project_id}`}>
          Project #{task.project_id}
          {task.milestone_id ? ` · M#${task.milestone_id}` : ""}
        </span>

        <span
          className={`kanban-card-due ${overdue ? "overdue" : ""}`}
          title={overdue ? "Task is past its due date!" : "Target due date"}
        >
          <span aria-hidden="true">📅</span>
          {overdue ? `Overdue (${formatDate(task.due_date)})` : formatDate(task.due_date)}
        </span>
      </div>

      {/* Quick Action to update progress */}
      {canUpdateProgress && (
        <div className="kanban-card-actions">
          <button
            type="button"
            className="btn-card-quick-action"
            onClick={(e) => {
              e.stopPropagation();
              onUpdateProgress(task);
            }}
            aria-label={`Update progress for task ${task.title}`}
          >
            <span aria-hidden="true">⚡</span> Update Progress
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * TaskKanbanBoard Component
 *
 * Renders a 5-column Kanban board (TODO, IN_PROGRESS, BLOCKED, IN_REVIEW, DONE)
 * displaying task summaries with priority, progress, due dates, and quick actions.
 *
 * @param {Object} props
 * @param {Array<Object>} props.tasks TaskSummaryResponse items
 * @param {(taskId: number) => void} props.onSelectTask Opens detail drawer
 * @param {(task: Object) => void} props.onUpdateProgress Opens progress modal
 */
export default function TaskKanbanBoard({
  tasks = [],
  onSelectTask,
  onUpdateProgress,
}) {
  // Group tasks into columns with strict isolation of REJECTED tasks
  const groupedTasks = useMemo(() => {
    return groupTasksForKanban(tasks);
  }, [tasks]);

  return (
    <div className="kanban-board-container" aria-label="Task Kanban Board">
      {/* Dedicated Section for Tasks Needing Revision (REJECTED) */}
      {groupedTasks.REJECTED && groupedTasks.REJECTED.length > 0 && (
        <section
          className="kanban-rejected-section"
          aria-label={`Needs Revision: ${groupedTasks.REJECTED.length} rejected tasks`}
        >
          <header className="kanban-rejected-header">
            <div className="kanban-rejected-title-group">
              <span className="kanban-rejected-icon" aria-hidden="true">
                ↩
              </span>
              <div>
                <h2 className="kanban-rejected-title">
                  Needs Revision / Rejected ({groupedTasks.REJECTED.length})
                </h2>
                <p className="kanban-rejected-desc">
                  These tasks were returned with reviewer feedback and require revision before resubmission.
                </p>
              </div>
            </div>
            <span className="kanban-rejected-badge">
              {groupedTasks.REJECTED.length}{" "}
              {groupedTasks.REJECTED.length === 1 ? "task" : "tasks"}
            </span>
          </header>

          <div className="kanban-rejected-grid">
            {groupedTasks.REJECTED.map((task) => (
              <TaskCard
                key={task.task_id}
                task={task}
                onSelectTask={onSelectTask}
                onUpdateProgress={onUpdateProgress}
              />
            ))}
          </div>
        </section>
      )}

      <div className="kanban-columns-grid">
        {KANBAN_COLUMNS.map((column) => {
          const colTasks = groupedTasks[column.id] || [];

          return (
            <section
              key={column.id}
              className="kanban-column"
              aria-label={`${column.title} column with ${colTasks.length} tasks`}
            >
              {/* Column Header */}
              <header className="kanban-column-header">
                <div className="kanban-column-title-group">
                  <span
                    className={`column-indicator-dot ${column.dotClass}`}
                    aria-hidden="true"
                  />
                  <h2 className="kanban-column-title">{column.title}</h2>
                </div>
                <span className="kanban-column-count">{colTasks.length}</span>
              </header>

              {/* Cards List */}
              <div className="kanban-cards-list">
                {colTasks.length === 0 ? (
                  <div className="kanban-empty-column">
                    <span className="kanban-empty-icon" aria-hidden="true">
                      ◻
                    </span>
                    <span>No tasks</span>
                  </div>
                ) : (
                  colTasks.map((task) => (
                    <TaskCard
                      key={task.task_id}
                      task={task}
                      onSelectTask={onSelectTask}
                      onUpdateProgress={onUpdateProgress}
                    />
                  ))
                )}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
