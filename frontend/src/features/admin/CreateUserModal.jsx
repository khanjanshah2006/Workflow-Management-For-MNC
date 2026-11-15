import React, { useState } from "react";

const AVAILABLE_ROLES = [
  { value: "EMPLOYEE", label: "Employee" },
  { value: "PM", label: "Project Manager (PM)" },
  { value: "ADMIN", label: "System Administrator" },
  { value: "HR", label: "HR Manager" },
  { value: "CLIENT", label: "Client" },
  { value: "IT_SUPPORT", label: "IT Support" },
  { value: "TEAM_LEAD", label: "Team Lead" },
];

export const CreateUserModal = ({ isOpen, onClose, onSubmit, isSubmitting = false }) => {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("EMPLOYEE");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState({});

  if (!isOpen) return null;

  const validate = () => {
    const errs = {};
    if (!email.trim()) {
      errs.email = "Email address is required.";
    } else {
      const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailPattern.test(email.trim())) {
        errs.email = "Please provide a valid corporate email format (e.g. user@worksphere.com).";
      }
    }

    if (!password) {
      errs.password = "Initial password is required.";
    } else if (password.length < 8) {
      errs.password = "Password must be at least 8 characters.";
    }

    if (!role) {
      errs.role = "Role designation is required.";
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!validate()) return;

    onSubmit({
      email: email.trim(),
      password,
      user_type: role,
    });
  };

  const handleClose = () => {
    setEmail("");
    setPassword("");
    setRole("EMPLOYEE");
    setErrors({});
    onClose();
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="create-user-modal-title">
      <div className="modal-card" style={{ maxWidth: "480px" }}>
        <header className="modal-header">
          <div>
            <span className="modal-eyebrow">USER ADMINISTRATION</span>
            <h2 id="create-user-modal-title" className="modal-title">
              Create New User Account
            </h2>
            <p className="modal-subtitle">
              Provision corporate credentials and assign designated system role.
            </p>
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

        <form onSubmit={handleSubmit} noValidate>
          <div className="modal-form-body" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {/* Email Field */}
            <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label htmlFor="create-user-email" style={{ fontSize: "12px", fontWeight: "600", color: "#334155" }}>
                Corporate Email Address *
              </label>
              <input
                id="create-user-email"
                type="email"
                className={`form-input ${errors.email ? "form-input-error" : ""}`}
                placeholder="e.g. new.employee@worksphere.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
                }}
                style={{
                  padding: "9px 12px",
                  fontSize: "13.5px",
                  borderRadius: "6px",
                  border: errors.email ? "1px solid #ef4444" : "1px solid #cbd5e1",
                  background: errors.email ? "#fef2f2" : "#ffffff",
                }}
              />
              {errors.email && (
                <span style={{ fontSize: "12px", color: "#dc2626" }}>{errors.email}</span>
              )}
            </div>

            {/* Role Field */}
            <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label htmlFor="create-user-role" style={{ fontSize: "12px", fontWeight: "600", color: "#334155" }}>
                Designated System Role *
              </label>
              <select
                id="create-user-role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                style={{
                  padding: "9px 12px",
                  fontSize: "13.5px",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  background: "#ffffff",
                  color: "#1e293b",
                }}
              >
                {AVAILABLE_ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Initial Password Field */}
            <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <label htmlFor="create-user-password" style={{ fontSize: "12px", fontWeight: "600", color: "#334155" }}>
                  Initial Password *
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
                    const temp = "TempPass#" + Math.floor(100000 + Math.random() * 900000);
                    setPassword(temp);
                    if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
                  }}
                >
                  Generate Strong Password
                </button>
              </div>
              <input
                id="create-user-password"
                type="text"
                className={`form-input ${errors.password ? "form-input-error" : ""}`}
                placeholder="Minimum 8 characters"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
                }}
                style={{
                  padding: "9px 12px",
                  fontSize: "13.5px",
                  borderRadius: "6px",
                  border: errors.password ? "1px solid #ef4444" : "1px solid #cbd5e1",
                  background: errors.password ? "#fef2f2" : "#ffffff",
                }}
              />
              {errors.password && (
                <span style={{ fontSize: "12px", color: "#dc2626" }}>{errors.password}</span>
              )}
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
              disabled={isSubmitting}
              style={{
                padding: "8px 18px",
                borderRadius: "6px",
                background: "#4456d9",
                color: "#ffffff",
                border: "none",
                fontWeight: "600",
              }}
            >
              {isSubmitting ? "Creating..." : "Create User"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
};

export default CreateUserModal;
