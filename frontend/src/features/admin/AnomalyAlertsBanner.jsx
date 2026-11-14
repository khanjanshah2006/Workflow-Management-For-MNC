import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "../../api/adminApi";
import "./admin.css";

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
        const isFailedLoginSpike =
          alert.alert_type === "SUSPICIOUS_FAILED_LOGINS" ||
          (alert.title &&
            alert.title.toLowerCase().includes("failed-login"));
        const isCritical =
          alert.severity === "CRITICAL" || isFailedLoginSpike;

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
                {isCritical ? "🚨" : "⚠️"}
              </span>
              <div className="anomaly-alert-body">
                <div className="anomaly-alert-title-row">
                  <h3 className="anomaly-alert-title">{alert.title}</h3>
                  <span className={badgeClass}>
                    {alert.severity || "HIGH"}
                  </span>
                  {isFailedLoginSpike && (
                    <span
                      className="anomaly-severity-badge"
                      style={{
                        background: "#7f1d1d",
                        color: "#fee2e2",
                      }}
                    >
                      FAILED LOGIN SPIKE
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

                  <div className="anomaly-meta-item">
                    <span className="anomaly-meta-label">Detected:</span>
                    <span>{formatAlertTime(alert.timestamp)}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="anomaly-alert-actions">
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

