import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createProject } from "../../api/projectsApi";
import { isAdmin } from "../../auth/session";

/**
 * Inner dialog component for creating a new project.
 * Mounts when the modal is open, ensuring clean state on every invocation.
 *
 * @param {Object} props
 * @param {() => void} props.onClose
 * @param {Object} [props.currentUser]
 */
function CreateProjectDialog({ onClose, currentUser }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const firstInputRef = useRef(null);

  const isUserAdmin = isAdmin(currentUser);

  // Form state initialized directly upon mounting
  const [formData, setFormData] = useState({
    name: "",
    project_code: "",
    description: "",
    start_date: "",
    end_date: "",
    priority: "MEDIUM",
    client_id: "",
    pm_id: "",
  });

  const [fieldErrors, setFieldErrors] = useState({});
  const [generalError, setGeneralError] = useState("");

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: (data) => {
      // Invalidate project list query
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      onClose();
      // Navigate to project handoff page using project_id (NOT id)
      navigate(`/projects/${data.project_id}`);
    },
    onError: (err) => {
      const message = err.message || "Failed to create project.";
      setGeneralError(message);

      // Map backend error messages to specific form fields
      const newFieldErrors = {};
      const lowerMsg = message.toLowerCase();

      if (lowerMsg.includes("code") || err.status === 409) {
        newFieldErrors.project_code = message;
      }
      if (lowerMsg.includes("client")) {
        newFieldErrors.client_id = message;
      }
      if (lowerMsg.includes("project manager") || lowerMsg.includes("pm")) {
        newFieldErrors.pm_id = message;
      }
      if (lowerMsg.includes("date")) {
        newFieldErrors.end_date = message;
      }

      if (Object.keys(newFieldErrors).length > 0) {
        setFieldErrors((prev) => ({ ...prev, ...newFieldErrors }));
      }
    },
  });

  const isPending = mutation.isPending;

  // Auto-focus first input on mount
  useEffect(() => {
    firstInputRef.current?.focus();
  }, []);

  // Handle escape key
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === "Escape" && !isPending) {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, isPending]);

  function handleChange(e) {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    // Clear error for field upon typing
    if (fieldErrors[name]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
    if (generalError) {
      setGeneralError("");
    }
  }

  function validate() {
    const errors = {};

    // Project Code validation
    const trimmedCode = formData.project_code.trim();
    if (!trimmedCode) {
      errors.project_code = "Project code is required.";
    } else if (trimmedCode.length < 2) {
      errors.project_code = "Project code must be at least 2 characters.";
    } else if (trimmedCode.length > 50) {
      errors.project_code = "Project code cannot exceed 50 characters.";
    }

    // Project Name validation
    const trimmedName = formData.name.trim();
    if (!trimmedName) {
      errors.name = "Project name is required.";
    } else if (trimmedName.length < 2) {
      errors.name = "Project name must be at least 2 characters.";
    } else if (trimmedName.length > 200) {
      errors.name = "Project name cannot exceed 200 characters.";
    }

    // Start Date validation
    if (!formData.start_date) {
      errors.start_date = "Start date is required.";
    }

    // Target End Date validation (required per FR-PM01 & US-06; must be strictly after start_date)
    if (!formData.end_date) {
      errors.end_date = "Target end date is required.";
    } else if (formData.start_date && formData.end_date <= formData.start_date) {
      errors.end_date = "Target end date must be after the start date.";
    }

    // Client ID validation (required positive integer)
    if (!formData.client_id || String(formData.client_id).trim() === "") {
      errors.client_id = "Client ID is required.";
    } else {
      const parsedClient = Number(formData.client_id);
      if (!Number.isInteger(parsedClient) || parsedClient <= 0) {
        errors.client_id = "Client ID must be a positive integer.";
      }
    }

    // Project Manager ID validation (Admin only - hidden for PM)
    if (isUserAdmin) {
      if (!formData.pm_id || String(formData.pm_id).trim() === "") {
        errors.pm_id = "Project Manager ID is required for administrators.";
      } else {
        const parsedPm = Number(formData.pm_id);
        if (!Number.isInteger(parsedPm) || parsedPm <= 0) {
          errors.pm_id = "Project Manager ID must be a positive integer.";
        }
      }
    }

    return errors;
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (mutation.isPending) return;

    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors);
      return;
    }

    setFieldErrors({});
    setGeneralError("");

    mutation.mutate({
      name: formData.name,
      project_code: formData.project_code,
      description: formData.description,
      start_date: formData.start_date,
      end_date: formData.end_date,
      priority: formData.priority,
      client_id: formData.client_id,
      pm_id: isUserAdmin ? formData.pm_id : null,
    });
  }

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget && !mutation.isPending) {
          onClose();
        }
      }}
      role="presentation"
    >
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-project-title"
      >
        <div className="modal-header">
          <div className="modal-header-text">
            <h2 id="create-project-title">Create New Project</h2>
            <p className="modal-header-subtitle">
              Configure project identity, schedule, client ownership, and management assignment.
            </p>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            disabled={mutation.isPending}
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className="modal-body">
            {generalError && (
              <div className="modal-alert modal-alert-error" role="alert">
                <span className="modal-alert-icon" aria-hidden="true">⚠</span>
                <span>{generalError}</span>
              </div>
            )}

            {/* Project Code & Priority */}
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label" htmlFor="project_code">
                  Project Code <span className="form-required-mark">*</span>
                </label>
                <input
                  ref={firstInputRef}
                  id="project_code"
                  name="project_code"
                  type="text"
                  placeholder="e.g. PRJ-CORP-01"
                  value={formData.project_code}
                  onChange={handleChange}
                  disabled={mutation.isPending}
                  className={`form-input ${fieldErrors.project_code ? "form-input-error" : ""}`}
                  aria-invalid={Boolean(fieldErrors.project_code)}
                  aria-describedby={fieldErrors.project_code ? "project_code-error" : undefined}
                  maxLength={50}
                  required
                />
                {fieldErrors.project_code ? (
                  <span id="project_code-error" className="form-field-error">
                    {fieldErrors.project_code}
                  </span>
                ) : (
                  <span className="form-field-hint">Unique identifier code</span>
                )}
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="priority">
                  Priority <span className="form-required-mark">*</span>
                </label>
                <select
                  id="priority"
                  name="priority"
                  value={formData.priority}
                  onChange={handleChange}
                  disabled={mutation.isPending}
                  className="form-select"
                >
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                  <option value="CRITICAL">Critical</option>
                </select>
                <span className="form-field-hint">Delivery priority level</span>
              </div>
            </div>

            {/* Project Name */}
            <div className="form-group">
              <label className="form-label" htmlFor="name">
                Project Name <span className="form-required-mark">*</span>
              </label>
              <input
                id="name"
                name="name"
                type="text"
                placeholder="e.g. Enterprise Cloud Migration"
                value={formData.name}
                onChange={handleChange}
                disabled={mutation.isPending}
                className={`form-input ${fieldErrors.name ? "form-input-error" : ""}`}
                aria-invalid={Boolean(fieldErrors.name)}
                aria-describedby={fieldErrors.name ? "name-error" : undefined}
                maxLength={200}
                required
              />
              {fieldErrors.name && (
                <span id="name-error" className="form-field-error">
                  {fieldErrors.name}
                </span>
              )}
            </div>

            {/* Description */}
            <div className="form-group">
              <label className="form-label" htmlFor="description">
                Description <span className="form-field-hint">(optional)</span>
              </label>
              <textarea
                id="description"
                name="description"
                placeholder="Brief summary of project scope, objectives, and deliverables..."
                value={formData.description}
                onChange={handleChange}
                disabled={mutation.isPending}
                className="form-textarea"
                rows={3}
              />
            </div>

            {/* Dates: Start Date & Target End Date (both required) */}
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label" htmlFor="start_date">
                  Start Date <span className="form-required-mark">*</span>
                </label>
                <input
                  id="start_date"
                  name="start_date"
                  type="date"
                  value={formData.start_date}
                  onChange={handleChange}
                  disabled={mutation.isPending}
                  className={`form-input ${fieldErrors.start_date ? "form-input-error" : ""}`}
                  aria-invalid={Boolean(fieldErrors.start_date)}
                  aria-describedby={fieldErrors.start_date ? "start_date-error" : undefined}
                  required
                />
                {fieldErrors.start_date && (
                  <span id="start_date-error" className="form-field-error">
                    {fieldErrors.start_date}
                  </span>
                )}
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="end_date">
                  Target End Date <span className="form-required-mark">*</span>
                </label>
                <input
                  id="end_date"
                  name="end_date"
                  type="date"
                  value={formData.end_date}
                  onChange={handleChange}
                  disabled={mutation.isPending}
                  min={formData.start_date || undefined}
                  className={`form-input ${fieldErrors.end_date ? "form-input-error" : ""}`}
                  aria-invalid={Boolean(fieldErrors.end_date)}
                  aria-describedby={fieldErrors.end_date ? "end_date-error" : undefined}
                  required
                />
                {fieldErrors.end_date && (
                  <span id="end_date-error" className="form-field-error">
                    {fieldErrors.end_date}
                  </span>
                )}
              </div>
            </div>

            {/* Client ID & (Admin only) PM ID */}
            <div className={isUserAdmin ? "form-grid" : "form-group"}>
              <div className="form-group">
                <label className="form-label" htmlFor="client_id">
                  Client ID <span className="form-required-mark">*</span>
                </label>
                <input
                  id="client_id"
                  name="client_id"
                  type="number"
                  min="1"
                  step="1"
                  placeholder="e.g. 1"
                  value={formData.client_id}
                  onChange={handleChange}
                  disabled={mutation.isPending}
                  className={`form-input ${fieldErrors.client_id ? "form-input-error" : ""}`}
                  aria-invalid={Boolean(fieldErrors.client_id)}
                  aria-describedby={fieldErrors.client_id ? "client_id-error" : undefined}
                  required
                />
                {fieldErrors.client_id ? (
                  <span id="client_id-error" className="form-field-error">
                    {fieldErrors.client_id}
                  </span>
                ) : (
                  <span className="form-field-hint">Numeric identifier of commissioning client</span>
                )}
              </div>

              {isUserAdmin && (
                <div className="form-group">
                  <label className="form-label" htmlFor="pm_id">
                    Project Manager ID <span className="form-required-mark">*</span>
                  </label>
                  <input
                    id="pm_id"
                    name="pm_id"
                    type="number"
                    min="1"
                    step="1"
                    placeholder="e.g. 2"
                    value={formData.pm_id}
                    onChange={handleChange}
                    disabled={mutation.isPending}
                    className={`form-input ${fieldErrors.pm_id ? "form-input-error" : ""}`}
                    aria-invalid={Boolean(fieldErrors.pm_id)}
                    aria-describedby={fieldErrors.pm_id ? "pm_id-error" : undefined}
                    required
                  />
                  {fieldErrors.pm_id ? (
                    <span id="pm_id-error" className="form-field-error">
                      {fieldErrors.pm_id}
                    </span>
                  ) : (
                    <span className="form-field-hint">Required for System Administrator assignment</span>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={mutation.isPending}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? "Creating Project..." : "Create Project"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/**
 * Modal wrapper for creating a new project (US-06).
 *
 * @param {Object} props
 * @param {boolean} props.isOpen
 * @param {() => void} props.onClose
 * @param {Object} [props.currentUser]
 */
export default function CreateProjectModal({ isOpen, onClose, currentUser }) {
  if (!isOpen) return null;
  return <CreateProjectDialog onClose={onClose} currentUser={currentUser} />;
}
