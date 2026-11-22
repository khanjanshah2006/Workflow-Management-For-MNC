import React, { useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { submitLeaveRequest, getLeavePolicies } from "../../api/leaveApi";
import { countBusinessDays, validateLeaveForm } from "./leaveUtils";

/**
 * ApplyLeaveModal Component (US-16 / S4)
 *
 * Leave application form and modal:
 * - Leave type dropdown populated using active leave policies
 * - Start date and end date inputs (inclusive)
 * - Reason textarea (10 to 2000 characters)
 * - Live calculation: "Working days requested: X"
 * - Live client-side validation against balances and business rules
 * - Disables submit when requested days exceed available balance
 * - Displays backend 400 / 409 inline error messages
 * - Can be rendered as a modal dialog or embedded directly into dashboard tab
 */
export default function ApplyLeaveModal({
  isOpen = true,
  embedded = false,
  onClose,
  onSuccess,
  balances = [],
  policies: externalPolicies = null,
  today = null,
}) {
  const queryClient = useQueryClient();

  // Form input state
  const [selectedLeaveTypeId, setSelectedLeaveTypeId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");

  // Validation and error state
  const [clientErrors, setClientErrors] = useState({});
  const [serverError, setServerError] = useState(null);

  // Fetch policies if not passed as prop
  const { data: fetchedPolicies = [] } = useQuery({
    queryKey: ["leave", "policies"],
    queryFn: () => getLeavePolicies(),
    enabled: isOpen && !externalPolicies,
  });

  const activePolicies = useMemo(() => {
    const list = externalPolicies || fetchedPolicies || [];
    return (list || []).filter((p) => p.is_active !== false);
  }, [externalPolicies, fetchedPolicies]);

  // Derive effective leave type ID (default to first active policy if not explicitly selected)
  const leaveTypeId = selectedLeaveTypeId || (activePolicies.length > 0 ? String(activePolicies[0].leave_type_id) : "");

  // Normalize balances array
  const balanceList = useMemo(() => {
    return Array.isArray(balances)
      ? balances
      : Array.isArray(balances?.balances)
      ? balances.balances
      : [];
  }, [balances]);

  // Find currently selected leave type's balance
  const selectedBalance = useMemo(() => {
    if (!leaveTypeId) return null;
    return balanceList.find((b) => Number(b.leave_type_id) === Number(leaveTypeId)) || null;
  }, [balanceList, leaveTypeId]);

  // Live count of requested working days
  const workingDays = useMemo(() => {
    if (!startDate || !endDate) return 0;
    return countBusinessDays(startDate, endDate);
  }, [startDate, endDate]);

  // Check if balance is exceeded
  const availableDays = selectedBalance?.available_days ?? null;
  const isBalanceExceeded = availableDays !== null && workingDays > availableDays;

  // Clear server error on input change
  const handleFieldChange = (setter, field) => (e) => {
    setter(e.target.value);
    setServerError(null);
    setClientErrors((prev) => {
      const updated = { ...prev };
      delete updated[field];
      delete updated.balance;
      delete updated.dates;
      return updated;
    });
  };

  // Submit mutation
  const submitMutation = useMutation({
    mutationFn: submitLeaveRequest,
    onSuccess: (data) => {
      // Invalidate both leave balances and leave requests history
      queryClient.invalidateQueries({ queryKey: ["leave"] });
      resetForm();
      if (onSuccess) {
        onSuccess(data);
      }
    },
    onError: (err) => {
      if (err?.status === 409) {
        setServerError("You already have a leave request overlapping these dates.");
      } else if (err?.status === 400) {
        setServerError(err?.message || "Invalid leave request. Please check dates and reason.");
      } else if (err?.status === 403) {
        setServerError(err?.message || "Access denied: An active employee profile is required to apply for leave.");
      } else {
        setServerError(err?.message || "An unexpected error occurred while submitting your leave request.");
      }
    },
  });

  const resetForm = () => {
    setSelectedLeaveTypeId("");
    setStartDate("");
    setEndDate("");
    setReason("");
    setClientErrors({});
    setServerError(null);
  };

  const handleClose = () => {
    resetForm();
    if (onClose) onClose();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setServerError(null);

    // Run client validation
    const check = validateLeaveForm(
      {
        leave_type_id: leaveTypeId,
        start_date: startDate,
        end_date: endDate,
        reason,
      },
      balanceList,
      today || new Date()
    );

    if (!check.isValid) {
      setClientErrors(check.errors);
      return;
    }

    submitMutation.mutate({
      leave_type_id: Number(leaveTypeId),
      start_date: startDate,
      end_date: endDate,
      reason: reason.trim(),
    });
  };

  // Determine if submit button should be disabled
  const isSubmitDisabled =
    submitMutation.isPending ||
    !leaveTypeId ||
    !startDate ||
    !endDate ||
    workingDays <= 0 ||
    isBalanceExceeded ||
    reason.trim().length < 10 ||
    reason.trim().length > 2000;

  if (!isOpen) return null;

  const formContent = (
    <form onSubmit={handleSubmit} noValidate data-testid="apply-leave-form">
      {/* Server or Global Error Banner */}
      {serverError && (
        <div className="leave-alert-error" role="alert" data-testid="leave-server-error" style={{ marginBottom: "16px" }}>
          <span>⚠️ {serverError}</span>
        </div>
      )}

      {/* Balance Exceeded Error Banner */}
      {isBalanceExceeded && (
        <div className="leave-alert-error" role="alert" data-testid="leave-balance-error" style={{ marginBottom: "16px" }}>
          <span>⚠️ Insufficient leave balance (Available: {availableDays} days)</span>
        </div>
      )}

      <div className="leave-form-grid">
        {/* Leave Type Selector */}
        <div className="leave-form-group leave-form-group-full">
          <label htmlFor="leave-type-select" className="leave-label">
            Leave Type *
            {selectedBalance && (
              <span style={{ fontSize: "12px", color: selectedBalance.available_days <= 0 ? "#dc2626" : "#4f46e5", fontWeight: "600" }}>
                Available: {selectedBalance.available_days} days
                {!selectedBalance.is_paid && " (Unpaid)"}
              </span>
            )}
          </label>
          <select
            id="leave-type-select"
            className={`leave-select ${clientErrors.leave_type_id ? "has-error" : ""}`}
            value={leaveTypeId}
            onChange={handleFieldChange(setSelectedLeaveTypeId, "leave_type_id")}
            disabled={submitMutation.isPending}
            required
            data-testid="leave-type-select"
          >
            {activePolicies.length === 0 ? (
              <option value="">Loading leave types...</option>
            ) : (
              activePolicies.map((p) => {
                const b = balanceList.find((item) => Number(item.leave_type_id) === Number(p.leave_type_id));
                const availText = b ? ` (${b.available_days} days available)` : "";
                return (
                  <option key={p.leave_type_id} value={p.leave_type_id}>
                    {p.name} {availText} {!p.is_paid ? "— Unpaid" : ""}
                  </option>
                );
              })
            )}
          </select>
          {clientErrors.leave_type_id && (
            <span className="leave-field-error" role="alert">
              {clientErrors.leave_type_id}
            </span>
          )}
        </div>

        {/* Start Date */}
        <div className="leave-form-group">
          <label htmlFor="leave-start-date" className="leave-label">
            Start Date *
          </label>
          <input
            id="leave-start-date"
            type="date"
            className={`leave-input ${clientErrors.start_date ? "has-error" : ""}`}
            value={startDate}
            onChange={handleFieldChange(setStartDate, "start_date")}
            disabled={submitMutation.isPending}
            required
            data-testid="leave-start-date"
          />
          {clientErrors.start_date && (
            <span className="leave-field-error" role="alert">
              {clientErrors.start_date}
            </span>
          )}
        </div>

        {/* End Date */}
        <div className="leave-form-group">
          <label htmlFor="leave-end-date" className="leave-label">
            End Date *
          </label>
          <input
            id="leave-end-date"
            type="date"
            className={`leave-input ${clientErrors.end_date ? "has-error" : ""}`}
            value={endDate}
            onChange={handleFieldChange(setEndDate, "end_date")}
            min={startDate || undefined}
            disabled={submitMutation.isPending}
            required
            data-testid="leave-end-date"
          />
          {clientErrors.end_date && (
            <span className="leave-field-error" role="alert">
              {clientErrors.end_date}
            </span>
          )}
        </div>

        {/* Live Working Days Calculation Badge */}
        <div className="working-days-indicator" data-testid="working-days-indicator">
          <span className="working-days-label">
            <span>📅 Working days requested:</span>
            <strong data-testid="working-days-count" style={{ fontSize: "16px", color: isBalanceExceeded ? "#dc2626" : "#4f46e5" }}>
              {workingDays}
            </strong>
          </span>
          <span className={`working-days-badge ${isBalanceExceeded ? "working-days-badge-warning" : ""}`}>
            {workingDays === 1 ? "1 day" : `${workingDays} days`} (excl. weekends)
          </span>
        </div>

        {clientErrors.dates && (
          <div className="leave-alert-error" role="alert" style={{ gridColumn: "1 / -1" }}>
            <span>⚠️ {clientErrors.dates}</span>
          </div>
        )}

        {/* Reason Textarea */}
        <div className="leave-form-group leave-form-group-full">
          <div className="leave-label">
            <label htmlFor="leave-reason">Reason * (10–2000 characters)</label>
            <span className="leave-char-counter" data-testid="leave-char-counter">
              {reason.trim().length} / 2000
            </span>
          </div>
          <textarea
            id="leave-reason"
            className={`leave-textarea ${clientErrors.reason ? "has-error" : ""}`}
            rows={4}
            placeholder="Please provide a clear reason for your leave request (minimum 10 characters)..."
            value={reason}
            onChange={handleFieldChange(setReason, "reason")}
            disabled={submitMutation.isPending}
            required
            data-testid="leave-reason"
          />
          {clientErrors.reason && (
            <span className="leave-field-error" role="alert">
              {clientErrors.reason}
            </span>
          )}
        </div>
      </div>

      {/* Action Footer */}
      <div style={{ marginTop: "24px", display: "flex", justifyContent: "flex-end", gap: "12px" }}>
        {!embedded && onClose && (
          <button
            type="button"
            className="leave-btn leave-btn-secondary"
            onClick={handleClose}
            disabled={submitMutation.isPending}
          >
            Cancel
          </button>
        )}
        <button
          type="submit"
          className="leave-btn leave-btn-primary"
          disabled={isSubmitDisabled}
          data-testid="leave-submit-button"
        >
          {submitMutation.isPending ? "Submitting..." : "Submit Leave Request"}
        </button>
      </div>
    </form>
  );

  if (embedded) {
    return (
      <div className="leave-form-card" data-testid="apply-leave-embedded">
        <div className="leave-form-header">
          <h2 className="leave-form-title">Apply for Leave</h2>
          <p className="leave-form-desc">
            Submit your upcoming leave request for team lead and manager review. Working days are computed excluding weekends.
          </p>
        </div>
        {formContent}
      </div>
    );
  }

  return (
    <div
      className="modal-backdrop"
      onClick={handleClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="apply-leave-modal-title"
    >
      <div className="leave-modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="leave-modal-header">
          <h2 id="apply-leave-modal-title" className="leave-modal-title">
            Apply for Leave
          </h2>
          <button
            type="button"
            className="leave-modal-close-btn"
            onClick={handleClose}
            aria-label="Close apply leave modal"
          >
            ×
          </button>
        </div>
        <div className="leave-modal-body">{formContent}</div>
      </div>
    </div>
  );
}
