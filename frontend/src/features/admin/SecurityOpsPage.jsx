import { useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth, normalizeRole } from "../../hooks/useAuth";
import AnomalyAlertsBanner from "./AnomalyAlertsBanner";
import SystemParamsTable from "./SystemParamsTable";
import ActiveGrantsTable from "./ActiveGrantsTable";
import ElevatedAccessModal from "./ElevatedAccessModal";
import "./admin.css";

/**
 * SecurityOpsPage Component (GitHub Issue #81 / S9-FE-1)
 *
 * Scenarios: S9 — Security Operations
 * User Stories:
 *  - US-45: Time-Bound Elevated Access
 *  - US-46: Operational System Parameters
 *  - US-49: Real-Time Security Anomaly Alerts
 *
 * RBAC: Strictly protected — Only accessible to SYSTEM_ADMIN role.
 * (ADMIN, PM, HR, EMPLOYEE, CLIENT and other roles are strictly denied).
 */
export function SecurityOpsPage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [isGrantModalOpen, setIsGrantModalOpen] = useState(false);

  // Strict RBAC enforcement: ONLY SYSTEM_ADMIN is authorized
  const currentRole = normalizeRole(user?.role || user?.user_type);
  const isSystemAdmin = currentRole === "SYSTEM_ADMIN";

  // RBAC Gate: Non-SYSTEM_ADMIN users are strictly denied access
  if (!isSystemAdmin) {
    return (
      <section className="page security-ops-page" aria-labelledby="rbac-denied-heading">
        <div className="security-ops-container">
          <div
            className="admin-card"
            style={{
              padding: "56px 32px",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "16px",
            }}
          >
            <div
              style={{
                width: "64px",
                height: "64px",
                borderRadius: "50%",
                background: "#fef2f2",
                color: "#dc2626",
                display: "grid",
                placeItems: "center",
                fontSize: "30px",
              }}
            >
              🔒
            </div>

            <div style={{ maxWidth: "520px" }}>
              <span className="modal-eyebrow" style={{ color: "#dc2626" }}>
                RBAC PROTECTED · SYSTEM ADMINISTRATORS ONLY
              </span>
              <h1
                id="rbac-denied-heading"
                style={{
                  fontSize: "22px",
                  fontWeight: 750,
                  color: "#0f172a",
                  margin: "8px 0 10px",
                }}
              >
                Access Restricted
              </h1>
              <p style={{ fontSize: "14px", color: "#64748b", lineHeight: "1.55", margin: 0 }}>
                The Security Operations Admin Console is strictly reserved for users with the{" "}
                <strong>SYSTEM_ADMIN</strong> role. Standard <strong>ADMIN</strong>, <strong>PM</strong>, or other roles
                do not possess the required privilege level. Current account:{" "}
                <code>{user?.email || "Unauthenticated User"}</code> &bull; Role:{" "}
                <code>{currentRole || "None"}</code>.
              </p>
            </div>

            <div style={{ marginTop: "8px" }}>
              <Link to="/dashboard" className="btn btn-primary">
                ← Return to Dashboard
              </Link>
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="page security-ops-page" aria-labelledby="security-ops-heading">
      <div className="security-ops-container">
        {/* Top Header Row */}
        <header className="security-header-row">
          <div className="security-header-info">
            <span className="page-eyebrow">SYSTEM ADMINISTRATION &bull; S9</span>
            <h1 id="security-ops-heading">Security Operations Console</h1>
            <p className="page-description">
              Configure global operational parameters, grant time-bound elevated roles with automated expiry,
              and monitor real-time intrusion anomaly telemetry.
            </p>
          </div>

          <div className="security-header-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setIsGrantModalOpen(true)}
              style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
            >
              <span aria-hidden="true">⚡</span> Grant Elevated Access
            </button>
          </div>
        </header>

        {/* 1. Real-Time Security Anomaly Alerts Banner (US-49) */}
        <AnomalyAlertsBanner />

        {/* 2. Active Elevated Access Grants with Countdown Timers (US-45) */}
        <ActiveGrantsTable onOpenGrantModal={() => setIsGrantModalOpen(true)} />

        {/* 3. Global System Parameters Configuration (US-46) */}
        <SystemParamsTable />

        {/* Elevated Access Granting Modal */}
        <ElevatedAccessModal
          isOpen={isGrantModalOpen}
          onClose={() => setIsGrantModalOpen(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({
              queryKey: ["admin", "elevated-access", "active"],
            });
          }}
        />
      </div>
    </section>
  );
}

export default SecurityOpsPage;
