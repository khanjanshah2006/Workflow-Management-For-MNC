/**
 * Admin MFA policy as seen by the UI (US-31).
 *
 * The backend enforces ENFORCE_ADMIN_MFA on its own; the frontend only needs to know
 * whether to label MFA as required for administrators. Set VITE_ENFORCE_ADMIN_MFA=true
 * in the frontend environment to match a backend running with ENFORCE_ADMIN_MFA=true.
 */
import { PLATFORM_ADMINS, normalizeRole } from "./session.js";

/**
 * @param {Record<string, any>} [env] defaults to import.meta.env
 * @returns {boolean}
 */
export function isAdminMfaEnforced(env) {
  const source =
    env || (typeof import.meta !== "undefined" && import.meta.env ? import.meta.env : {});
  return String(source.VITE_ENFORCE_ADMIN_MFA || "").trim().toLowerCase() === "true";
}

/**
 * True when the policy requires MFA for this role (ADMIN and SYSTEM_ADMIN only).
 * @param {string} role
 * @param {boolean} enforced
 */
export function isMfaRequiredForRole(role, enforced) {
  if (!enforced) return false;
  return PLATFORM_ADMINS.includes(normalizeRole(role || ""));
}
