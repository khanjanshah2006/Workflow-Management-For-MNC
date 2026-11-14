import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { projectsApi } from "../../../api/projectsApi";
import ProjectStaffingPanel from "../components/ProjectStaffingPanel";

// Fallback project representation for initial presentation if backend has no projects yet
const DEMO_PROJECT = {
  project_id: 1,
  project_code: "PRJ-CLOUD-01",
  name: "Enterprise Cloud Migration",
  description:
    "Migrate legacy core services to scalable microservices infrastructure with zero downtime.",
  start_date: new Date().toISOString().split("T")[0],
  end_date: new Date(Date.now() + 90 * 86400000).toISOString().split("T")[0],
  priority: "HIGH",
  status: "ACTIVE",
  client_id: 1,
  pm_id: 1,
};

export default function ProjectsPage() {
  const { projectId: urlProjectId } = useParams();
  const navigate = useNavigate();

  // Fetch real projects from backend
  const {
    data: projects = [],
    isLoading,
  } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.getProjects(),
    retry: 1,
  });

  const [selectedProjectId, setSelectedProjectId] = useState(null);

  // Derive the active project from URL param, user selection, or first available project
  const activeProjectId = urlProjectId
    ? Number(urlProjectId)
    : selectedProjectId || (projects[0]?.project_id ?? DEMO_PROJECT.project_id);

  const activeProject =
    projects.find((p) => p.project_id === activeProjectId) ||
    (activeProjectId === DEMO_PROJECT.project_id ? DEMO_PROJECT : null);

  const handleSelectProject = (id) => {
    setSelectedProjectId(id);
    navigate(`/projects/${id}`);
  };

  return (
    <section className="page projects-page-container">
      <div className="page-header-row">
        <div>
          <div className="page-eyebrow">PROJECT WORKSPACE</div>
          <h1 className="page-main-heading">Projects & Team Staffing</h1>
          <p className="page-description">
            Monitor active corporate projects and manage team staffing assignments.
          </p>
        </div>

        {/* Project Selector Dropdown */}
        <div className="project-selector-wrapper">
          <label htmlFor="project-select" className="selector-label">
            Active Project:
          </label>
          <select
            id="project-select"
            className="project-select-dropdown"
            value={activeProject?.project_id || ""}
            onChange={(e) => handleSelectProject(Number(e.target.value))}
          >
            {projects.length > 0 ? (
              projects.map((p) => (
                <option key={p.project_id} value={p.project_id}>
                  {p.project_code} — {p.name}
                </option>
              ))
            ) : (
              <option value={DEMO_PROJECT.project_id}>
                {DEMO_PROJECT.project_code} — {DEMO_PROJECT.name}
              </option>
            )}
          </select>
        </div>
      </div>

      {isLoading && projects.length === 0 ? (
        <div className="placeholder-panel">
          <div className="spinner-medium" />
          <h2>Connecting to Project API...</h2>
          <p>Fetching project data from backend service.</p>
        </div>
      ) : activeProject ? (
        <div className="project-details-layout">
          {/* Project Details Overview Card */}
          <div className="project-overview-card">
            <div className="project-overview-header">
              <div className="project-meta-top">
                <span className="project-code-badge">{activeProject.project_code}</span>
                <span className={`priority-badge priority-${(activeProject.priority || "medium").toLowerCase()}`}>
                  {activeProject.priority} Priority
                </span>
                <span className={`status-badge status-${(activeProject.status || "active").toLowerCase()}`}>
                  {activeProject.status}
                </span>
              </div>
              <h2 className="project-card-title">{activeProject.name}</h2>
              {activeProject.description && (
                <p className="project-card-desc">{activeProject.description}</p>
              )}
            </div>

            <div className="project-metrics-grid">
              <div className="metric-box">
                <span className="metric-box-label">START DATE</span>
                <strong className="metric-box-val">{activeProject.start_date || "—"}</strong>
              </div>
              <div className="metric-box">
                <span className="metric-box-label">TARGET COMPLETION</span>
                <strong className="metric-box-val">{activeProject.end_date || "Open Ended"}</strong>
              </div>
              <div className="metric-box">
                <span className="metric-box-label">MANAGED BY</span>
                <strong className="metric-box-val">PM #{activeProject.pm_id}</strong>
              </div>
              <div className="metric-box">
                <span className="metric-box-label">COMMISSIONING CLIENT</span>
                <strong className="metric-box-val">Client #{activeProject.client_id}</strong>
              </div>
            </div>
          </div>

          {/* Project Staffing Panel (US-07) */}
          <ProjectStaffingPanel projectId={activeProject.project_id} />
        </div>
      ) : (
        <div className="placeholder-panel">
          <div className="placeholder-symbol">📂</div>
          <h2>No Project Selected</h2>
          <p>Select a project from the menu above to view its team staffing.</p>
        </div>
      )}
    </section>
  );
}
