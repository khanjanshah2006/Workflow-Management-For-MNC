import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "../../api/adminApi";
import { useAuth, normalizeRole } from "../../hooks/useAuth";
import UserTable from "./UserTable";
import CreateUserModal from "./CreateUserModal";
import StatusToggleModal from "./StatusToggleModal";
import RoleChangeModal from "./RoleChangeModal";
import ResetPasswordModal from "./ResetPasswordModal";
import "./admin.css";

const ROLE_OPTIONS = [
  { value: "ALL", label: "All Roles" },
  { value: "EMPLOYEE", label: "Employee" },
  { value: "PM", label: "Project Manager (PM)" },
  { value: "ADMIN", label: "System Administrator" },
  { value: "HR", label: "HR Manager" },
  { value: "CLIENT", label: "Client" },
  { value: "IT_SUPPORT", label: "IT Support" },
  { value: "TEAM_LEAD", label: "Team Lead" },
];

const STATUS_OPTIONS = [
  { value: "", label: "All Statuses" },
  { value: "true", label: "Active Only" },
  { value: "false", label: "Deactivated Only" },
];

export function UserManagementPage() {
  const queryClient = useQueryClient();
  const { user: currentAdmin } = useAuth();

  // Search, filter, and pagination states
  const [searchTerm, setSearchTerm] = useState("");
  const [roleFilter, setRoleFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 10;

  // Modal visibility states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedUserForStatus, setSelectedUserForStatus] = useState(null);
  const [selectedUserForRole, setSelectedUserForRole] = useState(null);
  const [selectedUserForReset, setSelectedUserForReset] = useState(null);

  // Toast notifications state
  const [toasts, setToasts] = useState([]);

  const addToast = (type, message) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  };

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // RBAC validation: strictly accessible to ADMIN / SYSTEM_ADMIN
  const currentRole = normalizeRole(currentAdmin?.role || currentAdmin?.user_type);
  const isAuthorizedAdmin = currentRole === "ADMIN" || currentRole === "SYSTEM_ADMIN";

  // TanStack Query: Fetch users
  const {
    data: usersData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["admin", "users", { page, limit: pageSize, search: searchTerm, user_type: roleFilter, is_active: statusFilter }],
    queryFn: () =>
      adminApi.getUsers({
        page,
        limit: pageSize,
        search: searchTerm,
        user_type: roleFilter,
        is_active: statusFilter,
      }),
    keepPreviousData: true,
  });

  // TanStack Mutation: Create user
  const createMutation = useMutation({
    mutationFn: (payload) => adminApi.createUser(payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      setIsCreateModalOpen(false);
      addToast("success", `User account ${data?.email || "successfully"} created.`);
    },
    onError: (err) => {
      addToast("error", err?.message || "Failed to create user account.");
    },
  });

  // TanStack Mutation: Update status
  const statusMutation = useMutation({
    mutationFn: ({ accountId, isActive }) => adminApi.updateUserStatus(accountId, isActive),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      setSelectedUserForStatus(null);
      addToast(
        "success",
        `User account successfully ${variables.isActive ? "activated" : "deactivated"}.`
      );
    },
    onError: (err) => {
      addToast("error", err?.message || "Failed to update account status.");
    },
  });

  // TanStack Mutation: Update role
  const roleMutation = useMutation({
    mutationFn: ({ accountId, userType }) => adminApi.updateUserRole(accountId, userType),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      setSelectedUserForRole(null);
      addToast("success", `User role successfully updated to ${variables.userType}.`);
    },
    onError: (err) => {
      addToast("error", err?.message || "Failed to update user role.");
    },
  });

  // TanStack Mutation: Reset password
  const resetMutation = useMutation({
    mutationFn: ({ accountId, newPassword }) => adminApi.resetUserPassword(accountId, newPassword),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      addToast("success", "Temporary password successfully provisioned.");
    },
    onError: (err) => {
      addToast("error", err?.message || "Failed to reset password.");
    },
  });

  // Access denied screen for non-admin
  if (!isAuthorizedAdmin) {
    return (
      <section className="page" aria-labelledby="rbac-denied-heading">
        <div style={{ maxWidth: "600px", margin: "40px auto", textAlign: "center" }}>
          <div className="placeholder-panel">
            <div className="placeholder-symbol">🔒</div>
            <h1 id="rbac-denied-heading" style={{ fontSize: "20px", fontWeight: "700" }}>
              Administrator Privilege Required
            </h1>
            <p>
              The User Administration Console is restricted to users with the <strong>ADMIN</strong> or{" "}
              <strong>SYSTEM_ADMIN</strong> role.
            </p>
            <Link to="/dashboard" className="btn btn-primary" style={{ marginTop: "16px" }}>
              ← Return to Dashboard
            </Link>
          </div>
        </div>
      </section>
    );
  }

  const usersList = usersData?.items || [];
  const totalCount = usersData?.total ?? usersList.length;
  const totalPages = usersData?.pages || Math.max(1, Math.ceil(totalCount / pageSize));

  return (
    <section className="page user-management-page" aria-labelledby="user-mgmt-heading">
      <div className="security-ops-container">
        {/* Toast Notifications Overlay */}
        {toasts.length > 0 && (
          <div
            style={{
              position: "fixed",
              top: "24px",
              right: "24px",
              zIndex: 9999,
              display: "flex",
              flexDirection: "column",
              gap: "10px",
              maxWidth: "380px",
            }}
          >
            {toasts.map((toast) => (
              <div
                key={toast.id}
                role="alert"
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "10px",
                  padding: "12px 16px",
                  borderRadius: "8px",
                  background: toast.type === "success" ? "#f0fdf4" : "#fef2f2",
                  border: `1px solid ${toast.type === "success" ? "#bbf7d0" : "#fecaca"}`,
                  color: toast.type === "success" ? "#166534" : "#991b1b",
                  boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1)",
                  fontSize: "13.5px",
                  animation: "modal-fade-in 150ms ease",
                }}
              >
                <span>{toast.type === "success" ? "✓" : "⚠"}</span>
                <span style={{ flex: 1 }}>{toast.message}</span>
                <button
                  type="button"
                  onClick={() => removeToast(toast.id)}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    fontSize: "14px",
                    color: "inherit",
                    opacity: 0.7,
                    padding: 0,
                  }}
                  aria-label="Close notification"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Header & Sub-navigation Tabs */}
        <header className="security-header-row">
          <div className="security-header-info">
            <span className="page-eyebrow">SYSTEM ADMINISTRATION &bull; US-43, US-44, US-48</span>
            <h1 id="user-mgmt-heading">User Administration & Accounts</h1>
            <p className="page-description">
              Search, provision accounts, modify role assignments, toggle active status, and reset employee credentials.
            </p>
          </div>

          <div className="security-header-actions">
            <Link
              to="/admin/security"
              className="btn btn-secondary"
              style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
            >
              <span>⚙</span> Security Console
            </Link>

            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setIsCreateModalOpen(true)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                background: "#4456d9",
                color: "#ffffff",
                border: "none",
                padding: "8px 16px",
                borderRadius: "6px",
                fontWeight: "600",
              }}
            >
              <span>+</span> Create User Account
            </button>
          </div>
        </header>

        {/* Filter & Search Bar */}
        <div
          style={{
            background: "#ffffff",
            padding: "16px 20px",
            borderRadius: "12px",
            border: "1px solid #e7ebf2",
            display: "flex",
            alignItems: "center",
            gap: "16px",
            flexWrap: "wrap",
          }}
        >
          {/* Search by Name/Email */}
          <div style={{ flex: 1, minWidth: "240px", position: "relative" }}>
            <input
              type="text"
              placeholder="Search by name, corporate email, or ID..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setPage(1);
              }}
              style={{
                width: "100%",
                padding: "9px 12px",
                fontSize: "13.5px",
                borderRadius: "6px",
                border: "1px solid #cbd5e1",
                outline: "none",
              }}
            />
          </div>

          {/* Role Filter */}
          <div style={{ minWidth: "160px" }}>
            <select
              value={roleFilter}
              onChange={(e) => {
                setRoleFilter(e.target.value);
                setPage(1);
              }}
              style={{
                width: "100%",
                padding: "9px 12px",
                fontSize: "13.5px",
                borderRadius: "6px",
                border: "1px solid #cbd5e1",
                background: "#ffffff",
                color: "#1e293b",
              }}
            >
              {ROLE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div style={{ minWidth: "150px" }}>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              style={{
                width: "100%",
                padding: "9px 12px",
                fontSize: "13.5px",
                borderRadius: "6px",
                border: "1px solid #cbd5e1",
                background: "#ffffff",
                color: "#1e293b",
              }}
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Refresh button */}
          <button
            type="button"
            onClick={() => refetch()}
            className="btn btn-secondary"
            style={{
              padding: "9px 14px",
              fontSize: "13px",
              borderRadius: "6px",
              background: "#ffffff",
              border: "1px solid #cbd5e1",
            }}
            title="Refresh user list"
          >
            ↻ Refresh
          </button>
        </div>

        {/* Error banner if query fails */}
        {isError && (
          <div
            style={{
              padding: "12px 16px",
              background: "#fef2f2",
              border: "1px solid #fecaca",
              borderRadius: "8px",
              color: "#991b1b",
              fontSize: "13.5px",
            }}
          >
            Failed to fetch user accounts: {error?.message || "Ensure the backend server is reachable."}
          </div>
        )}

        {/* User Table with Actions */}
        <UserTable
          users={usersList}
          isLoading={isLoading}
          currentUser={currentAdmin}
          page={page}
          totalPages={totalPages}
          totalUsers={totalCount}
          onPageChange={(newPage) => setPage(newPage)}
          onToggleStatus={(user) => setSelectedUserForStatus(user)}
          onChangeRole={(user) => setSelectedUserForRole(user)}
          onResetPassword={(user) => setSelectedUserForReset(user)}
        />

        {/* Modals */}
        <CreateUserModal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          onSubmit={(payload) => createMutation.mutate(payload)}
          isSubmitting={createMutation.isPending}
        />

        <StatusToggleModal
          isOpen={Boolean(selectedUserForStatus)}
          user={selectedUserForStatus}
          onClose={() => setSelectedUserForStatus(null)}
          onConfirm={(user, newStatus) =>
            statusMutation.mutate({
              accountId: user.account_id || user.id,
              isActive: newStatus,
            })
          }
          isSubmitting={statusMutation.isPending}
        />

        <RoleChangeModal
          isOpen={Boolean(selectedUserForRole)}
          user={selectedUserForRole}
          onClose={() => setSelectedUserForRole(null)}
          onConfirm={(user, newRole) =>
            roleMutation.mutate({
              accountId: user.account_id || user.id,
              userType: newRole,
            })
          }
          isSubmitting={roleMutation.isPending}
        />

        <ResetPasswordModal
          isOpen={Boolean(selectedUserForReset)}
          user={selectedUserForReset}
          onClose={() => setSelectedUserForReset(null)}
          onConfirm={async (user, newPassword) => {
            await resetMutation.mutateAsync({
              accountId: user.account_id || user.id,
              newPassword,
            });
          }}
          isSubmitting={resetMutation.isPending}
        />
      </div>
    </section>
  );
}

export default UserManagementPage;
