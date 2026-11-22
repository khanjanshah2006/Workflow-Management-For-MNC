/**
 * Utility functions for Executive Command Center (S7-FE-1, US-24, US-25).
 */

/**
 * Format milestone velocity percentage to one decimal place.
 * Returns formatted string like "76.5%" or "0.0%".
 *
 * @param {number|null|undefined} value
 * @returns {string}
 */
export function formatVelocity(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "0.0%";
  }
  const num = Number(value);
  return `${num.toFixed(1)}%`;
}

/**
 * Status color palette matching WorkSphere design system.
 */
export const STATUS_COLORS = {
  PLANNED: "#64748b",   // Slate
  ACTIVE: "#2563eb",    // Blue
  ON_HOLD: "#f59e0b",   // Amber
  COMPLETED: "#10b981", // Emerald
  CANCELLED: "#ef4444", // Red
};

export const STATUS_LABELS = {
  PLANNED: "Planned",
  ACTIVE: "Active",
  ON_HOLD: "On Hold",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

/**
 * Computes segments for stacked status bar from projects_by_status counts.
 * Guarantees total percentage equals 100 when there are projects.
 * Safely handles zero-project count and missing status values.
 *
 * @param {Object} projectsByStatus Record of status -> count
 * @returns {Array<{ status: string, label: string, count: number, percentage: number, color: string }>}
 */
export function statusSegments(projectsByStatus) {
  const statuses = ["PLANNED", "ACTIVE", "ON_HOLD", "COMPLETED", "CANCELLED"];
  const safeData = projectsByStatus && typeof projectsByStatus === "object" ? projectsByStatus : {};

  const total = statuses.reduce((sum, s) => sum + Math.max(0, Number(safeData[s]) || 0), 0);

  if (total <= 0) {
    return statuses.map((status) => ({
      status,
      label: STATUS_LABELS[status] || status,
      count: 0,
      percentage: 0,
      color: STATUS_COLORS[status] || "#94a3b8",
    }));
  }

  // Calculate raw percentages rounded to 1 decimal place
  let rawSegments = statuses.map((status) => {
    const count = Math.max(0, Number(safeData[status]) || 0);
    const rawPct = (count / total) * 100;
    return {
      status,
      label: STATUS_LABELS[status] || status,
      count,
      percentage: Math.round(rawPct * 10) / 10,
      color: STATUS_COLORS[status] || "#94a3b8",
    };
  });

  // Adjust rounding so total equals exactly 100.0 for non-zero projects
  const sumPct = rawSegments.reduce((sum, seg) => sum + seg.percentage, 0);
  const diff = Math.round((100.0 - sumPct) * 10) / 10;

  if (diff !== 0) {
    // Find the non-zero segment with the largest count to absorb rounding variance
    const maxSegment = rawSegments
      .filter((s) => s.count > 0)
      .reduce((max, s) => (s.count > max.count ? s : max), rawSegments.find((s) => s.count > 0));

    if (maxSegment) {
      maxSegment.percentage = Math.round((maxSegment.percentage + diff) * 10) / 10;
    }
  }

  return rawSegments;
}

/**
 * Validates Executive Management Report Generation Form.
 *
 * Rules (matching S7-BE-2 / US-25):
 * 1. Title: 3–255 characters.
 * 2. Start date: valid YYYY-MM-DD, cannot be in the future (<= today).
 * 3. End date: valid YYYY-MM-DD, cannot precede start date (>= start_date).
 * 4. Reporting period range cannot exceed 366 days.
 * 5. Format: must be "PDF" or "CSV".
 *
 * @param {Object} form
 * @param {Date|string} [today] Optional reference date for testing
 * @returns {{ isValid: boolean, errors: Record<string, string> }}
 */
export function validateReportForm(form, today) {
  const errors = {};
  const current = today ? (today instanceof Date ? today : new Date(today)) : new Date();

  // Normalize today to UTC midnight or local start of day for clean date-only comparison
  const todayStr =
    today instanceof Date
      ? today.toISOString().split("T")[0]
      : typeof today === "string"
      ? today.split("T")[0]
      : current.toISOString().split("T")[0];

  // 1. Report Title Validation
  const title = form?.report_title?.trim() || "";
  if (!title) {
    errors.report_title = "Report title is required.";
  } else if (title.length < 3) {
    errors.report_title = "Report title must be at least 3 characters.";
  } else if (title.length > 255) {
    errors.report_title = "Report title cannot exceed 255 characters.";
  }

  // 2. Start Date Validation
  const startDateStr = form?.period_start?.trim() || "";
  if (!startDateStr) {
    errors.period_start = "Start date is required.";
  } else if (isNaN(Date.parse(startDateStr))) {
    errors.period_start = "Invalid start date.";
  } else if (startDateStr > todayStr) {
    errors.period_start = "Start date cannot be in the future.";
  }

  // 3. End Date Validation
  const endDateStr = form?.period_end?.trim() || "";
  if (!endDateStr) {
    errors.period_end = "End date is required.";
  } else if (isNaN(Date.parse(endDateStr))) {
    errors.period_end = "Invalid end date.";
  } else if (startDateStr && !errors.period_start) {
    if (endDateStr < startDateStr) {
      errors.period_end = "End date cannot precede start date.";
    } else {
      const startMs = Date.parse(startDateStr);
      const endMs = Date.parse(endDateStr);
      const diffDays = Math.round((endMs - startMs) / (1000 * 60 * 60 * 24));
      if (diffDays > 366) {
        errors.period_end = "Reporting period cannot exceed 366 days.";
      }
    }
  }

  // 4. Format Validation
  const format = (form?.format || "").toUpperCase();
  if (format && format !== "PDF" && format !== "CSV") {
    errors.format = "Report format must be PDF or CSV.";
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}

/**
 * Format bytes into human-readable string (e.g. 124.5 KB, 2.1 MB).
 * @param {number} bytes
 * @returns {string}
 */
export function formatBytes(bytes) {
  if (!bytes || bytes <= 0 || isNaN(bytes)) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const val = bytes / Math.pow(k, i);
  return `${val.toFixed(i === 0 ? 0 : 1)} ${sizes[i]}`;
}
