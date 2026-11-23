import React, { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getClientProjects } from "../../api/clientPortalApi";
import { formatDate } from "./clientPortalUtils";
import "./clientPortal.css";

/**
 * ClientProjectListPage Component (US-20)
 *
 * Client portal dashboard presenting an executive summary of all contracted
 * projects, milestones completion velocity, and direct links to project details.
 */
export default function ClientProjectListPage() {
  const [searchTerm, setSearchTerm] = useState("");

  const {
    data: projects = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["clientProjects"],
    queryFn: getClientProjects,
    staleTime: 60 * 1000,
  });

  // Calculate high-level summary KPIs
  const kpis = useMemo(() => {
    const totalProjects = projects.length;
    const activeProjects = projects.filter(
      (p) => (p.status || "").toUpperCase() === "ACTIVE"
    ).length;

    let totalMilestones = 0;
    let completedMilestones = 0;

    projects.forEach((p) => {
      if (p.milestones_summary) {
        totalMilestones += p.milestones_summary.total || 0;
        completedMilestones += p.milestones_summary.completed || 0;
      }
    });

    const overallPct =
      totalMilestones > 0
        ? Math.round((completedMilestones / totalMilestones) * 100)
        : 0;

    return {
      totalProjects,
      activeProjects,
      totalMilestones,
      completedMilestones,
      overallPct,
    };
  }, [projects]);

  // Filter projects by search query
  const filteredProjects = useMemo(() => {
    if (!searchTerm.trim()) return projects;
    const q = searchTerm.toLowerCase();
    return projects.filter(
      (p) =>
        (p.name || "").toLowerCase().includes(q) ||
        (p.project_code || "").toLowerCase().includes(q) ||
        (p.description || "").toLowerCase().includes(q)
    );
  }, [projects, searchTerm]);

  return (
    <div className="client-container" data-testid="client-projects-dashboard">
      {/* Page Header */}
      <div className="client-header">
        <div>
          <h1 className="client-page-title">My Contracted Projects</h1>
          <p className="client-page-subtitle">
            Track milestones, deliverable signoffs, and project velocity across your active contracts.
          </p>
        </div>

        <div>
          <input
            type="search"
            placeholder="Search by code or title..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              padding: "8px 14px",
              border: "1px solid #cbd5e1",
              borderRadius: "8px",
              fontSize: "13px",
              width: "240px",
            }}
            aria-label="Search projects"
          />
        </div>
      </div>

      {/* KPI Cards */}
      <div className="client-stats-grid">
        <div className="client-stat-card">
          <div className="client-stat-label">Contracted Projects</div>
          <div className="client-stat-value">{kpis.totalProjects}</div>
          <div className="client-stat-desc">{kpis.activeProjects} active contracts</div>
        </div>

        <div className="client-stat-card">
          <div className="client-stat-label">Milestone Completion</div>
          <div className="client-stat-value">{kpis.overallPct}%</div>
          <div className="client-stat-desc">
            {kpis.completedMilestones} of {kpis.totalMilestones} milestones completed
          </div>
        </div>

        <div className="client-stat-card">
          <div className="client-stat-label">Total Milestones</div>
          <div className="client-stat-value">{kpis.totalMilestones}</div>
          <div className="client-stat-desc">Across all contracted engagements</div>
        </div>
      </div>

      {/* Content State: Loading, Error, Empty, or Grid */}
      {isLoading ? (
        <div className="client-loading-spinner" role="status">
          <div className="placeholder-symbol">⏳</div>
          <p>Loading your contracted projects...</p>
        </div>
      ) : isError ? (
        <div className="client-empty-state" style={{ borderColor: "#fca5a5" }}>
          <div style={{ fontSize: "2rem", marginBottom: "8px" }}>⚠️</div>
          <h3>Failed to load projects</h3>
          <p>{error?.message || "An unexpected error occurred while loading projects."}</p>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => refetch()}
            style={{ marginTop: "12px" }}
          >
            Retry
          </button>
        </div>
      ) : filteredProjects.length === 0 ? (
        <div className="client-empty-state">
          <div style={{ fontSize: "2rem", marginBottom: "8px" }}>📁</div>
          <h3>No projects found</h3>
          <p>
            {searchTerm
              ? "No contracted projects match your search criteria."
              : "No contracted projects are currently assigned to your account."}
          </p>
        </div>
      ) : (
        <div className="client-projects-grid">
          {filteredProjects.map((project) => {
            const pct = Math.round(project.completion_pct || 0);
            const total = project.milestones_summary?.total || 0;
            const completed = project.milestones_summary?.completed || 0;

            return (
              <Link
                key={project.project_id}
                to={`/client/projects/${project.project_id}`}
                className="client-project-card"
                data-testid={`client-project-card-${project.project_id}`}
              >
                <div className="client-project-top">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span className="client-project-code">{project.project_code}</span>
                    <span
                      className={`chip ${
                        project.status === "ACTIVE"
                          ? "chip-green"
                          : project.status === "COMPLETED"
                          ? "chip-blue"
                          : "chip-grey"
                      }`}
                    >
                      {project.status}
                    </span>
                  </div>

                  <h3 className="client-project-name">{project.name}</h3>

                  {project.description && (
                    <p className="client-project-desc">{project.description}</p>
                  )}
                </div>

                <div>
                  <div className="client-project-dates">
                    <span>Start: {formatDate(project.start_date)}</span>
                    <span>Target: {formatDate(project.target_end_date)}</span>
                  </div>

                  <div className="client-progress-wrapper">
                    <div className="client-progress-header">
                      <span>Milestone Progress</span>
                      <span>{pct}%</span>
                    </div>
                    <div className="client-progress-track">
                      <div
                        className="client-progress-fill"
                        style={{ width: `${Math.min(pct, 100)}%` }}
                      />
                    </div>
                  </div>

                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginTop: "12px",
                      fontSize: "12px",
                      color: "#64748b",
                    }}
                  >
                    <span>
                      {completed} of {total} completed
                    </span>
                    <span style={{ color: "#2563eb", fontWeight: "600" }}>
                      View Details →
                    </span>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
