import React, { useEffect, useRef, useState } from "react";
import { Navigate } from "react-router-dom";
import { authApi } from "../../api/authApi";
import { useAuth } from "../../context/AuthContext";
import { MFA_STEP_CHALLENGE } from "../../auth/pendingMfa";
import {
  classifyLoginError,
  formatThrottleMessage,
  isMfaTokenRejected,
} from "../../auth/loginFlow";
import { ROUTES } from "../../routes";
import OtpCodeInput, { OTP_LENGTH } from "./OtpCodeInput";
import useMfaNavigation from "./useMfaNavigation";
import "./LoginPage.css";

export const INCORRECT_CODE_MESSAGE = "Incorrect code";

/**
 * Second sign-in step for accounts with MFA enabled (US-31).
 * POST /api/v1/auth/mfa/login with { mfa_token, code }; the code is submitted
 * automatically once all 6 digits are entered.
 */
export function MfaChallengePage() {
  const { completeSignIn } = useAuth();
  const { pending, backToLogin, timedOut, locked, finish } = useMfaNavigation(MFA_STEP_CHALLENGE);

  const [code, setCode] = useState("");
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [throttledUntil, setThrottledUntil] = useState(0);
  const inputRef = useRef(null);

  const throttleSecondsLeft = Math.max(0, Math.ceil((throttledUntil - now) / 1000));

  useEffect(() => {
    if (throttleSecondsLeft <= 0) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [throttleSecondsLeft]);

  if (!pending) {
    return <Navigate to={ROUTES.LOGIN} replace />;
  }

  const submitCode = async (value) => {
    if (isSubmitting || throttleSecondsLeft > 0 || value.length !== OTP_LENGTH) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const tokens = await authApi.mfaLogin(pending.token, value);
      const user = await completeSignIn(tokens);
      finish(user);
    } catch (err) {
      if (isMfaTokenRejected(err)) {
        timedOut();
        return;
      }
      const failure = classifyLoginError(err);
      if (failure.type === "locked") {
        locked(failure.message);
        return;
      }
      if (failure.type === "throttled") {
        const at = Date.now();
        setNow(at);
        setThrottledUntil(at + failure.retryAfterSeconds * 1000);
      } else if (failure.type === "invalid") {
        // Wrong codes count toward the account lockout on the backend
        setError(INCORRECT_CODE_MESSAGE);
      } else {
        setError(failure.message);
      }
      setCode("");
      inputRef.current?.focus();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="login-page-container">
      <div className="login-card">
        <div className="login-header">
          <div className="login-brand-wrapper">W</div>
          <h1>Two-Factor Verification</h1>
          <p>
            Enter the 6-digit code from your authenticator app
            {pending.email ? (
              <>
                {" "}for <strong>{pending.email}</strong>
              </>
            ) : null}
            .
          </p>
        </div>

        {throttleSecondsLeft > 0 && (
          <div className="login-error-banner" role="alert" aria-live="polite">
            <span aria-hidden="true">⏱</span>
            <span>{formatThrottleMessage(throttleSecondsLeft)}</span>
          </div>
        )}

        <form
          className="login-form"
          onSubmit={(e) => {
            e.preventDefault();
            submitCode(code);
          }}
          noValidate
        >
          <div className="form-group">
            <label className="form-label" htmlFor="mfa-code">
              Authentication code
            </label>
            <OtpCodeInput
              id="mfa-code"
              inputRef={inputRef}
              value={code}
              onChange={(value) => {
                setCode(value);
                if (error) setError(null);
              }}
              onComplete={submitCode}
              disabled={isSubmitting || throttleSecondsLeft > 0}
              hasError={Boolean(error)}
            />
            {error && (
              <span className="field-error" role="alert">
                {error}
              </span>
            )}
          </div>

          <button
            type="submit"
            className="login-submit-btn"
            disabled={isSubmitting || throttleSecondsLeft > 0 || code.length !== OTP_LENGTH}
          >
            {isSubmitting ? "Verifying..." : "Verify"}
          </button>
        </form>

        <div className="mfa-footer">
          <button type="button" className="login-link-btn" onClick={() => backToLogin()}>
            ← Use a different account
          </button>
        </div>
      </div>
    </div>
  );
}

export default MfaChallengePage;
