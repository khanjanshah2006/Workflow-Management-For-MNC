import React, { useState, useMemo } from "react";
import { overdueChipLabel, sortOverdue } from "./pmRiskUtils";

/**
 * OverdueTasksTable Component (US-15 / S5)
 *
 * Displays sortable table of overdue project tasks with:
 * - Red chip "N days overdue"
 * - Priority, Status, Assignee, Due date, and Progress
 * - Reassign action triggering ReassignTaskModal
 */
export default function OverdueTasksTable({
  tasks = [],
  isLoading = false,
  onReassignTask,
}) {
  const [sortKey, setSortKey] = useState("days_overdue");
  const [sortDir, setSortDir] = useState("desc");

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "days_overdue" ? "desc" : "asc");
    }
  };

  const sortedTasks = useMemo(() => {
    return sortOverdue(tasks, sortKey, sortDir);
  }, [tasks, sortKey, sortDir]);

  const renderSortIndicator = (key) => {
    if (sortKey !== key) return <span className="pm-sort-icon">↕</span>;
    return <span className="pm-sort-icon active">{sortDir === "asc" ? "▲" : "▼"}</span>;
  };

  return (
    <div className="pm-card pm-table-card">
      <div className="pm-card-header pm-flex-between">
        <div>
          <span className="pm-card-eyebrow">ACTIONABLE ESCALATION</span>
          <h2 className="pm-section-title">Overdue Task Triage</h2>
        </div>
        <span className={`pm-badge ${tasks.length > 0 ? "pm-badge-danger" : "pm-badge-neutral"}`}>
          {tasks.length} {tasks.length === 1 ? "Overdue Task" : "Overdue Tasks"}
        </span>
      </div>

      {isLoading ? (
        <div className="pm-loading-state">Loading overdue tasks...</div>
      ) : sortedTasks.length === 0 ? (
        <div className="pm-empty-state">
          <div className="pm-empty-icon">✓</div>
          <p className="pm-empty-title">Zero Overdue Tasks</p>
          <p className="pm-empty-desc">
            All project tasks are on schedule or completed ahead of their target deadlines.
          </p>
        </div>
      ) : (
        <div className="pm-table-responsive">
          <table className="pm-table" aria-label="Overdue tasks table">
            <thead>
              <tr>
                <th scope="col" onClick={() => handleSort("title")} className="pm-th-sortable">
                  Task {renderSortIndicator("title")}
                </th>
                <th scope="col" onClick={() => handleSort("assignee_name")} className="pm-th-sortable">
                  Assignee {renderSortIndicator("assignee_name")}
                </th>
                <th scope="col" onClick={() => handleSort("priority")} className="pm-th-sortable">
                  Priority {renderSortIndicator("priority")}
                </th>
                <th scope="col" onClick={() => handleSort("due_date")} className="pm-th-sortable">
                  Due Date {renderSortIndicator("due_date")}
                </th>
                <th scope="col" onClick={() => handleSort("days_overdue")} className="pm-th-sortable">
                  Overdue By {renderSortIndicator("days_overdue")}
                </th>
                <th scope="col" onClick={() => handleSort("progress_pct")} className="pm-th-sortable">
                  Progress {renderSortIndicator("progress_pct")}
                </th>
                <th scope="col" className="pm-th-action">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedTasks.map((task) => {
                const priorityLower = (task.priority || "medium").toLowerCase();
                const isCritical = task.priority === "CRITICAL";

                return (
                  <tr key={task.task_id} className={isCritical ? "pm-tr-critical" : ""}>
                    <td className="pm-cell-task">
                      <div className="pm-task-title-cell">
                        <span className="pm-task-id">#{task.task_id}</span>
                        <strong className="pm-task-name">{task.title}</strong>
                        {task.milestone_title && (
                          <span className="pm-task-milestone">📍 {task.milestone_title}</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className="pm-assignee-text">
                        {task.assignee_name || "Unassigned"}
                      </span>
                    </td>
                    <td>
                      <span className={`badge-pill badge-priority-${priorityLower}`}>
                        {task.priority || "MEDIUM"}
                      </span>
                    </td>
                    <td>
                      <span className="pm-date-text">
                        {task.due_date
                          ? new Date(task.due_date).toLocaleDateString(undefined, {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                            })
                          : "—"}
                      </span>
                    </td>
                    <td>
                      {/* Red chip: "N days overdue" */}
                      <span className="pm-chip pm-chip-overdue-red">
                        {overdueChipLabel(task.days_overdue)}
                      </span>
                    </td>
                    <td>
                      <div className="pm-progress-inline">
                        <div className="pm-progress-bar-sm">
                          <div
                            className="pm-progress-fill-sm"
                            style={{ width: `${Math.min(100, Math.max(0, task.progress_pct || 0))}%` }}
                          />
                        </div>
                        <span className="pm-progress-inline-val">{task.progress_pct || 0}%</span>
                      </div>
                    </td>
                    <td className="pm-cell-action">
                      <button
                        type="button"
                        className="pm-btn pm-btn-reassign"
                        onClick={() => onReassignTask && onReassignTask(task)}
                        title={`Reassign Task #${task.task_id}`}
                      >
                        Reassign
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
  );
}
