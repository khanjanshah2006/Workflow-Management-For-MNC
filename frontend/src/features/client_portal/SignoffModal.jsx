import React, { useState } from "react";
import { submitDeliverableFeedback } from "../../api/clientPortalApi";
import { validateSignoff } from "./clientPortalUtils";
import { useToast } from "../../components/common/Toast";

const RATING_DESCRIPTIONS = {
  1: "Poor - Significant issues found",
  2: "Fair - Needs substantial work",
  3: "Good - Meets basic expectations",
  4: "Very Good - Exceeds expectations",
  5: "Excellent - Outstanding quality",
};

/**
 * SignoffModal Component (US-22)
 *
 * Formal client signoff and review modal with 1-5 star rating,
 * formal acceptance / change request decision, and audit comments.
 */
export default function SignoffModal({ deliverable, onClose, onSuccess }) {
  const toast = useToast();

  const [rating, setRating] = useState(null);
  const [hoverRating, setHoverRating] = useState(null);
  const [decision, setDecision] = useState("ACCEPTED");
  const [comments, setComments] = useState("");
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState(null);

  if (!deliverable) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setApiError(null);

    const payload = {
      rating,
      decision,
      comments: comments.trim() ? comments.trim() : null,
    };

    const validation = validateSignoff(payload);
    if (!validation.isValid) {
      setErrors(validation.errors);
      return;
    }

    setErrors({});
    setIsSubmitting(true);

    try {
      const updated = await submitDeliverableFeedback(
        deliverable.deliverable_id,
        payload
      );
      toast.success(
        decision === "ACCEPTED"
          ? "Deliverable successfully accepted and signed off!"
          : "Revision request submitted to the project team."
      );
      onSuccess?.(updated);
      onClose();
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Failed to submit deliverable signoff. Please try again.";
      setApiError(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const activeRating = hoverRating !== null ? hoverRating : rating;

  return (
    <div
      className="client-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="signoff-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onClose();
      }}
    >
      <div className="client-modal">
        {/* Modal Header */}
        <div className="client-modal-header">
          <div>
            <h3 id="signoff-modal-title" className="client-modal-title">
              Deliverable Signoff
            </h3>
            <span
              style={{
                fontSize: "12px",
                color: "#64748b",
                display: "block",
                marginTop: "2px",
              }}
            >
              {deliverable.title} · v{deliverable.version}
            </span>
          </div>

          <button
            type="button"
            className="client-modal-close"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        {/* Modal Body Form */}
        <form onSubmit={handleSubmit}>
          <div className="client-modal-body">
            {apiError && (
              <div
                style={{
                  background: "#fee2e2",
                  border: "1px solid #fecaca",
                  borderRadius: "6px",
                  padding: "10px 14px",
                  color: "#991b1b",
                  fontSize: "13px",
                }}
              >
                {apiError}
              </div>
            )}

            {/* Decision Selection */}
            <div className="client-form-group">
              <label className="client-form-label">Review Decision *</label>
              <div style={{ display: "flex", gap: "12px", marginTop: "4px" }}>
                <label
                  style={{
                    flex: 1,
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "10px 14px",
                    border: `1.5px solid ${decision === "ACCEPTED" ? "#16a34a" : "#cbd5e1"}`,
                    background: decision === "ACCEPTED" ? "#f0fdf4" : "#ffffff",
                    borderRadius: "8px",
                    cursor: "pointer",
                    fontSize: "13px",
                    fontWeight: "600",
                    color: decision === "ACCEPTED" ? "#15803d" : "#334155",
                  }}
                >
                  <input
                    type="radio"
                    name="decision"
                    value="ACCEPTED"
                    checked={decision === "ACCEPTED"}
                    onChange={() => {
                      setDecision("ACCEPTED");
                      setErrors((prev) => ({ ...prev, decision: undefined }));
                    }}
                    disabled={isSubmitting}
                  />
                  <span>✓ Accept & Sign Off</span>
                </label>

                <label
                  style={{
                    flex: 1,
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "10px 14px",
                    border: `1.5px solid ${decision === "CHANGES_REQUESTED" ? "#dc2626" : "#cbd5e1"}`,
                    background: decision === "CHANGES_REQUESTED" ? "#fef2f2" : "#ffffff",
                    borderRadius: "8px",
                    cursor: "pointer",
                    fontSize: "13px",
                    fontWeight: "600",
                    color: decision === "CHANGES_REQUESTED" ? "#b91c1c" : "#334155",
                  }}
                >
                  <input
                    type="radio"
                    name="decision"
                    value="CHANGES_REQUESTED"
                    checked={decision === "CHANGES_REQUESTED"}
                    onChange={() => {
                      setDecision("CHANGES_REQUESTED");
                      setErrors((prev) => ({ ...prev, decision: undefined }));
                    }}
                    disabled={isSubmitting}
                  />
                  <span>↩ Request Changes</span>
                </label>
              </div>
              {errors.decision && (
                <div className="field-error">{errors.decision}</div>
              )}
            </div>

            {/* Interactive Star Rating */}
            <div className="client-form-group">
              <label className="client-form-label">
                Quality Rating (1–5 Stars) *
              </label>

              <div className="star-rating-row" role="radiogroup" aria-label="Rating">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    className={`star-btn ${star <= (activeRating || 0) ? "filled" : ""}`}
                    onClick={() => {
                      setRating(star);
                      setErrors((prev) => ({ ...prev, rating: undefined }));
                    }}
                    onMouseEnter={() => setHoverRating(star)}
                    onMouseLeave={() => setHoverRating(null)}
                    disabled={isSubmitting}
                    aria-label={`${star} star`}
                  >
                    ★
                  </button>
                ))}
              </div>

              {activeRating ? (
                <div style={{ fontSize: "12px", color: "#64748b" }}>
                  {RATING_DESCRIPTIONS[activeRating]}
                </div>
              ) : (
                <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                  Click a star to assign a quality rating
                </div>
              )}

              {errors.rating && (
                <div className="field-error">{errors.rating}</div>
              )}
            </div>

            {/* Comments Area */}
            <div className="client-form-group">
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <label className="client-form-label">
                  Feedback Remarks {decision === "CHANGES_REQUESTED" ? "*" : "(Optional)"}
                </label>
                <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                  {comments.length} / 4000
                </span>
              </div>

              <textarea
                rows={4}
                className="client-form-textarea"
                placeholder={
                  decision === "CHANGES_REQUESTED"
                    ? "Mandatory: Please explain specifically what modifications are needed..."
                    : "Optional: Add any feedback, comments, or notes for the delivery team..."
                }
                value={comments}
                onChange={(e) => {
                  setComments(e.target.value);
                  if (errors.comments) {
                    setErrors((prev) => ({ ...prev, comments: undefined }));
                  }
                }}
                disabled={isSubmitting}
                maxLength={4000}
                aria-label="Feedback comments"
              />

              {errors.comments && (
                <div className="field-error">{errors.comments}</div>
              )}
            </div>
          </div>

          {/* Modal Footer Actions */}
          <div className="client-modal-footer">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>

            <button
              type="submit"
              className="btn-primary"
              disabled={isSubmitting}
              data-testid="submit-signoff-btn"
            >
              {isSubmitting
                ? "Submitting Signoff..."
                : decision === "ACCEPTED"
                ? "Confirm Signoff"
                : "Submit Change Request"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
