import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { DEMO_USERS } from "../../auth/demoUsers";
import { getHomeRouteForRole } from "../../auth/session";
import "./LoginPage.css";

export const LoginPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  const searchParams = new URLSearchParams(location.search);
  const isExpired = searchParams.get("expired") === "1";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [serverError, setServerError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

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
    setServerError(null);

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    try {
      // Submitting credentials calls POST /api/v1/auth/login and queries GET /api/v1/auth/me
      const authenticatedUser = await login({
        email: email.trim(),
        password,
      });

      const requestedFrom = location.state?.from?.pathname;
      const targetPath =
        requestedFrom && requestedFrom !== "/login"
          ? requestedFrom
          : getHomeRouteForRole(authenticatedUser);

      navigate(targetPath, { replace: true });
    } catch (err) {
      setServerError(
        err?.message || "Invalid credentials. Please verify your email and password."
      );
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

  return (
    <div className="login-page-container">
      <div className="login-card">
        <div className="login-header">
          <div className="login-brand-wrapper">W</div>
          <h1>Sign In to WorkSphere</h1>
          <p>Workflow Management System for MNCs</p>
        </div>

        {isExpired && !serverError && (
          <div className="login-error-banner" role="alert">
            <span>⚠</span>
            <span>Your session expired. Please sign in again.</span>
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
            disabled={isSubmitting}
          >
            {isSubmitting ? "Authenticating..." : "Sign In"}
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
