import React from "react";
import { statusSegments } from "./executiveUtils.js";

/**
 * ProjectStatusBar
 * Renders a CSS-based stacked progress bar for projects by status with legend and percentages.
 *
 * @param {Object} props
 * @param {Object} props.projectsByStatus Map of status to count
 * @param {number} props.totalProjects Total projects count
 */
export default function ProjectStatusBar({ projectsByStatus, totalProjects = 0 }) {
  const segments = statusSegments(projectsByStatus);
  const total = Number(totalProjects) || 0;

  return (
    <div className="exec-status-bar-card" aria-label="Project Status Distribution">
      <div className="exec-card-header">
        <div>
          <h3 className="exec-card-title">Project Lifecycle Distribution</h3>
          <p className="exec-card-subtitle">
            Status breakdown across {total} {total === 1 ? "project" : "projects"}
          </p>
        </div>
      </div>

      {/* Stacked Progress Bar */}
      <div
        className="exec-stacked-bar-track"
        role="progressbar"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow="100"
        aria-label="Projects status breakdown"
      >
        {total === 0 ? (
          <div className="exec-stacked-bar-empty">No projects recorded</div>
        ) : (
          segments.map((seg) => {
            if (seg.percentage <= 0) return null;
            return (
              <div
                key={seg.status}
                className="exec-stacked-bar-segment"
                style={{
                  width: `${seg.percentage}%`,
                  backgroundColor: seg.color,
                }}
                title={`${seg.label}: ${seg.count} (${seg.percentage}%)`}
              />
            );
          })
        )}
      </div>

      {/* Legend */}
      <div className="exec-status-legend">
        {segments.map((seg) => (
          <div key={seg.status} className="exec-legend-item">
            <span
              className="exec-legend-dot"
              style={{ backgroundColor: seg.color }}
              aria-hidden="true"
            />
            <span className="exec-legend-label">{seg.label}</span>
            <span className="exec-legend-count">
              {seg.count} ({total > 0 ? `${seg.percentage}%` : "0%"})
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
