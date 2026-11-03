import { useState } from "react";

export default function ProjectStaffingPanel({ projectId }) {
  const [activeTab, setActiveTab] = useState("eligible"); // 'eligible' | 'roster'
  const [searchTerm, setSearchTerm] = useState("");

  return (
    <div className="staffing-panel-card">
      <div className="staffing-header">
        <div className="staffing-title-area">
          <div className="staffing-badge">US-07</div>
          <h2 className="staffing-title">Project Staffing & Team Management</h2>
          <p className="staffing-subtitle">
            Allocate eligible employees to project roster and monitor team workload.
          </p>
        </div>

        <div className="staffing-tabs">
          <button
            type="button"
            className={`staffing-tab-btn ${activeTab === "eligible" ? "active" : ""}`}
            onClick={() => setActiveTab("eligible")}
          >
            <span>Eligible Employees</span>
            <span className="tab-pill">0</span>
          </button>
          <button
            type="button"
            className={`staffing-tab-btn ${activeTab === "roster" ? "active" : ""}`}
            onClick={() => setActiveTab("roster")}
          >
            <span>Active Team Roster</span>
            <span className="tab-pill">0</span>
          </button>
        </div>
      </div>

      {activeTab === "eligible" && (
        <div className="staffing-content">
          <div className="staffing-filter-bar">
            <div className="search-input-wrapper">
              <span className="search-icon" aria-hidden="true">🔍</span>
              <input
                type="text"
                className="search-input"
                placeholder="Filter by name, designation, or department..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              {searchTerm && (
                <button
                  type="button"
                  className="clear-search-btn"
                  onClick={() => setSearchTerm("")}
                  aria-label="Clear search"
                >
                  ×
                </button>
              )}
            </div>
            <div className="staffing-count-label">
              Project #{projectId || "—"} Staffing Workspace
            </div>
          </div>

          <div className="eligible-table-wrapper">
            <table className="staffing-table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Department</th>
                  <th>Current Workload</th>
                  <th>Project Role</th>
                  <th className="th-action">Action</th>
                </tr>
              </thead>
              <tbody>
                <tr className="candidate-row">
                  <td colSpan={5} className="empty-cell">
                    <div className="staffing-empty-state">
                      <div className="empty-symbol">👥</div>
                      <h4>Candidate table initialized</h4>
                      <p>Connect with eligible employees API to populate real-time candidate roster.</p>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === "roster" && (
        <div className="staffing-content">
          <div className="staffing-empty-state">
            <div className="empty-symbol">📋</div>
            <h4>Active Roster</h4>
            <p>Team members currently assigned to this project will appear here.</p>
          </div>
        </div>
      )}
    </div>
  );
}
