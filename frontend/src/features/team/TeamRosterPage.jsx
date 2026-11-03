import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { teamApi } from "../../api/teamApi.js";

/**
 * TeamRosterPage (US-37: [S1-FE-4] Team Lead Team Roster View)
 *
 * Integrated with backend API (GET /api/v1/teams/{id}/members)
 * Dynamic member fetching, profile enrichment, and data normalization.
 */
export default function TeamRosterPage() {
  const [searchParams] = useSearchParams();
  const teamId = searchParams.get("teamId") || "1";

  const [members, setMembers] = useState([]);

  useEffect(() => {
    let ignore = false;

    async function loadMembers() {
      try {
        const rawMembers = await teamApi.getTeamMembers(teamId);
        if (ignore) return;

        if (!Array.isArray(rawMembers)) {
          setMembers([]);
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
      } catch {
        if (!ignore) {
          setMembers([]);
        }
      }
    }

    loadMembers();

    return () => {
      ignore = true;
    };
  }, [teamId]);

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
        </div>
      </div>

      {/* Dynamic Team Member Cards Grid */}
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
                    <a href={`mailto:${member.email}`} className="member-email">
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
    </section>
  );
}
