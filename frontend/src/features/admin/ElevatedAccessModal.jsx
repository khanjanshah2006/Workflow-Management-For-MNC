import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "../../api/adminApi";
import { useAuth, normalizeRole } from "../../hooks/useAuth";

const SUPPORTED_ELEVATED_ROLES = [
  { value: "PM", label: "Project Manager (PM)" },
  { value: "HR", label: "HR Manager (HR)" },
  { value: "ADMIN", label: "Administrator (ADMIN)" },
  { value: "IT_SUPPORT", label: "IT Support (IT_SUPPORT)" },
];

/**
 * Computes an ISO string or datetime-local string offset by given hours.
 * @param {number} hours
 * @returns {string} Value formatted for input type="datetime-local"
 */
function getFutureDateTimeLocal(hours = 24) {
  const target = new Date(Date.now() + hours * 60 * 60 * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  const yyyy = target.getFullYear();
  const MM = pad(target.getMonth() + 1);
  const dd = pad(target.getDate());
  const hh = pad(target.getHours());
  const mm = pad(target.getMinutes());
  return `${yyyy}-${MM}-${dd}T${hh}:${mm}`;
}

/**
 * Inner dialog component for granting elevated access.
 * Mounts when isOpen is true, guaranteeing fresh state per invocation.
 */
function ElevatedAccessDialog({ onClose, onGrantSuccess }) {
  const queryClient = useQueryClient();
  const userSelectRef = useRef(null);
  const { user } = useAuth();
  const isSystemAdmin = normalizeRole(user?.role || user?.user_type) === "SYSTEM_ADMIN";

  const [formData, setFormData] = useState({
    user_id: "",
    granted_role: "PM",
    expires_at: getFutureDateTimeLocal(4), // default to 4 hours in future
    reason: "",
  });

  const [fieldErrors, setFieldErrors] = useState({});
  const [generalError, setGeneralError] = useState("");

  // Fetch list of user accounts to populate user selector dropdown (US-43)
  const { data: usersData, isLoading: usersLoading } = useQuery({
    queryKey: ["admin", "users", { limit: 100 }],
    queryFn: () => adminApi.getUsers({ limit: 100 }),
    retry: 1,
  });

  const userList = Array.isArray(usersData?.items)
    ? usersData.items
    : Array.isArray(usersData)
    ? usersData
    : [];

  // Auto-focus first input on mount
  useEffect(() => {
    userSelectRef.current?.focus();
  }, []);

  // Handle escape key
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // 1. Mutation: POST /api/v1/admin/elevated-access
  const grantMutation = useMutation({
    mutationFn: (payload) => adminApi.grantElevatedAccess(payload),
    onSuccess: (data) => {
      // Invalidate active grants query
      queryClient.invalidateQueries({ queryKey: ["admin", "elevated-access", "active"] });
      if (onGrantSuccess) {
        onGrantSuccess(data);
      }
      onClose();
    },
    onError: (err) => {
      setGeneralError(err?.message || "Failed to grant elevated access. Verify inputs.");
    },
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    if (fieldErrors[name]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
    if (generalError) setGeneralError("");
  };

  const handleShortcutDuration = (hours) => {
    const futureVal = getFutureDateTimeLocal(hours);
    setFormData((prev) => ({ ...prev, expires_at: futureVal }));
    if (fieldErrors.expires_at) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next.expires_at;
        return next;
      });
    }
  };

  const validate = () => {
    const errors = {};

    // 1. User validation
    if (!formData.user_id || !formData.user_id.trim()) {
      errors.user_id = "Please select or specify a target user account.";
    }

    // 2. Role validation
    if (!formData.granted_role || !formData.granted_role.trim()) {
      errors.granted_role = "Elevated role selection is required.";
    }

    // 3. Expiration validation (must be strictly in the future)
    if (!formData.expires_at) {
      errors.expires_at = "Expiration datetime is required.";
    } else {
      const expDate = new Date(formData.expires_at);
      if (isNaN(expDate.getTime())) {
        errors.expires_at = "Please enter a valid datetime.";
      } else if (expDate.getTime() <= Date.now() + 60000) {
        // Must be in the future (at least 1 minute ahead)
        errors.expires_at = "Expiration must be a future timestamp.";
      }
    }

    // 4. Reason validation (mandatory, non-whitespace, min 5 chars per backend schema)
    const trimmedReason = formData.reason.trim();
    if (!trimmedReason) {
      errors.reason = "A non-empty business justification is required.";
    } else if (trimmedReason.length < 5) {
      errors.reason = "Business justification must be at least 5 characters.";
    } else if (trimmedReason.length > 1000) {
      errors.reason = "Business justification must not exceed 1000 characters.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (grantMutation.isPending) return;

    if (!isSystemAdmin) {
      setGeneralError("Permission denied. Only SYSTEM_ADMIN users can grant elevated access.");
      return;
    }

    if (!validate()) return;

    setGeneralError("");

    // Submit POST request with UTC ISO 8601 string
    grantMutation.mutate({
      user_id: formData.user_id.trim(),
      granted_role: formData.granted_role.trim(),
      expires_at: new Date(formData.expires_at).toISOString(),
      reason: formData.reason.trim(),
    });
  };

  return (
    <div
      className="modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget && !grantMutation.isPending) {
          onClose();
        }
      }}
      role="presentation"
    >
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="elevated-modal-title"
      >
        <div className="modal-header">
          <div>
            <div className="modal-eyebrow">US-45 · ELEVATED PRIVILEGE CONTROL</div>
            <h2 id="elevated-modal-title" className="modal-title">
              Grant Elevated Access
            </h2>
            <p className="modal-subtitle">
              Issue time-bound elevated role permissions with mandatory expiration and audit recording.
            </p>
          </div>
          <button
            type="button"
            className="modal-close-button"
            onClick={onClose}
            disabled={grantMutation.isPending}
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>

        {generalError && (
          <div className="modal-alert-error" role="alert">
            <span aria-hidden="true">⚠️</span>
            <span>{generalError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="modal-form-body">
            {/* Target User Account Selection */}
            <div className="form-group">
              <label htmlFor="elevated-user-id" className="form-label">
                Target User Account <span style={{ color: "#ef4444" }}>*</span>
              </label>
              <select
                ref={userSelectRef}
                id="elevated-user-id"
                name="user_id"
                className={`form-input ${fieldErrors.user_id ? "inline-input-error" : ""}`}
                value={formData.user_id}
                onChange={handleChange}
                disabled={grantMutation.isPending || usersLoading}
                aria-invalid={Boolean(fieldErrors.user_id)}
                required
              >
                <option value="">-- Select an active user account --</option>
                {userList.map((u) => (
                  <option key={u.account_id} value={u.account_id}>
                    {u.email} ({u.user_type || "EMPLOYEE"})
                  </option>
                ))}
              </select>
              {fieldErrors.user_id && (
                <span className="inline-error-msg" role="alert">
                  {fieldErrors.user_id}
                </span>
              )}
            </div>

            {/* Role to Grant */}
            <div className="form-group">
              <label htmlFor="elevated-granted-role" className="form-label">
                Elevated Role to Grant <span style={{ color: "#ef4444" }}>*</span>
              </label>
              <select
                id="elevated-granted-role"
                name="granted_role"
                className={`form-input ${fieldErrors.granted_role ? "inline-input-error" : ""}`}
                value={formData.granted_role}
                onChange={handleChange}
                disabled={grantMutation.isPending}
                aria-invalid={Boolean(fieldErrors.granted_role)}
                required
              >
                {SUPPORTED_ELEVATED_ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              {fieldErrors.granted_role && (
                <span className="inline-error-msg" role="alert">
                  {fieldErrors.granted_role}
                </span>
              )}
            </div>

            {/* Expiration Datetime with Quick Duration Shortcuts */}
            <div className="form-group">
              <label htmlFor="elevated-expires-at" className="form-label">
                Access Expiration (Must be in the future) <span style={{ color: "#ef4444" }}>*</span>
              </label>
              <input
                id="elevated-expires-at"
                name="expires_at"
                type="datetime-local"
                className={`form-input ${fieldErrors.expires_at ? "inline-input-error" : ""}`}
                value={formData.expires_at}
                onChange={handleChange}
                min={getFutureDateTimeLocal(0)}
                disabled={grantMutation.isPending}
                aria-invalid={Boolean(fieldErrors.expires_at)}
                required
              />
              <div className="duration-chips-row">
                <span style={{ fontSize: "11px", color: "#64748b" }}>Quick window:</span>
                <button
                  type="button"
                  className="duration-chip"
                  onClick={() => handleShortcutDuration(1)}
                  disabled={grantMutation.isPending}
                >
                  +1 Hour
                </button>
                <button
                  type="button"
                  className="duration-chip"
                  onClick={() => handleShortcutDuration(4)}
                  disabled={grantMutation.isPending}
                >
                  +4 Hours
                </button>
                <button
                  type="button"
                  className="duration-chip"
                  onClick={() => handleShortcutDuration(24)}
                  disabled={grantMutation.isPending}
                >
                  +24 Hours
                </button>
                <button
                  type="button"
                  className="duration-chip"
                  onClick={() => handleShortcutDuration(72)}
                  disabled={grantMutation.isPending}
                >
                  +3 Days
                </button>
              </div>
              {fieldErrors.expires_at && (
                <span className="inline-error-msg" role="alert">
                  {fieldErrors.expires_at}
                </span>
              )}
            </div>

            {/* Mandatory Reason */}
            <div className="form-group">
              <label htmlFor="elevated-reason" className="form-label">
                Business Justification / Reason <span style={{ color: "#ef4444" }}>*</span>
              </label>
              <textarea
                id="elevated-reason"
                name="reason"
                rows={3}
                placeholder="State the explicit operational or emergency justification for this elevated grant (min 5 chars)..."
                className={`form-textarea ${fieldErrors.reason ? "inline-input-error" : ""}`}
                value={formData.reason}
                onChange={handleChange}
                disabled={grantMutation.isPending}
                maxLength={1000}
                aria-invalid={Boolean(fieldErrors.reason)}
                required
              />
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
                {fieldErrors.reason ? (
                  <span className="inline-error-msg" role="alert">
                    {fieldErrors.reason}
                  </span>
                ) : (
                  <span style={{ fontSize: 11, color: "#94a3b8" }}>
                    Recorded permanently in the immutable audit trail
                  </span>
                )}
                <span style={{ fontSize: 11, color: "#94a3b8" }}>
                  {(formData.reason || "").length}/1000
                </span>
              </div>
            </div>
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={grantMutation.isPending}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={grantMutation.isPending || !isSystemAdmin}
            >
              {grantMutation.isPending ? "Granting Privilege..." : "Grant Elevated Access"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/**
 * Modal Wrapper Component for Granting Elevated Access (US-45).
 * Only renders the inner dialog when isOpen is true.
 */
export default function ElevatedAccessModal({ isOpen, onClose, onGrantSuccess }) {
  if (!isOpen) return null;
  return <ElevatedAccessDialog onClose={onClose} onGrantSuccess={onGrantSuccess} />;
}

