/**
 * In-memory session adapter for WorkSphere frontend.
 *
 * Requirements:
 * - Integrates with shared apiClient (client.js) token handling.
 * - Stores access token and user information in module memory and synchronizes with wms_access_token.
 * - Exposes setSession(tokenResponse), getSession(), clearSession().
 * - getSession() returns a stable, immutable snapshot between updates for useSyncExternalStore.
 * - Snapshots change on setSession() and clearSession().
 * - Avoids exposing mutable internal session data via Object.freeze.
 * - Exposes window.__wmsSession in development mode only (import.meta.env.DEV).
 */

import { useSyncExternalStore } from "react";
import { getStoredToken, setStoredToken, setTokenGetter } from "../api/client";

// In-memory stable snapshot reference
function getInitialSnapshot() {
  const token = getStoredToken();
  if (!token) return null;
  return createSnapshot({ access_token: token, user: null });
}

let currentSnapshot = getInitialSnapshot();
const listeners = new Set();

// Register session's access token getter with shared apiClient
setTokenGetter(() => currentSnapshot?.access_token || getStoredToken());

function emitChange() {
  for (const listener of listeners) {
    listener();
  }
}

/**
 * Creates an immutable snapshot from the given token response.
 * @param {Object} tokenResponse
 * @returns {Readonly<Object>|null}
 */
function createSnapshot(tokenResponse) {
  if (!tokenResponse) {
    return null;
  }

  const user = tokenResponse.user
    ? Object.freeze({
        account_id: tokenResponse.user.account_id || "",
        email: tokenResponse.user.email || "",
        user_type: tokenResponse.user.user_type || "",
        role: tokenResponse.user.role || tokenResponse.user.user_type || "",
        is_active: Boolean(tokenResponse.user.is_active),
      })
    : null;

  return Object.freeze({
    access_token: tokenResponse.access_token || "",
    refresh_token: tokenResponse.refresh_token || "",
    token_type: tokenResponse.token_type || "bearer",
    expires_in: tokenResponse.expires_in ?? 1800,
    user,
  });
}

/**
 * Sets the active in-memory session, syncs with shared token store, and notifies listeners.
 * @param {Object} tokenResponse Expected shape from POST /api/v1/auth/login:
 * {
 *   access_token: string,
 *   refresh_token: string,
 *   token_type: string,
 *   expires_in: number,
 *   user: {
 *     account_id: string,
 *     email: string,
 *     user_type: "EMPLOYEE" | "PM" | "ADMIN" | "HR" | "CLIENT",
 *     is_active: boolean
 *   }
 * }
 */
export function setSession(tokenResponse) {
  currentSnapshot = createSnapshot(tokenResponse);
  if (tokenResponse?.access_token) {
    setStoredToken(tokenResponse.access_token);
  } else {
    setStoredToken("");
  }
  emitChange();
}

/**
 * Returns a stable immutable snapshot of the active session, or null if unauthenticated.
 * Guarantees referential stability between updates for useSyncExternalStore.
 * @returns {Readonly<Object>|null}
 */
export function getSession() {
  return currentSnapshot;
}

/**
 * Clears the active in-memory session, clears shared token store, and notifies listeners.
 */
export function clearSession() {
  currentSnapshot = null;
  setStoredToken("");
  emitChange();
}

/**
 * Subscribes a listener callback to session changes.
 * @param {() => void} listener
 * @returns {() => void} unsubscribe function
 */
export function subscribeSession(listener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * React hook to access the current session reactively via useSyncExternalStore.
 */
export function useSession() {
  return useSyncExternalStore(subscribeSession, getSession, () => null);
}

/**
 * Normalizes role string for consistent comparison.
 * Converts to uppercase and replaces spaces and hyphens with underscores.
 * E.g. "Project Manager" -> "PROJECT_MANAGER", "PM" -> "PM", "Admin" -> "ADMIN".
 * @param {string} role
 * @returns {string}
 */
export function normalizeRole(role) {
  if (!role || typeof role !== "string") return "";
  return role.trim().toUpperCase().replace(/[\s-]+/g, "_");
}

/**
 * Extracts normalized role/user_type from a user object or string.
 * @param {Object|string} user
 * @returns {string}
 */
export function getUserRole(user) {
  if (!user) return "";
  if (typeof user === "string") return normalizeRole(user);
  const rawRole = user.user_type || user.role || "";
  return normalizeRole(rawRole);
}

/**
 * Checks if the role represents a Project Manager ("PM" or "PROJECT_MANAGER").
 * @param {Object|string} roleOrUser
 * @returns {boolean}
 */
export function isProjectManager(roleOrUser) {
  const norm = typeof roleOrUser === "string" ? normalizeRole(roleOrUser) : getUserRole(roleOrUser);
  return norm === "PM" || norm === "PROJECT_MANAGER";
}

/**
 * Checks if the role represents a System Admin ("ADMIN" or "SYSTEM_ADMIN").
 * @param {Object|string} roleOrUser
 * @returns {boolean}
 */
export function isAdmin(roleOrUser) {
  const norm = typeof roleOrUser === "string" ? normalizeRole(roleOrUser) : getUserRole(roleOrUser);
  return norm === "ADMIN" || norm === "SYSTEM_ADMIN";
}

/**
 * Checks if the role is authorized to create projects (PM or Admin).
 * @param {Object|string} roleOrUser
 * @returns {boolean}
 */
export function canCreateProject(roleOrUser) {
  return isProjectManager(roleOrUser) || isAdmin(roleOrUser);
}

// Expose on window in browser dev environment only for testing
if (typeof window !== "undefined" && import.meta.env.DEV) {
  window.__wmsSession = {
    setSession,
    getSession,
    clearSession,
  };
}
