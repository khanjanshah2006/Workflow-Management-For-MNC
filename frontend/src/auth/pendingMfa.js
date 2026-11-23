/**
 * In-memory holder for the short-lived MFA token returned by POST /api/v1/auth/login
 * when a second step is needed (US-31).
 *
 * The token lives only in this module's memory. It is never written to
 * localStorage, sessionStorage or cookies, so a page reload drops it and the
 * user starts again at /login.
 */

/** Login needs a TOTP code: go to /login/mfa. */
export const MFA_STEP_CHALLENGE = "mfa_required";
/** Admin MFA is enforced and not set up yet: go to /login/mfa-setup. */
export const MFA_STEP_SETUP = "mfa_setup_required";

let pending = null;

/**
 * Reads the `exp` claim (seconds) of a JWT without verifying it.
 * @param {string} token
 * @returns {number|null} expiry in epoch milliseconds
 */
export function getTokenExpiryMs(token) {
  if (!token || typeof token !== "string") return null;
  const part = token.split(".")[1];
  if (!part) return null;
  try {
    const base64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const payload = JSON.parse(atob(padded));
    return typeof payload?.exp === "number" ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

/**
 * Stores the pending MFA step in memory.
 * @param {{ token: string, step: string, email?: string }} value
 */
export function setPendingMfa({ token, step, email = "" }) {
  pending = token
    ? Object.freeze({ token, step, email, expiresAt: getTokenExpiryMs(token) })
    : null;
}

/** @returns {Readonly<{ token: string, step: string, email: string, expiresAt: number|null }>|null} */
export function getPendingMfa() {
  return pending;
}

export function clearPendingMfa() {
  pending = null;
}

/**
 * True when the pending token's own expiry has passed (the backend issues 5-minute tokens).
 * A token without a readable `exp` is left for the backend to judge.
 * @param {{ expiresAt: number|null }|null} value
 * @param {number} [now]
 */
export function isPendingMfaExpired(value, now = Date.now()) {
  if (!value) return true;
  return typeof value.expiresAt === "number" && value.expiresAt <= now;
}
