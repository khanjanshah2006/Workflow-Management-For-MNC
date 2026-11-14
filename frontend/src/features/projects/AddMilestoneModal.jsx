import { useState, useEffect, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { projectsApi } from "../../api/projectsApi";

/**
 * Inner dialog component for adding a project milestone.
 * Mounts only when isOpen is true, ensuring fresh state on open.
 */
function AddMilestoneDialog({ onClose, project }) {
  const queryClient = useQueryClient();
  const firstInputRef = useRef(null);

  const [formData, setFormData] = useState({
    title: "",
    description: "",
    target_date: "",
  });

  const [fieldErrors, setFieldErrors] = useState({});
  const [generalError, setGeneralError] = useState("");

  useEffect(() => {
    firstInputRef.current?.focus();
  }, []);

  // Handle Escape key to close
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const mutation = useMutation({
    mutationFn: (payload) => projectsApi.createMilestone(project.project_id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["projects", project.project_id, "milestones"],
      });
      onClose();
    },
    onError: (err) => {
      setGeneralError(err?.message || "Failed to create milestone.");
    },
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    // Clear error for field
    if (fieldErrors[name]) {
      setFieldErrors((prev) => ({ ...prev, [name]: "" }));
    }
    if (generalError) setGeneralError("");
  };

  const validate = () => {
    const errors = {};

    const trimmedTitle = formData.title.trim();
    if (!trimmedTitle) {
      errors.title = "Milestone title is required.";
    } else if (trimmedTitle.length > 255) {
      errors.title = "Milestone title must not exceed 255 characters.";
    }

    if (!formData.target_date) {
      errors.target_date = "Target completion date is required.";
    } else {
      // Validate against project start_date
      if (project.start_date && formData.target_date < project.start_date) {
        errors.target_date = `Target date cannot be earlier than project start date (${project.start_date}).`;
      }

      // Validate against project end_date (only if present)
      if (project.end_date && formData.target_date > project.end_date) {
        errors.target_date = `Target date cannot be after project target completion date (${project.end_date}).`;
      }
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!validate()) return;

    const payload = {
      title: formData.title.trim(),
      target_date: formData.target_date,
    };

    if (formData.description && formData.description.trim()) {
      payload.description = formData.description.trim();
    }

    mutation.mutate(payload);
  };

  return (
    <div
      className="modal-overlay"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget && !mutation.isPending) {
          onClose();
        }
      }}
    >
      <div
        className="modal-card add-milestone-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-milestone-title"
      >
        <div className="modal-header">
          <div>
            <div className="modal-eyebrow">MILESTONE ROADMAP · US-08</div>
            <h2 id="add-milestone-title" className="modal-title">
              Add Project Milestone
            </h2>
            <p className="modal-subtitle">
              Define a major checkpoint or delivery milestone for{" "}
              <strong>{project.project_code}</strong>.
            </p>
          </div>
          <button
            type="button"
            className="modal-close-button"
            onClick={onClose}
            disabled={mutation.isPending}
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        {generalError && (
          <div className="modal-alert-error" role="alert">
            <span className="alert-symbol">⚠️</span>
            <span>{generalError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="modal-form-body">
            {/* Milestone Title */}
            <div className="form-group">
              <label htmlFor="milestone-title" className="form-label">
                Milestone Title <span className="required-star">*</span>
              </label>
              <input
                ref={firstInputRef}
                id="milestone-title"
                name="title"
                type="text"
                className={`form-input ${fieldErrors.title ? "form-input-error" : ""}`}
                placeholder="e.g. Phase 1 Architecture Sign-off"
                value={formData.title}
                onChange={handleChange}
                disabled={mutation.isPending}
                maxLength={255}
                required
              />
              {fieldErrors.title && (
                <span id="milestone-title-error" className="field-error-text">
                  {fieldErrors.title}
                </span>
              )}
            </div>

            {/* Target Date */}
            <div className="form-group">
              <label htmlFor="milestone-target-date" className="form-label">
                Target Completion Date <span className="required-star">*</span>
              </label>
              <input
                id="milestone-target-date"
                name="target_date"
                type="date"
                className={`form-input ${fieldErrors.target_date ? "form-input-error" : ""}`}
                value={formData.target_date}
                onChange={handleChange}
                disabled={mutation.isPending}
                min={project.start_date || undefined}
                max={project.end_date || undefined}
                required
              />
              <span className="field-hint">
                {project.end_date
                  ? `Allowed window: ${project.start_date || "Start"} to ${project.end_date}`
                  : `Project window starts on ${project.start_date || "start date"} (Open-ended)`}
              </span>
              {fieldErrors.target_date && (
                <span id="milestone-target-date-error" className="field-error-text">
                  {fieldErrors.target_date}
                </span>
              )}
            </div>

            {/* Description */}
            <div className="form-group">
              <label htmlFor="milestone-description" className="form-label">
                Description <span className="optional-tag">(Optional)</span>
              </label>
              <textarea
                id="milestone-description"
                name="description"
                className="form-textarea"
                rows={3}
                placeholder="Key deliverables, stakeholder sign-offs, or review criteria..."
                value={formData.description}
                onChange={handleChange}
                disabled={mutation.isPending}
              />
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
              id="submit-milestone-btn"
            >
              {mutation.isPending ? (
                <>
                  <span className="spinner-inline" />
                  <span>Creating...</span>
                </>
              ) : (
                "Create Milestone"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/**
 * Add Milestone Modal Wrapper Component.
 */
export default function AddMilestoneModal({ isOpen, onClose, project }) {
  if (!isOpen || !project) return null;
  return <AddMilestoneDialog onClose={onClose} project={project} />;
}
