import React from "react";

export const StatusToggleModal = ({
  isOpen,
  onClose,
  onConfirm,
  user = null,
  isSubmitting = false,
}) => {
  if (!isOpen || !user) return null;

  const willActivate = !user.is_active;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="status-toggle-title">
      <div className="modal-card" style={{ maxWidth: "440px" }}>
        <header className="modal-header">
          <div>
            <span className="modal-eyebrow" style={{ color: willActivate ? "#16a34a" : "#dc2626" }}>
              CONFIRM ACCOUNT STATUS CHANGE
            </span>
            <h2 id="status-toggle-title" className="modal-title">
              {willActivate ? "Activate User Account" : "Deactivate User Account"}
            </h2>
          </div>
          <button
            type="button"
            className="modal-close-button"
            onClick={onClose}
            aria-label="Close modal"
          >
            ✕
          </button>
        </header>

        <div className="modal-form-body" style={{ marginTop: "12px" }}>
          <p style={{ fontSize: "14px", color: "#334155", lineHeight: "1.5", margin: "0 0 16px" }}>
            Are you sure you want to {willActivate ? "activate" : "deactivate"} access for{" "}
            <strong>{user.email}</strong>?
          </p>

          <div
            style={{
              padding: "12px",
              borderRadius: "8px",
              background: willActivate ? "#f0fdf4" : "#fef2f2",
              border: `1px solid ${willActivate ? "#bbf7d0" : "#fecaca"}`,
              fontSize: "13px",
              color: willActivate ? "#166534" : "#991b1b",
            }}
          >
            {willActivate ? (
              <span>
                ✓ The user will be immediately granted permission to sign in and access the system.
              </span>
            ) : (
              <span>
                ⚠ Deactivating this account will immediately revoke all active JWT sessions and block further portal access.
              </span>
            )}
          </div>
        </div>

        <footer className="modal-footer" style={{ marginTop: "24px", display: "flex", justifyContent: "flex-end", gap: "10px" }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClose}
            disabled={isSubmitting}
            style={{ padding: "8px 16px", borderRadius: "6px" }}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn"
            disabled={isSubmitting}
            onClick={() => onConfirm(user, willActivate)}
            style={{
              padding: "8px 18px",
              borderRadius: "6px",
              background: willActivate ? "#16a34a" : "#dc2626",
              color: "#ffffff",
              border: "none",
              fontWeight: "600",
            }}
          >
            {isSubmitting
              ? "Updating..."
              : willActivate
              ? "Confirm Activation"
              : "Confirm Deactivation"}
          </button>
        </footer>
      </div>
    </div>
  );
};

export default StatusToggleModal;
