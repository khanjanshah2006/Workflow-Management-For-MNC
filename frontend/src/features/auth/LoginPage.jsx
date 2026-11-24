import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { DEMO_USERS } from "../../auth/demoUsers";
import { getHomeRouteForRole } from "../../auth/session";
import {
  classifyLoginError,
  formatThrottleMessage,
  LOCKED_SUBMIT_COOLDOWN_SECONDS,
  SIGN_IN_TIMED_OUT_MESSAGE,
} from "../../auth/loginFlow";
import "./LoginPage.css";

export const LoginPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  const searchParams = new URLSearchParams(location.search);
  const isExpired = searchParams.get("expired") === "1";
  // Set by the MFA screens when they send the user back here
  const isMfaTimedOut = location.state?.notice === "timeout";
  const incomingLockMessage = location.state?.lockMessage || null;

  const [email, setEmail] = useState(() => location.state?.email || "");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [serverError, setServerError] = useState(null);
  const [lockMessage, setLockMessage] = useState(incomingLockMessage);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Submit cool-downs (epoch ms): 30 s after a 423, Retry-After seconds after a 429
  const [now, setNow] = useState(() => Date.now());
  const [lockCooldownUntil, setLockCooldownUntil] = useState(() =>
    incomingLockMessage ? Date.now() + LOCKED_SUBMIT_COOLDOWN_SECONDS * 1000 : 0
  );
  const [throttledUntil, setThrottledUntil] = useState(0);

  const lockSecondsLeft = Math.max(0, Math.ceil((lockCooldownUntil - now) / 1000));
  const throttleSecondsLeft = Math.max(0, Math.ceil((throttledUntil - now) / 1000));
  const isCoolingDown = lockSecondsLeft > 0 || throttleSecondsLeft > 0;

  useEffect(() => {
    if (!isCoolingDown) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [isCoolingDown]);

  // Validate form fields
  const validateForm = () => {
    const errors = {};

    if (!email.trim()) {
      errors.email = "Email address is required.";
    } else {
      const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailPattern.test(email.trim())) {
        errors.email = "Please provide a valid corporate email address.";
      }
    }

    if (!password) {
      errors.password = "Password is required.";
    } else if (password.length < 6) {
      errors.password = "Password must be at least 6 characters.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isCoolingDown) return;
    setServerError(null);

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    try {
      // Submitting credentials calls POST /api/v1/auth/login and queries GET /api/v1/auth/me
      const result = await login({
        email: email.trim(),
        password,
      });

      const requestedFrom = location.state?.from?.pathname;

      if (result.type !== "authenticated") {
        // MFA challenge or forced enrolment: the mfa_token is held in memory by AuthContext
        navigate(result.route, {
          replace: true,
          state: requestedFrom ? { from: location.state.from } : undefined,
        });
        return;
      }

      setLockMessage(null);
      const targetPath =
        requestedFrom && requestedFrom !== "/login"
          ? requestedFrom
          : getHomeRouteForRole(result.user);

      navigate(targetPath, { replace: true });
    } catch (err) {
      const failure = classifyLoginError(err);
      const at = Date.now();
      setNow(at);
      if (failure.type === "locked") {
        setLockMessage(failure.message);
        setLockCooldownUntil(at + failure.cooldownSeconds * 1000);
      } else if (failure.type === "throttled") {
        setLockMessage(null);
        setThrottledUntil(at + failure.retryAfterSeconds * 1000);
      } else {
        setLockMessage(null);
        setServerError(failure.message);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickDemoFill = (demoEmail) => {
    const demo = DEMO_USERS[demoEmail];
    if (demo) {
      setEmail(demo.email);
      setPassword("");
      setFieldErrors({});
      setServerError(null);
    }
  };

  const noticeMessage = isMfaTimedOut
    ? SIGN_IN_TIMED_OUT_MESSAGE
    : isExpired
    ? "Your session expired. Please sign in again."
    : null;

  let submitLabel = "Sign In";
  if (isSubmitting) submitLabel = "Authenticating...";
  else if (throttleSecondsLeft > 0) submitLabel = `Try again in ${throttleSecondsLeft}s`;
  else if (lockSecondsLeft > 0) submitLabel = `Sign In (${lockSecondsLeft}s)`;

  return (
    <div className="login-page-container">
      <div className="login-card">
        <div className="login-header">
          <div className="login-brand-wrapper">W</div>
          <h1>Sign In to WorkSphere</h1>
          <p>Workflow Management System for MNCs</p>
        </div>

        {noticeMessage && !serverError && !lockMessage && throttleSecondsLeft === 0 && (
          <div className="login-error-banner" role="alert">
            <span>⚠</span>
            <span>{noticeMessage}</span>
          </div>
        )}

        {lockMessage && (
          <div className="login-error-banner login-lock-banner" role="alert" data-testid="login-lock-banner">
            <span aria-hidden="true">🔒</span>
            <span>{lockMessage}</span>
          </div>
        )}

        {throttleSecondsLeft > 0 && (
          <div className="login-error-banner" role="alert" aria-live="polite" data-testid="login-throttle-banner">
            <span aria-hidden="true">⏱</span>
            <span>{formatThrottleMessage(throttleSecondsLeft)}</span>
          </div>
        )}

        {serverError && (
          <div className="login-error-banner" role="alert">
            <span>⚠</span>
            <span>{serverError}</span>
          </div>
        )}

        <form className="login-form" onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="email">
              Corporate Email
            </label>
            <input
              id="email"
              type="email"
              className={`form-input ${fieldErrors.email ? "form-input-error" : ""}`}
              placeholder="e.g. employee@worksphere.com"
              value={email}
              autoComplete="email"
              onChange={(e) => {
                setEmail(e.target.value);
                if (fieldErrors.email) {
                  setFieldErrors((prev) => ({ ...prev, email: undefined }));
                }
              }}
            />
            {fieldErrors.email && (
              <span className="field-error">{fieldErrors.email}</span>
            )}
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              className={`form-input ${fieldErrors.password ? "form-input-error" : ""}`}
              placeholder="••••••••••••"
              value={password}
              autoComplete="current-password"
              onChange={(e) => {
                setPassword(e.target.value);
                if (fieldErrors.password) {
                  setFieldErrors((prev) => ({ ...prev, password: undefined }));
                }
              }}
            />
            {fieldErrors.password && (
              <span className="field-error">{fieldErrors.password}</span>
            )}
          </div>

          <button
            type="submit"
            className="login-submit-btn"
            disabled={isSubmitting || isCoolingDown}
          >
            {submitLabel}
          </button>
        </form>

        {import.meta.env.DEV && (
          <div className="demo-credentials-section">
            <div className="demo-title">Quick Demo Switcher (Testing / RBAC)</div>
            <div className="demo-buttons-grid">
              {Object.entries(DEMO_USERS).map(([demoEmail, user]) => (
                <button
                  key={demoEmail}
                  type="button"
                  className="demo-btn"
                  onClick={() => handleQuickDemoFill(demoEmail)}
                >
                  <span className="demo-btn-role">{user.role}</span>
                  <span className="demo-btn-email">{user.email}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LoginPage;
