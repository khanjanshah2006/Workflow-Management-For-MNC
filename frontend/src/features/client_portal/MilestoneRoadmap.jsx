import React from "react";
import {
  isMilestoneOverdue,
  milestoneStatusTone,
  formatDate,
} from "./clientPortalUtils";

/**
 * MilestoneRoadmap Component (US-21)
 *
 * Visual timeline displaying delivery milestones for a client project,
 * highlighting completion status and highlighting overdue deliverables.
 */
export default function MilestoneRoadmap({ milestones = [], isLoading = false }) {
  if (isLoading) {
    return (
      <div className="client-loading-spinner" role="status">
        <div className="placeholder-symbol">⏳</div>
        <p>Loading delivery milestones...</p>
      </div>
    );
  }

  if (!milestones || milestones.length === 0) {
    return (
      <div className="client-empty-state">
        <div style={{ fontSize: "2rem", marginBottom: "8px" }}>📅</div>
        <h3>No milestones scheduled</h3>
        <p>There are no delivery milestones published for this project yet.</p>
      </div>
    );
  }

  // Sort milestones chronologically by target_date
  const sortedMilestones = [...milestones].sort((a, b) => {
    const da = new Date(a.target_date || 0).getTime();
    const db = new Date(b.target_date || 0).getTime();
    return da - db;
  });

  return (
    <div className="milestone-timeline" aria-label="Milestone Roadmap Timeline">
      {sortedMilestones.map((milestone) => {
        const isOverdue = isMilestoneOverdue(milestone);
        const normStatus = (milestone.status || "pending").toLowerCase();
        const dotClass = isOverdue
          ? "overdue"
          : normStatus === "completed"
          ? "completed"
          : normStatus === "in_progress"
          ? "in_progress"
          : "pending";

        const tone = milestoneStatusTone(milestone.status);

        return (
          <div
            key={milestone.id}
            className="milestone-item"
            data-testid={`milestone-item-${milestone.id}`}
          >
            <div className={`milestone-dot ${dotClass}`} aria-hidden="true" />

            <div className="milestone-info">
              <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                <span className="milestone-title">{milestone.title}</span>
                <span className={`chip chip-${tone}`}>{milestone.status}</span>
                {isOverdue && (
                  <span className="chip chip-red" title="Target date has passed">
                    Overdue
                  </span>
                )}
              </div>

              {milestone.description && (
                <div className="milestone-desc">{milestone.description}</div>
              )}
            </div>

            <div className="milestone-meta">
              <div className="milestone-date">
                📅 Target: {formatDate(milestone.target_date)}
              </div>
              {milestone.completed_at && (
                <div className="milestone-date" style={{ color: "#16a34a", fontWeight: "600" }}>
                  ✓ Completed: {formatDate(milestone.completed_at)}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
