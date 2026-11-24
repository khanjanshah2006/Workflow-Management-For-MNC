import React, { useState, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createDepartmentTeam,
  updateTeam,
  addTeamMembers,
  removeTeamMember,
  searchEmployees,
  teamApi,
} from "../../../api/teamApi.js";
import {
  validateTeamForm,
  buildCreatePayload,
  diffMembers,
} from "./teamFormUtils.js";

const NO_MEMBERS = Object.freeze([]);

/**
 * TeamFormModal (Issue #160 — HR Department Teams Console)
 *
 * Handles team creation and editing with searchable employee selection,
 * lead designation, member management, and conflict handling.
 */
export default function TeamFormModal({
  isOpen,
  onClose,
  onSuccess,
  deptId,
  editingTeam = null,
}) {
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [leadEmpId, setLeadEmpId] = useState(null);
  const [memberEmpIds, setMemberEmpIds] = useState([]);
  const [initialMemberIds, setInitialMemberIds] = useState([]);
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const prevOpenRef = useRef(false);
  const prevEditingTeamIdRef = useRef(null);

  // Fetch team members if editing (stable NO_MEMBERS fallback prevents re-renders)
  const { data: rawTeamMembers = NO_MEMBERS } = useQuery({
    queryKey: ["teamMembers", editingTeam?.team_id],
    queryFn: () => teamApi.getTeamMembers(editingTeam.team_id),
    enabled: isOpen && !!editingTeam?.team_id,
  });

  // Fetch eligible active employees in this department
  const { data: employees = [], isLoading: isEmployeesLoading } = useQuery({
    queryKey: ["employees", deptId, employeeSearch],
    queryFn: () => searchEmployees({ deptId, search: employeeSearch }),
    enabled: isOpen && !!deptId,
  });

  // Populate or reset form fields strictly when modal opens or target team changes
  useEffect(() => {
    if (!isOpen) {
      prevOpenRef.current = false;
      prevEditingTeamIdRef.current = null;
      setErrors({});
      setIsSubmitting(false);
      return;
    }

    const wasClosed = !prevOpenRef.current;
    const currentTeamId = editingTeam?.team_id ?? null;
    const teamChanged = currentTeamId !== prevEditingTeamIdRef.current;

    if (wasClosed || teamChanged) {
      prevOpenRef.current = true;
      prevEditingTeamIdRef.current = currentTeamId;

      if (editingTeam) {
        setName(editingTeam.name || "");
        setDescription(editingTeam.description || "");
        const leadId = editingTeam.lead_emp_id || null;
        setLeadEmpId(leadId);

        const existingMemberIds = rawTeamMembers
          .map((m) => m.emp_id || m.employee_id || m.id)
          .filter((id) => id != null);

        if (leadId && !existingMemberIds.includes(leadId)) {
          existingMemberIds.push(leadId);
        }

        setMemberEmpIds(existingMemberIds);
        setInitialMemberIds(existingMemberIds);
      } else {
        setName("");
        setDescription("");
        setLeadEmpId(null);
        setMemberEmpIds([]);
        setInitialMemberIds([]);
        setEmployeeSearch("");
      }
      setErrors({});
    }
  }, [isOpen, editingTeam]);

  // When editing, populate members once rawTeamMembers resolves asynchronously
  useEffect(() => {
    if (
      isOpen &&
      editingTeam &&
      rawTeamMembers.length > 0 &&
      initialMemberIds.length === 0
    ) {
      const leadId = editingTeam.lead_emp_id || null;
      const loadedMemberIds = rawTeamMembers
        .map((m) => m.emp_id || m.employee_id || m.id)
        .filter((id) => id != null);

      if (leadId && !loadedMemberIds.includes(leadId)) {
        loadedMemberIds.push(leadId);
      }

      setMemberEmpIds(loadedMemberIds);
      setInitialMemberIds(loadedMemberIds);
    }
  }, [isOpen, editingTeam, rawTeamMembers, initialMemberIds.length]);

  if (!isOpen) return null;

  const handleSelectLead = (empId) => {
    setLeadEmpId(empId);
    setMemberEmpIds((prev) => (prev.includes(empId) ? prev : [...prev, empId]));
    if (errors.leadEmpId) {
      setErrors((prev) => ({ ...prev, leadEmpId: undefined }));
    }
  };

  const handleToggleMember = (empId) => {
    if (empId === leadEmpId) return; // Lead cannot be removed from members
    setMemberEmpIds((prev) =>
      prev.includes(empId)
        ? prev.filter((id) => id !== empId)
        : [...prev, empId]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrors({});

    const { valid, errors: validationErrors } = validateTeamForm({
      name,
      description,
      leadEmpId,
    });

    if (!valid) {
      setErrors(validationErrors);
      return;
    }

    setIsSubmitting(true);

    try {
      if (editingTeam) {
        // Update team name, description, lead
        await updateTeam(editingTeam.team_id, {
          name: name.trim(),
          description: description.trim() || null,
          lead_emp_id: leadEmpId,
        });

        // Sync member additions/removals
        const { toAdd, toRemove } = diffMembers(
          initialMemberIds,
          memberEmpIds,
          leadEmpId
        );

        if (toAdd.length > 0) {
          await addTeamMembers(editingTeam.team_id, toAdd);
        }

        for (const remId of toRemove) {
          await removeTeamMember(editingTeam.team_id, remId);
        }

        queryClient.invalidateQueries({
          queryKey: ["departmentTeams", deptId],
        });
        queryClient.invalidateQueries({
          queryKey: ["teamMembers", editingTeam.team_id],
        });
        queryClient.invalidateQueries({ queryKey: ["departments"] });

        onSuccess?.(`Team "${name.trim()}" updated successfully.`);
      } else {
        // Create team
        const payload = buildCreatePayload({
          name,
          description,
          leadEmpId,
          memberEmpIds,
        });

        await createDepartmentTeam(deptId, payload);

        queryClient.invalidateQueries({
          queryKey: ["departmentTeams", deptId],
        });
        queryClient.invalidateQueries({ queryKey: ["departments"] });

        onSuccess?.(`Team "${name.trim()}" created successfully.`);
      }

      onClose();
    } catch (err) {
      const errMsg = err.message || "";
      if (
        err.status === 409 ||
        errMsg.toLowerCase().includes("already exists")
      ) {
        setErrors((prev) => ({
          ...prev,
          name: "A team with this name already exists in this department.",
        }));
      } else {
        setErrors((prev) => ({
          ...prev,
          form: errMsg || "Failed to save team.",
        }));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="dt-modal-overlay" role="dialog" aria-modal="true">
      <div className="dt-modal">
        <div className="dt-modal-header">
          <h2>{editingTeam ? "Edit Team" : "Create New Team"}</h2>
          <button
            type="button"
            className="dt-modal-close"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="dt-modal-body">
            {errors.form && (
              <div
                className="dt-field-error"
                style={{ marginBottom: "16px", fontWeight: "600" }}
              >
                {errors.form}
              </div>
            )}

            {/* Team Name */}
            <div className="dt-form-group">
              <label htmlFor="dt-team-name-input">
                Team Name <span className="dt-required">*</span>
              </label>
              <input
                id="dt-team-name-input"
                type="text"
                className={`dt-form-input ${errors.name ? "dt-input-error" : ""}`}
                value={name}
                maxLength={100}
                onChange={(e) => {
                  setName(e.target.value);
                  if (errors.name) {
                    setErrors((prev) => ({ ...prev, name: undefined }));
                  }
                }}
                placeholder="e.g. Frontend Engineering"
                disabled={isSubmitting}
              />
              <div className="dt-char-count">{name.length} / 100</div>
              {errors.name && (
                <div className="dt-field-error">{errors.name}</div>
              )}
            </div>

            {/* Description */}
            <div className="dt-form-group">
              <label htmlFor="dt-team-desc-input">Description</label>
              <textarea
                id="dt-team-desc-input"
                className={`dt-form-textarea ${errors.description ? "dt-input-error" : ""}`}
                value={description}
                maxLength={500}
                onChange={(e) => {
                  setDescription(e.target.value);
                  if (errors.description) {
                    setErrors((prev) => ({ ...prev, description: undefined }));
                  }
                }}
                placeholder="Briefly describe the team's scope or purpose"
                disabled={isSubmitting}
              />
              <div className="dt-char-count">{description.length} / 500</div>
              {errors.description && (
                <div className="dt-field-error">{errors.description}</div>
              )}
            </div>

            {/* Employee Search */}
            <div className="dt-form-group">
              <label htmlFor="dt-emp-search-input">Search Employees</label>
              <input
                id="dt-emp-search-input"
                type="text"
                className="dt-search-input"
                value={employeeSearch}
                onChange={(e) => setEmployeeSearch(e.target.value)}
                placeholder="Filter department employees by name or email..."
                disabled={isSubmitting}
              />
            </div>

            {/* Team Lead Selection (Radio) */}
            <div className="dt-form-group">
              <label>
                Designate Team Lead <span className="dt-required">*</span>
              </label>
              {errors.leadEmpId && (
                <div className="dt-field-error" style={{ marginBottom: "6px" }}>
                  {errors.leadEmpId}
                </div>
              )}
              <div className="dt-employee-list">
                {isEmployeesLoading ? (
                  <div style={{ padding: "12px", color: "#64748b", fontSize: "13px" }}>
                    Loading employees...
                  </div>
                ) : employees.length === 0 ? (
                  <div style={{ padding: "12px", color: "#64748b", fontSize: "13px" }}>
                    No active employees found in this department.
                  </div>
                ) : (
                  employees.map((emp) => {
                    const isSelected = leadEmpId === emp.emp_id;
                    return (
                      <label
                        key={`lead-${emp.emp_id}`}
                        className={`dt-employee-option ${isSelected ? "dt-selected" : ""}`}
                      >
                        <input
                          type="radio"
                          name="team-lead-select"
                          checked={isSelected}
                          onChange={() => handleSelectLead(emp.emp_id)}
                          disabled={isSubmitting}
                        />
                        <div className="dt-employee-info">
                          <span className="dt-employee-name">
                            {emp.full_name}
                          </span>
                          <span className="dt-employee-detail">
                            {" "}— {emp.email || emp.designation || `ID: ${emp.emp_id}`}
                          </span>
                        </div>
                        {isSelected && (
                          <span className="dt-lead-badge">Selected Lead</span>
                        )}
                      </label>
                    );
                  })
                )}
              </div>
            </div>

            {/* Additional Members Selection (Checkboxes) */}
            <div className="dt-form-group">
              <label>Manage Team Members</label>
              <div className="dt-employee-list">
                {isEmployeesLoading ? (
                  <div style={{ padding: "12px", color: "#64748b", fontSize: "13px" }}>
                    Loading employees...
                  </div>
                ) : employees.length === 0 ? (
                  <div style={{ padding: "12px", color: "#64748b", fontSize: "13px" }}>
                    No employees available.
                  </div>
                ) : (
                  employees.map((emp) => {
                    const isLead = leadEmpId === emp.emp_id;
                    const isMember = memberEmpIds.includes(emp.emp_id);
                    return (
                      <label
                        key={`member-${emp.emp_id}`}
                        className={`dt-employee-option ${isMember ? "dt-selected" : ""} ${isLead ? "dt-disabled" : ""}`}
                        title={isLead ? "Designated team lead is automatically a member" : ""}
                      >
                        <input
                          type="checkbox"
                          checked={isMember || isLead}
                          onChange={() => handleToggleMember(emp.emp_id)}
                          disabled={isLead || isSubmitting}
                        />
                        <div className="dt-employee-info">
                          <span className="dt-employee-name">
                            {emp.full_name}
                          </span>
                          <span className="dt-employee-detail">
                            {" "}— {emp.email || emp.designation}
                          </span>
                        </div>
                        {isLead && (
                          <span className="dt-lead-badge">Team Lead</span>
                        )}
                      </label>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          <div className="dt-modal-footer">
            <button
              type="button"
              className="dt-btn-cancel"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="dt-btn-primary"
              disabled={isSubmitting}
            >
              {isSubmitting
                ? "Saving..."
                : editingTeam
                ? "Save Changes"
                : "Create Team"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
