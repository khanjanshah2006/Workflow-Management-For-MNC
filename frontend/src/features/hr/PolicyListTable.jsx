import React, { useState } from "react";
import { formatQuotaLabel } from "./leavePolicyUtils.js";

/**
 * PolicyListTable Component (US-18 / S4-FE-3)
 *
 * Renders the tabular policy directory:
 * - Name
 * - Yearly Quota (e.g., "20 days")
 * - Type: Paid / Unpaid badge
 * - Status: Active / Inactive badge
 * - Description (trimmed with tooltip or fallback "—")
 * - Actions: Edit button, Deactivate / Reactivate button with confirmation dialog
 */
export default function PolicyListTable({
  policies = [],
  isLoading = false,
  onEdit,
  onToggleStatus,
  actionLoadingId = null,
}) {
  // Confirmation state for Deactivate / Reactivate action: { policy, action: "DEACTIVATE" | "REACTIVATE" } | null
  const [confirmTarget, setConfirmTarget] = useState(null);

  if (isLoading) {
    return (
      <div className="lp-policy-table-container">
        <div className="lp-table-loading-state" role="status">
          <div className="lp-spinner"></div>
          <p>Loading leave policies...</p>
        </div>
      </div>
    );
  }

  if (!policies || policies.length === 0) {
    return (
      <div className="lp-policy-table-container">
        <div className="lp-table-empty-state">
          <span className="lp-empty-icon">📜</span>
          <h3>No Leave Policies Found</h3>
          <p>
            No matching leave policies found. Click &quot;Create policy&quot; to establish an entitlement.
          </p>
        </div>
      </div>
    );
  }

  const handleConfirmAction = () => {
    if (!confirmTarget) return;
    const { policy, action } = confirmTarget;
    setConfirmTarget(null);
    onToggleStatus(policy, action === "REACTIVATE");
  };

  return (
    <div className="lp-policy-table-container">
      <table className="lp-policy-table" aria-label="Leave Policies Directory">
        <thead>
          <tr>
            <th scope="col" style={{ width: "24%" }}>Policy Name</th>
            <th scope="col" style={{ width: "16%" }}>Yearly Quota</th>
            <th scope="col" style={{ width: "14%" }}>Type</th>
            <th scope="col" style={{ width: "14%" }}>Status</th>
            <th scope="col" style={{ width: "20%" }}>Description</th>
            <th scope="col" style={{ width: "12%", textAlign: "right" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {policies.map((policy) => {
            const isTargetLoading = actionLoadingId === policy.leave_type_id;
            const isActive = policy.is_active !== false;

            return (
              <tr key={policy.leave_type_id} className={!isActive ? "lp-row-inactive" : ""}>
                <td className="lp-cell-policy-name">
                  <div className="lp-policy-name-wrapper">
                    <span className="lp-policy-title">{policy.name}</span>
                    <span className="lp-policy-id-tag">ID #{policy.leave_type_id}</span>
                  </div>
                </td>
                <td className="lp-cell-quota">
                  <span className="lp-quota-pill">{formatQuotaLabel(policy.yearly_quota)}</span>
                </td>
                <td className="lp-cell-type">
                  {policy.is_paid ? (
                    <span className="lp-badge lp-badge-paid" title="Employee is compensated normally">
                      ● Paid
                    </span>
                  ) : (
                    <span className="lp-badge lp-badge-unpaid" title="Uncompensated absence">
                      ○ Unpaid
                    </span>
                  )}
                </td>
                <td className="lp-cell-status">
                  {isActive ? (
                    <span className="lp-badge lp-badge-active">Active</span>
                  ) : (
                    <span className="lp-badge lp-badge-inactive">Inactive</span>
                  )}
                </td>
                <td className="lp-cell-description">
                  <span className="lp-description-text" title={policy.description || ""}>
                    {policy.description ? policy.description : <span className="lp-text-muted">—</span>}
                  </span>
                </td>
                <td className="lp-cell-actions" style={{ textAlign: "right" }}>
                  <div className="lp-action-buttons-group">
                    <button
                      type="button"
                      className="lp-btn-action lp-btn-edit"
                      onClick={() => onEdit(policy)}
                      disabled={isTargetLoading}
                      title={`Edit ${policy.name}`}
                    >
                      Edit
                    </button>
                    {isActive ? (
                      <button
                        type="button"
                        className="lp-btn-action lp-btn-deactivate"
                        onClick={() =>
                          setConfirmTarget({
                            policy,
                            action: "DEACTIVATE",
                          })
                        }
                        disabled={isTargetLoading}
                        title={`Deactivate ${policy.name}`}
                      >
                        {isTargetLoading ? "..." : "Deactivate"}
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="lp-btn-action lp-btn-reactivate"
                        onClick={() =>
                          setConfirmTarget({
                            policy,
                            action: "REACTIVATE",
                          })
                        }
                        disabled={isTargetLoading}
                        title={`Reactivate ${policy.name}`}
                      >
                        {isTargetLoading ? "..." : "Reactivate"}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Confirmation Modal for Deactivate / Reactivate */}
      {confirmTarget && (
        <div
          className="lp-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-modal-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) setConfirmTarget(null);
          }}
        >
          <div className="lp-modal-dialog lp-policy-confirm-modal-dialog">
            <div className="lp-modal-header">
              <div>
                <h3 id="confirm-modal-title" className="lp-modal-title">
                  {confirmTarget.action === "DEACTIVATE"
                    ? "Deactivate Leave Policy?"
                    : "Reactivate Leave Policy?"}
                </h3>
              </div>
              <button
                type="button"
                className="lp-modal-close-btn"
                onClick={() => setConfirmTarget(null)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <div className="lp-modal-body">
              {confirmTarget.action === "DEACTIVATE" ? (
                <p>
                  Are you sure you want to deactivate <strong>&quot;{confirmTarget.policy.name}&quot;</strong>?
                  Employees will no longer be able to select this policy when submitting new leave requests.
                  Existing historical requests and balances remain preserved.
                </p>
              ) : (
                <p>
                  Are you sure you want to reactivate <strong>&quot;{confirmTarget.policy.name}&quot;</strong>?
                  Employees will be able to select this policy immediately for future leave requests.
                </p>
              )}
            </div>
            <div className="lp-modal-footer">
              <button
                type="button"
                className="lp-btn lp-btn-secondary"
                onClick={() => setConfirmTarget(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className={`lp-btn ${
                  confirmTarget.action === "DEACTIVATE" ? "lp-btn-danger" : "lp-btn-primary"
                }`}
                onClick={handleConfirmAction}
              >
                {confirmTarget.action === "DEACTIVATE"
                  ? "Yes, Deactivate"
                  : "Yes, Reactivate"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
