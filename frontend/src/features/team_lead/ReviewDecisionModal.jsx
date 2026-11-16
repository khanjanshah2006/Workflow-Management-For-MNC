import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { reviewTask, validateRejectionFeedback } from "../../api/tasksApi";

/**
 * ReviewDecisionModal Component (US-12)
 *
 * Allows a Team Lead to evaluate submitted deliverables:
 * - Displays deliverable link, submission remarks, and timestamp
 * - Approve button (green) -> transitions to DONE (100% progress)
 * - Reject button (red with mandatory feedback textarea >= 10 chars)
 * - Reject button disabled until mandatory feedback is provided
 * - Updates review queue immediately upon decision
 */
export default function ReviewDecisionModal({
  isOpen = false,
  task = null,
  onClose,
  onSuccess,
}) {
  const queryClient = useQueryClient();

  // Mode: "VIEW" | "REJECT_FORM"
  const [mode, setMode] = useState("VIEW");
  const [feedback, setFeedback] = useState("");
  const [validationError, setValidationError] = useState(null);

  const handleClose = () => {
    setMode("VIEW");
    setFeedback("");
    setValidationError(null);
    if (onClose) onClose();
  };

  const reviewMutation = useMutation({
    mutationFn: ({ taskId, payload }) => reviewTask(taskId, payload),
    onSuccess: (data) => {
      // Invalidate relevant task queries immediately
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["tasks", "review-queue"] });

      handleClose();
      if (onSuccess) onSuccess(data);
    },
    onError: (err) => {
      setValidationError(err?.message || "Failed to submit review decision.");
    },
  });

  if (!isOpen || !task) return null;

  const handleFeedbackChange = (e) => {
    const val = e.target.value;
    setFeedback(val);
    if (validationError) {
      const check = validateRejectionFeedback(val);
      if (check.valid) setValidationError(null);
    }
  };

  const handleApprove = () => {
    setValidationError(null);
    reviewMutation.mutate({
      taskId: task.task_id,
      payload: { decision: "APPROVE" },
    });
  };

  const handleConfirmReject = (e) => {
    e.preventDefault();
    setValidationError(null);

    const check = validateRejectionFeedback(feedback);
    if (!check.valid) {
      setValidationError(check.error);
      return;
    }

    reviewMutation.mutate({
      taskId: task.task_id,
      payload: {
        decision: "REJECT",
        feedback: feedback.trim(),
      },
    });
  };

  const charCount = feedback.trim().length;
  const isFeedbackValid = charCount >= 10;

  // Format submission timestamp
  const timestamp = task.submission_timestamp || task.updated_at || task.created_at;
  const formattedTime = timestamp
    ? new Date(timestamp).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "Recently submitted";

  const deliverableUrl = task.deliverable_file_url || task.file_url;

  return (
    <div className="modal-backdrop" onClick={handleClose} role="dialog" aria-modal="true" aria-labelledby="review-modal-title">
      <div className="modal-dialog modal-dialog-md" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <h2 id="review-modal-title">Review Deliverable — Task #{task.task_id}</h2>
            <p className="modal-task-subtitle">{task.title}</p>
          </div>
          <button className="btn-modal-close" onClick={handleClose} aria-label="Close dialog" disabled={reviewMutation.isPending}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          {validationError && (
            <div className="alert-banner alert-banner-danger" role="alert">
              <span className="alert-icon">⚠️</span>
              <span>{validationError}</span>
            </div>
          )}

          {/* Submission Highlights Card */}
          <div className="deliverable-inspection-card">
            <div className="inspection-header">
              <div className="inspection-submitter">
                <span className="submitter-label">Submitted by</span>
                <strong>{task.assignee_name || task.assignee?.full_name || (task.assigned_to ? `Employee #${task.assigned_to}` : "Team Member")}</strong>
              </div>
              <div className="inspection-time">
                <span className="timestamp-badge">🕒 {formattedTime}</span>
              </div>
            </div>

            {/* Deliverable File / URL */}
            <div className="inspection-link-section">
              <span className="inspection-subhead">Deliverable Link / File:</span>
              {deliverableUrl ? (
                <a
                  href={deliverableUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="deliverable-external-link"
                >
                  <span className="link-icon">🔗</span>
                  <span className="link-text">{deliverableUrl}</span>
                  <span className="link-arrow">↗</span>
                </a>
              ) : (
                <span className="text-muted-italic">No deliverable URL attached with submission.</span>
              )}
            </div>

            {/* Submission Remarks */}
            <div className="inspection-remarks-section">
              <span className="inspection-subhead">Submitter Remarks:</span>
              <div className="remarks-quote-box">
                {task.submission_remarks || task.remarks || "No additional remarks supplied by submitter."}
              </div>
            </div>
          </div>

          {/* Rejection Feedback Form Mode */}
          {mode === "REJECT_FORM" && (
            <form onSubmit={handleConfirmReject} className="rejection-form-container">
              <div className="form-group">
                <div className="form-label-with-counter">
                  <label htmlFor="rejection-feedback" className="form-label form-label-danger">
                    Mandatory Rejection Feedback <span className="field-required">*</span>
                  </label>
                  <span className={`char-counter ${charCount < 10 ? "char-counter-insufficient" : "char-counter-valid"}`}>
                    {charCount}/10 min characters
                  </span>
                </div>
                <textarea
                  id="rejection-feedback"
                  rows={4}
                  className="form-control form-control-danger"
                  placeholder="Detail why this deliverable was rejected and outline specific corrections required..."
                  value={feedback}
                  onChange={handleFeedbackChange}
                  required
                  autoFocus
                  disabled={reviewMutation.isPending}
                />
                <span className="form-hint">
                  The submitter will receive a rejection notification with this feedback and must resubmit revised work.
                </span>
              </div>

              <div className="rejection-actions-row">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    setMode("VIEW");
                    setFeedback("");
                    setValidationError(null);
                  }}
                  disabled={reviewMutation.isPending}
                >
                  ← Back to Options
                </button>
                <button
                  type="submit"
                  className="btn btn-danger btn-sm"
                  disabled={reviewMutation.isPending || !isFeedbackValid}
                >
                  {reviewMutation.isPending ? "Submitting Rejection..." : "Confirm & Send Rejection"}
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Modal Footer with Primary Decision Actions */}
        {mode === "VIEW" && (
          <div className="modal-footer review-decision-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleClose}
              disabled={reviewMutation.isPending}
            >
              Cancel
            </button>
            <div className="decision-buttons-group">
              <button
                type="button"
                className="btn btn-reject"
                onClick={() => setMode("REJECT_FORM")}
                disabled={reviewMutation.isPending}
              >
                ✕ Reject Deliverable...
              </button>
              <button
                type="button"
                className="btn btn-approve"
                onClick={handleApprove}
                disabled={reviewMutation.isPending}
              >
                {reviewMutation.isPending ? "Approving..." : "✓ Approve Deliverable"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
