import React from "react";
import {
  SKILL_ACTIONS,
  SKILL_STATUSES,
  PROFICIENCY_LABELS,
  formatSkillDate,
} from "../skills/skillRequestUtils.js";

/**
 * MySkillRequestsList Component (US-34 / Issue #161)
 *
 * Displays employee's submitted skill change proposals underneath the skills table:
 * - Action badge (ADD / UPDATE / REMOVE)
 * - Skill name and proposed attributes
 * - Status badge (PENDING / APPROVED / REJECTED)
 * - Reviewer remarks
 * - Submitted date
 */
export default function MySkillRequestsList({
  requests = [],
  isLoading = false,
  isError = false,
  error = null,
  onRefresh,
}) {
  const getActionBadgeClass = (action) => {
    switch (action?.toUpperCase()) {
      case SKILL_ACTIONS.ADD:
        return "skill-action-tag-add";
      case SKILL_ACTIONS.UPDATE:
        return "skill-action-tag-update";
      case SKILL_ACTIONS.REMOVE:
        return "skill-action-tag-remove";
      default:
        return "";
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status?.toUpperCase()) {
      case SKILL_STATUSES.APPROVED:
        return "skill-status-tag-approved";
      case SKILL_STATUSES.REJECTED:
        return "skill-status-tag-rejected";
      case SKILL_STATUSES.PENDING:
      default:
        return "skill-status-tag-pending";
    }
  };

  return (
    <div className="my-skill-requests-section" data-testid="my-skill-requests-list">
      <div className="my-skill-requests-header">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h4>My Skill Change Proposals</h4>
            <p>Track history and review decisions for all your submitted skill proposals.</p>
          </div>
          {onRefresh && (
            <button
              type="button"
              className="skill-btn-action"
              onClick={onRefresh}
              disabled={isLoading}
              title="Refresh requests"
              style={{ fontSize: "12px", padding: "4px 10px" }}
            >
              ↻ Refresh
            </button>
          )}
        </div>
      </div>

      {isLoading && (
        <div style={{ padding: "20px 0", textAlign: "center", color: "#64748b", fontSize: "13px" }}>
          Loading skill proposals...
        </div>
      )}

      {isError && (
        <div className="skill-alert-banner skill-alert-error" style={{ margin: "10px 0" }}>
          <span className="skill-alert-icon">⚠️</span>
          <div className="skill-alert-body">
            <strong>Unable to load skill requests</strong>
            <p>{error?.message || "Server error occurred while loading requests."}</p>
          </div>
        </div>
      )}

      {!isLoading && !isError && requests.length === 0 && (
        <div
          style={{
            padding: "24px",
            textAlign: "center",
            background: "#f8fafc",
            borderRadius: "8px",
            border: "1px dashed #cbd5e1",
            color: "#64748b",
            fontSize: "13.5px",
          }}
          data-testid="no-skill-requests-empty"
        >
          No skill change proposals submitted yet. Click <strong>"+ Add Skill"</strong> above to propose a new skill rating.
        </div>
      )}

      {!isLoading && !isError && requests.length > 0 && (
        <div className="profile-table-container">
          <table className="profile-skills-table" aria-label="My skill change requests">
            <thead>
              <tr>
                <th>Action</th>
                <th>Skill</th>
                <th>Proposed Proficiency</th>
                <th>Status</th>
                <th>Reviewer Remarks</th>
                <th>Submitted Date</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((req) => {
                const action = (req.action || "").toUpperCase();
                const skillName = req.skill_name || req.proposed_skill_name || `Skill #${req.skill_id || "—"}`;
                const remarks = req.remarks || req.review_remarks;
                const status = (req.status || "PENDING").toUpperCase();

                return (
                  <tr key={req.request_id} data-testid={`skill-request-row-${req.request_id}`}>
                    <td>
                      <span className={`skill-action-tag ${getActionBadgeClass(action)}`}>
                        {action}
                      </span>
                    </td>
                    <td>
                      <span className="skill-name-text">{skillName}</span>
                    </td>
                    <td>
                      {action !== SKILL_ACTIONS.REMOVE ? (
                        <span>
                          {req.proficiency ? PROFICIENCY_LABELS[req.proficiency] || req.proficiency : "—"}
                          {req.years_of_experience != null && ` (${req.years_of_experience} yrs)`}
                        </span>
                      ) : (
                        <span style={{ color: "#94a3b8" }}>— (Removal)</span>
                      )}
                    </td>
                    <td>
                      <span className={`skill-status-tag ${getStatusBadgeClass(status)}`}>
                        {status === "PENDING" && "⏳ "}
                        {status}
                      </span>
                    </td>
                    <td>
                      {remarks ? (
                        <span className="skill-remarks-text">{remarks}</span>
                      ) : (
                        <span style={{ color: "#94a3b8" }}>—</span>
                      )}
                    </td>
                    <td>
                      <span style={{ color: "#64748b", fontSize: "12.5px" }}>
                        {formatSkillDate(req.created_at)}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
