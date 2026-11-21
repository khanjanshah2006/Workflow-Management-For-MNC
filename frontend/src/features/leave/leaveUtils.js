/**
 * WorkSphere Leave Management Utilities (S4 / US-16)
 *
 * Implements business day calculation, form validation, and status tone mapping.
 */

/**
 * Normalizes input date to a UTC Date object at 00:00:00Z.
 * Handles strings (YYYY-MM-DD or ISO) and Date objects safely
 * without timezone offset skew.
 *
 * @param {string|Date} dateInput
 * @returns {Date|null}
 */
export function parseDateOnly(dateInput) {
  if (!dateInput) return null;
  if (dateInput instanceof Date) {
    if (isNaN(dateInput.getTime())) return null;
    return new Date(Date.UTC(dateInput.getFullYear(), dateInput.getMonth(), dateInput.getDate()));
  }
  if (typeof dateInput === "string") {
    const trimmed = dateInput.trim();
    if (!trimmed) return null;
    const match = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (match) {
      const year = parseInt(match[1], 10);
      const month = parseInt(match[2], 10) - 1;
      const day = parseInt(match[3], 10);
      const d = new Date(Date.UTC(year, month, day));
      if (d.getUTCFullYear() === year && d.getUTCMonth() === month && d.getUTCDate() === day) {
        return d;
      }
      return null;
    }
    const parsed = new Date(trimmed);
    if (isNaN(parsed.getTime())) return null;
    return new Date(Date.UTC(parsed.getFullYear(), parsed.getMonth(), parsed.getDate()));
  }
  return null;
}

/**
 * Counts business days (Monday through Friday) inclusive between start and end.
 * Excludes Saturday (day 6) and Sunday (day 0).
 * If start date is after end date or dates are invalid, returns 0.
 *
 * @param {string|Date} start
 * @param {string|Date} end
 * @returns {number}
 */
export function countBusinessDays(start, end) {
  const startDate = parseDateOnly(start);
  const endDate = parseDateOnly(end);

  if (!startDate || !endDate) return 0;
  if (startDate > endDate) return 0;

  let businessDays = 0;
  const current = new Date(startDate.getTime());

  while (current <= endDate) {
    const dayOfWeek = current.getUTCDay();
    // 0 is Sunday, 6 is Saturday
    if (dayOfWeek !== 0 && dayOfWeek !== 6) {
      businessDays++;
    }
    current.setUTCDate(current.getUTCDate() + 1);
  }

  return businessDays;
}

/**
 * Maps leave request status to its corresponding tone representation.
 * - APPROVED -> "green"
 * - PENDING -> "amber"
 * - REJECTED -> "red"
 * - CANCELLED -> "grey"
 *
 * @param {string} status
 * @returns {"green"|"amber"|"red"|"grey"}
 */
export function leaveStatusTone(status) {
  const s = String(status || "").trim().toUpperCase();
  switch (s) {
    case "APPROVED":
      return "green";
    case "PENDING":
      return "amber";
    case "REJECTED":
      return "red";
    case "CANCELLED":
    case "CANCELED":
      return "grey";
    default:
      return "grey";
  }
}

/**
 * Returns CSS class for leave status badge.
 * @param {string} status
 * @returns {string}
 */
export function getLeaveStatusBadgeClass(status) {
  return `leave-badge-${leaveStatusTone(status)}`;
}

/**
 * Validates leave application form against US-16 business rules.
 *
 * Rules:
 * 1. Start date must be today or later.
 * 2. End date must be on or after the start date.
 * 3. Start and end dates must belong to the same calendar year.
 * 4. Requested working days must be greater than zero (excluding weekends).
 * 5. Requested working days must not exceed available leave balance.
 * 6. Reason must contain 10–2000 characters.
 *
 * @param {Object} form { leave_type_id, start_date, end_date, reason }
 * @param {Array|Object} [balances] Leave balances array or response object
 * @param {string|Date} [today] Reference today's date (defaults to current date)
 * @returns {{
 *   isValid: boolean,
 *   errors: Record<string, string>,
 *   workingDays: number,
 *   availableDays: number|null
 * }}
 */
export function validateLeaveForm(form, balances = [], today = new Date()) {
  const errors = {};
  const todayDate = parseDateOnly(today) || parseDateOnly(new Date());

  const startDate = parseDateOnly(form?.start_date);
  const endDate = parseDateOnly(form?.end_date);

  // Leave type validation
  const leaveTypeId = form?.leave_type_id ? Number(form.leave_type_id) : null;
  if (!leaveTypeId) {
    errors.leave_type_id = "Please select a leave type";
  }

  // Date presence validation
  if (!form?.start_date) {
    errors.start_date = "Start date is required";
  }
  if (!form?.end_date) {
    errors.end_date = "End date is required";
  }

  // Business day calculation
  let workingDays = 0;
  if (startDate && endDate) {
    if (startDate < todayDate) {
      errors.start_date = "Start date must be today or later";
    }

    if (endDate < startDate) {
      errors.end_date = "End date must be on or after start date";
    } else {
      // Check cross-year
      if (startDate.getUTCFullYear() !== endDate.getUTCFullYear()) {
        errors.end_date = "Leave cannot span calendar years; submit two requests";
      }

      workingDays = countBusinessDays(startDate, endDate);

      if (workingDays === 0 && !errors.end_date && !errors.start_date) {
        errors.dates = "Selected date range contains no working days (weekends only)";
      }
    }
  }

  // Find balance for selected leave type
  let availableDays = null;
  const balanceList = Array.isArray(balances)
    ? balances
    : Array.isArray(balances?.balances)
    ? balances.balances
    : [];

  if (leaveTypeId && balanceList.length > 0) {
    const selectedBalance = balanceList.find(
      (b) => Number(b.leave_type_id) === leaveTypeId
    );
    if (selectedBalance) {
      availableDays = selectedBalance.available_days ?? 0;
      if (workingDays > availableDays) {
        const errorMsg = `Insufficient leave balance (Available: ${availableDays} days)`;
        errors.balance = errorMsg;
      }
    }
  }

  // Reason validation
  const rawReason = form?.reason ?? "";
  const trimmedReason = typeof rawReason === "string" ? rawReason.trim() : "";
  if (!trimmedReason) {
    errors.reason = "Reason is required (minimum 10 characters)";
  } else if (trimmedReason.length < 10) {
    errors.reason = "Reason must contain between 10 and 2000 characters";
  } else if (trimmedReason.length > 2000) {
    errors.reason = "Reason must not exceed 2000 characters";
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
    workingDays,
    availableDays,
  };
}
