import React, { useState } from "react";
import {
  approveSkillRequest,
  rejectSkillRequest,
} from "../../api/profileApi.js";
import {
  validateRejectionRemarks,
  describeChange,
} from "./skillRequestUtils.js";

/**
 * SkillDecisionModal Component (US-34 / Issue #161)
 *
 * Provides review decision workflows for HR and Team Leads:
 * - APPROVE: Remarks optional, calls approveSkillRequest, refetches queue & profile.
 * - REJECT: Remarks mandatory (min 5 chars), validated before submission, calls rejectSkillRequest.
 * - Error Handling:
 *   - HTTP 409: Shows "already decided" notification and refreshes queue.
 *   - HTTP 403: Shows authorization notification.
 */
export default function SkillDecisionModal({
  isOpen = false,
  action = "APPROVE",
  request = null,
  onClose,
  onSuccess,
  onRefresh,
  onShowToast,
}) {
  const isApprove = String(action || "APPROVE").toUpperCase() === "APPROVE";

  const [remarks, setRemarks] = useState("");
  const [validationError, setValidationError] = useState(null);
  const [serverError, setServerError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen || !request) return null;

  const handleRemarksChange = (e) => {
    const val = e.target.value;
    setRemarks(val);
    if (validationError) {
      setValidationError(null);
    }
    if (serverError) {
      setServerError(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    setServerError(null);

    // Validate rejection remarks before dispatching
    if (!isApprove) {
      const validation = validateRejectionRemarks(remarks);
      if (!validation.isValid) {
        setValidationError(validation.error);
        return;
      }
    }

    setValidationError(null);
    setIsSubmitting(true);

    try {
      let result;
      if (isApprove) {
        result = await approveSkillRequest(request.request_id, remarks.trim());
      } else {
        result = await rejectSkillRequest(request.request_id, remarks.trim());
      }

      if (onSuccess) {
        onSuccess(result, isApprove ? "APPROVE" : "REJECT");
      } else if (onRefresh) {
        onRefresh();
        onClose();
      } else {
        onClose();
      }
    } catch (err) {
      const statusCode = err?.status || err?.response?.status;
      const detailMsg =
        err?.data?.detail ||
        err?.message ||
        "An unexpected error occurred while submitting decision.";

      const isConflict =
        statusCode === 409 ||
        detailMsg.toLowerCase().includes("already decided");
      const isForbidden =
        statusCode === 403 ||
        detailMsg.toLowerCase().includes("not authorized");

      if (isConflict) {
        const conflictMsg = "This proposal has already been decided by another reviewer.";
        setServerError(conflictMsg);
        if (onShowToast) {
          onShowToast(conflictMsg, "error");
        }
        if (onRefresh) {
          onRefresh();
        }
      } else if (isForbidden) {
        const forbiddenMsg =
          "You are not authorized to decide this proposal. Team leads can only review active members of teams they lead.";
        setServerError(forbiddenMsg);
        if (onShowToast) {
          onShowToast(forbiddenMsg, "error");
        }
      } else {
        setServerError(detailMsg);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const getActionBadgeClass = (act) => {
    switch (String(act || "").toUpperCase()) {
      case "ADD":
        return "skill-action-tag-add";
      case "UPDATE":
        return "skill-action-tag-update";
      case "REMOVE":
        return "skill-action-tag-remove";
      default:
        return "";
    }
  };

  return (
    <div
      className="modal-backdrop"
      onClick={!isSubmitting ? onClose : undefined}
      role="dialog"
      aria-modal="true"
      aria-labelledby="skill-decision-modal-title"
      data-testid="skill-decision-modal"
    >
      <div
        className="skill-decision-modal-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="skill-modal-header">
          <div>
            <h2 id="skill-decision-modal-title" className="skill-modal-title">
              {isApprove ? "Approve Skill Proposal" : "Reject Skill Proposal"}
            </h2>
            <p className="skill-modal-subtitle">
              {isApprove
                ? "Confirm and apply this skill change to the employee's official profile."
                : "Decline this skill change proposal. Reviewer remarks explaining the decision are mandatory."}
            </p>
          </div>
          <button
            type="button"
            className="skill-modal-close-btn"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close modal"
          >
            ×
          </button>
        </div>

        {/* Server Error Alert Banner */}
        {serverError && (
          <div
            className="skill-alert-banner skill-alert-error"
            role="alert"
            data-testid="decision-error-banner"
          >
            <span className="skill-alert-icon" aria-hidden="true">⚠️</span>
            <div className="skill-alert-body">
              <strong>Decision Error</strong>
              <p>{serverError}</p>
            </div>
          </div>
        )}

        {/* Modal Body */}
        <form onSubmit={handleSubmit} noValidate>
          <div className="skill-modal-body">
            {/* Proposal Summary Card */}
            <div className="skill-decision-summary" data-testid="decision-summary">
              <div className="skill-decision-summary-row">
                <span className="skill-decision-label">Employee</span>
                <span className="skill-decision-val">
                  {request.employee_name || `Employee #${request.emp_id}`} (ID: #{request.emp_id})
                </span>
              </div>
              <div className="skill-decision-summary-row">
                <span className="skill-decision-label">Department</span>
                <span className="skill-decision-val">
                  {request.department || request.department_name || "—"}
                </span>
              </div>
              <div className="skill-decision-summary-row">
                <span className="skill-decision-label">Action</span>
                <span>
                  <span className={`skill-action-tag ${getActionBadgeClass(request.action)}`}>
                    {request.action}
                  </span>
                </span>
              </div>
              <div className="skill-decision-summary-row">
                <span className="skill-decision-label">Change</span>
                <span className="skill-decision-val" style={{ color: "#2563eb" }}>
                  {describeChange(request)}
                </span>
              </div>
              <div className="skill-decision-summary-row" style={{ flexDirection: "column", gap: "4px" }}>
                <span className="skill-decision-label">Justification:</span>
                <p
                  style={{
                    margin: 0,
                    fontSize: "12.5px",
                    lineHeight: "1.4",
                    color: "#334155",
                    background: "#ffffff",
                    padding: "8px 10px",
                    borderRadius: "6px",
                    border: "1px solid #e2e8f0",
                  }}
                >
                  {request.justification}
                </p>
              </div>
            </div>

            {/* Remarks Input Field */}
            <div className="skill-form-group">
              <label htmlFor="decision-remarks" className="skill-form-label">
                {isApprove ? "Review Remarks (Optional)" : "Rejection Remarks "}
                {!isApprove && <span className="skill-required">*</span>}
                <span className="skill-field-hint-text">
                  {isApprove
                    ? "(Optional feedback for the employee)"
                    : "(Minimum 5 characters explaining reason for decline)"}
                </span>
              </label>
              <textarea
                id="decision-remarks"
                name="remarks"
                className={`skill-textarea ${validationError ? "skill-input-error" : ""}`}
                placeholder={
                  isApprove
                    ? "Add optional approval comments or congratulations..."
                    : "Explain why this proposal is declined (e.g. Needs further project demonstration)..."
                }
                value={remarks}
                onChange={handleRemarksChange}
                disabled={isSubmitting}
                maxLength={1000}
                rows={3}
                aria-invalid={Boolean(validationError)}
                data-testid="decision-remarks-input"
              />
              <div className="skill-field-footer">
                {validationError ? (
                  <span className="skill-field-error-msg" role="alert" data-testid="remarks-validation-error">
                    {validationError}
                  </span>
                ) : (
                  <span className="skill-char-hint">
                    {!isApprove ? "Minimum 5 characters required" : "Optional"}
                  </span>
                )}
                <span className="skill-char-count">{remarks.length}/1000</span>
              </div>
            </div>
          </div>

          {/* Modal Footer */}
          <div className="skill-modal-footer">
            <button
              type="button"
              className="skill-btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
              data-testid="decision-cancel-btn"
            >
              Cancel
            </button>
            <button
              type="submit"
              className={isApprove ? "skill-btn-primary" : "skill-btn-danger"}
              disabled={isSubmitting}
              data-testid="decision-submit-btn"
            >
              {isSubmitting
                ? "Processing..."
                : isApprove
                ? "Confirm Approval"
                : "Reject Proposal"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
