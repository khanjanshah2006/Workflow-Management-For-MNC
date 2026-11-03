import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { teamApi } from "../../api/teamApi.js";

/**
 * TeamRosterPage (US-37: [S1-FE-4] Team Lead Team Roster View)
 *
 * Implements graceful loading skeletons, empty state, error state with retry,
 * live data cards, and an initial Wave 2 placeholder for Team Tasks.
 */
export default function TeamRosterPage() {
  const [searchParams] = useSearchParams();
  const teamId = searchParams.get("teamId") || "1";

  const [members, setMembers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [fetchTrigger, setFetchTrigger] = useState(0);

  useEffect(() => {
    let ignore = false;

    async function loadMembers() {
      try {
        setErrorMessage(null);

        const rawMembers = await teamApi.getTeamMembers(teamId);
        if (ignore) return;

        if (!Array.isArray(rawMembers) || rawMembers.length === 0) {
          setMembers([]);
          setIsLoading(false);
          setIsRetrying(false);
          return;
        }

        const normalized = await Promise.all(
          rawMembers.map(async (raw) => {
            if (raw.full_name || raw.name || !raw.emp_id) {
              return teamApi.normalizeMember(raw);
            }
            try {
              const detail = await teamApi.getEmployeeById(raw.emp_id);
              return teamApi.normalizeMember(raw, detail);
            } catch {
              return teamApi.normalizeMember(raw);
            }
          })
        );

        if (!ignore) {
          setMembers(normalized);
        }
      } catch (err) {
        if (!ignore) {
          const message =
            err?.message ||
            "Failed to load team roster from API. Please verify the backend service is reachable.";
          setErrorMessage(message);
          setMembers([]);
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
          setIsRetrying(false);
        }
      }
    }

    loadMembers();

    return () => {
      ignore = true;
    };
  }, [teamId, fetchTrigger]);

  const handleRetry = () => {
    setIsRetrying(true);
    setIsLoading(true);
    setFetchTrigger((prev) => prev + 1);
  };

  return (
    <section className="page roster-page-container">
      {/* Page Header */}
      <div className="page-header-row">
        <div>
          <div className="page-eyebrow">TEAM WORKSPACE</div>
          <h1 className="page-main-heading">Team Roster</h1>
          <p className="page-description">
            View and monitor your assigned team members, contact information, roles, and active status.
          </p>
        </div>

        <div className="roster-header-actions">
          <div className="team-badge-container">
            <span className="team-context-label">Current Team:</span>
            <span className="team-pill">
              <span className="team-pill-indicator" />
              Team #{teamId}
            </span>
          </div>

          <button
            type="button"
            className="roster-refresh-button"
            onClick={handleRetry}
            disabled={isLoading || isRetrying}
            title="Refresh team roster data from API"
          >
            {isLoading || isRetrying ? "Refreshing..." : "↻ Refresh"}
          </button>
        </div>
      </div>

      {/* Error State Banner */}
      {errorMessage && (
        <div className="roster-error-banner" role="alert">
          <div className="error-banner-icon">⚠</div>
          <div className="error-banner-content">
            <h4 className="error-banner-title">Unable to fetch team members</h4>
            <p className="error-banner-desc">{errorMessage}</p>
          </div>
          <button
            type="button"
            className="retry-button"
            onClick={handleRetry}
            disabled={isRetrying}
          >
            {isRetrying ? "Retrying..." : "Retry"}
          </button>
        </div>
      )}

      {/* Loading State Skeletons */}
      {isLoading && (
        <div className="roster-section">
          <div className="section-meta-row">
            <div className="skeleton-line skeleton-title" style={{ width: "160px", height: "18px" }} />
          </div>
          <div className="team-cards-grid" aria-busy="true" aria-label="Loading team members">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="team-member-card skeleton-card">
                <div className="card-top-row">
                  <div className="skeleton-circle" />
                  <div className="skeleton-badge" />
                </div>
                <div className="card-body">
                  <div className="skeleton-line skeleton-name" />
                  <div className="skeleton-line skeleton-role" />
                  <div className="skeleton-line skeleton-email" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !errorMessage && members.length === 0 && (
        <div className="roster-empty-state">
          <div className="empty-symbol">👥</div>
          <h3 className="empty-title">No team members found</h3>
          <p className="empty-description">
            There are currently no active employees assigned to Team #{teamId}.
            When team members are assigned by the Project Manager, they will appear here.
          </p>
          <button
            type="button"
            className="retry-button empty-refresh-button"
            onClick={handleRetry}
          >
            Refresh Roster
          </button>
        </div>
      )}

      {/* Data State: Team Member Cards */}
      {!isLoading && !errorMessage && members.length > 0 && (
        <div className="roster-section">
          <div className="section-meta-row">
            <h2 className="section-heading">Team Members ({members.length})</h2>
            <span className="roster-live-indicator">
              <span className="live-dot" /> Live Data
            </span>
          </div>

          <div className="team-cards-grid">
            {members.map((member) => {
              const isActive = member.status === "ACTIVE";
              const initials = member.name
                ? member.name
                    .split(" ")
                    .map((n) => n[0])
                    .slice(0, 2)
                    .join("")
                    .toUpperCase()
                : "EM";

              return (
                <div key={member.id} className="team-member-card">
                  <div className="card-top-row">
                    <div className="member-avatar" aria-hidden="true">
                      {initials}
                    </div>

                    <span
                      className={`status-badge ${
                        isActive ? "status-badge-active" : "status-badge-inactive"
                      }`}
                    >
                      <span
                        className={`status-dot ${
                          isActive ? "status-dot-active" : "status-dot-inactive"
                        }`}
                      />
                      {isActive ? "Active" : "Inactive"}
                    </span>
                  </div>

                  <div className="card-body">
                    <h3 className="member-name">{member.name}</h3>
                    <div className="member-role">{member.role}</div>

                    <div className="member-contact">
                      <span className="contact-icon" aria-hidden="true">✉</span>
                      <a
                        href={`mailto:${member.email}`}
                        className="member-email"
                        title={`Send email to ${member.email}`}
                      >
                        {member.email}
                      </a>
                    </div>

                    {member.joined_on && (
                      <div className="member-footer-info">
                        <span className="footer-label">Joined:</span>
                        <span className="footer-value">{member.joined_on}</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Team Tasks Placeholder Container (Wave 2) */}
      <section className="tasks-placeholder-section" aria-labelledby="team-tasks-heading">
        <div className="tasks-placeholder-header">
          <div className="tasks-heading-row">
            <h2 id="team-tasks-heading" className="tasks-title">Team Tasks</h2>
            <span className="wave2-badge">Wave 2 Feature</span>
          </div>
          <p className="tasks-subtitle">
            Sprint 4 work tracking and task lifecycle management for team members.
          </p>
        </div>

        <div className="tasks-placeholder-card">
          <div className="placeholder-content">
            <div className="tasks-icon" aria-hidden="true">📋</div>
            <h3 className="placeholder-headline">Team task information will be available in Wave 2</h3>
            <p className="placeholder-subtext">
              Task assignment (US-09), progress tracking (US-10), work review (US-12), and task
              reassignment (US-14) will be integrated here during Wave 2. Team Leads will be able
              to view, filter, and assign tasks directly to team members from this dashboard.
            </p>
            <div className="placeholder-roadmap">
              <span className="roadmap-pill">✓ US-37 Roster Foundation (Current)</span>
              <span className="roadmap-arrow">→</span>
              <span className="roadmap-pill roadmap-pill-upcoming">US-09 Task Assignment</span>
              <span className="roadmap-arrow">→</span>
              <span className="roadmap-pill roadmap-pill-upcoming">US-10 Progress Tracking</span>
            </div>
          </div>
        </div>
      </section>
    </section>
  );
}
