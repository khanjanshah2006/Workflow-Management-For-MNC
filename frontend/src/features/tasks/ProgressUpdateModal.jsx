import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateTaskProgress } from "../../api/tasksApi";

/**
 * ProgressUpdateModal Component (US-10: Update Task Progress & Blocker Reason)
 *
 * Allows assigned employees and leads to update task progress (0–99%)
 * and transition between IN_PROGRESS and BLOCKED.
 *
 * Enforces business rules:
 * - 100% is disallowed (requires separate submit-for-review flow).
 * - Supported statuses are strictly IN_PROGRESS and BLOCKED.
 * - BLOCKED requires at least 5 non-whitespace characters in blocker_reason.
 * - API failures preserve form state and show inline error alert.
 *
 * @param {Object} props
 * @param {Object|null} props.task Task object being edited
 * @param {() => void} props.onClose Callback to dismiss modal
 * @param {(updatedTask: Object) => void} props.onSuccess Callback on successful update
 */
export default function ProgressUpdateModal({
  task,
  onClose,
  onSuccess,
}) {
  const queryClient = useQueryClient();

  // Form states initialized from task
  const initialStatus =
    task?.status === "BLOCKED" ? "BLOCKED" : "IN_PROGRESS";
  const initialProgress = Math.min(
    99,
    Math.max(0, Number(task?.progress_pct) || 0)
  );
  const initialBlocker = task?.blocker_reason || "";

  const [status, setStatus] = useState(initialStatus);
  const [progressPct, setProgressPct] = useState(initialProgress);
  const [blockerReason, setBlockerReason] = useState(initialBlocker);
  const [validationError, setValidationError] = useState("");
  const [serverError, setServerError] = useState("");

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // TanStack Query Mutation
  const mutation = useMutation({
    mutationFn: ({ taskId, payload }) => updateTaskProgress(taskId, payload),
    onSuccess: (updatedTask) => {
      // Invalidate both the list and the single task detail queries
      queryClient.invalidateQueries({ queryKey: ["my-tasks"] });
      if (task?.task_id) {
        queryClient.invalidateQueries({
          queryKey: ["task-detail", task.task_id],
        });
      }
      onSuccess?.(updatedTask);
      onClose();
    },
    onError: (err) => {
      // Preserve form values and display backend error
      const message =
        err?.message ||
        err?.data?.detail ||
        "Failed to update task progress. Please verify the inputs and try again.";
      setServerError(message);
    },
  });

  if (!task) return null;

  const handleStatusChange = (newStatus) => {
    setStatus(newStatus);
    setValidationError("");
    setServerError("");
    if (newStatus === "IN_PROGRESS") {
      // Follow backend contract: clear blocker reason when returning to IN_PROGRESS
      setBlockerReason("");
    }
  };

  const handleProgressSliderChange = (e) => {
    const val = Number(e.target.value);
    // Strictly clamp between 0 and 99
    const clamped = Math.min(99, Math.max(0, val));
    setProgressPct(clamped);
  };

  const handleProgressInputChange = (e) => {
    const val = e.target.value;
    if (val === "") {
      setProgressPct(0);
      return;
    }
    const num = parseInt(val, 10);
    if (!isNaN(num)) {
      const clamped = Math.min(99, Math.max(0, num));
      setProgressPct(clamped);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setValidationError("");
    setServerError("");

    // Validate progress range 0-99
    if (progressPct < 0 || progressPct > 99) {
      setValidationError(
        "Progress percentage must be between 0% and 99%. 100% requires submitting the task for review."
      );
      return;
    }

    // Validate blocker reason when status is BLOCKED
    if (status === "BLOCKED") {
      const trimmed = blockerReason.trim();
      if (!trimmed || trimmed.length < 5) {
        setValidationError(
          "Blocker reason is required and must contain at least 5 non-whitespace characters."
        );
        return;
      }
    }

    mutation.mutate({
      taskId: task.task_id,
      payload: {
        status,
        progress_pct: progressPct,
        blocker_reason: status === "BLOCKED" ? blockerReason.trim() : null,
      },
    });
  };

  const isBlocked = status === "BLOCKED";
  const trimmedLength = blockerReason.trim().length;

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="progress-modal-title"
    >
      <div
        className="progress-modal"
        onClick={(e) => e.stopPropagation()}
        tabIndex={-1}
      >
        {/* Modal Header */}
        <header className="modal-header">
          <div className="modal-title-group">
            <h2 id="progress-modal-title">Update Task Progress</h2>
            <p className="modal-task-subtitle">
              #{task.task_id} · {task.title}
            </p>
          </div>
          <button
            type="button"
            className="btn-modal-close"
            onClick={onClose}
            aria-label="Close modal"
          >
            ✕
          </button>
        </header>

        {/* Modal Form */}
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {/* Server Error Alert Banner */}
            {serverError && (
              <div className="modal-error-banner" role="alert">
                <span aria-hidden="true">⚠️</span>
                <div>
                  <strong>Update Failed:</strong> {serverError}
                </div>
              </div>
            )}

            {/* Validation Error Alert */}
            {validationError && (
              <div className="modal-error-banner" role="alert">
                <span aria-hidden="true">❌</span>
                <div>{validationError}</div>
              </div>
            )}

            {/* Status Selection Cards */}
            <div className="form-group">
              <label className="form-label" id="status-selection-label">
                Task Status
              </label>
              <div
                className="status-radio-options"
                role="radiogroup"
                aria-labelledby="status-selection-label"
              >
                {/* IN_PROGRESS Card */}
                <div
                  className={`status-radio-card ${
                    status === "IN_PROGRESS" ? "active-in_progress" : ""
                  }`}
                  role="radio"
                  aria-checked={status === "IN_PROGRESS"}
                  tabIndex={0}
                  onClick={() => handleStatusChange("IN_PROGRESS")}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      handleStatusChange("IN_PROGRESS");
                    }
                  }}
                >
                  <div className="status-card-header">
                    <span
                      className="badge-dot"
                      style={{ background: "#3b82f6" }}
                    />
                    <span>In Progress</span>
                  </div>
                  <span className="status-card-desc">
                    Work is actively underway without blocking impediments.
                  </span>
                </div>

                {/* BLOCKED Card */}
                <div
                  className={`status-radio-card ${
                    status === "BLOCKED" ? "active-blocked" : ""
                  }`}
                  role="radio"
                  aria-checked={status === "BLOCKED"}
                  tabIndex={0}
                  onClick={() => handleStatusChange("BLOCKED")}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      handleStatusChange("BLOCKED");
                    }
                  }}
                >
                  <div className="status-card-header">
                    <span
                      className="badge-dot"
                      style={{ background: "#ef4444" }}
                    />
                    <span>Blocked</span>
                  </div>
                  <span className="status-card-desc">
                    Work is stopped waiting on an external dependency or lead assistance.
                  </span>
                </div>
              </div>
              <span className="form-hint">
                Note: Setting to 100% or completing work requires submitting through the review flow.
              </span>
            </div>

            {/* Progress Percentage (0–99%) Slider & Input */}
            <div className="form-group">
              <label htmlFor="progress-slider" className="form-label">
                <span>Progress Percentage</span>
                <span style={{ color: "#4456d9", fontWeight: 750 }}>
                  {progressPct}%
                </span>
              </label>

              <div className="progress-slider-container">
                <input
                  id="progress-slider"
                  type="range"
                  min="0"
                  max="99"
                  value={progressPct}
                  onChange={handleProgressSliderChange}
                  className="progress-slider"
                  aria-valuemin={0}
                  aria-valuemax={99}
                  aria-valuenow={progressPct}
                  aria-label="Progress percentage slider (0 to 99)"
                />
                <input
                  type="number"
                  min="0"
                  max="99"
                  value={progressPct}
                  onChange={handleProgressInputChange}
                  className="progress-number-input"
                  aria-label="Progress percentage input"
                />
              </div>

              <span className="form-hint">
                Allowable values: 0% – 99%. 100% is reserved for approved submissions.
              </span>
            </div>

            {/* Blocker Reason (Mandatory when BLOCKED) */}
            {isBlocked && (
              <div className="form-group">
                <label htmlFor="blocker-reason-input" className="form-label">
                  <span>
                    Blocker Explanation <span style={{ color: "#dc2626" }}>*</span>
                  </span>
                  <span className="char-counter">
                    {trimmedLength} / 5 min chars
                  </span>
                </label>

                <textarea
                  id="blocker-reason-input"
                  className={`blocker-textarea ${
                    validationError && trimmedLength < 5 ? "input-error" : ""
                  }`}
                  placeholder="Explain what is blocking progress (minimum 5 characters)..."
                  value={blockerReason}
                  onChange={(e) => {
                    setBlockerReason(e.target.value);
                    if (validationError) setValidationError("");
                  }}
                  rows={3}
                  required={isBlocked}
                />

                {trimmedLength > 0 && trimmedLength < 5 && (
                  <span className="validation-error-text">
                    ⚠️ At least 5 non-whitespace characters required ({5 - trimmedLength} more needed).
                  </span>
                )}

                <span className="form-hint">
                  Alerts your Team Lead so they can assist in clearing the impediment.
                </span>
              </div>
            )}
          </div>

          {/* Modal Footer */}
          <footer className="modal-footer">
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
              className="btn-save-progress"
              disabled={
                mutation.isPending ||
                (isBlocked && trimmedLength < 5)
              }
            >
              {mutation.isPending ? (
                <>
                  <span aria-hidden="true">⏳</span> Saving...
                </>
              ) : (
                "Save Progress"
              )}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
