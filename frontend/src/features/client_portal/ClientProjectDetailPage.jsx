import React from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getClientProjects, getClientMilestones } from "../../api/clientPortalApi";
import { formatDate } from "./clientPortalUtils";
import MilestoneRoadmap from "./MilestoneRoadmap";
import "./clientPortal.css";

/**
 * ClientProjectDetailPage Component (US-20, US-21)
 *
 * Detailed client view of a specific contracted project showing its delivery
 * milestone roadmap, completion metrics, and client deliverables.
 */
export default function ClientProjectDetailPage() {
  const { projectId } = useParams();

  // 1. Fetch contracted projects to verify ownership and retrieve metadata
  const {
    data: projects = [],
    isLoading: isLoadingProjects,
    isError: isProjectsError,
    error: projectsError,
  } = useQuery({
    queryKey: ["clientProjects"],
    queryFn: getClientProjects,
    staleTime: 60 * 1000,
  });

  const project = projects.find((p) => String(p.project_id) === String(projectId));

  // 2. Fetch delivery milestones for this project (US-21)
  const {
    data: milestones = [],
    isLoading: isLoadingMilestones,
    isError: isMilestonesError,
    error: milestonesError,
  } = useQuery({
    queryKey: ["clientMilestones", projectId],
    queryFn: () => getClientMilestones(projectId),
    enabled: Boolean(project),
  });

  if (isLoadingProjects) {
    return (
      <div className="client-loading-spinner" role="status">
        <div className="placeholder-symbol">⏳</div>
        <p>Loading project details...</p>
      </div>
    );
  }

  if (isProjectsError) {
    return (
      <div className="client-empty-state" style={{ borderColor: "#fca5a5" }}>
        <div style={{ fontSize: "2rem", marginBottom: "8px" }}>⚠️</div>
        <h3>Failed to load project</h3>
        <p>{projectsError?.message || "Could not retrieve project data."}</p>
        <Link to="/client/projects" className="btn-secondary" style={{ marginTop: "12px", display: "inline-block" }}>
          ← Back to Projects
        </Link>
      </div>
    );
  }

  // 404 / Forbidden fallback if project is not in client's contracted projects
  if (!project) {
    return (
      <div className="client-empty-state" data-testid="client-project-not-found">
        <div style={{ fontSize: "2rem", marginBottom: "8px" }}>🔒</div>
        <h3>Project Not Found or Access Denied</h3>
        <p>The requested project does not exist or does not belong to your client account.</p>
        <Link
          to="/client/projects"
          className="btn-secondary"
          style={{ marginTop: "12px", display: "inline-block", textDecoration: "none" }}
        >
          ← Return to My Projects
        </Link>
      </div>
    );
  }

  const pct = Math.round(project.completion_pct || 0);
  const totalMilestones = project.milestones_summary?.total || milestones.length;
  const completedMilestones =
    project.milestones_summary?.completed ||
    milestones.filter((m) => (m.status || "").toLowerCase() === "completed").length;

  return (
    <div className="client-container" data-testid="client-project-detail-view">
      {/* Navigation Breadcrumb */}
      <div>
        <Link
          to="/client/projects"
          style={{
            fontSize: "13px",
            color: "#64748b",
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            fontWeight: "500",
          }}
        >
          ← Back to My Projects
        </Link>
      </div>

      {/* Project Header Banner */}
      <div className="client-card">
        <div className="client-header" style={{ marginBottom: "16px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
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
            <h1 className="client-page-title" style={{ margin: "0 0 8px 0" }}>
              {project.name}
            </h1>
            {project.description && (
              <p className="client-page-subtitle">{project.description}</p>
            )}
          </div>
        </div>

        {/* Project Meta Metrics */}
        <div className="client-stats-grid" style={{ marginTop: "16px" }}>
          <div className="client-stat-card" style={{ padding: "14px 18px" }}>
            <div className="client-stat-label">Start Date</div>
            <div style={{ fontSize: "16px", fontWeight: "600", color: "#0f172a" }}>
              {formatDate(project.start_date)}
            </div>
          </div>

          <div className="client-stat-card" style={{ padding: "14px 18px" }}>
            <div className="client-stat-label">Target Completion</div>
            <div style={{ fontSize: "16px", fontWeight: "600", color: "#0f172a" }}>
              {formatDate(project.target_end_date)}
            </div>
          </div>

          <div className="client-stat-card" style={{ padding: "14px 18px" }}>
            <div className="client-stat-label">Milestones Completed</div>
            <div style={{ fontSize: "16px", fontWeight: "600", color: "#0f172a" }}>
              {completedMilestones} / {totalMilestones}
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="client-progress-wrapper" style={{ marginTop: "20px" }}>
          <div className="client-progress-header">
            <span>Overall Delivery Progress</span>
            <span style={{ fontWeight: "700" }}>{pct}%</span>
          </div>
          <div className="client-progress-track" style={{ height: "10px" }}>
            <div
              className="client-progress-fill"
              style={{ width: `${Math.min(pct, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Section: Delivery Milestones Roadmap (US-21) */}
      <div className="client-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 className="client-card-title" style={{ margin: 0 }}>
              Milestone Roadmap
            </h2>
            <p className="client-page-subtitle" style={{ marginTop: "4px" }}>
              High-level milestone schedule and release tracking.
            </p>
          </div>
        </div>

        <MilestoneRoadmap
          milestones={milestones}
          isLoading={isLoadingMilestones}
        />
      </div>

      {/* Placeholder / anchor for Deliverables and PDF Report (Commit 3 & 4) */}
      <div id="client-deliverables-section" />
    </div>
  );
}
