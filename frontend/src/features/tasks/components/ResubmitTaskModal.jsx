import { useState, useRef, useEffect } from "react";
import { resubmitTask, isValidUrl } from "../../../api/tasksApi";

/**
 * ResubmitTaskModal Component (US-13)
 *
 * Allows an assigned employee to resubmit revised work following a rejection:
 * - Revised remarks detailing modifications made in response to reviewer notes
 * - Optional updated deliverable URL (evidence link, cloud file, PR)
 * - Clear explanation of backend URL-based deliverable dependency
 * - Preserves form inputs on request failure
 * - Accessible dialog semantics and keyboard navigation
 *
 * @param {Object} props
 * @param {Object} props.task TaskDetailResponse object
 * @param {() => void} props.onClose Callback to close the modal
 * @param {(response: Object) => void} props.onSuccess Callback invoked upon successful resubmission
 */
export default function ResubmitTaskModal({ task, onClose, onSuccess }) {
  const [revisedRemarks, setRevisedRemarks] = useState("");
  const [newFileUrl, setNewFileUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  const remarksRef = useRef(null);
  const urlInputRef = useRef(null);

  useEffect(() => {
    remarksRef.current?.focus();

    const handleKeyDown = (e) => {
      if (e.key === "Escape" && !isSubmitting) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isSubmitting, onClose]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage(null);

    const trimmedRemarks = revisedRemarks.trim();
    if (!trimmedRemarks) {
      setErrorMessage(
        "Please provide revised remarks explaining what was changed or fixed."
      );
      remarksRef.current?.focus();
      return;
    }

    const trimmedUrl = newFileUrl.trim();
    if (trimmedUrl && !isValidUrl(trimmedUrl)) {
      setErrorMessage(
        "Please provide a valid deliverable URL (starting with http:// or https://) or leave the field blank."
      );
      urlInputRef.current?.focus();
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await resubmitTask(task.task_id, {
        revised_remarks: trimmedRemarks,
        new_file_url: trimmedUrl || null,
      });

      if (onSuccess) {
        onSuccess(result);
      }
      onClose();
    } catch (err) {
      // Preserve form values on error
      setErrorMessage(
        err.message || "Failed to resubmit revised task. Please try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="modal-overlay"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) {
          onClose();
        }
      }}
    >
      <div
        className="resubmit-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="resubmit-modal-title"
      >
        {/* Header */}
        <header className="modal-header">
          <div className="modal-title-group">
            <h2 id="resubmit-modal-title">Revise &amp; Resubmit Task</h2>
            <p className="modal-task-subtitle">
              Task #{task?.task_id}: {task?.title} (Attempt #{Number(task?.rejection_count || 0) + 1})
            </p>
          </div>
          <button
            type="button"
            className="btn-modal-close"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close resubmission modal"
          >
            ✕
          </button>
        </header>

        {/* Form Body */}
        <form onSubmit={handleSubmit} noValidate>
          <div className="modal-body">
            {/* Prior Reviewer Feedback Context */}
            {task?.rejection_feedback && (
              <div
                className="rejection-feedback-banner"
                style={{ marginBottom: 0, padding: 12 }}
                role="note"
                aria-label="Prior Reviewer Feedback"
              >
                <div style={{ fontSize: 11.5, fontWeight: 700, color: "#9a3412" }}>
                  Prior Reviewer Notes:
                </div>
                <div style={{ fontSize: 12, color: "#7c2d12", margin: "4px 0 0" }}>
                  {task.rejection_feedback}
                </div>
              </div>
            )}

            {/* API / Validation Error Banner */}
            {errorMessage && (
              <div
                className="drawer-alert drawer-alert-blocked"
                role="alert"
                style={{ margin: 0 }}
              >
                <span className="drawer-alert-icon" aria-hidden="true">
                  ⚠️
                </span>
                <div className="drawer-alert-content">
                  <div className="drawer-alert-title">Resubmission Error</div>
                  <div>{errorMessage}</div>
                </div>
              </div>
            )}

            {/* Revised Remarks Textarea */}
            <div className="form-group">
              <label htmlFor="resubmit-remarks" className="form-label">
                <span>Revision Remarks <span style={{ color: "#dc2626" }}>*</span></span>
                <span style={{ fontSize: 11, fontWeight: 500, color: "#64748b" }}>
                  {revisedRemarks.length} characters
                </span>
              </label>
              <textarea
                id="resubmit-remarks"
                ref={remarksRef}
                className="form-textarea"
                rows={4}
                placeholder="Explain the specific fixes made in response to the reviewer feedback..."
                value={revisedRemarks}
                onChange={(e) => setRevisedRemarks(e.target.value)}
                disabled={isSubmitting}
                required
                aria-required="true"
              />
            </div>

            {/* Revised Deliverable URL Input */}
            <div className="form-group">
              <label htmlFor="resubmit-url" className="form-label">
                <span>Updated Deliverable URL (Optional)</span>
              </label>
              <input
                ref={urlInputRef}
                id="resubmit-url"
                type="url"
                className="form-input"
                placeholder="https://github.com/.../pull/123 or https://drive.google.com/..."
                value={newFileUrl}
                onChange={(e) => setNewFileUrl(e.target.value)}
                disabled={isSubmitting}
              />
              <div className="resubmit-url-notice">
                <span className="resubmit-url-notice-icon" aria-hidden="true">
                  ℹ️
                </span>
                <div>
                  <strong>Backend Deliverable Contract:</strong> The backend resubmission endpoint
                  currently accepts deliverables via URL reference (e.g. GitHub Pull Request, Cloud Storage link,
                  or deployment preview). Direct binary file upload for resubmission is tracked as a pending backend capability.
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <footer className="modal-footer">
            <button
              type="button"
              className="btn-modal-cancel"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-modal-submit"
              disabled={isSubmitting || !revisedRemarks.trim()}
              style={{ background: "#ea580c" }}
            >
              {isSubmitting ? "Resubmitting Task..." : "Resubmit for Review"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
