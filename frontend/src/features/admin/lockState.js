/**
 * Account lock state for the admin console (US-48 / US-49).
 *
 * GET /api/v1/admin/users does not return lock state, so it is taken from the
 * ACCOUNT_LOCKED items of GET /api/v1/admin/anomaly-alerts:
 *   account_id     → the locked account
 *   last_timestamp → locked until
 */

export const ACCOUNT_LOCKED_ALERT = "ACCOUNT_LOCKED";

/**
 * Parses a backend timestamp. Values without a zone are treated as UTC.
 * @param {string|Date|null|undefined} value
 * @returns {number|null} epoch milliseconds
 */
export function parseServerTimestamp(value) {
  if (!value) return null;
  if (value instanceof Date) {
    const t = value.getTime();
    return Number.isNaN(t) ? null : t;
  }
  let text = String(value).trim();
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(text);
  if (!hasZone && /^\d{4}-\d{2}-\d{2}T/.test(text)) {
    text = `${text}Z`;
  }
  const t = Date.parse(text);
  return Number.isNaN(t) ? null : t;
}

/**
 * Builds a map of account_id → lock details from the anomaly alerts, keeping only
 * locks that have not expired yet.
 * @param {Array<Object>} alerts
 * @param {number} [now]
 * @returns {Map<string, { lockedUntil: number, email: string|null, alertId: string|null }>}
 */
export function getLockedAccounts(alerts, now = Date.now()) {
  const locked = new Map();
  if (!Array.isArray(alerts)) return locked;

  for (const alert of alerts) {
    if (alert?.alert_type !== ACCOUNT_LOCKED_ALERT) continue;
    const accountId = alert.account_id || alert.target_account_id;
    if (!accountId) continue;
    const lockedUntil = parseServerTimestamp(alert.last_timestamp);
    if (lockedUntil === null || lockedUntil <= now) continue;

    const key = String(accountId);
    const existing = locked.get(key);
    if (!existing || lockedUntil > existing.lockedUntil) {
      locked.set(key, {
        lockedUntil,
        email: alert.attempted_email || alert.target_account || null,
        alertId: alert.id || null,
      });
    }
  }
  return locked;
}

/**
 * Adds is_locked / locked_until (ISO string) to each user row.
 * @param {Array<Object>} users
 * @param {Map<string, { lockedUntil: number }>} lockedAccounts
 * @returns {Array<Object>}
 */
export function mergeLockState(users, lockedAccounts) {
  if (!Array.isArray(users)) return [];
  return users.map((user) => {
    const lock = lockedAccounts?.get(String(user?.account_id ?? ""));
    return {
      ...user,
      is_locked: Boolean(lock),
      locked_until: lock ? new Date(lock.lockedUntil).toISOString() : null,
    };
  });
}

/**
 * Formats a lock expiry as local HH:MM.
 * @param {string|number|Date} value
 */
export function formatLockedUntil(value) {
  const t = typeof value === "number" ? value : parseServerTimestamp(value);
  if (t === null || Number.isNaN(t)) return "";
  const d = new Date(t);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}
