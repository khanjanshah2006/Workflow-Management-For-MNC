import { useState, useEffect } from "react";
import { getStoredToken } from "../api/client";

/**
 * Safely parses JWT payload without external libraries.
 * @param {string} token
 * @returns {Object|null}
 */
export function parseJwt(token) {
  if (!token || typeof token !== "string") return null;
  try {
    const parts = token.split(".");
    if (parts.length < 2) return null;
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(jsonPayload);
  } catch {
    try {
      return JSON.parse(atob(token.split(".")[1]));
    } catch {
      return null;
    }
  }
}

/**
 * Retrieves the current authenticated user context from stored token or localStorage.
 * @returns {Object|null}
 */
export function getCurrentUser() {
  // Support window override in test/dev environment
  if (typeof window !== "undefined" && window.__wmsUser) {
    return window.__wmsUser;
  }

  if (typeof localStorage !== "undefined") {
    try {
      const stored = localStorage.getItem("wms_user");
      if (stored) {
        return JSON.parse(stored);
      }
    } catch {}
  }

  const token = getStoredToken();
  if (token) {
    const payload = parseJwt(token);
    if (payload) {
      const rawRole = payload.user_type || payload.role || "";
      return {
        account_id: payload.sub || "",
        email: payload.email || "",
        user_type: rawRole,
        role: rawRole,
      };
    }
  }

  return null;
}

/**
 * Role normalization and permission checks.
 */
export function normalizeRole(role) {
  if (!role || typeof role !== "string") return "";
  return role.trim().toUpperCase().replace(/[\s-]+/g, "_");
}

export function isProjectManager(user) {
  const role = normalizeRole(user?.role || user?.user_type || user);
  return role === "PM" || role === "PROJECT_MANAGER";
}

export function isAdmin(user) {
  const role = normalizeRole(user?.role || user?.user_type || user);
  return role === "ADMIN" || role === "SYSTEM_ADMIN";
}

export function canManageProject(user) {
  return isProjectManager(user) || isAdmin(user);
}

/**
 * Custom React hook for accessing current authenticated session and RBAC flags.
 */
export function useAuth() {
  const [user, setUser] = useState(() => getCurrentUser());
  const token = getStoredToken();

  useEffect(() => {
    const handleStorage = () => {
      setUser(getCurrentUser());
    };

    window.addEventListener("storage", handleStorage);
    window.addEventListener("wms-auth-change", handleStorage);

    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("wms-auth-change", handleStorage);
    };
  }, []);

  const pm = isProjectManager(user);
  const admin = isAdmin(user);

  return {
    user,
    token,
    isAuthenticated: Boolean(token || user),
    isPM: pm,
    isAdmin: admin,
    canManageProject: pm || admin,
  };
}

export default useAuth;

