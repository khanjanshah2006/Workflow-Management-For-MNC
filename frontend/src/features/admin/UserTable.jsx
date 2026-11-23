import React from "react";
import { normalizeRole } from "../../hooks/useAuth";

const ROLE_DISPLAY_NAMES = {
  ADMIN: "System Admin",
  SYSTEM_ADMIN: "System Admin",
  PM: "Project Manager",
  EMPLOYEE: "Employee",
  HR: "HR",
  CLIENT: "Client",
  IT_SUPPORT: "IT Support",
  TEAM_LEAD: "Team Lead",
  MNC_EXECUTIVE: "MNC Executive",
};

export const UserTable = ({
  users = [],
  isLoading = false,
  currentUser = null,
  page = 1,
  totalPages = 1,
  totalUsers = 0,
  onPageChange,
  onToggleStatus,
  onChangeRole,
  onResetPassword,
}) => {
  const currentAdminEmail = currentUser?.email?.toLowerCase();
  const currentAdminId = currentUser?.account_id;

  if (isLoading) {
    return (
      <div className="admin-table-container" style={{ padding: "40px", textAlign: "center" }}>
        <div className="placeholder-symbol" style={{ fontSize: "24px", animation: "spin 1s linear infinite" }}>
          ✳
        </div>
        <p style={{ marginTop: "12px", color: "#64748b", fontSize: "14px" }}>
          Loading user accounts...
        </p>
      </div>
    );
  }

  if (!users || users.length === 0) {
    return (
      <div className="admin-table-container" style={{ padding: "48px 24px", textAlign: "center" }}>
        <div style={{ fontSize: "32px", marginBottom: "8px" }}>👥</div>
        <h3 style={{ fontSize: "16px", fontWeight: "600", color: "#1e293b", margin: "0 0 4px" }}>
          No users found
        </h3>
        <p style={{ fontSize: "13px", color: "#64748b", margin: 0 }}>
          No accounts matched your search criteria or filter settings.
        </p>
      </div>
    );
  }

  return (
    <div className="admin-table-container">
      <table className="admin-table">
        <thead>
          <tr>
            <th>User Account</th>
            <th>Role</th>
            <th>Account Status</th>
            <th>Security / MFA</th>
            <th>Account ID</th>
            <th style={{ textAlign: "right" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => {
            const rawRole = user.user_type || user.role || "EMPLOYEE";
            const normRole = normalizeRole(rawRole);
            const displayRole = ROLE_DISPLAY_NAMES[normRole] || normRole;
            const isSelf =
              (currentAdminId && user.account_id === currentAdminId) ||
              (currentAdminEmail && user.email?.toLowerCase() === currentAdminEmail);

            return (
              <tr key={user.account_id || user.id || user.email}>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <div
                      style={{
                        width: "34px",
                        height: "34px",
                        borderRadius: "50%",
                        background: isSelf ? "#4456d9" : "#e2e8f0",
                        color: isSelf ? "#ffffff" : "#475569",
                        display: "grid",
                        placeItems: "center",
                        fontWeight: "700",
                        fontSize: "13px",
                        flexShrink: 0,
                      }}
                    >
                      {user.email ? user.email.charAt(0).toUpperCase() : "U"}
                    </div>
                    <div>
                      <div style={{ fontWeight: "600", color: "#1e293b", fontSize: "13.5px" }}>
                        {user.email}
                      </div>
                      {isSelf && (
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: "700",
                            background: "#e0e7ff",
                            color: "#3730a3",
                            padding: "1px 6px",
                            borderRadius: "4px",
                            textTransform: "uppercase",
                          }}
                        >
                          You (Logged In)
                        </span>
                      )}
                    </div>
                  </div>
                </td>

                <td>
                  <span
                    style={{
                      display: "inline-block",
                      padding: "2px 8px",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: "600",
                      background:
                        normRole.includes("ADMIN")
                          ? "#fef2f2"
                          : normRole.includes("PM")
                          ? "#eef2ff"
                          : "#f1f5f9",
                      color:
                        normRole.includes("ADMIN")
                          ? "#b91c1c"
                          : normRole.includes("PM")
                          ? "#3730a3"
                          : "#475569",
                      border: "1px solid",
                      borderColor:
                        normRole.includes("ADMIN")
                          ? "#fecaca"
                          : normRole.includes("PM")
                          ? "#c7d2fe"
                          : "#e2e8f0",
                    }}
                  >
                    {displayRole}
                  </span>
                </td>

                <td>
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      fontSize: "12px",
                      fontWeight: "600",
                      color: user.is_active ? "#15803d" : "#991b1b",
                    }}
                  >
                    <span
                      style={{
                        width: "8px",
                        height: "8px",
                        borderRadius: "50%",
                        background: user.is_active ? "#22c55e" : "#ef4444",
                      }}
                    />
                    {user.is_active ? "Active" : "Deactivated"}
                  </span>
                </td>

                <td>
                  <span
                    style={{
                      fontSize: "12px",
                      color: user.is_mfa_enabled ? "#15803d" : "#64748b",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    {user.is_mfa_enabled ? "✓ MFA Enabled" : "○ Password Only"}
                  </span>
                </td>

                <td>
                  <code
                    style={{
                      fontSize: "11px",
                      background: "#f8fafc",
                      padding: "2px 6px",
                      borderRadius: "4px",
                      color: "#64748b",
                      border: "1px solid #e2e8f0",
                      maxWidth: "140px",
                      display: "inline-block",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={user.account_id}
                  >
                    {user.account_id || "—"}
                  </code>
                </td>

                <td style={{ textAlign: "right" }}>
                  <div style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                    {/* Role Change Button */}
                    <button
                      type="button"
                      className="btn"
                      style={{
                        fontSize: "12px",
                        padding: "5px 10px",
                        background: "#ffffff",
                        border: "1px solid #cbd5e1",
                        color: "#334155",
                        borderRadius: "6px",
                      }}
                      onClick={() => onChangeRole(user)}
                      title="Reassign role"
                    >
                      Role
                    </button>

                    {/* Reset Password Button */}
                    <button
                      type="button"
                      className="btn"
                      style={{
                        fontSize: "12px",
                        padding: "5px 10px",
                        background: "#ffffff",
                        border: "1px solid #cbd5e1",
                        color: "#334155",
                        borderRadius: "6px",
                      }}
                      onClick={() => onResetPassword(user)}
                      title="Trigger password reset"
                    >
                      Reset Pwd
                    </button>

                    {/* Status Toggle Button / Tooltip */}
                    {isSelf ? (
                      <span
                        title="You cannot disable your own administrator account."
                        style={{ display: "inline-block" }}
                      >
                        <button
                          type="button"
                          className="btn"
                          disabled
                          style={{
                            fontSize: "12px",
                            padding: "5px 10px",
                            background: "#f1f5f9",
                            border: "1px solid #e2e8f0",
                            color: "#94a3b8",
                            borderRadius: "6px",
                            cursor: "not-allowed",
                            opacity: 0.6,
                          }}
                        >
                          Deactivate
                        </button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="btn"
                        style={{
                          fontSize: "12px",
                          padding: "5px 10px",
                          background: user.is_active ? "#fef2f2" : "#f0fdf4",
                          border: "1px solid",
                          borderColor: user.is_active ? "#fecaca" : "#bbf7d0",
                          color: user.is_active ? "#b91c1c" : "#166534",
                          borderRadius: "6px",
                        }}
                        onClick={() => onToggleStatus(user)}
                        title={user.is_active ? "Deactivate user account" : "Activate user account"}
                      >
                        {user.is_active ? "Deactivate" : "Activate"}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Pagination Controls */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 20px",
          borderTop: "1px solid #e2e8f0",
          background: "#fafafa",
          fontSize: "13px",
          color: "#64748b",
        }}
      >
        <div>
          Showing page <strong>{page}</strong> of <strong>{totalPages || 1}</strong> ({totalUsers} total users)
        </div>

        <div style={{ display: "flex", gap: "6px" }}>
          <button
            type="button"
            className="btn"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            style={{
              padding: "4px 10px",
              fontSize: "12px",
              borderRadius: "6px",
              background: "#ffffff",
              border: "1px solid #cbd5e1",
              color: page <= 1 ? "#94a3b8" : "#334155",
              cursor: page <= 1 ? "not-allowed" : "pointer",
            }}
          >
            ← Previous
          </button>

          <button
            type="button"
            className="btn"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            style={{
              padding: "4px 10px",
              fontSize: "12px",
              borderRadius: "6px",
              background: "#ffffff",
              border: "1px solid #cbd5e1",
              color: page >= totalPages ? "#94a3b8" : "#334155",
              cursor: page >= totalPages ? "not-allowed" : "pointer",
            }}
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
};

export default UserTable;
