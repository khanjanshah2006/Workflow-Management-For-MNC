/**
 * Leave Policy Administration Utilities (US-18, S4-BE-2 / S4-FE-3)
 *
 * Provides client-side validation and formatting helpers for HR leave policy management.
 */

/**
 * Validates the Leave Policy Create/Edit Form (US-18).
 *
 * Rules:
 * - name: required, stripped length between 2 and 50 characters.
 * - yearly_quota: required, integer between 0 and 366.
 *   - Rejects empty, non-numeric, negative values (< 0), decimals (non-integer), and values > 366.
 * - description: optional, max 1000 characters if provided.
 *
 * @param {{ name?: string, yearly_quota?: number|string, is_paid?: boolean, description?: string }} values
 * @returns {{ isValid: boolean, errors: Record<string, string> }}
 */
export function validatePolicyForm(values = {}) {
  const errors = {};

  // 1. Name validation
  const rawName = values?.name;
  if (rawName === undefined || rawName === null || typeof rawName !== "string" || rawName.trim() === "") {
    errors.name = "Policy name is required.";
  } else {
    const trimmedName = rawName.trim();
    if (trimmedName.length < 2) {
      errors.name = "Policy name must be at least 2 characters.";
    } else if (trimmedName.length > 50) {
      errors.name = "Policy name cannot exceed 50 characters.";
    }
  }

  // 2. Yearly quota validation
  const rawQuota = values?.yearly_quota;
  if (rawQuota === undefined || rawQuota === null || String(rawQuota).trim() === "") {
    errors.yearly_quota = "Yearly quota is required.";
  } else {
    const quotaStr = String(rawQuota).trim();
    const num = Number(quotaStr);
    if (Number.isNaN(num)) {
      errors.yearly_quota = "Yearly quota must be a valid number.";
    } else if (!Number.isInteger(num) || quotaStr.includes(".")) {
      errors.yearly_quota = "Yearly quota must be an integer.";
    } else if (num < 0) {
      errors.yearly_quota = "Yearly quota cannot be negative.";
    } else if (num > 366) {
      errors.yearly_quota = "Yearly quota cannot exceed 366 days.";
    }
  }

  // 3. Description validation
  const rawDesc = values?.description;
  if (rawDesc !== undefined && rawDesc !== null && typeof rawDesc === "string") {
    if (rawDesc.length > 1000) {
      errors.description = "Description cannot exceed 1000 characters.";
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}

/**
 * Format quota display (e.g., "20 days" or "1 day").
 *
 * @param {number|string} quota
 * @returns {string}
 */
export function formatQuotaLabel(quota) {
  const num = Number(quota);
  if (Number.isNaN(num) || num < 0) return "0 days";
  return num === 1 ? "1 day" : `${num} days`;
}
