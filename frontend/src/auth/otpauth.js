/**
 * Builds TOTP provisioning URIs for authenticator apps (US-31).
 * Format: otpauth://totp/{issuer}:{account}?secret={secret}&issuer={issuer}
 */

export const OTP_ISSUER = "WorkSphere";

/**
 * Normalizes a base32 secret: removes spaces / separators and upper-cases it.
 * @param {string} secret
 */
export function normalizeOtpSecret(secret) {
  return String(secret || "")
    .replace(/[\s-]/g, "")
    .toUpperCase();
}

/**
 * @param {{ email: string, secret: string, issuer?: string }} params
 * @returns {string} otpauth URI, or "" when the secret is missing
 */
export function buildOtpauthUri({ email, secret, issuer = OTP_ISSUER }) {
  const cleanSecret = normalizeOtpSecret(secret);
  if (!cleanSecret) return "";
  const label = `${encodeURIComponent(issuer)}:${encodeURIComponent(String(email || "").trim())}`;
  return `otpauth://totp/${label}?secret=${cleanSecret}&issuer=${encodeURIComponent(issuer)}`;
}

/**
 * Splits a secret into groups of four for easier manual entry.
 * @param {string} secret
 */
export function formatOtpSecret(secret) {
  return normalizeOtpSecret(secret).replace(/(.{4})(?=.)/g, "$1 ");
}
