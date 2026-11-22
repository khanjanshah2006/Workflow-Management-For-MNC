import React from "react";
import { coverageLabel } from "./leaveTriageUtils";

/**
 * TaskCoverageMatrix Component (US-17 / Issue #106)
 *
 * Displays teammate availability and workload during applicant's leave window:
 * - One row per teammate.
 * - Availability information formatted as:
 *   - Available: "Available · N active tasks"
 *   - On leave: "On leave"
 *   - At capacity: "At capacity (N tasks)"
 * - Pending leave overlap informational tag.
 * - Read-only matrix view or selectable picker support.
 */
export default function TaskCoverageMatrix({ coverage = [] }) {
  if (!Array.isArray(coverage) || coverage.length === 0) {
    return (
      <div className="coverage-matrix-card" style={{ padding: "16px", textAlign: "center", color: "#64748b", fontSize: "13px" }}>
        No teammate coverage data available.
      </div>
    );
  }

  return (
    <div className="coverage-matrix-card" data-testid="task-coverage-matrix">
      {coverage.map((member) => {
        const label = coverageLabel(member);
        const isAvailable = member.is_available_for_reassignment;
        const isOnLeave = member.has_leave_overlap;
        const hasPendingLeave = member.has_pending_leave_overlap;

        let statusClass = "coverage-status-available";
        if (isOnLeave) {
          statusClass = "coverage-status-onleave";
        } else if (!isAvailable) {
          statusClass = "coverage-status-capacity";
        }

        const initials = (member.full_name || "TM")
          .split(" ")
          .map((n) => n[0])
          .slice(0, 2)
          .join("")
          .toUpperCase();

        return (
          <div
            key={member.emp_id}
            className="coverage-member-row"
            data-testid={`coverage-member-${member.emp_id}`}
          >
            <div className="coverage-member-info">
              <div className="coverage-member-avatar" aria-hidden="true">
                {initials}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                <span className="coverage-member-name">{member.full_name}</span>
                <span style={{ fontSize: "11px", color: "#64748b" }}>
                  Emp ID #{member.emp_id}
                </span>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              {hasPendingLeave && (
                <span
                  className="badge-pending-leave-tag"
                  title="This teammate has pending leave overlapping these dates"
                  data-testid="tag-pending-overlap"
                >
                  Pending leave overlap
                </span>
              )}
              <span
                className={`coverage-status-tag ${statusClass}`}
                data-testid={`status-${member.emp_id}`}
              >
                {label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
