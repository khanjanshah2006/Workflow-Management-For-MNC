import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi } from "../../api/authApi";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../components/common/Toast";
import { isAdminMfaEnforced, isMfaRequiredForRole } from "../../auth/mfaPolicy";
import MfaEnrollmentPanel from "../auth/MfaEnrollmentPanel";
import "./AccountSecurityPage.css";

const MFA_STATUS_QUERY_KEY = ["auth", "mfa-status"];

/**
 * Account Security (/account/security), available to every signed-in role (US-31).
 * Shows MFA status from GET /api/v1/auth/mfa/status and lets the user enrol voluntarily
 * with the same setup / verify flow used for forced admin enrolment.
 */
export function AccountSecurityPage() {
  const { user, role } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [isEnrolling, setIsEnrolling] = useState(false);

  const requiredForAdmins = isMfaRequiredForRole(role, isAdminMfaEnforced());

  const {
    data: status,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: MFA_STATUS_QUERY_KEY,
    queryFn: authApi.getMfaStatus,
    staleTime: 30 * 1000,
  });

  const isEnabled = Boolean(status?.is_mfa_enabled);

  const handleVerified = async () => {
    setIsEnrolling(false);
    toast.success("Two-factor authentication is now on for your account.");
    await queryClient.invalidateQueries({ queryKey: MFA_STATUS_QUERY_KEY });
  };

  return (
    <section className="page account-security-page" aria-labelledby="account-security-heading">
      <div className="page-eyebrow">ACCOUNT</div>
      <h1 id="account-security-heading">Account Security</h1>
      <p className="page-description">
        Protect your sign-in with a code from an authenticator app.
      </p>

      <div className="account-security-card">
        <div className="account-security-card-header">
          <div>
            <h2>Two-factor authentication (MFA)</h2>
            <p>
              After your password, you will be asked for a 6-digit code from your authenticator app.
            </p>
          </div>
          {!isLoading && !isError && (
            <span
              className={`account-mfa-badge ${isEnabled ? "account-mfa-badge-on" : "account-mfa-badge-off"}`}
              data-testid="mfa-status-badge"
            >
              {isEnabled ? "✓ Enabled" : "Not enabled"}
            </span>
          )}
        </div>

        {requiredForAdmins && (
          <div className="account-mfa-required" role="note">
            <strong>Required for administrators.</strong>{" "}
            {isEnabled
              ? "Your administrator account is protected by MFA."
              : "You will be asked to set up MFA the next time you sign in."}
          </div>
        )}

        {isLoading && <p className="account-security-muted">Checking MFA status...</p>}

        {isError && (
          <div className="account-security-error" role="alert">
            <span>Could not load MFA status: {error?.message || "Unknown error"}</span>
            <button type="button" className="btn btn-secondary" onClick={() => refetch()}>
              Retry
            </button>
          </div>
        )}

        {!isLoading && !isError && isEnabled && (
          <p className="account-security-muted">
            MFA is on for <strong>{status?.email || user?.email}</strong>. Keep your authenticator
            app available: every sign-in asks for a code.
          </p>
        )}

        {!isLoading && !isError && !isEnabled && !isEnrolling && (
          <button type="button" className="btn btn-primary" onClick={() => setIsEnrolling(true)}>
            Enable MFA
          </button>
        )}

        {!isLoading && !isError && !isEnabled && isEnrolling && (
          <div className="account-security-enroll">
            <MfaEnrollmentPanel email={status?.email || user?.email || ""} onVerified={handleVerified} />
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setIsEnrolling(false)}
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </section>
  );
}

export default AccountSecurityPage;
