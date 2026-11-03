import { useSearchParams } from "react-router-dom";

/**
 * TeamRosterPage (US-37: [S1-FE-4] Team Lead Team Roster View)
 *
 * Initial Page Structure:
 * - Page Header with eyebrow, title, and description.
 * - Team context and active team indicator.
 * - Team member card layout displaying employee name, role, email, and active badge.
 */
export default function TeamRosterPage() {
  const [searchParams] = useSearchParams();
  const teamId = searchParams.get("teamId") || "1";

  // Demo initial team members for structure verification
  const demoMembers = [
    {
      id: 1,
      emp_id: 101,
      name: "Rahul Sharma",
      role: "Software Engineer",
      email: "rahul@example.com",
      status: "ACTIVE",
    },
    {
      id: 2,
      emp_id: 102,
      name: "Priya Patel",
      role: "Frontend Engineer",
      email: "priya@example.com",
      status: "ACTIVE",
    },
  ];

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

      {/* Team Member Cards Grid */}
      <div className="roster-section">
        <div className="section-meta-row">
          <h2 className="section-heading">Team Members ({demoMembers.length})</h2>
        </div>

        <div className="team-cards-grid">
          {demoMembers.map((member) => {
            const isActive = member.status === "ACTIVE";
            const initials = member.name
              .split(" ")
              .map((n) => n[0])
              .slice(0, 2)
              .join("")
              .toUpperCase();

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
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
