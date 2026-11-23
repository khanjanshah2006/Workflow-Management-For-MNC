/**
 * Client Portal Utilities (US-20, US-21, US-22, US-41)
 * Validation, formatting, and milestone progress calculation helpers.
 */

/**
 * Validates deliverable signoff submission payload (US-22).
 * - Rating: Required integer from 1 to 5.
 * - Decision: Must be 'ACCEPTED' or 'CHANGES_REQUESTED'.
 * - Comments: Mandatory when decision is 'CHANGES_REQUESTED', max 4000 chars.
 *
 * @param {{ rating: number, decision: string, comments?: string }} payload
 * @returns {{ isValid: boolean, errors: Record<string, string> }}
 */
export function validateSignoff(payload = {}) {
  const errors = {};
  const { rating, decision, comments } = payload;

  // Rating validation
  if (rating === undefined || rating === null || rating === "") {
    errors.rating = "Rating between 1 and 5 is required";
  } else {
    const num = Number(rating);
    if (!Number.isInteger(num) || num < 1 || num > 5) {
      errors.rating = "Rating must be an integer from 1 to 5";
    }
  }

  // Decision validation
  const validDecisions = ["ACCEPTED", "CHANGES_REQUESTED"];
  const normalizedDecision = typeof decision === "string" ? decision.trim().toUpperCase() : "";
  if (!normalizedDecision || !validDecisions.includes(normalizedDecision)) {
    errors.decision = "Decision must be either ACCEPTED or CHANGES_REQUESTED";
  }

  // Comments validation
  const cleanedComments = typeof comments === "string" ? comments.trim() : "";
  if (normalizedDecision === "CHANGES_REQUESTED" && !cleanedComments) {
    errors.comments = "Comments are mandatory when requesting changes";
  } else if (cleanedComments.length > 4000) {
    errors.comments = "Comments cannot exceed 4000 characters";
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}

/**
 * Calculates milestone completion metrics and percentage (US-20, US-21).
 *
 * @param {Array<Object>} milestones
 * @returns {{ total: number, completed: number, pending: number, percentage: number }}
 */
export function milestoneProgress(milestones = []) {
  if (!Array.isArray(milestones) || milestones.length === 0) {
    return { total: 0, completed: 0, pending: 0, percentage: 0 };
  }

  const total = milestones.length;
  const completed = milestones.filter(
    (m) => (m?.status || "").toLowerCase() === "completed"
  ).length;
  const pending = total - completed;
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

  return { total, completed, pending, percentage };
}

/**
 * Determines whether a delivery milestone is overdue (US-21).
 * An item is overdue if it is not completed and target_date is before currentDate.
 *
 * @param {Object} milestone
 * @param {Date|string|number} currentDate
 * @returns {boolean}
 */
export function isMilestoneOverdue(milestone, currentDate = new Date()) {
  if (!milestone || !milestone.target_date) return false;
  if ((milestone.status || "").toLowerCase() === "completed") return false;

  const target = new Date(milestone.target_date);
  if (isNaN(target.getTime())) return false;

  const curr = new Date(currentDate);
  if (isNaN(curr.getTime())) return false;

  // Compare calendar dates (midnight)
  target.setHours(0, 0, 0, 0);
  curr.setHours(0, 0, 0, 0);

  return target.getTime() < curr.getTime();
}

/**
 * Returns badge color tone for deliverable status (US-22).
 *
 * @param {string} status
 * @returns {'green'|'red'|'amber'|'grey'}
 */
export function deliverableStatusTone(status) {
  const norm = (status || "").toUpperCase();
  if (norm === "ACCEPTED") return "green";
  if (norm === "CHANGES_REQUESTED") return "red";
  if (norm === "PENDING_REVIEW" || norm === "PENDING") return "amber";
  return "grey";
}

/**
 * Returns badge color tone for milestone status (US-21).
 *
 * @param {string} status
 * @returns {'green'|'blue'|'amber'|'grey'}
 */
export function milestoneStatusTone(status) {
  const norm = (status || "").toLowerCase();
  if (norm === "completed") return "green";
  if (norm === "in_progress") return "blue";
  if (norm === "pending") return "amber";
  return "grey";
}

/**
 * Safely format ISO date to human-readable string.
 *
 * @param {string|Date} dateVal
 * @returns {string}
 */
export function formatDate(dateVal) {
  if (!dateVal) return "—";
  try {
    const d = new Date(dateVal);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "—";
  }
}
