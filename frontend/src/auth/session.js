/**
 * In-memory session adapter for WorkSphere frontend.
 *
 * Requirements:
 * - Integrates with shared apiClient (client.js) token handling and silent refresh.
 * - Stores access token and user information in module memory and synchronizes with wms_access_token.
 * - Exposes setSession(tokenResponse), getSession(), clearSession().
 * - getSession() returns a stable, immutable snapshot between updates for useSyncExternalStore.
 * - Canonical role definitions mirroring backend/app/core/roles.py.
 * - Exposes window.__wmsSession in development mode only (import.meta.env.DEV).
 */

import { useSyncExternalStore } from "react";
import {
  getStoredToken,
  setStoredToken,
  setTokenGetter,
  setTokenRefreshHandler,
  setSessionClearHandler,
} from "../api/client.js";

/**
 * Canonical system roles mirroring backend/app/core/roles.py.
 */
export const ROLES = Object.freeze({
  ADMIN: "ADMIN",
  SYSTEM_ADMIN: "SYSTEM_ADMIN",
  HR: "HR",
  PM: "PM",
  TEAM_LEAD: "TEAM_LEAD",
  EMPLOYEE: "EMPLOYEE",
  IT_SUPPORT: "IT_SUPPORT",
  MNC_EXECUTIVE: "MNC_EXECUTIVE",
  CLIENT: "CLIENT",
});

/**
 * All internal workforce roles (every valid enterprise role except CLIENT).
 */
export const INTERNAL_ROLES = Object.freeze([
  ROLES.EMPLOYEE,
  ROLES.TEAM_LEAD,
  ROLES.PM,
  ROLES.HR,
  ROLES.ADMIN,
  ROLES.IT_SUPPORT,
  ROLES.SYSTEM_ADMIN,
  ROLES.MNC_EXECUTIVE,
]);

/**
 * Roles with platform administrative authority across security and system ops.
 */
export const PLATFORM_ADMINS = Object.freeze([
  ROLES.ADMIN,
  ROLES.SYSTEM_ADMIN,
]);

/**
 * Roles authorized to access IT support operations and ticket resolution.
 */
export const IT_STAFF = Object.freeze([
  ROLES.IT_SUPPORT,
  ROLES.SYSTEM_ADMIN,
]);

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

if (typeof setTokenRefreshHandler === "function") {
  setTokenRefreshHandler((newToken) => {
    if (currentSnapshot) {
      currentSnapshot = Object.freeze({
        ...currentSnapshot,
        access_token: newToken,
      });
    }
    emitChange();
  });
}

if (typeof setSessionClearHandler === "function") {
  setSessionClearHandler(() => {
    currentSnapshot = null;
    emitChange();
  });
}

function emitChange() {
  for (const listener of listeners) {
    listener();
  }
}

/**
 * Creates an immutable snapshot from the given token response.
 * Preserves user profile fields including emp_id, led_team_ids, team_ids, active_elevated_roles.
 * @param {Object} tokenResponse
 * @returns {Readonly<Object>|null}
 */
export function createSnapshot(tokenResponse) {
  if (!tokenResponse) {
    return null;
  }

  const rawUser = tokenResponse.user;
  const user = rawUser
    ? Object.freeze({
        account_id: rawUser.account_id || "",
        email: rawUser.email || "",
        user_type: rawUser.user_type || "",
        role: rawUser.role || rawUser.user_type || "",
        is_active: Boolean(rawUser.is_active),
        emp_id: rawUser.emp_id ?? null,
        led_team_ids: Array.isArray(rawUser.led_team_ids)
          ? Object.freeze([...rawUser.led_team_ids])
          : Object.freeze([]),
        team_ids: Array.isArray(rawUser.team_ids)
          ? Object.freeze([...rawUser.team_ids])
          : Object.freeze([]),
        active_elevated_roles: Array.isArray(rawUser.active_elevated_roles)
          ? Object.freeze([...rawUser.active_elevated_roles])
          : Object.freeze([]),
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
 * @param {Object} tokenResponse Expected shape from auth response:
 * {
 *   access_token: string,
 *   refresh_token?: string,
 *   token_type?: string,
 *   expires_in?: number,
 *   user?: Object
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
 * E.g. "PM" -> "PM", "Admin" -> "ADMIN".
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
 * Checks if the role represents a Project Manager ("PM").
 * @param {Object|string} roleOrUser
 * @returns {boolean}
 */
export function isProjectManager(roleOrUser) {
  const norm = typeof roleOrUser === "string" ? normalizeRole(roleOrUser) : getUserRole(roleOrUser);
  return norm === ROLES.PM;
}

/**
 * Checks if the role represents a Platform Admin ("ADMIN" or "SYSTEM_ADMIN").
 * @param {Object|string} roleOrUser
 * @returns {boolean}
 */
export function isAdmin(roleOrUser) {
  const norm = typeof roleOrUser === "string" ? normalizeRole(roleOrUser) : getUserRole(roleOrUser);
  return PLATFORM_ADMINS.includes(norm);
}

/**
 * Checks if the role is authorized to create projects (PM or Admin).
 * @param {Object|string} roleOrUser
 * @returns {boolean}
 */
export function canCreateProject(roleOrUser) {
  return isProjectManager(roleOrUser) || isAdmin(roleOrUser);
}

/**
 * Checks if the role represents an MNC Executive ("MNC_EXECUTIVE").
 * @param {Object|string} roleOrUser
 * @returns {boolean}
 */
export function isExecutive(roleOrUser) {
  const norm = typeof roleOrUser === "string" ? normalizeRole(roleOrUser) : getUserRole(roleOrUser);
  return norm === ROLES.MNC_EXECUTIVE;
}

/**
 * Checks if the role represents a Client ("CLIENT").
 * @param {Object|string} roleOrUser
 * @returns {boolean}
 */
export function isClient(roleOrUser) {
  const norm = typeof roleOrUser === "string" ? normalizeRole(roleOrUser) : getUserRole(roleOrUser);
  return norm === ROLES.CLIENT;
}

/**
 * Checks if the role represents HR ("HR").
 * @param {Object|string} roleOrUser
 * @returns {boolean}
 */
export function isHr(roleOrUser) {
  const norm = typeof roleOrUser === "string" ? normalizeRole(roleOrUser) : getUserRole(roleOrUser);
  return norm === ROLES.HR;
}

/**
 * Checks if the role is an authorized internal role.
 * @param {Object|string} roleOrUser
 * @returns {boolean}
 */
export function isInternalRole(roleOrUser) {
  const norm = typeof roleOrUser === "string" ? normalizeRole(roleOrUser) : getUserRole(roleOrUser);
  return INTERNAL_ROLES.includes(norm);
}

/**
 * Maps an authenticated role to its designated landing route.
 * - CLIENT -> /client/projects
 * - MNC_EXECUTIVE -> /executive/console
 * - All other valid internal roles -> /dashboard
 * - Unknown or invalid roles -> /login (fails safely without granting privileged access)
 * @param {Object|string} roleOrUser
 * @returns {string}
 */
export function getHomeRouteForRole(roleOrUser) {
  const norm = typeof roleOrUser === "string" ? normalizeRole(roleOrUser) : getUserRole(roleOrUser);
  if (norm === ROLES.CLIENT) {
    return "/client/projects";
  }
  if (norm === ROLES.MNC_EXECUTIVE) {
    return "/executive/console";
  }
  if (INTERNAL_ROLES.includes(norm)) {
    return "/dashboard";
  }
  return "/login";
}

// Expose on window in browser dev environment only for testing
if (typeof window !== "undefined" && import.meta.env.DEV) {
  window.__wmsSession = {
    setSession,
    getSession,
    clearSession,
  };
}
