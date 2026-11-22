import React, { useState, useEffect } from "react";
import { validatePolicyForm } from "./leavePolicyUtils.js";

/**
 * PolicyFormModal Component (US-18 / S4-FE-3)
 *
 * Reusable modal for creating and editing leave policies:
 * - name: 2–50 chars (stripped)
 * - yearly_quota: integer 0–366 (type="number" min="0" max="366" step="1")
 * - is_paid: Paid/Unpaid toggle
 * - description: ≤ 1000 chars optional note
 * - Server 409 conflict maps directly to the name field error
 */
export default function PolicyFormModal({
  isOpen,
  onClose,
  onSave,
  policy = null,
  isLoading = false,
  serverError = null,
}) {
  const isEdit = Boolean(policy && policy.leave_type_id);

  const [formData, setFormData] = useState({
    name: "",
    yearly_quota: "",
    is_paid: true,
    description: "",
  });

  const [fieldErrors, setFieldErrors] = useState({});

  // Reset or populate formData when modal opens or policy prop changes
  useEffect(() => {
    if (isOpen) {
      if (policy) {
        setFormData({
          name: policy.name || "",
          yearly_quota: policy.yearly_quota !== undefined ? String(policy.yearly_quota) : "",
          is_paid: policy.is_paid !== undefined ? Boolean(policy.is_paid) : true,
          description: policy.description || "",
        });
      } else {
        setFormData({
          name: "",
          yearly_quota: "",
          is_paid: true,
          description: "",
        });
      }
      setFieldErrors({});
    }
  }, [isOpen, policy]);

  // Handle server errors (especially 409 Duplicate Name)
  useEffect(() => {
    if (!serverError) return;

    const errMsg = typeof serverError === "string" ? serverError : serverError?.message || "";
    const isConflict =
      serverError?.status === 409 ||
      errMsg.toLowerCase().includes("already exists") ||
      errMsg.toLowerCase().includes("duplicate");

    if (isConflict) {
      setFieldErrors((prev) => ({
        ...prev,
        name: "A policy with this name already exists.",
      }));
    } else if (errMsg) {
      setFieldErrors((prev) => ({
        ...prev,
        general: errMsg,
      }));
    }
  }, [serverError]);

  if (!isOpen) return null;

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    // Clear error for that field as user types
    if (fieldErrors[field]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  };

  const handleBlur = (field) => {
    const result = validatePolicyForm(formData);
    if (result.errors[field]) {
      setFieldErrors((prev) => ({ ...prev, [field]: result.errors[field] }));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    const validation = validatePolicyForm(formData);
    if (!validation.isValid) {
      setFieldErrors(validation.errors);
      return;
    }

    const payload = {
      name: formData.name.trim(),
      yearly_quota: parseInt(formData.yearly_quota, 10),
      is_paid: Boolean(formData.is_paid),
      description: formData.description.trim() || null,
    };

    onSave(payload);
  };

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="policy-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isLoading) {
          onClose();
        }
      }}
    >
      <div className="modal-dialog policy-form-modal-dialog">
        <div className="modal-header">
          <div>
            <h2 id="policy-modal-title" className="modal-title">
              {isEdit ? "Edit Leave Policy" : "Create Leave Policy"}
            </h2>
            <p className="modal-subtitle">
              {isEdit
                ? "Update quota, compensation type, or description."
                : "Define a new leave category and annual entitlement."}
            </p>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            disabled={isLoading}
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className="modal-body">
            {fieldErrors.general && (
              <div className="form-alert-error" role="alert">
                ⚠️ {fieldErrors.general}
              </div>
            )}

            {/* Policy Name */}
            <div className="form-group">
              <label htmlFor="policy-name" className="form-label">
                Policy Name <span className="required-star">*</span>
              </label>
              <input
                id="policy-name"
                type="text"
                className={`form-input ${fieldErrors.name ? "input-error" : ""}`}
                placeholder="e.g. Annual Leave, Paternity Leave"
                value={formData.name}
                onChange={(e) => handleChange("name", e.target.value)}
                onBlur={() => handleBlur("name")}
                maxLength={60}
                disabled={isLoading}
                required
                autoFocus
              />
              <div className="form-field-meta">
                {fieldErrors.name ? (
                  <span className="field-error-msg" role="alert">{fieldErrors.name}</span>
                ) : (
                  <span className="field-hint">2 to 50 characters</span>
                )}
                <span className="char-count">{formData.name.trim().length}/50</span>
              </div>
            </div>

            {/* Yearly Quota */}
            <div className="form-group">
              <label htmlFor="policy-quota" className="form-label">
                Yearly Quota (Days) <span className="required-star">*</span>
              </label>
              <input
                id="policy-quota"
                type="number"
                min="0"
                max="366"
                step="1"
                className={`form-input ${fieldErrors.yearly_quota ? "input-error" : ""}`}
                placeholder="e.g. 20"
                value={formData.yearly_quota}
                onChange={(e) => handleChange("yearly_quota", e.target.value)}
                onBlur={() => handleBlur("yearly_quota")}
                disabled={isLoading}
                required
              />
              <div className="form-field-meta">
                {fieldErrors.yearly_quota ? (
                  <span className="field-error-msg" role="alert">{fieldErrors.yearly_quota}</span>
                ) : (
                  <span className="field-hint">Whole integer between 0 and 366 days</span>
                )}
              </div>
            </div>

            {/* Paid / Unpaid Toggle */}
            <div className="form-group">
              <label className="form-label">Compensation Type</label>
              <div className="paid-toggle-container">
                <label className="switch-label">
                  <input
                    type="checkbox"
                    className="switch-checkbox"
                    checked={formData.is_paid}
                    onChange={(e) => handleChange("is_paid", e.target.checked)}
                    disabled={isLoading}
                  />
                  <span className="switch-slider"></span>
                  <span className="switch-text">
                    {formData.is_paid ? "Paid Leave" : "Unpaid Leave"}
                  </span>
                </label>
                <span className="toggle-explanation">
                  {formData.is_paid
                    ? "Employee is compensated normally during this absence."
                    : "Absence is recorded without wage compensation."}
                </span>
              </div>
            </div>

            {/* Description */}
            <div className="form-group">
              <label htmlFor="policy-description" className="form-label">
                Description <span className="optional-tag">(Optional)</span>
              </label>
              <textarea
                id="policy-description"
                className={`form-textarea ${fieldErrors.description ? "input-error" : ""}`}
                placeholder="Guidelines, eligibility rules, or documentation required..."
                rows={3}
                value={formData.description}
                onChange={(e) => handleChange("description", e.target.value)}
                onBlur={() => handleBlur("description")}
                maxLength={1000}
                disabled={isLoading}
              />
              <div className="form-field-meta">
                {fieldErrors.description ? (
                  <span className="field-error-msg" role="alert">{fieldErrors.description}</span>
                ) : (
                  <span className="field-hint">Maximum 1000 characters</span>
                )}
                <span className="char-count">{formData.description.length}/1000</span>
              </div>
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isLoading}
            >
              {isLoading
                ? isEdit
                  ? "Saving Changes..."
                  : "Creating Policy..."
                : isEdit
                ? "Save Changes"
                : "Create Policy"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
