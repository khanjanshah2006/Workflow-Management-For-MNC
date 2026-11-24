import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { createTask, validateTaskDates } from "../../api/tasksApi";
import { getProjects, getMilestones } from "../../api/projectsApi";
import { teamApi } from "../../api/teamApi";
import { useAuth } from "../../context/AuthContext";

/**
 * CreateTaskModal Component (US-09)
 *
 * Team Lead / PM task creation modal:
 * - Selects project and associated milestones
 * - Loads live team members from roster API for team assignment
 * - Enforces date picker validation: due_date >= start_date
 * - Dispatches POST /api/v1/tasks
 */
export default function CreateTaskModal({
  isOpen = false,
  onClose,
  onSuccess,
  defaultProjectId = null,
  defaultTeamId = null,
}) {
  const { user } = useAuth();
  const ledTeamIds = user?.led_team_ids || [];
  const initialTeamId = defaultTeamId
    ? String(defaultTeamId)
    : (ledTeamIds.length > 0 ? String(ledTeamIds[0]) : (user?.team_id ? String(user.team_id) : ""));

  const [formData, setFormData] = useState({
    title: "",
    description: "",
    priority: "MEDIUM",
    project_id: defaultProjectId ? String(defaultProjectId) : "",
    team_id: initialTeamId,
    milestone_id: "",
    assigned_to: "",
    start_date: "",
    due_date: "",
  });

  const [validationError, setValidationError] = useState(null);

  // Fetch available projects
  const { data: projects = [], isLoading: isLoadingProjects } = useQuery({
    queryKey: ["projects"],
    queryFn: () => getProjects(),
    enabled: isOpen,
  });

  const effectiveProjectId = formData.project_id || (projects.length > 0 ? String(projects[0].project_id) : "");

  // Fetch milestones for selected project
  const { data: milestones = [], isLoading: isLoadingMilestones } = useQuery({
    queryKey: ["projects", effectiveProjectId, "milestones"],
    queryFn: () => getMilestones(effectiveProjectId),
    enabled: isOpen && Boolean(effectiveProjectId),
  });

  // Fetch live team members from roster API (US-37 / US-09 requirement)
  const { data: rawTeamMembers = [], isLoading: isLoadingMembers } = useQuery({
    queryKey: ["teams", formData.team_id, "members"],
    queryFn: () => teamApi.getTeamMembers(formData.team_id, effectiveProjectId || null),
    enabled: isOpen && Boolean(formData.team_id),
  });

  // Normalize member records
  const teamMembers = (rawTeamMembers || []).map((m) => teamApi.normalizeMember(m));

  const resetForm = () => {
    setFormData({
      title: "",
      description: "",
      priority: "MEDIUM",
      project_id: defaultProjectId ? String(defaultProjectId) : "",
      team_id: defaultTeamId
        ? String(defaultTeamId)
        : (ledTeamIds.length > 0 ? String(ledTeamIds[0]) : (user?.team_id ? String(user.team_id) : "")),
      milestone_id: "",
      assigned_to: "",
      start_date: "",
      due_date: "",
    });
    setValidationError(null);
  };

  const handleClose = () => {
    resetForm();
    if (onClose) onClose();
  };

  // Mutation for creating task
  const createMutation = useMutation({
    mutationFn: (payload) => createTask(payload),
    onSuccess: (data) => {
      resetForm();
      if (onSuccess) onSuccess(data);
      if (onClose) onClose();
    },
    onError: (err) => {
      setValidationError(err?.message || "Failed to create task. Please verify your inputs.");
    },
  });

  if (!isOpen) return null;

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => {
      const updated = { ...prev, [name]: value };

      // Instant date validation
      if (name === "start_date" || name === "due_date") {
        const start = name === "start_date" ? value : prev.start_date;
        const due = name === "due_date" ? value : prev.due_date;
        const check = validateTaskDates(start, due);
        if (!check.valid) {
          setValidationError(check.error);
        } else if (validationError && validationError.includes("Due date")) {
          setValidationError(null);
        }
      }

      return updated;
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setValidationError(null);

    const titleTrimmed = formData.title.trim();
    if (!titleTrimmed) {
      setValidationError("Task title is required.");
      return;
    }

    const projectIdNum = Number(effectiveProjectId);
    if (!projectIdNum || projectIdNum <= 0) {
      setValidationError("Please select a project.");
      return;
    }

    const teamIdNum = Number(formData.team_id);
    if (!teamIdNum || teamIdNum <= 0) {
      setValidationError("Please specify a valid team ID.");
      return;
    }

    const dateCheck = validateTaskDates(formData.start_date, formData.due_date);
    if (!dateCheck.valid) {
      setValidationError(dateCheck.error);
      return;
    }

    const payload = {
      title: titleTrimmed,
      description: formData.description.trim() || undefined,
      priority: formData.priority,
      project_id: projectIdNum,
      team_id: teamIdNum,
      milestone_id: formData.milestone_id ? Number(formData.milestone_id) : undefined,
      assigned_to: formData.assigned_to ? Number(formData.assigned_to) : undefined,
      start_date: formData.start_date || undefined,
      due_date: formData.due_date || undefined,
    };

    createMutation.mutate(payload);
  };

  return (
    <div className="modal-backdrop" onClick={handleClose} role="dialog" aria-modal="true" aria-labelledby="create-task-modal-title">
      <div className="modal-dialog modal-dialog-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <h2 id="create-task-modal-title">Create New Task</h2>
            <p className="modal-task-subtitle">Define task details, assign team members, and set milestone deadlines.</p>
          </div>
          <button className="btn-modal-close" onClick={handleClose} aria-label="Close dialog" disabled={createMutation.isPending}>
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

            {/* Task Title */}
            <div className="form-group">
              <label htmlFor="task-title" className="form-label">
                Task Title <span className="field-required">*</span>
              </label>
              <input
                id="task-title"
                name="title"
                type="text"
                className="form-control"
                placeholder="e.g. Implement OAuth token refresh flow"
                value={formData.title}
                onChange={handleChange}
                maxLength={200}
                required
                disabled={createMutation.isPending}
              />
            </div>

            {/* Project & Milestone Row */}
            <div className="form-row form-grid-2">
              <div className="form-group">
                <label htmlFor="task-project" className="form-label">
                  Project <span className="field-required">*</span>
                </label>
                <select
                  id="task-project"
                  name="project_id"
                  className="form-control"
                  value={effectiveProjectId}
                  onChange={handleChange}
                  required
                  disabled={createMutation.isPending || isLoadingProjects}
                >
                  <option value="">{isLoadingProjects ? "Loading projects..." : "-- Select Project --"}</option>
                  {projects.map((proj) => (
                    <option key={proj.project_id} value={proj.project_id}>
                      {proj.name} ({proj.project_code || `#${proj.project_id}`})
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="task-milestone" className="form-label">
                  Milestone (Optional)
                </label>
                <select
                  id="task-milestone"
                  name="milestone_id"
                  className="form-control"
                  value={formData.milestone_id}
                  onChange={handleChange}
                  disabled={createMutation.isPending || !effectiveProjectId || isLoadingMilestones}
                >
                  <option value="">
                    {!effectiveProjectId
                      ? "Select project first"
                      : isLoadingMilestones
                      ? "Loading milestones..."
                      : milestones.length === 0
                      ? "No milestones defined"
                      : "-- No Milestone --"}
                  </option>
                  {milestones.map((m) => (
                    <option key={m.id || m.milestone_id} value={m.id || m.milestone_id}>
                      {m.title}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Team & Live Member Assignee Row */}
            <div className="form-row form-grid-2">
              <div className="form-group">
                <label htmlFor="task-team" className="form-label">
                  Team ID <span className="field-required">*</span>
                </label>
                <input
                  id="task-team"
                  name="team_id"
                  type="number"
                  min="1"
                  className="form-control"
                  placeholder="e.g. 1"
                  value={formData.team_id}
                  onChange={handleChange}
                  required
                  disabled={createMutation.isPending}
                />
              </div>

              <div className="form-group">
                <label htmlFor="task-assignee" className="form-label">
                  Assign To (Live Team Roster)
                </label>
                <select
                  id="task-assignee"
                  name="assigned_to"
                  className="form-control"
                  value={formData.assigned_to}
                  onChange={handleChange}
                  disabled={createMutation.isPending || isLoadingMembers}
                >
                  <option value="">
                    {isLoadingMembers
                      ? "Loading team roster..."
                      : teamMembers.length === 0
                      ? "No active team members (Unassigned)"
                      : "-- Unassigned --"}
                  </option>
                  {teamMembers.map((member) => (
                    <option key={member.emp_id || member.id} value={member.emp_id || member.id}>
                      {member.name} — {member.role || "Team Member"}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Priority & Date Range Row */}
            <div className="form-row form-grid-3">
              <div className="form-group">
                <label htmlFor="task-priority" className="form-label">
                  Priority
                </label>
                <select
                  id="task-priority"
                  name="priority"
                  className="form-control"
                  value={formData.priority}
                  onChange={handleChange}
                  disabled={createMutation.isPending}
                >
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                  <option value="CRITICAL">Critical</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="task-start-date" className="form-label">
                  Start Date
                </label>
                <input
                  id="task-start-date"
                  name="start_date"
                  type="date"
                  className="form-control"
                  value={formData.start_date}
                  onChange={handleChange}
                  disabled={createMutation.isPending}
                />
              </div>

              <div className="form-group">
                <label htmlFor="task-due-date" className="form-label">
                  Due Date
                </label>
                <input
                  id="task-due-date"
                  name="due_date"
                  type="date"
                  className="form-control"
                  min={formData.start_date || undefined}
                  value={formData.due_date}
                  onChange={handleChange}
                  disabled={createMutation.isPending}
                />
              </div>
            </div>

            {/* Description */}
            <div className="form-group">
              <label htmlFor="task-desc" className="form-label">
                Description (Optional)
              </label>
              <textarea
                id="task-desc"
                name="description"
                rows={3}
                className="form-control"
                placeholder="Provide task acceptance criteria, scope, and technical context..."
                value={formData.description}
                onChange={handleChange}
                disabled={createMutation.isPending}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleClose}
              disabled={createMutation.isPending}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={createMutation.isPending || !formData.title.trim()}
            >
              {createMutation.isPending ? "Creating Task..." : "Create Task"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
