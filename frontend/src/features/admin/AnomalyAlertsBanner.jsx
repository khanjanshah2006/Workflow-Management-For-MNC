import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "../../api/adminApi";
import { useToast } from "../../components/common/Toast";
import { ACCOUNT_LOCKED_ALERT, formatLockedUntil } from "./lockState";
import useUnlockAccount from "./useUnlockAccount";
import "./admin.css";

/**
 * Icon and badge label per backend alert_type. Unknown types fall back to the severity styling.
 */
const ALERT_TYPE_META = {
  ACCOUNT_LOCKED: { icon: "🔒", label: "ACCOUNT LOCKED" },
  FAILED_LOGIN_BURST: { icon: "🚨", label: "FAILED LOGIN SPIKE", critical: true },
  SUSPICIOUS_FAILED_LOGINS: { icon: "🚨", label: "FAILED LOGIN SPIKE", critical: true },
  PRIVILEGE_ESCALATION: { icon: "⬆️", label: "PRIVILEGE ESCALATION" },
  BACKUP_FAILURE: { icon: "💾", label: "BACKUP FAILURE" },
};

/**
 * Format timestamp to readable string.
 */
function formatAlertTime(isoStr) {
  if (!isoStr) return "Just now";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return String(isoStr);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(isoStr);
  }
}

/**
 * AnomalyAlertsBanner Component (US-49 / Issue #81)
 *
 * Displays high-severity real-time security anomaly alerts,
 * specifically highlighting suspicious / repeated failed-login spikes.
 */
export function AnomalyAlertsBanner() {
  const [dismissedAlertIds, setDismissedAlertIds] = useState(() => new Set());
  const toast = useToast();
  const unlockMutation = useUnlockAccount((type, message) =>
    type === "success" ? toast.success(message) : toast.error(message)
  );

  // Polling query every 30 seconds for real-time security alerts
  const {
    data: alerts = [],
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["admin", "anomaly-alerts"],
    queryFn: adminApi.getAnomalyAlerts,
    refetchInterval: 30000,
    staleTime: 10000,
  });

  const activeAlerts = useMemo(() => {
    if (!Array.isArray(alerts)) return [];
    return alerts.filter(
      (a) => a.status !== "RESOLVED" && !dismissedAlertIds.has(a.id)
    );
  }, [alerts, dismissedAlertIds]);

  const handleDismiss = (alertId) => {
    setDismissedAlertIds((prev) => {
      const next = new Set(prev);
      next.add(alertId);
      return next;
    });
  };

  // If loading and no cache
  if (isLoading) {
    return (
      <div
        className="admin-card-badge"
        style={{ padding: "8px 16px", alignSelf: "flex-start" }}
      >
        <span>Checking security telemetry...</span>
      </div>
    );
  }

  // Graceful error state (does not crash parent console)
  if (isError) {
    return (
      <div
        className="anomaly-alert-card anomaly-alert-high"
        role="alert"
        style={{ marginBottom: "8px" }}
      >
        <div className="anomaly-alert-content">
          <span className="anomaly-alert-icon" aria-hidden="true">
            ⚠
          </span>
          <div className="anomaly-alert-body">
            <h4 className="anomaly-alert-title">
              Telemetry Ingestion Warning
            </h4>
            <p className="anomaly-alert-description">
              Could not retrieve real-time anomaly alerts (
              {error?.message || "Endpoint offline"}). Ensure the security
              telemetry pipeline is running.
            </p>
          </div>
        </div>
        <div className="anomaly-alert-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => refetch()}
            disabled={isFetching}
            style={{ fontSize: "12px", padding: "4px 8px" }}
          >
            {isFetching ? "Retrying..." : "Retry"}
          </button>
        </div>
      </div>
    );
  }

  // Empty state: All signals normal
  if (activeAlerts.length === 0) {
    return (
      <div
        className="anomaly-empty-banner"
        role="status"
        aria-label="Security status normal"
      >
        <div className="anomaly-empty-icon" aria-hidden="true">
          🛡
        </div>
        <div>
          <div className="anomaly-empty-text">
            All Security Signals Normal
          </div>
          <div className="anomaly-empty-subtext">
            No active intrusion anomalies or suspicious authentication spikes
            detected across system endpoints in the last 24 hours.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="anomaly-alerts-section"
      role="region"
      aria-label="Security anomaly alerts"
    >
      {activeAlerts.map((alert) => {
        const typeMeta = ALERT_TYPE_META[alert.alert_type] || null;
        const isFailedLoginSpike =
          Boolean(typeMeta?.critical) ||
          (alert.title &&
            alert.title.toLowerCase().includes("failed-login"));
        const isCritical =
          alert.severity === "CRITICAL" || isFailedLoginSpike;
        const isAccountLocked = alert.alert_type === ACCOUNT_LOCKED_ALERT;
        const lockedAccountId = alert.account_id || alert.target_account_id;
        const isUnlocking =
          unlockMutation.isPending &&
          unlockMutation.variables?.accountId === lockedAccountId;

        const cardClass = isCritical
          ? "anomaly-alert-card anomaly-alert-critical"
          : "anomaly-alert-card anomaly-alert-high";

        const badgeClass = isCritical
          ? "anomaly-severity-badge anomaly-severity-critical"
          : "anomaly-severity-badge anomaly-severity-high";

        return (
          <div
            key={alert.id}
            className={cardClass}
            role="alert"
            data-testid={`anomaly-alert-${alert.id}`}
          >
            <div className="anomaly-alert-content">
              <span className="anomaly-alert-icon" aria-hidden="true">
                {typeMeta?.icon || (isCritical ? "🚨" : "⚠️")}
              </span>
              <div className="anomaly-alert-body">
                <div className="anomaly-alert-title-row">
                  <h3 className="anomaly-alert-title">{alert.title}</h3>
                  <span className={badgeClass}>
                    {alert.severity || "HIGH"}
                  </span>
                  {(typeMeta || isFailedLoginSpike) && (
                    <span
                      className="anomaly-severity-badge"
                      style={{
                        background: isFailedLoginSpike ? "#7f1d1d" : "#334155",
                        color: isFailedLoginSpike ? "#fee2e2" : "#f1f5f9",
                      }}
                    >
                      {typeMeta?.label || "FAILED LOGIN SPIKE"}
                    </span>
                  )}
                </div>

                <p className="anomaly-alert-description">
                  {alert.description}
                </p>

                {/* Metadata Row: Source IP, Target Account, Attempts, Timestamp */}
                <div className="anomaly-alert-meta">
                  {alert.source_ip && (
                    <div className="anomaly-meta-item">
                      <span className="anomaly-meta-label">Source IP:</span>
                      <span className="anomaly-meta-val">
                        {alert.source_ip}
                      </span>
                    </div>
                  )}

                  {alert.target_account && (
                    <div className="anomaly-meta-item">
                      <span className="anomaly-meta-label">Target Account:</span>
                      <span className="anomaly-meta-val">
                        {alert.target_account}
                      </span>
                    </div>
                  )}

                  {alert.attempts_count !== undefined && (
                    <div className="anomaly-meta-item">
                      <span className="anomaly-meta-label">
                        Failed Attempts:
                      </span>
                      <span
                        className="anomaly-meta-val"
                        style={{ color: isCritical ? "#b91c1c" : "inherit" }}
                      >
                        {alert.attempts_count}
                      </span>
                    </div>
                  )}

                  {isAccountLocked && alert.last_timestamp && (
                    <div className="anomaly-meta-item">
                      <span className="anomaly-meta-label">Locked Until:</span>
                      <span className="anomaly-meta-val">
                        {formatLockedUntil(alert.last_timestamp)}
                      </span>
                    </div>
                  )}

                  <div className="anomaly-meta-item">
                    <span className="anomaly-meta-label">Detected:</span>
                    <span>{formatAlertTime(alert.timestamp)}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="anomaly-alert-actions">
              {isAccountLocked && lockedAccountId && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() =>
                    unlockMutation.mutate({
                      accountId: lockedAccountId,
                      email: alert.attempted_email || alert.target_account,
                    })
                  }
                  disabled={isUnlocking}
                  style={{ fontSize: "11.5px", padding: "4px 9px" }}
                  title="Clear the failed sign-in lock on this account"
                >
                  {isUnlocking ? "Unlocking..." : "Unlock"}
                </button>
              )}
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => handleDismiss(alert.id)}
                style={{
                  fontSize: "11.5px",
                  padding: "4px 9px",
                  borderColor: isCritical ? "#fca5a5" : "#fcd34d",
                  background: "#ffffff",
                }}
                title="Acknowledge and dismiss alert"
              >
                Dismiss
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default AnomalyAlertsBanner;

