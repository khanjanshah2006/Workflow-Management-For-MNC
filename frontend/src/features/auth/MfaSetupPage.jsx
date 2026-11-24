import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { MFA_STEP_SETUP } from "../../auth/pendingMfa";
import { classifyLoginError, isMfaTokenRejected } from "../../auth/loginFlow";
import { ROUTES } from "../../routes";
import MfaEnrollmentPanel from "./MfaEnrollmentPanel";
import useMfaNavigation from "./useMfaNavigation";
import "./LoginPage.css";

/**
 * Forced MFA enrolment for administrators when ENFORCE_ADMIN_MFA is on (US-31).
 * Uses the mfa_setup token from POST /api/v1/auth/login as the bearer for
 * POST /api/v1/auth/mfa/setup and /mfa/verify. A successful verify returns normal
 * tokens (and sets the refresh cookie), which signs the user in.
 */
export function MfaSetupPage() {
  const { completeSignIn } = useAuth();
  const { pending, backToLogin, timedOut, locked, finish } = useMfaNavigation(MFA_STEP_SETUP);

  if (!pending) {
    return <Navigate to={ROUTES.LOGIN} replace />;
  }

  const handleError = (err) => {
    if (isMfaTokenRejected(err)) {
      timedOut();
      return null;
    }
    const failure = classifyLoginError(err);
    if (failure.type === "locked") {
      locked(failure.message);
      return null;
    }
    return err?.message || "Something went wrong. Please try again.";
  };

  const handleVerified = async (response) => {
    const user = await completeSignIn(response);
    finish(user);
  };

  return (
    <div className="login-page-container">
      <div className="login-card mfa-setup-card">
        <div className="login-header">
          <div className="login-brand-wrapper">W</div>
          <h1>Set Up Two-Factor Authentication</h1>
          <p>
            Administrator accounts must use an authenticator app. Finish this setup to sign in
            {pending.email ? (
              <>
                {" "}as <strong>{pending.email}</strong>
              </>
            ) : null}
            .
          </p>
        </div>

        <MfaEnrollmentPanel
          bearerToken={pending.token}
          email={pending.email}
          onVerified={handleVerified}
          onError={handleError}
        />

        <div className="mfa-footer">
          <button type="button" className="login-link-btn" onClick={() => backToLogin()}>
            ← Cancel and return to sign in
          </button>
        </div>
      </div>
    </div>
  );
}

export default MfaSetupPage;
