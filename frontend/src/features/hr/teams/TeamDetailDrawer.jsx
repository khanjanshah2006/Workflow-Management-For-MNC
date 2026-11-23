import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  teamApi,
  removeTeamMember,
  updateTeam,
} from "../../../api/teamApi.js";
import { useToast } from "../../../components/common/Toast.jsx";

/**
 * TeamDetailDrawer (Issue #160 — HR Department Teams Console)
 *
 * Slide-out drawer displaying team metadata, designation info,
 * member roster with removal action (and 409 lead safeguard),
 * edit trigger, and disband confirmation flow.
 */
export default function TeamDetailDrawer({
  team,
  isOpen,
  onClose,
  onEdit,
  deptId,
  departmentName = "",
}) {
  const queryClient = useQueryClient();
  const toast = useToast();

  const [isConfirmingDisband, setIsConfirmingDisband] = useState(false);
  const [isDisbanding, setIsDisbanding] = useState(false);
  const [removingEmpId, setRemovingEmpId] = useState(null);

  // Fetch team members list
  const {
    data: rawMembers = [],
    isLoading: isMembersLoading,
  } = useQuery({
    queryKey: ["teamMembers", team?.team_id],
    queryFn: () => teamApi.getTeamMembers(team.team_id),
    enabled: isOpen && !!team?.team_id,
  });

  if (!isOpen || !team) return null;

  // Normalize members list
  const members = rawMembers.map((m) => teamApi.normalizeMember(m));

  const isDisbanded = team.status === "DISBANDED";

  const handleRemoveMember = async (empId, memberName) => {
    setRemovingEmpId(empId);
    try {
      await removeTeamMember(team.team_id, empId);
      queryClient.invalidateQueries({
        queryKey: ["teamMembers", team.team_id],
      });
      queryClient.invalidateQueries({
        queryKey: ["departmentTeams", deptId],
      });
      queryClient.invalidateQueries({ queryKey: ["departments"] });
      toast.success(`${memberName || "Member"} removed from team.`);
    } catch (err) {
      if (err.status === 409) {
        toast.error("Change the team lead before removing them.");
      } else {
        toast.error(err.message || "Failed to remove team member.");
      }
    } finally {
      setRemovingEmpId(null);
    }
  };

  const handleConfirmDisband = async () => {
    setIsDisbanding(true);
    try {
      await updateTeam(team.team_id, { status: "DISBANDED" });
      queryClient.invalidateQueries({
        queryKey: ["departmentTeams", deptId],
      });
      queryClient.invalidateQueries({ queryKey: ["departments"] });
      toast.success(`Team "${team.name}" has been disbanded.`);
      setIsConfirmingDisband(false);
      onClose();
    } catch (err) {
      toast.error(err.message || "Failed to disband team.");
    } finally {
      setIsDisbanding(false);
    }
  };

  return (
    <>
      <div
        className="dt-drawer-overlay"
        onClick={() => {
          if (!isDisbanding && !removingEmpId) {
            setIsConfirmingDisband(false);
            onClose();
          }
        }}
      />
      <div
        className="dt-drawer"
        role="region"
        aria-label={`Details for ${team.name}`}
      >
        <div className="dt-drawer-header">
          <div>
            <h2>{team.name}</h2>
            <div style={{ marginTop: "6px" }}>
              <span
                className={`dt-status-badge ${
                  isDisbanded ? "dt-status-disbanded" : "dt-status-active"
                }`}
              >
                {team.status || "ACTIVE"}
              </span>
            </div>
          </div>
          <button
            type="button"
            className="dt-modal-close"
            onClick={onClose}
            aria-label="Close details"
          >
            ✕
          </button>
        </div>

        <div className="dt-drawer-body">
          {/* Overview Section */}
          <div className="dt-drawer-section">
            <h3>Overview</h3>
            <div className="dt-drawer-field">
              <div className="dt-label">Department</div>
              <div className="dt-value">
                {departmentName || `Department #${team.dept_id}`}
              </div>
            </div>

            <div className="dt-drawer-field">
              <div className="dt-label">Description</div>
              <div className="dt-value">
                {team.description || "No description provided."}
              </div>
            </div>

            <div className="dt-drawer-field">
              <div className="dt-label">Designated Team Lead</div>
              <div
                className="dt-value"
                style={{ display: "flex", alignItems: "center", gap: "8px" }}
              >
                <strong>{team.lead_name || "Unassigned"}</strong>
                {team.lead_name && (
                  <span className="dt-lead-badge">Lead</span>
                )}
              </div>
            </div>
          </div>

          {/* Member Roster Section */}
          <div className="dt-drawer-section">
            <h3>
              Member Roster (
              {isMembersLoading ? "..." : members.length || team.member_count || 0}
              )
            </h3>
            {isMembersLoading ? (
              <div style={{ color: "#64748b", fontSize: "13px" }}>
                Loading member roster...
              </div>
            ) : members.length === 0 ? (
              <div style={{ color: "#64748b", fontSize: "13px" }}>
                No members found in this team.
              </div>
            ) : (
              <ul className="dt-member-list">
                {members.map((member) => {
                  const isLead =
                    member.emp_id === team.lead_emp_id ||
                    member.id === team.lead_emp_id;
                  const isRemovingThis = removingEmpId === member.emp_id;

                  return (
                    <li key={`roster-${member.emp_id || member.id}`} className="dt-member-item">
                      <div className="dt-member-info">
                        <div className="dt-member-name-row">
                          <span className="dt-member-name">{member.name}</span>
                          {isLead && (
                            <span className="dt-lead-badge">Team Lead</span>
                          )}
                        </div>
                        <div className="dt-member-email">{member.email}</div>
                      </div>

                      {!isDisbanded && (
                        <button
                          type="button"
                          className="dt-btn-remove"
                          disabled={isLead || isRemovingThis || isDisbanding}
                          title={
                            isLead
                              ? "Cannot remove designated team lead. Reassign lead first."
                              : "Remove member from team"
                          }
                          onClick={() =>
                            handleRemoveMember(member.emp_id, member.name)
                          }
                        >
                          {isRemovingThis ? "..." : "Remove"}
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Disband Confirmation Dialog */}
          {isConfirmingDisband && (
            <div className="dt-confirm-box">
              <p>
                Are you sure you want to disband <strong>{team.name}</strong>?
                The team lead will be demoted to an employee and the team will be marked as disbanded.
              </p>
              <div className="dt-confirm-actions">
                <button
                  type="button"
                  className="dt-btn-cancel"
                  onClick={() => setIsConfirmingDisband(false)}
                  disabled={isDisbanding}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="dt-btn-danger"
                  onClick={handleConfirmDisband}
                  disabled={isDisbanding}
                >
                  {isDisbanding ? "Disbanding..." : "Confirm Disband"}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Drawer Actions */}
        {!isDisbanded && !isConfirmingDisband && (
          <div className="dt-drawer-actions">
            <button
              type="button"
              className="dt-btn-cancel"
              onClick={() => onEdit(team)}
              disabled={isDisbanding}
            >
              Edit Team
            </button>
            <button
              type="button"
              className="dt-btn-danger"
              onClick={() => setIsConfirmingDisband(true)}
              disabled={isDisbanding}
            >
              Disband Team
            </button>
          </div>
        )}
      </div>
    </>
  );
}
