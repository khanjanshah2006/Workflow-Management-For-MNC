import React from "react";

/**
 * BlockedTasksList Component (US-38 / S5)
 *
 * Displays currently blocked project tasks with:
 * - Blocker reason explanation
 * - Blocked-since timestamp
 * - Assignee information
 */
export default function BlockedTasksList({ tasks = [], isLoading = false }) {
  return (
    <div className="pm-card pm-blocked-card">
      <div className="pm-card-header pm-flex-between">
        <div>
          <span className="pm-card-eyebrow">IMPEDIMENT TRIAGE</span>
          <h2 className="pm-section-title">Blocked Tasks</h2>
        </div>
        <span className={`pm-badge ${tasks.length > 0 ? "pm-badge-warning" : "pm-badge-neutral"}`}>
          {tasks.length} {tasks.length === 1 ? "Blocked Task" : "Blocked Tasks"}
        </span>
      </div>

      {isLoading ? (
        <div className="pm-loading-state">Loading blocked tasks...</div>
      ) : tasks.length === 0 ? (
        <div className="pm-empty-state">
          <div className="pm-empty-icon">✓</div>
          <p className="pm-empty-title">No Blocked Tasks</p>
          <p className="pm-empty-desc">
            No work is currently impeded. Team members are progressing on scheduled work.
          </p>
        </div>
      ) : (
        <div className="pm-blocked-list">
          {tasks.map((task) => (
            <div key={task.task_id} className="pm-blocked-item">
              <div className="pm-blocked-top">
                <div className="pm-task-title-wrap">
                  <span className="pm-task-id">#{task.task_id}</span>
                  <strong className="pm-task-title">{task.title}</strong>
                </div>
                <span className="pm-chip pm-chip-blocked">BLOCKED</span>
              </div>

              {/* Blocker Reason Box */}
              <div className="pm-blocker-reason-box">
                <div className="pm-blocker-icon">⚠️</div>
                <div className="pm-blocker-content">
                  <span className="pm-blocker-label">Blocker Reason:</span>
                  <p className="pm-blocker-text">
                    {task.blocker_reason || "No blocker details provided by assignee."}
                  </p>
                </div>
              </div>

              <div className="pm-blocked-footer">
                <span className="pm-blocked-assignee">
                  Assignee: <strong>{task.assignee_name || "Unassigned"}</strong>
                </span>
                <span className="pm-blocked-since">
                  Blocked since:{" "}
                  <strong>
                    {task.blocked_since
                      ? new Date(task.blocked_since).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })
                      : "—"}
                  </strong>
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
