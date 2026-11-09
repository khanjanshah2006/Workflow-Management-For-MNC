import { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listProjects } from "../../api/projectsApi";
import { useSession, canCreateProject } from "../../auth/session";
import CreateProjectModal from "./CreateProjectModal";
import "./projects.css";

const PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  "ALL",
  "PLANNED",
  "ACTIVE",
  "ON_HOLD",
  "COMPLETED",
];

/**
 * Extracts a 1-2 letter uppercase monogram from a project's name or code.
 * @param {string} name
 * @param {string} code
 * @returns {string}
 */
function getProjectMonogram(name, code) {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.trim().slice(0, 2).toUpperCase();
  }
  if (code && code.trim()) {
    return code.trim().slice(0, 2).toUpperCase();
  }
  return "PR";
}

/**
 * Formats an ISO date string (YYYY-MM-DD) into a clean readable date.
 * @param {string|null} dateStr
 * @returns {string}
 */
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
 * Project List Directory Page (US-06).
 *
 * Implements approved WorkSphere Figma design for the project directory.
 * Scoped by role and RBAC permissions.
 */
export default function ProjectListPage() {
  const navigate = useNavigate();
  const session = useSession();
  const currentUser = session?.user;

  // Filter & Search states
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(0);

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);

  const canCreate = canCreateProject(currentUser);

  // TanStack Query for projects
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["projects", { skip: page * PAGE_SIZE, limit: PAGE_SIZE }],
    queryFn: () => listProjects({ skip: page * PAGE_SIZE, limit: PAGE_SIZE }),
    enabled: Boolean(session?.access_token),
    retry: 1,
  });

  const rawProjects = data?.projects;
  const totalCount = data?.totalCount ?? 0;

  // Client-side filtering by status and search
  const filteredProjects = useMemo(() => {
    if (!rawProjects || rawProjects.length === 0) {
      return [];
    }

    return rawProjects.filter((project) => {
      // Status filter
      if (statusFilter !== "ALL" && project.status !== statusFilter) {
        return false;
      }

      // Search query (case-insensitive on name and project_code)
      if (searchQuery.trim()) {
        const query = searchQuery.trim().toLowerCase();
        const matchesName = (project.name || "").toLowerCase().includes(query);
        const matchesCode = (project.project_code || "").toLowerCase().includes(query);
        if (!matchesName && !matchesCode) {
          return false;
        }
      }

      return true;
    });
  }, [rawProjects, statusFilter, searchQuery]);

  // Unauthenticated sign-in required state
  if (!session?.access_token) {
    return (
      <section className="page">
        <div className="page-eyebrow">WORKSPACE / PROJECT MANAGEMENT</div>
        <h1>Projects Directory</h1>
        <p className="page-description">
          Directory of ongoing, planned, and completed projects across the organization.
        </p>

        <div className="placeholder-panel">
          <div className="placeholder-symbol">🔒</div>
          <h2>Authentication Required</h2>
          <p>
            An active WorkSphere session is required to view enterprise project records and
            manage project lifecycles. Please sign in with your authorized credentials.
          </p>
          <div style={{ marginTop: 20 }}>
            <Link to="/login" className="btn-primary" style={{ textDecoration: "none" }}>
              Go to Sign In →
            </Link>
          </div>
          <span className="status-label" style={{ marginTop: 24 }}>
            RBAC Protected · Access Token Required
          </span>
        </div>
      </section>
    );
  }

  const projectCount = rawProjects ? rawProjects.length : 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  return (
    <section className="page">
      {/* Page Header */}
      <div className="projects-header">
        <div className="projects-header-info">
          <div className="page-eyebrow">WORKSPACE / PROJECT MANAGEMENT</div>
          <div className="projects-title-row">
            <h1>Projects Directory</h1>
            {!isLoading && (
              <span className="projects-count-pill" title="Total recorded projects">
                {totalCount} {totalCount === 1 ? "project" : "projects"}
              </span>
            )}
          </div>
          <p className="page-description">
            Directory of ongoing, planned, and completed projects across the organization.
          </p>
        </div>

        {canCreate && (
          <button
            type="button"
            className="btn-primary"
            onClick={() => setIsModalOpen(true)}
            id="create-project-btn"
          >
            <span className="btn-icon" aria-hidden="true">+</span> Create Project
          </button>
        )}
      </div>

      {/* Toolbar: Search and Status Filter Dropdown */}
      <div className="projects-toolbar">
        <div className="projects-search-wrapper">
          <span className="projects-search-icon" aria-hidden="true">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
          </span>
          <input
            type="search"
            className="projects-search-input"
            placeholder="Search by project name or code..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search projects by name or code"
          />
          {searchQuery && (
            <button
              type="button"
              className="projects-search-clear"
              onClick={() => setSearchQuery("")}
              aria-label="Clear search input"
            >
              ✕
            </button>
          )}
        </div>

        <div className="status-filter-wrapper">
          <label htmlFor="status-filter" className="status-filter-label">
            Status
          </label>
          <div className="status-select-wrapper">
            <select
              id="status-filter"
              name="status-filter"
              className="status-filter-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter projects by status"
            >
              {STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Table Content & States */}
      <div className="projects-table-card">
        {/* Loading State */}
        {isLoading && (
          <div className="state-panel" role="status">
            <div className="spinner" />
            <h3>Loading Projects</h3>
            <p>Fetching project directory from enterprise database...</p>
          </div>
        )}

        {/* Error State */}
        {!isLoading && isError && (
          <div className="state-panel" role="alert">
            <div className="state-icon state-icon-error">⚠</div>
            <h3>Unable to Load Projects</h3>
            <p>{error?.message || "An unexpected error occurred while loading projects."}</p>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => refetch()}
            >
              Try Again
            </button>
          </div>
        )}

        {/* Empty State: No projects in database at all */}
        {!isLoading && !isError && projectCount === 0 && (
          <div className="state-panel">
            <div className="state-icon state-icon-empty">◇</div>
            <h3>No Projects Found</h3>
            <p>There are currently no active or planned projects registered in the system.</p>
            {canCreate && (
              <button
                type="button"
                className="btn-primary"
                onClick={() => setIsModalOpen(true)}
              >
                + Create First Project
              </button>
            )}
          </div>
        )}

        {/* Empty State: Filter / Search produced no results */}
        {!isLoading && !isError && projectCount > 0 && filteredProjects.length === 0 && (
          <div className="state-panel">
            <div className="state-icon state-icon-info">🔍</div>
            <h3>No Matching Projects</h3>
            <p>
              No projects match your current filter criteria. Try adjusting your search query or status filter.
            </p>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setStatusFilter("ALL");
                setSearchQuery("");
              }}
            >
              Reset Filters
            </button>
          </div>
        )}

        {/* Data Table */}
        {!isLoading && !isError && filteredProjects.length > 0 && (
          <div className="projects-table-scroll">
            <table className="projects-table" aria-label="Projects directory table">
              <thead>
                <tr>
                  <th scope="col">Project</th>
                  <th scope="col">Code</th>
                  <th scope="col">Status</th>
                  <th scope="col">Priority</th>
                  <th scope="col">Start Date</th>
                  <th scope="col">Target End Date</th>
                  <th scope="col">Client / PM</th>
                  <th scope="col" style={{ textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredProjects.map((project) => {
                  const statusKey = (project.status || "").toLowerCase();
                  const priorityKey = (project.priority || "").toLowerCase();
                  const monogram = getProjectMonogram(project.name, project.project_code);

                  return (
                    <tr
                      key={project.project_id}
                      onClick={() => navigate(`/projects/${project.project_id}`)}
                      style={{ cursor: "pointer" }}
                    >
                      {/* Project Identity with Monogram & Description */}
                      <td className="project-identity-cell">
                        <div className="project-identity">
                          <div className="project-monogram" aria-hidden="true">
                            {monogram}
                          </div>
                          <div className="project-identity-text">
                            <Link
                              to={`/projects/${project.project_id}`}
                              className="project-name-title"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {project.name}
                            </Link>
                            {project.description && (
                              <p className="project-desc-excerpt" title={project.description}>
                                {project.description}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Project Code */}
                      <td>
                        <span className="project-code-badge">
                          {project.project_code}
                        </span>
                      </td>

                      {/* Status Badge */}
                      <td>
                        <span className={`badge badge-status badge-status-${statusKey}`}>
                          <span className="badge-dot" aria-hidden="true" />
                          {project.status}
                        </span>
                      </td>

                      {/* Priority Badge */}
                      <td>
                        <span className={`badge badge-priority badge-priority-${priorityKey}`}>
                          {project.priority}
                        </span>
                      </td>

                      {/* Start Date */}
                      <td className="project-date-cell">
                        {formatDate(project.start_date)}
                      </td>

                      {/* Target End Date */}
                      <td className="project-date-cell">
                        {project.end_date ? (
                          formatDate(project.end_date)
                        ) : (
                          <span className="project-date-empty">Not specified</span>
                        )}
                      </td>

                      {/* Client ID / PM ID */}
                      <td>
                        <div className="project-id-meta">
                          <span className="meta-chip" title={`Commissioning Client ID: ${project.client_id}`}>
                            <span className="meta-chip-label">Client</span>
                            <span className="meta-chip-val">#{project.client_id}</span>
                          </span>
                          <span className="meta-chip" title={`Managing PM ID: ${project.pm_id}`}>
                            <span className="meta-chip-label">PM</span>
                            <span className="meta-chip-val">#{project.pm_id}</span>
                          </span>
                        </div>
                      </td>

                      {/* Actions */}
                      <td style={{ textAlign: "right" }}>
                        <Link
                          to={`/projects/${project.project_id}`}
                          className="view-link"
                          onClick={(e) => e.stopPropagation()}
                          aria-label={`View details for ${project.name}`}
                        >
                          View <span aria-hidden="true">→</span>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {!isLoading && !isError && projectCount > 0 && (
          <div className="projects-pagination">
            <div className="pagination-summary">
              Showing{" "}
              <strong>
                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, totalCount)}
              </strong>{" "}
              of <strong>{totalCount}</strong> projects
              {isFetching && <span style={{ marginLeft: 8, color: "#8791a5" }}>(refreshing...)</span>}
            </div>

            <div className="pagination-actions">
              <button
                type="button"
                className="btn-page"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                ← Previous
              </button>
              <span style={{ fontSize: 12, color: "#647087" }}>
                Page {page + 1} of {totalPages}
              </span>
              <button
                type="button"
                className="btn-page"
                disabled={page >= totalPages - 1 || projectCount < PAGE_SIZE}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Create Project Modal */}
      <CreateProjectModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        currentUser={currentUser}
      />
    </section>
  );
}
