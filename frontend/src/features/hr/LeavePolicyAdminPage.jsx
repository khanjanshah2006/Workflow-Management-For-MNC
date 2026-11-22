import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../context/AuthContext.jsx";
import { normalizeRole } from "../../auth/session.js";
import {
  getLeavePolicies,
  createLeavePolicy,
  updateLeavePolicy,
} from "../../api/leaveApi.js";
import PolicyListTable from "./PolicyListTable.jsx";
import PolicyFormModal from "./PolicyFormModal.jsx";
import "./leavePolicy.css";

/**
 * LeavePolicyAdminPage Component (US-18 / S4-FE-3)
 *
 * Route: /hr/leave-policies
 * Permissions: HR, ADMIN (fail-closed for all other roles)
 *
 * Features:
 * - Header with "Create policy" button and "Show inactive" toggle (?include_inactive=true)
 * - Tabular policy directory with name, quota, compensation type, active status, description
 * - Modal for creating and editing policies with client validation and 409 conflict handling
 * - Inline Deactivate / Reactivate confirmation flows
 * - Cache invalidation via TanStack Query for immediate updates without page reload
 */
export default function LeavePolicyAdminPage() {
  const { user, role } = useAuth();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  // Belt-and-suspenders role check (ProtectedRoute also enforces this)
  const currentRole = normalizeRole(role || user?.user_type || user?.role || "");
  const isAuthorized = currentRole === "HR" || currentRole === "ADMIN";

  // URL-driven include_inactive parameter
  const showInactive = searchParams.get("include_inactive") === "true";

  const handleToggleInactive = (checked) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (checked) {
        next.set("include_inactive", "true");
      } else {
        next.delete("include_inactive");
      }
      return next;
    });
  };

  // Modal and action states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState(null);
  const [serverError, setServerError] = useState(null);
  const [actionLoadingId, setActionLoadingId] = useState(null);

  // Toast alert state
  const [toast, setToast] = useState(null);

  const showToast = (message, type = "success") => {
    setToast({ message, type, id: Date.now() });
    setTimeout(() => setToast(null), 4000);
  };

  // Query leave policies from API
  const {
    data: policies = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["leave-policies", { includeInactive: showInactive }],
    queryFn: () => getLeavePolicies({ includeInactive: showInactive }),
    enabled: isAuthorized,
  });

  // Create Policy Mutation
  const createMutation = useMutation({
    mutationFn: (payload) => createLeavePolicy(payload),
    onSuccess: (newPolicy) => {
      queryClient.invalidateQueries({ queryKey: ["leave-policies"] });
      setIsModalOpen(false);
      setEditingPolicy(null);
      setServerError(null);
      showToast(`Leave policy "${newPolicy.name}" created successfully.`);
    },
    onError: (err) => {
      setServerError(err);
    },
  });

  // Update Policy Mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, payload }) => updateLeavePolicy(id, payload),
    onSuccess: (updatedPolicy) => {
      queryClient.invalidateQueries({ queryKey: ["leave-policies"] });
      setIsModalOpen(false);
      setEditingPolicy(null);
      setServerError(null);
      showToast(`Leave policy "${updatedPolicy.name}" updated successfully.`);
    },
    onError: (err) => {
      setServerError(err);
    },
  });

  // Toggle Policy Status (Deactivate / Reactivate) Mutation
  const toggleStatusMutation = useMutation({
    mutationFn: ({ id, isActive }) => updateLeavePolicy(id, { is_active: isActive }),
    onSuccess: (updatedPolicy, variables) => {
      queryClient.invalidateQueries({ queryKey: ["leave-policies"] });
      setActionLoadingId(null);
      const actionName = variables.isActive ? "reactivated" : "deactivated";
      showToast(`Policy "${updatedPolicy.name}" ${actionName} successfully.`);
    },
    onError: (err) => {
      setActionLoadingId(null);
      showToast(err.message || "Failed to update policy status.", "error");
    },
  });

  if (!isAuthorized) {
    return (
      <section className="page leave-policy-admin-page">
        <div className="page-eyebrow">ACCESS CONTROL</div>
        <h1>403 — Unauthorized Access</h1>
        <p className="page-description">
          Your current assigned role ({role || user?.user_type || "User"}) does not have permissions to administer leave policies.
        </p>
        <div className="placeholder-panel">
          <div className="placeholder-symbol">🔒</div>
          <h2>Restricted View</h2>
          <p>Leave policy configuration is restricted to Human Resources (HR) and Administrators.</p>
        </div>
      </section>
    );
  }

  const handleOpenCreate = () => {
    setEditingPolicy(null);
    setServerError(null);
    setIsModalOpen(true);
  };

  const handleOpenEdit = (policy) => {
    setEditingPolicy(policy);
    setServerError(null);
    setIsModalOpen(true);
  };

  const handleModalSave = (payload) => {
    setServerError(null);
    if (editingPolicy) {
      updateMutation.mutate({
        id: editingPolicy.leave_type_id,
        payload,
      });
    } else {
      createMutation.mutate(payload);
    }
  };

  const handleToggleStatus = (policy, makeActive) => {
    setActionLoadingId(policy.leave_type_id);
    toggleStatusMutation.mutate({
      id: policy.leave_type_id,
      isActive: makeActive,
    });
  };

  return (
    <section className="page leave-policy-admin-page">
      {/* Toast Notification */}
      {toast && (
        <div
          className={`policy-toast policy-toast-${toast.type}`}
          role="status"
          aria-live="polite"
        >
          <span className="toast-icon">{toast.type === "error" ? "⚠️" : "✓"}</span>
          <span>{toast.message}</span>
        </div>
      )}

      {/* Page Header */}
      <div className="leave-policy-header">
        <div>
          <div className="page-eyebrow">HUMAN RESOURCES</div>
          <h1 className="page-title">Leave Policy Administration</h1>
          <p className="page-description">
            Configure annual entitlement quotas, compensation types, and active availability for all company leave categories.
          </p>
        </div>

        <div className="policy-header-actions">
          {/* Show Inactive Toggle */}
          <label className="show-inactive-control">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => handleToggleInactive(e.target.checked)}
              id="show-inactive-toggle"
            />
            <span className="show-inactive-label">Show inactive</span>
          </label>

          {/* Create Policy Button */}
          <button
            type="button"
            className="btn btn-primary btn-create-policy"
            onClick={handleOpenCreate}
          >
            + Create policy
          </button>
        </div>
      </div>

      {/* Error state if query fails */}
      {isError && (
        <div className="policy-error-banner" role="alert">
          <div>
            <strong>Error loading policies:</strong> {error?.message || "Failed to retrieve policy directory."}
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => refetch()}
          >
            Retry
          </button>
        </div>
      )}

      {/* Policy Directory Table */}
      <PolicyListTable
        policies={policies}
        isLoading={isLoading}
        onEdit={handleOpenEdit}
        onToggleStatus={handleToggleStatus}
        actionLoadingId={actionLoadingId}
      />

      {/* Create / Edit Policy Modal */}
      <PolicyFormModal
        isOpen={isModalOpen}
        onClose={() => {
          if (!createMutation.isPending && !updateMutation.isPending) {
            setIsModalOpen(false);
            setServerError(null);
          }
        }}
        onSave={handleModalSave}
        policy={editingPolicy}
        isLoading={createMutation.isPending || updateMutation.isPending}
        serverError={serverError}
      />
    </section>
  );
}
