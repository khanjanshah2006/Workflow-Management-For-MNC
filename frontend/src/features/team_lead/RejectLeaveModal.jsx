import React, { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { rejectLeave } from "../../api/leaveApi";
import { validateRejectionRemarks } from "./leaveTriageUtils";

/**
 * RejectLeaveModal Component (US-16 / Issue #106)
 *
 * Team Lead leave rejection modal:
 * - Mandatory rejection remarks (>= 10 non-whitespace characters, <= 2000)
 * - Live character counter
 * - Disables Submit when remarks contain fewer than 10 valid characters
 * - Clear inline error messages and toast notification on completion
 */
export default function RejectLeaveModal({
  isOpen = false,
  leaveRequest,
  onClose,
  onSuccess,
}) {
  const queryClient = useQueryClient();

  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen || !leaveRequest) return null;

  const applicantName =
    leaveRequest.employee_name || `Employee #${leaveRequest.employee_id || leaveRequest.emp_id}`;
  const validation = validateRejectionRemarks(remarks);
  const isSubmitDisabled = isSubmitting || !validation.isValid;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    const check = validateRejectionRemarks(remarks);
    if (!check.isValid) {
      setError(check.error);
      return;
    }

    setIsSubmitting(true);
    try {
      await rejectLeave(leaveRequest.leave_id, {
        review_remarks: remarks.trim(),
      });

      queryClient.invalidateQueries({ queryKey: ["leave"] });

      if (onSuccess) {
        onSuccess({
          toastMessage: `Leave request for ${applicantName} rejected`,
        });
      }
      onClose();
    } catch (err) {
      setError(err?.data?.detail || err?.message || "Failed to reject leave request.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="reject-modal-title"
      data-testid="reject-leave-modal"
    >
      <div
        className="leave-modal-dialog"
        style={{ maxWidth: "520px" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="leave-modal-header">
          <div>
            <h2 id="reject-modal-title" className="leave-modal-title">
              Reject Leave Request
            </h2>
            <span style={{ fontSize: "13px", color: "#64748b" }}>
              Request #{leaveRequest.leave_id} · {applicantName}
            </span>
          </div>
          <button
            type="button"
            className="leave-modal-close-btn"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close reject modal"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="leave-modal-body">
            {error && (
              <div className="leave-alert-error" role="alert" data-testid="reject-error-banner">
                <span>⚠️ {error}</span>
              </div>
            )}

            <p style={{ margin: 0, fontSize: "14px", color: "#334155", lineHeight: "1.5" }}>
              Please provide clear review remarks explaining the business reason for rejecting this leave request. The applicant will be notified of this decision.
            </p>

            <div className="leave-form-group">
              <div className="leave-label">
                <label htmlFor="reject-remarks">Review Remarks * (minimum 10 characters)</label>
                <span className="leave-char-counter" data-testid="reject-char-counter">
                  {validation.length} / 2000
                </span>
              </div>
              <textarea
                id="reject-remarks"
                className={`leave-textarea ${error || (!validation.isValid && validation.length > 0) ? "has-error" : ""}`}
                rows={4}
                placeholder="Enter detailed reason for rejection (e.g. Critical project deadline on target dates, insufficient staffing coverage)..."
                value={remarks}
                onChange={(e) => {
                  setRemarks(e.target.value);
                  setError(null);
                }}
                disabled={isSubmitting}
                required
                data-testid="reject-remarks-input"
              />
              {!validation.isValid && validation.length > 0 && (
                <span className="leave-field-error" role="alert">
                  {validation.error}
                </span>
              )}
            </div>
          </div>

          <div className="leave-modal-footer">
            <button
              type="button"
              className="leave-btn leave-btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="leave-btn leave-btn-danger"
              disabled={isSubmitDisabled}
              data-testid="confirm-reject-button"
            >
              {isSubmitting ? "Rejecting..." : "Confirm Rejection"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
