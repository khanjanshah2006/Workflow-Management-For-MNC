import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { reassignTask, validateReassignReason } from "../../api/tasksApi";
import { teamApi } from "../../api/teamApi";

/**
 * ReassignTaskModal Component (US-14 / US-09)
 *
 * Allows a Team Lead to reassign an active task to another team member:
 * - Displays current task information and current assignee
 * - Lists eligible team members from live roster (excluding current assignee)
 * - Enforces mandatory business justification reason (minimum 10 characters)
 * - Dispatches PUT /api/v1/tasks/{id}/reassign
 */
export default function ReassignTaskModal({
  isOpen = false,
  task = null,
  onClose,
  onSuccess,
}) {
  const [newAssigneeId, setNewAssigneeId] = useState("");
  const [reason, setReason] = useState("");
  const [validationError, setValidationError] = useState(null);

  const teamId = task?.team_id || 1;

  // Fetch live team members for the task's team
  const { data: rawTeamMembers = [], isLoading: isLoadingMembers } = useQuery({
    queryKey: ["teams", teamId, "members"],
    queryFn: () => teamApi.getTeamMembers(teamId, task?.project_id || null),
    enabled: isOpen && Boolean(teamId),
  });

  const teamMembers = (rawTeamMembers || []).map((m) => teamApi.normalizeMember(m));

  // Filter out the current assignee to avoid no-op reassignment
  const currentAssigneeId = task?.assigned_to || task?.assignee?.emp_id;
  const eligibleAssignees = teamMembers.filter(
    (member) => String(member.emp_id || member.id) !== String(currentAssigneeId)
  );

  const handleClose = () => {
    setNewAssigneeId("");
    setReason("");
    setValidationError(null);
    if (onClose) onClose();
  };

  const reassignMutation = useMutation({
    mutationFn: ({ taskId, payload }) => reassignTask(taskId, payload),
    onSuccess: (data) => {
      handleClose();
      if (onSuccess) onSuccess(data);
    },
    onError: (err) => {
      setValidationError(err?.message || "Failed to reassign task. Please check your justification.");
    },
  });

  if (!isOpen || !task) return null;

  const handleReasonChange = (e) => {
    const val = e.target.value;
    setReason(val);
    if (validationError) {
      const check = validateReassignReason(val);
      if (check.valid) {
        setValidationError(null);
      }
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setValidationError(null);

    if (!newAssigneeId) {
      setValidationError("Please select a new team member to assign this task to.");
      return;
    }

    const checkReason = validateReassignReason(reason);
    if (!checkReason.valid) {
      setValidationError(checkReason.error);
      return;
    }

    reassignMutation.mutate({
      taskId: task.task_id,
      payload: {
        new_assignee_id: Number(newAssigneeId),
        reason: reason.trim(),
      },
    });
  };

  const charCount = reason.trim().length;
  const isReasonValid = charCount >= 10;

  return (
    <div className="modal-backdrop" onClick={handleClose} role="dialog" aria-modal="true" aria-labelledby="reassign-modal-title">
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <h2 id="reassign-modal-title">Reassign Task #{task.task_id}</h2>
            <p className="modal-task-subtitle">{task.title}</p>
          </div>
          <button className="btn-modal-close" onClick={handleClose} aria-label="Close dialog" disabled={reassignMutation.isPending}>
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {validationError && (
              <div className="alert-banner alert-banner-danger" role="alert">
                <span className="alert-icon">⚠️</span>
                <span>{validationError}</span>
              </div>
            )}

            {/* Current Assignment Overview */}
            <div className="assignment-overview-card">
              <div className="overview-row">
                <span className="overview-label">Current Assignee:</span>
                <span className="overview-val font-semibold">
                  {task.assignee?.full_name || (task.assigned_to ? `Employee #${task.assigned_to}` : "Unassigned")}
                </span>
              </div>
              <div className="overview-row">
                <span className="overview-label">Task Priority:</span>
                <span className={`badge-pill badge-priority-${(task.priority || "MEDIUM").toLowerCase()}`}>
                  {task.priority || "MEDIUM"}
                </span>
              </div>
              <div className="overview-row">
                <span className="overview-label">Current Status:</span>
                <span className="badge-pill badge-status-default">
                  {task.status || "TODO"}
                </span>
              </div>
            </div>

            {/* New Assignee Selection */}
            <div className="form-group">
              <label htmlFor="reassign-new-assignee" className="form-label">
                New Assignee <span className="field-required">*</span>
              </label>
              <select
                id="reassign-new-assignee"
                className="form-control"
                value={newAssigneeId}
                onChange={(e) => setNewAssigneeId(e.target.value)}
                required
                disabled={reassignMutation.isPending || isLoadingMembers}
              >
                <option value="">
                  {isLoadingMembers
                    ? "Loading available team members..."
                    : eligibleAssignees.length === 0
                    ? "No other team members available in this team"
                    : "-- Select New Assignee --"}
                </option>
                {eligibleAssignees.map((member) => (
                  <option key={member.emp_id || member.id} value={member.emp_id || member.id}>
                    {member.name} — {member.role || "Team Member"}
                  </option>
                ))}
              </select>
            </div>

            {/* Business Justification Textarea */}
            <div className="form-group">
              <div className="form-label-with-counter">
                <label htmlFor="reassign-reason" className="form-label">
                  Business Justification Reason <span className="field-required">*</span>
                </label>
                <span className={`char-counter ${charCount < 10 ? "char-counter-insufficient" : "char-counter-valid"}`}>
                  {charCount}/10 min characters
                </span>
              </div>
              <textarea
                id="reassign-reason"
                rows={4}
                className="form-control"
                placeholder="Explain the reason for workload reassignment (e.g., skill alignment, unexpected leave, emergency sprint blocker)..."
                value={reason}
                onChange={handleReasonChange}
                required
                disabled={reassignMutation.isPending}
              />
              <span className="form-hint">
                Mandatory minimum 10 characters. Both the previous and new assignees will receive notifications.
              </span>
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleClose}
              disabled={reassignMutation.isPending}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={reassignMutation.isPending || !newAssigneeId || !isReasonValid}
            >
              {reassignMutation.isPending ? "Reassigning..." : "Confirm Reassignment"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
