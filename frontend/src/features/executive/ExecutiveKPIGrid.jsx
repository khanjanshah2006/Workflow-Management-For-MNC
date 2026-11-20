import React from "react";
import { formatVelocity } from "./executiveUtils.js";

/**
 * ExecutiveKPIGrid
 * Displays enterprise-level KPI cards for projects, milestone velocity, tasks, and headcount.
 *
 * @param {Object} props
 * @param {Object} props.overview ExecutiveOverviewResponse data
 */
export default function ExecutiveKPIGrid({ overview }) {
  if (!overview) return null;

  const {
    total_projects = 0,
    active_projects = 0,
    delayed_projects = 0,
    completed_projects = 0,
    overall_milestone_velocity_pct = 0,
    task_kpis = {},
    total_employees = 0,
  } = overview;

  const openTasks = task_kpis.open_tasks ?? 0;
  const overdueTasks = task_kpis.overdue_tasks ?? 0;

  return (
    <div className="exec-kpi-grid" aria-label="Executive KPI Overview">
      {/* 1. Total Projects */}
      <div className="exec-kpi-card">
        <div className="exec-kpi-header">
          <span className="exec-kpi-title">Total Projects</span>
          <span className="exec-kpi-icon" aria-hidden="true">📁</span>
        </div>
        <div className="exec-kpi-value">{total_projects}</div>
        <div className="exec-kpi-subtext">Enterprise portfolio total</div>
      </div>

      {/* 2. Active Projects */}
      <div className="exec-kpi-card">
        <div className="exec-kpi-header">
          <span className="exec-kpi-title">Active Projects</span>
          <span className="exec-kpi-icon" aria-hidden="true">⚡</span>
        </div>
        <div className="exec-kpi-value">{active_projects}</div>
        <div className="exec-kpi-subtext">Currently in progress</div>
      </div>

      {/* 3. Delayed Projects (Warning treatment if > 0) */}
      <div
        className={`exec-kpi-card ${delayed_projects > 0 ? "exec-kpi-warning" : ""}`}
        data-testid="kpi-delayed-projects"
      >
        <div className="exec-kpi-header">
          <span className="exec-kpi-title">Delayed Projects</span>
          <span className="exec-kpi-icon" aria-hidden="true">
            {delayed_projects > 0 ? "⚠️" : "✓"}
          </span>
        </div>
        <div className="exec-kpi-value">{delayed_projects}</div>
        <div className="exec-kpi-subtext">
          {delayed_projects > 0 ? "Requires executive review" : "No overdue milestones"}
        </div>
      </div>

      {/* 4. Completed Projects */}
      <div className="exec-kpi-card">
        <div className="exec-kpi-header">
          <span className="exec-kpi-title">Completed Projects</span>
          <span className="exec-kpi-icon" aria-hidden="true">🏁</span>
        </div>
        <div className="exec-kpi-value">{completed_projects}</div>
        <div className="exec-kpi-subtext">Successfully delivered</div>
      </div>

      {/* 5. Overall Milestone Velocity */}
      <div className="exec-kpi-card">
        <div className="exec-kpi-header">
          <span className="exec-kpi-title">Milestone Velocity</span>
          <span className="exec-kpi-icon" aria-hidden="true">📈</span>
        </div>
        <div className="exec-kpi-value">
          {formatVelocity(overall_milestone_velocity_pct)}
        </div>
        <div className="exec-kpi-subtext">Portfolio delivery pace</div>
      </div>

      {/* 6. Open Tasks */}
      <div className="exec-kpi-card">
        <div className="exec-kpi-header">
          <span className="exec-kpi-title">Open Tasks</span>
          <span className="exec-kpi-icon" aria-hidden="true">📋</span>
        </div>
        <div className="exec-kpi-value">{openTasks}</div>
        <div className="exec-kpi-subtext">Active work items</div>
      </div>

      {/* 7. Overdue Tasks */}
      <div
        className={`exec-kpi-card ${overdueTasks > 0 ? "exec-kpi-warning" : ""}`}
        data-testid="kpi-overdue-tasks"
      >
        <div className="exec-kpi-header">
          <span className="exec-kpi-title">Overdue Tasks</span>
          <span className="exec-kpi-icon" aria-hidden="true">
            {overdueTasks > 0 ? "⏰" : "✓"}
          </span>
        </div>
        <div className="exec-kpi-value">{overdueTasks}</div>
        <div className="exec-kpi-subtext">
          {overdueTasks > 0 ? "Exceeded target deadline" : "All tasks on schedule"}
        </div>
      </div>

      {/* 8. Total Employee Headcount */}
      <div className="exec-kpi-card">
        <div className="exec-kpi-header">
          <span className="exec-kpi-title">Total Headcount</span>
          <span className="exec-kpi-icon" aria-hidden="true">👥</span>
        </div>
        <div className="exec-kpi-value">{total_employees}</div>
        <div className="exec-kpi-subtext">Active employees</div>
      </div>
    </div>
  );
}
