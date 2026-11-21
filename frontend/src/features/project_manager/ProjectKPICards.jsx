import React from "react";
import { statusBarSegments } from "./pmRiskUtils";

/**
 * ProjectKPICards Component (US-23 / S5)
 *
 * Renders project performance metrics, status distribution stacked bar,
 * overdue count, blocked count, at-risk milestones, and repeated rejections.
 */
export default function ProjectKPICards({ dashboard = null }) {
  if (!dashboard) {
    return (
      <div className="pm-kpi-loading-grid">
        <div className="pm-card pm-skeleton-card" />
        <div className="pm-card pm-skeleton-card" />
        <div className="pm-card pm-skeleton-card" />
        <div className="pm-card pm-skeleton-card" />
      </div>
    );
  }

  const {
    completion_pct = 0,
    total_tasks = 0,
    tasks_by_status = {},
    overdue_tasks_count = 0,
    blocked_tasks_count = 0,
    at_risk_milestones_count = 0,
    repeatedly_rejected_count = 0,
    rejection_threshold = 2,
  } = dashboard;

  const segments = statusBarSegments(tasks_by_status, total_tasks);
  const doneCount = tasks_by_status?.DONE || 0;

  return (
    <section className="pm-kpi-container" aria-label="Project Key Performance Indicators">
      {/* Top Row: Overall Completion & Stacked Status Bar */}
      <div className="pm-kpi-overview-grid">
        {/* Card 1: Completion % */}
        <div className="pm-card pm-card-completion">
          <div className="pm-card-header">
            <span className="pm-card-eyebrow">PROJECT PROGRESS</span>
            <span className="pm-card-badge">{completion_pct >= 100 ? "Complete" : "In Flight"}</span>
          </div>
          <div className="pm-card-metric-row">
            <span className="pm-metric-giant">{completion_pct}%</span>
            <div className="pm-completion-sub">
              <strong>{doneCount}</strong> of <strong>{total_tasks}</strong> tasks completed
            </div>
          </div>
          <div className="pm-progress-track" role="progressbar" aria-valuenow={completion_pct} aria-valuemin={0} aria-valuemax={100}>
            <div className="pm-progress-fill" style={{ width: `${Math.min(100, Math.max(0, completion_pct))}%` }} />
          </div>
        </div>

        {/* Card 2: Tasks by Status Stacked Bar */}
        <div className="pm-card pm-card-status-bar">
          <div className="pm-card-header">
            <span className="pm-card-eyebrow">TASK STATUS DISTRIBUTION</span>
            <span className="pm-card-count">{total_tasks} Total Tasks</span>
          </div>

          {/* CSS Stacked Bar */}
          <div className="pm-stacked-bar" aria-label="Tasks by status breakdown">
            {segments.map((seg) =>
              seg.pct > 0 ? (
                <div
                  key={seg.status}
                  className={`pm-stacked-segment ${seg.className}`}
                  style={{ width: `${seg.pct}%`, backgroundColor: seg.color }}
                  title={`${seg.label}: ${seg.count} (${seg.pct}%)`}
                />
              ) : null
            )}
          </div>

          {/* Legend */}
          <div className="pm-status-legend">
            {segments.map((seg) => (
              <div key={seg.status} className="pm-legend-item">
                <span className="pm-legend-dot" style={{ backgroundColor: seg.color }} />
                <span className="pm-legend-label">{seg.label}</span>
                <span className="pm-legend-count">{seg.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Row: 4 Risk Indicator Cards */}
      <div className="pm-risk-indicators-grid">
        {/* Overdue Tasks */}
        <div className={`pm-card pm-kpi-card ${overdue_tasks_count > 0 ? "pm-kpi-card-danger" : ""}`}>
          <div className="pm-kpi-icon-wrap">⏰</div>
          <div className="pm-kpi-content">
            <div className="pm-kpi-value">{overdue_tasks_count}</div>
            <div className="pm-kpi-title">Overdue Tasks</div>
            <div className="pm-kpi-meta">Tasks past due date</div>
          </div>
        </div>

        {/* Blocked Tasks */}
        <div className={`pm-card pm-kpi-card ${blocked_tasks_count > 0 ? "pm-kpi-card-warning" : ""}`}>
          <div className="pm-kpi-icon-wrap">🚫</div>
          <div className="pm-kpi-content">
            <div className="pm-kpi-value">{blocked_tasks_count}</div>
            <div className="pm-kpi-title">Blocked Tasks</div>
            <div className="pm-kpi-meta">Awaiting impediment resolution</div>
          </div>
        </div>

        {/* At-Risk Milestones */}
        <div className={`pm-card pm-kpi-card ${at_risk_milestones_count > 0 ? "pm-kpi-card-warning" : ""}`}>
          <div className="pm-kpi-icon-wrap">🎯</div>
          <div className="pm-kpi-content">
            <div className="pm-kpi-value">{at_risk_milestones_count}</div>
            <div className="pm-kpi-title">At-Risk Milestones</div>
            <div className="pm-kpi-meta">Due within 3 days with open work</div>
          </div>
        </div>

        {/* Repeated Rejections */}
        <div className={`pm-card pm-kpi-card ${repeatedly_rejected_count > 0 ? "pm-kpi-card-danger" : ""}`}>
          <div className="pm-kpi-icon-wrap">🔄</div>
          <div className="pm-kpi-content">
            <div className="pm-kpi-value">{repeatedly_rejected_count}</div>
            <div className="pm-kpi-title">Repeated Rejections</div>
            <div className="pm-kpi-meta">Quality threshold: ≥ {rejection_threshold} rejections</div>
          </div>
        </div>
      </div>
    </section>
  );
}
