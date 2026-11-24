import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueries } from "@tanstack/react-query";
import { useAuth } from "../../../context/AuthContext.jsx";
import { normalizeRole } from "../../../auth/session.js";
import {
  getDepartments,
  getDepartmentTeams,
} from "../../../api/teamApi.js";
import { useToast } from "../../../components/common/Toast.jsx";
import { calculateDepartmentTeamCount } from "./teamFormUtils.js";
import TeamFormModal from "./TeamFormModal.jsx";
import TeamDetailDrawer from "./TeamDetailDrawer.jsx";
import "./teams.css";

/**
 * DepartmentTeamsPage (Issue #160 — S1-FE-2)
 *
 * Route: /hr/teams
 * Permissions: HR, ADMIN (fail-closed for all other roles)
 *
 * Provides department-level team management:
 * - Department selection sidebar with team counts
 * - Team grid with lead designation and member counts
 * - Filter toggle for disbanded teams
 * - Create and Edit modal workflows
 * - Team detail drawer with member roster and disbanding
 */
export default function DepartmentTeamsPage() {
  const { user, role } = useAuth();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  // Belt-and-suspenders role check (ProtectedRoute also enforces this)
  const currentRole = normalizeRole(role || user?.user_type || user?.role || "");
  const isAuthorized = currentRole === "HR" || currentRole === "ADMIN";

  // URL state
  const deptParam = searchParams.get("dept_id");
  const showDisbanded = searchParams.get("include_disbanded") === "true";

  // Modal and drawer UI states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTeam, setEditingTeam] = useState(null);
  const [selectedTeam, setSelectedTeam] = useState(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Load departments
  const {
    data: departments = [],
    isLoading: isDeptsLoading,
    isError: isDeptsError,
    error: deptsError,
    refetch: refetchDepts,
  } = useQuery({
    queryKey: ["departments"],
    queryFn: getDepartments,
    enabled: isAuthorized,
  });

  // Query teams for all departments to derive accurate active team counts
  const deptTeamQueries = useQueries({
    queries: departments.map((d) => ({
      queryKey: ["departmentTeams", d.dept_id, false],
      queryFn: () => getDepartmentTeams(d.dept_id, { includeDisbanded: false }),
      enabled: isAuthorized && Boolean(d.dept_id),
      staleTime: 30000,
    })),
  });

  // Determine active department ID
  const activeDeptId = deptParam
    ? Number(deptParam)
    : departments.length > 0
    ? departments[0].dept_id
    : null;

  const activeDept = departments.find((d) => d.dept_id === activeDeptId);

  // Load teams for active department
  const {
    data: teams = [],
    isLoading: isTeamsLoading,
    isError: isTeamsError,
    error: teamsError,
    refetch: refetchTeams,
  } = useQuery({
    queryKey: ["departmentTeams", activeDeptId, showDisbanded],
    queryFn: () =>
      getDepartmentTeams(activeDeptId, { includeDisbanded: showDisbanded }),
    enabled: isAuthorized && activeDeptId != null,
  });

  if (!isAuthorized) {
    return (
      <section className="page department-teams-page">
        <div className="page-eyebrow">ACCESS CONTROL</div>
        <h1>403 — Unauthorized Access</h1>
        <p className="page-description">
          Your current assigned role ({role || user?.user_type || "User"}) does
          not have permissions to manage department teams.
        </p>
        <div className="placeholder-panel">
          <div className="placeholder-symbol">🔒</div>
          <h2>Restricted View</h2>
          <p>
            Department team management is restricted to Human Resources (HR)
            and Administrators.
          </p>
        </div>
      </section>
    );
  }

  const handleSelectDepartment = (deptId) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("dept_id", String(deptId));
      return next;
    });
  };

  const handleToggleDisbanded = (checked) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (checked) {
        next.set("include_disbanded", "true");
      } else {
        next.delete("include_disbanded");
      }
      return next;
    });
  };

  const handleOpenCreate = () => {
    setEditingTeam(null);
    setIsModalOpen(true);
  };

  const handleOpenEdit = (team) => {
    setIsDrawerOpen(false);
    setEditingTeam(team);
    setIsModalOpen(true);
  };

  const handleCardClick = (team) => {
    setSelectedTeam(team);
    setIsDrawerOpen(true);
  };

  return (
    <section className="page department-teams-page">
      {/* Header */}
      <div className="dt-header">
        <div>
          <div className="page-eyebrow">HUMAN RESOURCES</div>
          <h1 className="page-title">Department Teams</h1>
          <p className="page-description">
            Organize department workflows, designate team leads, and manage member rosters.
          </p>
        </div>

        <div className="dt-header-actions">
          <label className="dt-show-disbanded-control">
            <input
              type="checkbox"
              id="dt-show-disbanded-toggle"
              checked={showDisbanded}
              onChange={(e) => handleToggleDisbanded(e.target.checked)}
            />
            <span>Show disbanded</span>
          </label>

          <button
            type="button"
            className="dt-btn-primary"
            onClick={handleOpenCreate}
            disabled={!activeDeptId}
          >
            + Create team
          </button>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="dt-layout">
        {/* Department Sidebar */}
        <aside className="dt-dept-sidebar" aria-label="Department Selection">
          {isDeptsLoading ? (
            <div style={{ padding: "16px", color: "#64748b", fontSize: "14px" }}>
              Loading departments...
            </div>
          ) : isDeptsError ? (
            <div style={{ padding: "16px", color: "#ef4444", fontSize: "13px" }}>
              Failed to load departments.
              <button
                type="button"
                style={{ display: "block", marginTop: "8px" }}
                className="dt-btn-cancel"
                onClick={() => refetchDepts()}
              >
                Retry
              </button>
            </div>
          ) : (
            <ul className="dt-dept-list">
              {departments.map((dept, index) => {
                const isActive = dept.dept_id === activeDeptId;
                const teamsData = deptTeamQueries[index]?.data;
                const count = calculateDepartmentTeamCount(dept, teamsData);
                return (
                  <li
                    key={`dept-${dept.dept_id}`}
                    className={`dt-dept-item ${isActive ? "dt-active" : ""}`}
                    onClick={() => handleSelectDepartment(dept.dept_id)}
                  >
                    <span>{dept.name}</span>
                    <span className="dt-dept-count">{count}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>

        {/* Teams Content Area */}
        <main className="dt-content">
          {isTeamsLoading ? (
            <div className="dt-loading-state">
              <div className="dt-loading-icon">⏳</div>
              <p>Loading teams...</p>
            </div>
          ) : isTeamsError ? (
            <div className="dt-error-state">
              <p style={{ color: "#ef4444", fontWeight: "600" }}>
                {teamsError?.message || "Failed to load teams for this department."}
              </p>
              <button
                type="button"
                className="dt-btn-cancel"
                onClick={() => refetchTeams()}
                style={{ marginTop: "12px" }}
              >
                Retry
              </button>
            </div>
          ) : teams.length === 0 ? (
            <div className="dt-empty-state">
              <div className="dt-empty-icon">👥</div>
              <h3>No teams found</h3>
              <p>
                {showDisbanded
                  ? "There are no active or disbanded teams in this department."
                  : "No active teams found in this department. Click \"+ Create team\" to set up a new team."}
              </p>
              <button
                type="button"
                className="dt-btn-primary"
                onClick={handleOpenCreate}
                style={{ marginTop: "16px" }}
              >
                + Create team
              </button>
            </div>
          ) : (
            <div className="dt-team-grid">
              {teams.map((team) => {
                const isDisbanded = team.status === "DISBANDED";
                return (
                  <div
                    key={`team-card-${team.team_id}`}
                    className={`dt-team-card ${
                      isDisbanded ? "dt-disbanded" : ""
                    }`}
                    onClick={() => handleCardClick(team)}
                    tabIndex={0}
                    role="button"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleCardClick(team);
                      }
                    }}
                  >
                    <div className="dt-team-card-header">
                      <h3 className="dt-team-name">{team.name}</h3>
                      <span
                        className={`dt-status-badge ${
                          isDisbanded
                            ? "dt-status-disbanded"
                            : "dt-status-active"
                        }`}
                      >
                        {team.status || "ACTIVE"}
                      </span>
                    </div>

                    <p className="dt-team-desc">
                      {team.description || "No description provided."}
                    </p>

                    <div className="dt-team-meta">
                      <span>👤 {team.lead_name || "Unassigned"}</span>
                      <span>
                        👥 {team.member_count !== undefined ? team.member_count : 0} members
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </main>
      </div>

      {/* Create / Edit Team Modal */}
      <TeamFormModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={(msg) => toast.success(msg)}
        deptId={activeDeptId}
        editingTeam={editingTeam}
      />

      {/* Team Detail Drawer */}
      <TeamDetailDrawer
        team={selectedTeam}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onEdit={handleOpenEdit}
        deptId={activeDeptId}
        departmentName={activeDept?.name || ""}
      />
    </section>
  );
}
