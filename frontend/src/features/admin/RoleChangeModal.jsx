import React, { useState } from "react";
import { normalizeRole } from "../../hooks/useAuth";

const ROLES_LIST = [
  { value: "EMPLOYEE", label: "Employee" },
  { value: "PM", label: "Project Manager (PM)" },
  { value: "ADMIN", label: "System Administrator (ADMIN)" },
  { value: "HR", label: "HR Manager" },
  { value: "CLIENT", label: "Client" },
  { value: "IT_SUPPORT", label: "IT Support" },
  { value: "TEAM_LEAD", label: "Team Lead" },
];

export const RoleChangeModal = ({
  isOpen,
  onClose,
  onConfirm,
  user = null,
  isSubmitting = false,
}) => {
  const initialRole = user
    ? normalizeRole(user.user_type || user.role || "EMPLOYEE") === "SYSTEM_ADMIN"
      ? "ADMIN"
      : normalizeRole(user.user_type || user.role || "EMPLOYEE")
    : "EMPLOYEE";

  const [selectedRole, setSelectedRole] = useState(initialRole);

  if (!isOpen || !user) return null;

  const currentRoleNorm = normalizeRole(user.user_type || user.role || "EMPLOYEE");

  const handleSubmit = (e) => {
    e.preventDefault();
    onConfirm(user, selectedRole);
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="role-change-modal-title">
      <div className="modal-card" style={{ maxWidth: "440px" }}>
        <header className="modal-header">
          <div>
            <span className="modal-eyebrow">RBAC ROLE ASSIGNMENT</span>
            <h2 id="role-change-modal-title" className="modal-title">
              Change User Role
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

        <form onSubmit={handleSubmit}>
          <div className="modal-form-body" style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "14px" }}>
            <p style={{ fontSize: "13.5px", color: "#475569", margin: 0 }}>
              Modifying permissions for account <strong>{user.email}</strong>.
            </p>

            <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label htmlFor="user-new-role" style={{ fontSize: "12px", fontWeight: "600", color: "#334155" }}>
                Select New Role
              </label>
              <select
                id="user-new-role"
                value={selectedRole}
                onChange={(e) => setSelectedRole(e.target.value)}
                style={{
                  padding: "9px 12px",
                  fontSize: "13.5px",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  background: "#ffffff",
                  color: "#1e293b",
                }}
              >
                {ROLES_LIST.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>

            {selectedRole === currentRoleNorm ? (
              <p style={{ fontSize: "12px", color: "#64748b", margin: 0 }}>
                This is already the user's current role.
              </p>
            ) : (
              <div
                style={{
                  padding: "10px 12px",
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: "6px",
                  fontSize: "12.5px",
                  color: "#475569",
                }}
              >
                Role will be updated immediately from <strong>{currentRoleNorm}</strong> to{" "}
                <strong>{selectedRole}</strong>.
              </div>
            )}
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
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting || selectedRole === currentRoleNorm}
              style={{
                padding: "8px 18px",
                borderRadius: "6px",
                background: "#4456d9",
                color: "#ffffff",
                border: "none",
                fontWeight: "600",
              }}
            >
              {isSubmitting ? "Updating..." : "Update Role"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
};

export default RoleChangeModal;
