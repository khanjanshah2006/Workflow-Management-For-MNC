import { useState, useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "../../api/adminApi";
import { useAuth, normalizeRole } from "../../hooks/useAuth";
import "./admin.css";

/**
 * Computes remaining time and status classification relative to current timestamp.
 *
 * @param {string|Date} expiresAt Target expiration ISO string or Date
 * @param {number} now Current timestamp in milliseconds (Date.now())
 * @returns {{ text: string, status: 'active' | 'expiring-soon' | 'expired', diffMs: number }}
 */
export function formatCountdown(expiresAt, now = Date.now()) {
  if (!expiresAt) {
    return { text: "No expiry", status: "expired", diffMs: 0 };
  }
  const target = new Date(expiresAt).getTime();
  if (isNaN(target)) {
    return { text: "Invalid date", status: "expired", diffMs: 0 };
  }

  const diffMs = target - now;
  if (diffMs <= 0) {
    return { text: "Expired", status: "expired", diffMs };
  }

  const totalSeconds = Math.floor(diffMs / 1000);
  const seconds = totalSeconds % 60;
  const minutes = Math.floor((totalSeconds / 60) % 60);
  const hours = Math.floor((totalSeconds / 3600) % 24);
  const days = Math.floor(totalSeconds / 86400);

  let text = "";
  if (days > 0) {
    text = `${days}d ${hours}h ${minutes}m ${seconds}s`;
  } else if (hours > 0) {
    text = `${hours}h ${minutes}m ${seconds}s`;
  } else if (minutes > 0) {
    text = `${minutes}m ${seconds}s`;
  } else {
    text = `${seconds}s`;
  }

  // Under 2 hours remaining is visually highlighted as expiring soon
  const isExpiringSoon = diffMs < 2 * 60 * 60 * 1000;
  const status = isExpiringSoon ? "expiring-soon" : "active";

  return { text, status, diffMs };
}

/**
 * Format timestamp to clean local string.
 */
export function formatTimestamp(isoStr) {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return String(isoStr);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(isoStr);
  }
}

/**
 * ActiveGrantsTable Component (US-45 / Issue #81)
 *
 * Displays currently active time-bound elevated access grants,
 * live countdown timers, and manual revocation action.
 *
 * @param {Object} props
 * @param {Function} [props.onOpenGrantModal] Callback to open grant modal
 */
export function ActiveGrantsTable({ onOpenGrantModal }) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const isSystemAdmin = normalizeRole(user?.role || user?.user_type) === "SYSTEM_ADMIN";

  const [currentTime, setCurrentTime] = useState(() => Date.now());
  const [confirmRevokeTarget, setConfirmRevokeTarget] = useState(null);
  const [actionFeedback, setActionFeedback] = useState(null);

  // Single efficient 1-second interval for all countdowns with automatic cleanup
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Fetch active elevated access grants
  const {
    data: grants = [],
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["admin", "elevated-access", "active"],
    queryFn: adminApi.getActiveElevatedGrants,
    staleTime: 15 * 1000,
  });

  // Filter only unrevoked grants for active table view
  const activeGrants = useMemo(() => {
    if (!Array.isArray(grants)) return [];
    return grants.filter((g) => !g.revoked_at);
  }, [grants]);

  // Revoke elevated access mutation
  const revokeMutation = useMutation({
    mutationFn: (grantId) => adminApi.revokeElevatedGrant(grantId),
    onSuccess: (_, grantId) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "elevated-access", "active"] });
      setConfirmRevokeTarget(null);
      setActionFeedback({
        type: "success",
        message: `Elevated access grant #${grantId} was successfully revoked.`,
      });
      setTimeout(() => setActionFeedback(null), 6000);
    },
    onError: (err) => {
      setConfirmRevokeTarget(null);
      setActionFeedback({
        type: "error",
        message:
          err.message ||
          "Failed to revoke elevated access grant. Please verify router endpoints.",
      });
    },
  });

  const handleConfirmRevoke = () => {
    if (!confirmRevokeTarget) return;
    if (!isSystemAdmin) {
      setActionFeedback({
        type: "error",
        message: "Permission denied. Only SYSTEM_ADMIN users can revoke elevated access.",
      });
      setConfirmRevokeTarget(null);
      return;
    }
    revokeMutation.mutate(confirmRevokeTarget.id);
  };

  const getRoleBadgeClass = (role) => {
    const r = (role || "").toUpperCase();
    if (r === "PM" || r === "PROJECT_MANAGER") return "role-badge role-badge-pm";
    if (r === "ADMIN" || r === "SYSTEM_ADMIN") return "role-badge role-badge-admin";
    if (r === "HR") return "role-badge role-badge-hr";
    if (r === "IT" || r === "DEVOPS") return "role-badge role-badge-it";
    return "role-badge role-badge-pm";
  };

  return (
    <section className="admin-card" aria-labelledby="active-grants-heading">
      {/* Header */}
      <div className="admin-card-header">
        <div className="admin-card-title-group">
          <h2 id="active-grants-heading">
            <span aria-hidden="true">⏱</span> Active Elevated Grants
          </h2>
          <p className="admin-card-subtitle">
            Time-bound privileged role assignments currently active in the organization
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span className="admin-card-badge" title="Active Grants Count">
            {activeGrants.length} Active
          </span>
          {onOpenGrantModal && isSystemAdmin && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={onOpenGrantModal}
              style={{ fontSize: "12.5px", padding: "6px 12px" }}
            >
              + Grant Access
            </button>
          )}
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => refetch()}
            disabled={isFetching}
            title="Refresh active grants"
            style={{ fontSize: "12.5px", padding: "6px 10px" }}
          >
            {isFetching ? "Refreshing..." : "↻ Refresh"}
          </button>
        </div>
      </div>

      {/* Action Feedback Banner (Success / Error) */}
      {actionFeedback && (
        <div
          className={
            actionFeedback.type === "success"
              ? "modal-alert-success"
              : "modal-alert-error"
          }
          style={{ margin: "16px 20px 0" }}
          role="alert"
        >
          <span aria-hidden="true">
            {actionFeedback.type === "success" ? "✓" : "⚠"}
          </span>
          <div style={{ flex: 1 }}>{actionFeedback.message}</div>
          <button
            type="button"
            onClick={() => setActionFeedback(null)}
            style={{
              background: "none",
              border: "none",
              color: "inherit",
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Confirmation Modal / Banner for Revoke */}
      {confirmRevokeTarget && (
        <div
          className="modal-overlay"
          role="dialog"
          aria-labelledby="confirm-revoke-title"
          aria-modal="true"
        >
          <div className="modal-card" style={{ maxWidth: "460px" }}>
            <div className="modal-header">
              <div>
                <span className="modal-eyebrow">REVOCATION CONFIRMATION</span>
                <h3 className="modal-title" id="confirm-revoke-title">
                  Revoke Elevated Privilege?
                </h3>
              </div>
              <button
                type="button"
                className="modal-close-button"
                onClick={() => setConfirmRevokeTarget(null)}
                aria-label="Cancel revocation"
              >
                ✕
              </button>
            </div>
            <div className="modal-form-body">
              <p style={{ margin: 0, fontSize: "13.5px", lineHeight: "1.5" }}>
                Are you sure you want to immediately revoke the{" "}
                <strong>{confirmRevokeTarget.granted_role}</strong> elevated
                privilege for user{" "}
                <strong>
                  {confirmRevokeTarget.user_email || confirmRevokeTarget.user_id}
                </strong>
                ?
              </p>
              <p
                style={{
                  margin: "8px 0 0",
                  fontSize: "12.5px",
                  color: "#64748b",
                }}
              >
                This action is immediate and will terminate active elevated
                sessions.
              </p>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setConfirmRevokeTarget(null)}
                disabled={revokeMutation.isPending}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-revoke"
                style={{ padding: "8px 16px", fontSize: "13px" }}
                onClick={handleConfirmRevoke}
                disabled={revokeMutation.isPending}
              >
                {revokeMutation.isPending ? "Revoking..." : "Confirm Revoke"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div style={{ padding: "36px 24px", textAlign: "center", color: "#64748b" }}>
          <div className="admin-card-badge" style={{ padding: "6px 14px" }}>
            Loading active elevated grants...
          </div>
        </div>
      )}

      {/* Error State */}
      {isError && (
        <div className="modal-alert-error" style={{ margin: "20px" }}>
          <span aria-hidden="true">⚠</span>
          <div style={{ flex: 1 }}>
            <strong>Failed to load active elevated grants:</strong>{" "}
            {error?.message || "Internal server error"}
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => refetch()}
            style={{ fontSize: "12px", padding: "4px 8px" }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !isError && activeGrants.length === 0 && (
        <div
          style={{
            padding: "48px 24px",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "50%",
              background: "#f1f5f9",
              display: "grid",
              placeItems: "center",
              fontSize: "22px",
            }}
          >
            🛡
          </div>
          <h4 style={{ margin: 0, fontSize: "15px", color: "#334155" }}>
            No active elevated access grants
          </h4>
          <p
            style={{
              margin: 0,
              fontSize: "13px",
              color: "#64748b",
              maxWidth: "400px",
            }}
          >
            All standard roles apply. Click &ldquo;+ Grant Access&rdquo; to
            provision time-bound administrative privileges with automatic
            expiration.
          </p>
        </div>
      )}

      {/* Data Table */}
      {!isLoading && !isError && activeGrants.length > 0 && (
        <div className="admin-table-container">
          <table className="admin-table" aria-label="Active elevated access grants table">
            <thead>
              <tr>
                <th scope="col">User Account</th>
                <th scope="col">Elevated Role</th>
                <th scope="col">Granted Reason</th>
                <th scope="col">Granted At</th>
                <th scope="col">Expires At</th>
                <th scope="col">Time Remaining</th>
                <th scope="col" style={{ textAlign: "right" }}>
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {activeGrants.map((grant) => {
                const countdown = formatCountdown(grant.expires_at, currentTime);
                const pillClass =
                  countdown.status === "active"
                    ? "countdown-pill countdown-active"
                    : countdown.status === "expiring-soon"
                    ? "countdown-pill countdown-expiring-soon"
                    : "countdown-pill countdown-expired";

                return (
                  <tr key={grant.id}>
                    <td>
                      <div style={{ fontWeight: 600, color: "#1e293b" }}>
                        {grant.user_email || "User"}
                      </div>
                      <div
                        style={{
                          fontSize: "11px",
                          color: "#94a3b8",
                          fontFamily: "monospace",
                        }}
                      >
                        {grant.user_id}
                      </div>
                    </td>
                    <td>
                      <span className={getRoleBadgeClass(grant.granted_role)}>
                        {grant.granted_role}
                      </span>
                    </td>
                    <td>
                      <div
                        style={{
                          maxWidth: "260px",
                          fontSize: "12px",
                          color: "#475569",
                          lineHeight: "1.4",
                        }}
                        title={grant.reason}
                      >
                        {grant.reason}
                      </div>
                    </td>
                    <td style={{ fontSize: "12px", color: "#64748b", whiteSpace: "nowrap" }}>
                      {formatTimestamp(grant.granted_at)}
                    </td>
                    <td style={{ fontSize: "12px", color: "#64748b", whiteSpace: "nowrap" }}>
                      {formatTimestamp(grant.expires_at)}
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <span
                        className={pillClass}
                        title={`Expires: ${formatTimestamp(grant.expires_at)}`}
                      >
                        <span className="countdown-dot" aria-hidden="true" />
                        {countdown.text}
                      </span>
                    </td>
                    <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      {!isSystemAdmin ? (
                        <span style={{ fontSize: "12px", color: "#94a3b8" }}>
                          Read-only
                        </span>
                      ) : (
                        <button
                          type="button"
                          className="btn-revoke"
                          onClick={() => setConfirmRevokeTarget(grant)}
                          disabled={
                            revokeMutation.isPending &&
                            confirmRevokeTarget?.id === grant.id
                          }
                          title={`Revoke ${grant.granted_role} privilege for this user`}
                        >
                          Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default ActiveGrantsTable;

