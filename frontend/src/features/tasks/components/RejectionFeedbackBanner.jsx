/**
 * RejectionFeedbackBanner Component (US-13)
 *
 * Prominently surfaces the Team Lead's review feedback and rejection count
 * on tasks with status == REJECTED.
 *
 * @param {Object} props
 * @param {Object} props.task TaskDetailResponse object
 * @param {() => void} [props.onOpenResubmit] Optional callback to launch ResubmitTaskModal
 */
export default function RejectionFeedbackBanner({ task, onOpenResubmit }) {
  if (!task || task.status !== "REJECTED") {
    return null;
  }

  const rejectionCount = Number(task.rejection_count) || 1;
  const feedbackText =
    task.rejection_feedback && task.rejection_feedback.trim()
      ? task.rejection_feedback
      : "The reviewer requested modifications before this task can be approved. Please review the requirements, address the noted concerns, and resubmit.";

  return (
    <div
      className="rejection-feedback-banner"
      role="alert"
      aria-label="Task Rejection and Revision Feedback"
    >
      <div className="rejection-banner-header">
        <div className="rejection-banner-title-group">
          <span className="rejection-banner-icon" aria-hidden="true">
            ↩
          </span>
          <div>
            <h4 className="rejection-banner-title">
              Revision Required by Reviewer
            </h4>
          </div>
        </div>
        <span className="rejection-count-badge">
          Attempt #{rejectionCount}
        </span>
      </div>

      <div className="rejection-feedback-body">
        <strong>Reviewer Feedback:</strong>
        <p style={{ margin: "6px 0 0", whiteSpace: "pre-wrap" }}>
          {feedbackText}
        </p>
      </div>

      {onOpenResubmit && (
        <div className="rejection-feedback-footer">
          <button
            type="button"
            className="btn-banner-action"
            onClick={onOpenResubmit}
            aria-label="Open task revision and resubmission modal"
          >
            <span aria-hidden="true">🔄</span> Revise &amp; Resubmit Task
          </button>
        </div>
      )}
    </div>
  );
}
