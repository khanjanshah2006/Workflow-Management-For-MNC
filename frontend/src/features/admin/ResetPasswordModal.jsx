import React, { useState } from "react";

export const ResetPasswordModal = ({
  isOpen,
  onClose,
  onConfirm,
  user = null,
  isSubmitting = false,
}) => {
  const [newPassword, setNewPassword] = useState(() => {
    return "TempPass#" + Math.floor(100000 + Math.random() * 900000);
  });
  const [isCopied, setIsCopied] = useState(false);
  const [isResetDone, setIsResetDone] = useState(false);

  if (!isOpen || !user) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(newPassword);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!newPassword || newPassword.length < 8) return;

    await onConfirm(user, newPassword);
    setIsResetDone(true);
  };

  const handleClose = () => {
    setIsResetDone(false);
    setIsCopied(false);
    setNewPassword("TempPass#" + Math.floor(100000 + Math.random() * 900000));
    onClose();
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="reset-password-modal-title">
      <div className="modal-card" style={{ maxWidth: "460px" }}>
        <header className="modal-header">
          <div>
            <span className="modal-eyebrow">CREDENTIAL MANAGEMENT</span>
            <h2 id="reset-password-modal-title" className="modal-title">
              {isResetDone ? "Temporary Password Generated" : "Reset User Password"}
            </h2>
          </div>
          <button
            type="button"
            className="modal-close-button"
            onClick={handleClose}
            aria-label="Close modal"
          >
            ✕
          </button>
        </header>

        {isResetDone ? (
          <div className="modal-form-body" style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "16px" }}>
            <div
              style={{
                padding: "12px 14px",
                background: "#f0fdf4",
                border: "1px solid #bbf7d0",
                borderRadius: "8px",
                color: "#166534",
                fontSize: "13px",
              }}
            >
              ✓ Password successfully reset for <strong>{user.email}</strong>.
            </div>

            <div>
              <label style={{ fontSize: "12px", fontWeight: "600", color: "#475569", display: "block", marginBottom: "6px" }}>
                Temporary Password to share with user:
              </label>
              <div style={{ display: "flex", gap: "8px" }}>
                <input
                  type="text"
                  readOnly
                  value={newPassword}
                  style={{
                    flex: 1,
                    fontFamily: "monospace",
                    fontSize: "15px",
                    fontWeight: "700",
                    padding: "8px 12px",
                    background: "#f8fafc",
                    border: "1px solid #cbd5e1",
                    borderRadius: "6px",
                    color: "#1e293b",
                  }}
                />
                <button
                  type="button"
                  className="btn"
                  onClick={handleCopy}
                  style={{
                    padding: "8px 14px",
                    borderRadius: "6px",
                    background: isCopied ? "#16a34a" : "#4456d9",
                    color: "#ffffff",
                    border: "none",
                    fontWeight: "600",
                    fontSize: "13px",
                  }}
                >
                  {isCopied ? "✓ Copied!" : "Copy"}
                </button>
              </div>
            </div>

            <p style={{ fontSize: "12px", color: "#64748b", margin: 0 }}>
              The user should change this temporary password immediately after their next login.
            </p>

            <footer className="modal-footer" style={{ marginTop: "12px", display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleClose}
                style={{
                  padding: "8px 20px",
                  borderRadius: "6px",
                  background: "#4456d9",
                  color: "#ffffff",
                  border: "none",
                  fontWeight: "600",
                }}
              >
                Done
              </button>
            </footer>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="modal-form-body" style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "14px" }}>
              <p style={{ fontSize: "13.5px", color: "#334155", margin: 0, lineHeight: "1.5" }}>
                Generate or define a temporary password for <strong>{user.email}</strong>.
              </p>

              <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <label htmlFor="temp-password-input" style={{ fontSize: "12px", fontWeight: "600", color: "#334155" }}>
                    Temporary Password
                  </label>
                  <button
                    type="button"
                    style={{
                      fontSize: "11px",
                      color: "#4456d9",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      fontWeight: "600",
                    }}
                    onClick={() => {
                      setNewPassword("TempPass#" + Math.floor(100000 + Math.random() * 900000));
                    }}
                  >
                    Regenerate
                  </button>
                </div>
                <input
                  id="temp-password-input"
                  type="text"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  style={{
                    padding: "9px 12px",
                    fontFamily: "monospace",
                    fontSize: "14px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    color: "#1e293b",
                  }}
                  required
                />
              </div>

              <div
                style={{
                  padding: "10px 12px",
                  background: "#fffbeb",
                  border: "1px solid #fef3c7",
                  borderRadius: "6px",
                  fontSize: "12.5px",
                  color: "#92400e",
                }}
              >
                ⚠ Confirming will overwrite the existing credentials and terminate all active sessions for this user.
              </div>

              <div
                data-testid="reset-clears-lock-note"
                style={{
                  padding: "10px 12px",
                  background: user.is_locked ? "#fff7ed" : "#f8fafc",
                  border: `1px solid ${user.is_locked ? "#fed7aa" : "#e2e8f0"}`,
                  borderRadius: "6px",
                  fontSize: "12.5px",
                  color: user.is_locked ? "#9a3412" : "#475569",
                }}
              >
                🔓 Resetting the password also clears any failed sign-in lock on this account
                {user.is_locked ? " (currently locked)." : "."}
              </div>
            </div>

            <footer className="modal-footer" style={{ marginTop: "24px", display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleClose}
                disabled={isSubmitting}
                style={{ padding: "8px 16px", borderRadius: "6px" }}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={isSubmitting || !newPassword || newPassword.length < 8}
                style={{
                  padding: "8px 18px",
                  borderRadius: "6px",
                  background: "#4456d9",
                  color: "#ffffff",
                  border: "none",
                  fontWeight: "600",
                }}
              >
                {isSubmitting ? "Resetting..." : "Reset Password"}
              </button>
            </footer>
          </form>
        )}
      </div>
    </div>
  );
};

export default ResetPasswordModal;
