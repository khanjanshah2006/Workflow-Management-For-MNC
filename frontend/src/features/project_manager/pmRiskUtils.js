/**
 * PM Risk & Delivery Dashboard Utilities (US-15, US-23, US-38, US-39)
 */

/**
 * Format overdue days chip label.
 * Produces "1 day overdue" for 1, and "N days overdue" for N > 1 or 0.
 *
 * @param {number|string} days
 * @returns {string}
 */
export function overdueChipLabel(days) {
  const count = Math.max(0, parseInt(days, 10) || 0);
  if (count === 1) {
    return "1 day overdue";
  }
  return `${count} days overdue`;
}

/**
 * Maps project risk level ("LOW" | "MEDIUM" | "HIGH") to visual tone identifier.
 *
 * @param {string} level
 * @returns {"low" | "medium" | "high"}
 */
export function riskTone(level) {
  const s = String(level || "").toUpperCase().trim();
  if (s === "LOW") return "low";
  if (s === "MEDIUM") return "medium";
  if (s === "HIGH" || s === "CRITICAL") return "high";
  return "low";
}

/**
 * Priority weighting for sorting.
 */
const PRIORITY_WEIGHTS = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

/**
 * Stable sort for overdue task items.
 * Guarantees original relative index preservation for equal sort keys.
 *
 * @param {Array<Object>} items
 * @param {string} key Property name to sort by
 * @param {"asc" | "desc"} [dir="asc"]
 * @returns {Array<Object>} New sorted array without mutating input
 */
export function sortOverdue(items, key, dir = "asc") {
  if (!Array.isArray(items)) return [];
  if (!key) return [...items];

  const indexed = items.map((item, index) => ({ item, index }));
  const multiplier = dir === "desc" ? -1 : 1;

  indexed.sort((a, b) => {
    const valA = a.item?.[key];
    const valB = b.item?.[key];

    let comparison = 0;

    if (key === "priority") {
      const weightA = PRIORITY_WEIGHTS[String(valA || "").toUpperCase()] || 0;
      const weightB = PRIORITY_WEIGHTS[String(valB || "").toUpperCase()] || 0;
      comparison = weightA - weightB;
    } else if (valA === valB) {
      comparison = 0;
    } else if (valA === null || valA === undefined) {
      comparison = 1;
    } else if (valB === null || valB === undefined) {
      comparison = -1;
    } else if (typeof valA === "number" && typeof valB === "number") {
      comparison = valA - valB;
    } else if (key === "due_date") {
      const timeA = new Date(valA).getTime() || 0;
      const timeB = new Date(valB).getTime() || 0;
      comparison = timeA - timeB;
    } else {
      comparison = String(valA).localeCompare(String(valB), undefined, {
        numeric: true,
        sensitivity: "base",
      });
    }

    if (comparison !== 0) {
      return comparison * multiplier;
    }

    // Stability: tie-breaker using original insertion order
    return a.index - b.index;
  });

  return indexed.map((x) => x.item);
}

/**
 * All six canonical task statuses displayed in the PM stacked status bar.
 */
export const STATUS_BAR_CONFIG = [
  { status: "DONE", label: "Done", color: "#10b981", className: "status-done" },
  { status: "IN_REVIEW", label: "In Review", color: "#6366f1", className: "status-in-review" },
  { status: "IN_PROGRESS", label: "In Progress", color: "#3b82f6", className: "status-in-progress" },
  { status: "TODO", label: "To Do", color: "#94a3b8", className: "status-todo" },
  { status: "BLOCKED", label: "Blocked", color: "#f59e0b", className: "status-blocked" },
  { status: "REJECTED", label: "Rejected", color: "#ef4444", className: "status-rejected" },
];

/**
 * Calculates CSS bar segments for task status distribution.
 * Guarantees that segment percentages sum up to exactly 100% when totalTasks > 0.
 *
 * @param {Record<string, number>} [tasksByStatus={}]
 * @param {number} [totalTasks=0]
 * @returns {Array<{ status: string, label: string, count: number, pct: number, color: string, className: string }>}
 */
export function statusBarSegments(tasksByStatus = {}, totalTasks = 0) {
  const safeTotal = typeof totalTasks === "number" && totalTasks > 0
    ? totalTasks
    : Object.values(tasksByStatus || {}).reduce((acc, v) => acc + (Number(v) || 0), 0);

  if (safeTotal <= 0) {
    return STATUS_BAR_CONFIG.map((s) => ({
      ...s,
      count: 0,
      pct: 0,
    }));
  }

  const segments = STATUS_BAR_CONFIG.map((s) => {
    const count = Math.max(0, Number(tasksByStatus?.[s.status]) || 0);
    return {
      ...s,
      count,
      pct: (count / safeTotal) * 100,
    };
  });

  const activeSegments = segments.filter((s) => s.count > 0);
  if (activeSegments.length === 0) {
    return segments;
  }

  let sumRounded = 0;
  segments.forEach((seg) => {
    if (seg.count > 0) {
      seg.pct = Math.round(seg.pct * 10) / 10;
      sumRounded += seg.pct;
    } else {
      seg.pct = 0;
    }
  });

  sumRounded = Math.round(sumRounded * 10) / 10;
  const delta = Math.round((100 - sumRounded) * 10) / 10;

  if (delta !== 0) {
    let largest = activeSegments[0];
    for (const seg of activeSegments) {
      if (seg.count > largest.count) {
        largest = seg;
      }
    }
    largest.pct = Math.round((largest.pct + delta) * 10) / 10;
  }

  return segments;
}

export const pmRiskUtils = {
  overdueChipLabel,
  riskTone,
  sortOverdue,
  statusBarSegments,
  STATUS_BAR_CONFIG,
};

export default pmRiskUtils;
