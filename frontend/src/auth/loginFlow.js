/**
 * Pure helpers that turn sign-in responses into what the UI should do next
 * (US-31 Admin MFA, US-48 / US-49 Account Lockout and login throttling).
 */
import { MFA_STEP_CHALLENGE, MFA_STEP_SETUP } from "./pendingMfa.js";
import { ROUTES } from "../routes.js";

/** Submit stays disabled this long after a 423 (account locked). */
export const LOCKED_SUBMIT_COOLDOWN_SECONDS = 30;
/** Used when a 429 arrives without a readable Retry-After header. */
export const DEFAULT_RETRY_AFTER_SECONDS = 60;

export const INVALID_CREDENTIALS_MESSAGE = "Invalid email or password";
export const SIGN_IN_TIMED_OUT_MESSAGE = "Your sign-in timed out. Please sign in again.";
export const DEFAULT_LOCKED_MESSAGE =
  "Account locked. Try again later or contact an administrator.";

export const MFA_CHALLENGE_ROUTE = `${ROUTES.LOGIN}/mfa`;
export const MFA_SETUP_ROUTE = `${ROUTES.LOGIN}/mfa-setup`;

/**
 * Classifies a 200 response from POST /api/v1/auth/login.
 * @param {Object} data
 * @returns {{ type: "authenticated" } | { type: "mfa_required" | "mfa_setup_required", mfaToken: string, route: string }}
 */
export function classifyLoginResponse(data) {
  if (data?.mfa_setup_required && data?.mfa_token) {
    return { type: MFA_STEP_SETUP, mfaToken: data.mfa_token, route: MFA_SETUP_ROUTE };
  }
  if (data?.mfa_required && data?.mfa_token) {
    return { type: MFA_STEP_CHALLENGE, mfaToken: data.mfa_token, route: MFA_CHALLENGE_ROUTE };
  }
  return { type: "authenticated" };
}

/**
 * Reads Retry-After (delta-seconds or HTTP-date) from a Headers-like object.
 * @param {Headers|Record<string,string>|null|undefined} headers
 * @param {number} [fallback]
 * @param {number} [now]
 * @returns {number} whole seconds, at least 1
 */
export function getRetryAfterSeconds(headers, fallback = DEFAULT_RETRY_AFTER_SECONDS, now = Date.now()) {
  let raw = null;
  if (headers && typeof headers.get === "function") {
    raw = headers.get("retry-after");
  } else if (headers && typeof headers === "object") {
    const key = Object.keys(headers).find((k) => k.toLowerCase() === "retry-after");
    raw = key ? headers[key] : null;
  }
  if (raw === null || raw === undefined || String(raw).trim() === "") return fallback;

  const text = String(raw).trim();
  if (/^\d+$/.test(text)) {
    return Math.max(1, parseInt(text, 10));
  }
  const dateMs = Date.parse(text);
  if (!Number.isNaN(dateMs)) {
    return Math.max(1, Math.ceil((dateMs - now) / 1000));
  }
  return fallback;
}

/** @param {number} seconds */
export function formatThrottleMessage(seconds) {
  const n = Math.max(0, Math.ceil(seconds));
  return `Too many sign-in attempts. Try again in ${n} second${n === 1 ? "" : "s"}.`;
}

/**
 * Classifies a failed sign-in request (password or MFA code).
 * @param {{ status?: number, message?: string, headers?: any }} error
 * @param {number} [now]
 * @returns {
 *   { type: "locked", message: string, cooldownSeconds: number } |
 *   { type: "throttled", retryAfterSeconds: number } |
 *   { type: "invalid", message: string } |
 *   { type: "error", message: string }
 * }
 */
export function classifyLoginError(error, now = Date.now()) {
  const status = error?.status;
  if (status === 423) {
    return {
      type: "locked",
      message: error?.message || DEFAULT_LOCKED_MESSAGE,
      cooldownSeconds: LOCKED_SUBMIT_COOLDOWN_SECONDS,
    };
  }
  if (status === 429) {
    return {
      type: "throttled",
      retryAfterSeconds: getRetryAfterSeconds(error?.headers, DEFAULT_RETRY_AFTER_SECONDS, now),
    };
  }
  if (status === 401) {
    return { type: "invalid", message: INVALID_CREDENTIALS_MESSAGE };
  }
  return {
    type: "error",
    message: error?.message || "Sign-in failed. Please try again.",
  };
}

/**
 * True when a 401 from /auth/mfa/login, /auth/mfa/setup or /auth/mfa/verify means the
 * pending token is no longer accepted (rather than a wrong code).
 * @param {{ status?: number, message?: string }} error
 */
export function isMfaTokenRejected(error) {
  if (error?.status !== 401) return false;
  const message = String(error?.message || "").toLowerCase();
  return (
    message.includes("expired") ||
    message.includes("invalid token") ||
    message.includes("could not validate") ||
    message.includes("inactive or does not exist")
  );
}
