import React, { useState, useMemo } from "react";

/**
 * RepeatedRejectionsCard Component (US-38 / S5)
 *
 * Displays tasks exceeding the repeated rejection threshold with:
 * - "Rejected N×" chip
 * - Latest feedback callout
 * - Expandable rejection history timeline
 * - Assignee filter dropdown
 */
export default function RepeatedRejectionsCard({
  tasks = [],
  rejectionThreshold = 2,
  isLoading = false,
}) {
  const [selectedAssignee, setSelectedAssignee] = useState("ALL");
  const [expandedTasks, setExpandedTasks] = useState(() => new Set());

  // Extract distinct assignees for filter dropdown
  const assignees = useMemo(() => {
    const map = new Map();
    tasks.forEach((t) => {
      if (t.assignee_id && t.assignee_name) {
        map.set(String(t.assignee_id), t.assignee_name);
      }
    });
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [tasks]);

  // Filter tasks based on selected assignee
  const filteredTasks = useMemo(() => {
    if (selectedAssignee === "ALL") return tasks;
    return tasks.filter((t) => String(t.assignee_id) === String(selectedAssignee));
  }, [tasks, selectedAssignee]);

  const toggleExpand = (taskId) => {
    setExpandedTasks((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) {
        next.delete(taskId);
      } else {
        next.add(taskId);
      }
      return next;
    });
  };

  return (
    <div className="pm-card pm-rejections-card">
      <div className="pm-card-header pm-flex-between">
        <div>
          <span className="pm-card-eyebrow">QUALITY MONITORING</span>
          <h2 className="pm-section-title">Repeatedly Rejected Deliverables</h2>
        </div>
        <div className="pm-rejection-badge">
          Threshold: ≥ {rejectionThreshold} rejections
        </div>
      </div>

      {/* Assignee Filter Dropdown */}
      <div className="pm-filter-bar">
        <label htmlFor="rejections-assignee-filter" className="pm-filter-label">
          Filter by Assignee:
        </label>
        <select
          id="rejections-assignee-filter"
          className="pm-select-sm"
          value={selectedAssignee}
          onChange={(e) => setSelectedAssignee(e.target.value)}
        >
          <option value="ALL">All Assignees ({tasks.length})</option>
          {assignees.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="pm-loading-state">Loading rejection history...</div>
      ) : filteredTasks.length === 0 ? (
        <div className="pm-empty-state">
          <div className="pm-empty-icon">✓</div>
          <p className="pm-empty-title">No Repeated Rejections</p>
          <p className="pm-empty-desc">
            {selectedAssignee === "ALL"
              ? "All deliverables are meeting quality expectations on the first or second review."
              : "This team member has no deliverables exceeding the rejection threshold."}
          </p>
        </div>
      ) : (
        <div className="pm-rejection-list">
          {filteredTasks.map((item) => {
            const isExpanded = expandedTasks.has(item.task_id);
            const history = Array.isArray(item.rejection_history)
              ? item.rejection_history
              : [];

            return (
              <div key={item.task_id} className="pm-rejection-item">
                <div className="pm-rejection-top">
                  <div className="pm-rejection-title-group">
                    <span className="pm-task-id">#{item.task_id}</span>
                    <strong className="pm-task-title">{item.title}</strong>
                    <span className="pm-task-assignee">
                      {item.assignee_name || "Unassigned"}
                    </span>
                  </div>
                  {/* Rejected N× chip */}
                  <span className="pm-chip pm-chip-rejected">
                    Rejected {item.rejection_count}×
                  </span>
                </div>

                {/* Latest Feedback Box */}
                {item.latest_rejection_feedback && (
                  <div className="pm-feedback-box">
                    <span className="pm-feedback-label">Latest Feedback:</span>
                    <p className="pm-feedback-text">"{item.latest_rejection_feedback}"</p>
                  </div>
                )}

                {/* History Toggle */}
                {history.length > 0 && (
                  <div className="pm-history-container">
                    <button
                      type="button"
                      className="pm-btn-text"
                      onClick={() => toggleExpand(item.task_id)}
                      aria-expanded={isExpanded}
                    >
                      {isExpanded
                        ? `▲ Hide Rejection History`
                        : `▼ View Rejection History (${history.length})`}
                    </button>

                    {/* Expandable Rejection Timeline */}
                    {isExpanded && (
                      <ol className="pm-timeline">
                        {history.map((entry, idx) => (
                          <li key={idx} className="pm-timeline-item">
                            <div className="pm-timeline-marker">{idx + 1}</div>
                            <div className="pm-timeline-content">
                              <div className="pm-timeline-time">
                                Rejection #{idx + 1} ·{" "}
                                {entry.rejected_at
                                  ? new Date(entry.rejected_at).toLocaleString(undefined, {
                                      month: "short",
                                      day: "numeric",
                                      hour: "2-digit",
                                      minute: "2-digit",
                                    })
                                  : "Recorded"}
                              </div>
                              <p className="pm-timeline-feedback">
                                {entry.feedback || "No specific feedback comment provided."}
                              </p>
                            </div>
                          </li>
                        ))}
                      </ol>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
