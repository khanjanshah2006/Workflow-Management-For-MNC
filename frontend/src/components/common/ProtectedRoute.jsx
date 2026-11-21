import React from "react";
import { Navigate, useLocation, Outlet } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { normalizeRole } from "../../auth/session";

/**
 * Route protection wrapper.
 * - Redirects unauthenticated requests to /login, saving current path in location state.
 * - Validates permitted roles if allowedRoles is provided.
 */
export const ProtectedRoute = ({ children, allowedRoles = [] }) => {
  const { isAuthenticated, role, user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: "60vh" }}>
        <div style={{ textAlign: "center" }}>
          <div className="placeholder-symbol" style={{ fontSize: "2rem" }}>✳</div>
          <p style={{ marginTop: "12px", color: "#64748b", fontSize: "14px", fontWeight: "500" }}>
            Verifying authentication...
          </p>
        </div>
      </div>
    );
  }

  // Acceptance Criteria: Redirect to /login if unauthenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Acceptance Criteria: Check permitted roles
  if (allowedRoles && allowedRoles.length > 0) {
    const currentNorm = normalizeRole(role || user?.user_type || user?.role || "");
    const isAuthorized = allowedRoles.some((allowed) => {
      const allowedNorm = normalizeRole(allowed);
      if (
        (allowedNorm === "PM" || allowedNorm === "PROJECT_MANAGER") &&
        (currentNorm === "PM" || currentNorm === "PROJECT_MANAGER")
      ) {
        return true;
      }
      return allowedNorm === currentNorm;
    });

    if (!isAuthorized) {
      return (
        <section className="page">
          <div className="page-eyebrow">ACCESS CONTROL</div>
          <h1>403 — Unauthorized Access</h1>
          <p className="page-description">
            Your current assigned role ({role || "User"}) does not have permissions to access this view.
          </p>
          <div className="placeholder-panel">
            <div className="placeholder-symbol">🔒</div>
            <h2>Restricted View</h2>
            <p>Please contact your System Administrator to request elevated authorization.</p>
          </div>
        </section>
      );
    }
  }

  return children ? children : <Outlet />;
};

export default ProtectedRoute;
