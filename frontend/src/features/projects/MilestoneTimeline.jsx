import { useQuery } from "@tanstack/react-query";
import { projectsApi } from "../../api/projectsApi";

function formatDate(dateStr) {
  if (!dateStr) return "—";
  try {
    const [year, month, day] = dateStr.split("-");
    if (!year || !month || !day) return dateStr;
    const date = new Date(Number(year), Number(month) - 1, Number(day));
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

/**
 * Milestone Roadmap Timeline Component (US-08 - Frame 9:378).
 *
 * Displays a chronological vertical timeline of milestones with status indicators.
 * Distinguishes pending vs completed milestones.
 */
export default function MilestoneTimeline({ projectId, project, canManage, onAddMilestone }) {
  const {
    data: milestones = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["projects", projectId, "milestones"],
    queryFn: () => projectsApi.getMilestones(projectId),
    enabled: Boolean(projectId),
    retry: 1,
  });

  // Sort milestones strictly chronologically by target_date ASC, then id ASC
  const sortedMilestones = [...milestones].sort((a, b) => {
    const dateA = a.target_date || "";
    const dateB = b.target_date || "";
    if (dateA !== dateB) return dateA.localeCompare(dateB);
    return (a.id || 0) - (b.id || 0);
  });

  const completedCount = sortedMilestones.filter(
    (m) => (m.status || "").toLowerCase() === "completed"
  ).length;
  const totalCount = sortedMilestones.length;
  const percentComplete = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <div className="milestone-roadmap-section">
      {/* Section Header */}
      <div className="milestone-section-header">
        <div className="milestone-header-left">
          <div className="section-eyebrow">US-08 ROADMAP</div>
          <h2 className="milestone-section-title">Milestones & Key Checkpoints</h2>
          <p className="milestone-section-subtitle">
            Chronological delivery timeline and progress tracking toward project completion.
          </p>
        </div>

        <div className="milestone-header-actions">
          {totalCount > 0 && (
            <div className="milestone-progress-pill" title={`${completedCount} of ${totalCount} milestones completed`}>
              <span className="progress-pill-label">
                {completedCount}/{totalCount} Completed
              </span>
              <div className="progress-pill-bar">
                <div
                  className="progress-pill-fill"
                  style={{ width: `${percentComplete}%` }}
                />
              </div>
              <span className="progress-pill-percent">{percentComplete}%</span>
            </div>
          )}

          {canManage && (
            <button
              type="button"
              className="btn-primary btn-add-milestone"
              onClick={onAddMilestone}
              id="open-add-milestone-btn"
            >
              <span className="btn-icon" aria-hidden="true">+</span>
              <span>Add Milestone</span>
            </button>
          )}
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="milestone-loading-panel" role="status">
          <div className="spinner-medium" />
          <p>Loading project milestones...</p>
        </div>
      )}

      {/* Error State */}
      {isError && (
        <div className="milestone-error-panel" role="alert">
          <span className="error-symbol">⚠️</span>
          <h4>Unable to load milestone roadmap</h4>
          <p>{error?.message || "Failed to retrieve milestones from service."}</p>
          <button type="button" className="btn-secondary" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !isError && sortedMilestones.length === 0 && (
        <div className="milestone-empty-card">
          <div className="milestone-empty-icon" aria-hidden="true">🚩</div>
          <h3 className="milestone-empty-title">No Milestones Defined Yet</h3>
          <p className="milestone-empty-desc">
            Define critical delivery dates, phase completions, and stakeholder checkpoints
            for {project?.name || "this project"}.
          </p>
          {canManage && (
            <button
              type="button"
              className="btn-primary btn-add-milestone"
              onClick={onAddMilestone}
              id="empty-add-milestone-btn"
            >
              + Define First Milestone
            </button>
          )}
        </div>
      )}

      {/* Chronological Timeline */}
      {!isLoading && !isError && sortedMilestones.length > 0 && (
        <div className="timeline-container">
          <div className="timeline-track" aria-hidden="true" />
          <div className="timeline-list" role="feed" aria-label="Milestone delivery checkpoints">
            {sortedMilestones.map((milestone, idx) => {
              const isCompleted = (milestone.status || "").toLowerCase() === "completed";

              return (
                <article
                  key={milestone.id}
                  className={`timeline-entry ${isCompleted ? "entry-completed" : "entry-pending"}`}
                  aria-labelledby={`milestone-title-${milestone.id}`}
                >
                  {/* Timeline Node Badge */}
                  <div
                    className={`timeline-node ${isCompleted ? "node-completed" : "node-pending"}`}
                    aria-hidden="true"
                  >
                    {isCompleted ? "✓" : idx + 1}
                  </div>

                  {/* Milestone Card */}
                  <div className="milestone-card">
                    <div className="milestone-card-header">
                      <div className="milestone-meta-row">
                        <span className="milestone-target-date">
                          📅 Target: <strong>{formatDate(milestone.target_date)}</strong>
                        </span>

                        <span
                          className={`milestone-status-badge ${
                            isCompleted ? "badge-completed" : "badge-pending"
                          }`}
                        >
                          <span className="status-dot" aria-hidden="true" />
                          {isCompleted ? "Completed" : "Pending"}
                        </span>
                      </div>

                      <h3
                        id={`milestone-title-${milestone.id}`}
                        className="milestone-card-title"
                      >
                        {milestone.title}
                      </h3>
                    </div>

                    {milestone.description && (
                      <p className="milestone-card-desc">{milestone.description}</p>
                    )}

                    <div className="milestone-card-footer">
                      <span className="milestone-id-tag">ID #{milestone.id}</span>
                      {isCompleted && milestone.completed_at && (
                        <span className="milestone-completed-at">
                          Achieved on {formatDate(milestone.completed_at.split("T")[0])}
                        </span>
                      )}
                      {!isCompleted && (
                        <span className="milestone-checkpoint-label">
                          Phase Checkpoint {idx + 1} of {totalCount}
                        </span>
                      )}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
