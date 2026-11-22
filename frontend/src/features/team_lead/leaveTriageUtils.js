/**
 * WorkSphere Team Lead Leave Triage Utilities (S4 / Issue #106)
 *
 * Implements validation for review rejection remarks, batch reallocation payload builder,
 * and teammate workload/coverage label formatting.
 */

/**
 * Validates rejection remarks for a leave request.
 *
 * Rules:
 * - Mandatory (cannot be null, undefined, or empty).
 * - Minimum 10 characters after trimming whitespace.
 * - Maximum 2000 characters.
 *
 * @param {string} remarks
 * @returns {{ isValid: boolean, error: string|null, length: number }}
 */
export function validateRejectionRemarks(remarks) {
  if (remarks === null || remarks === undefined) {
    return {
      isValid: false,
      error: "Rejection remarks are mandatory (minimum 10 characters).",
      length: 0,
    };
  }

  const trimmed = typeof remarks === "string" ? remarks.trim() : "";
  const length = trimmed.length;

  if (length === 0) {
    return {
      isValid: false,
      error: "Rejection remarks are mandatory (minimum 10 characters).",
      length: 0,
    };
  }

  if (length < 10) {
    return {
      isValid: false,
      error: "Review remarks must contain at least 10 non-whitespace characters.",
      length,
    };
  }

  if (length > 2000) {
    return {
      isValid: false,
      error: "Review remarks cannot exceed 2000 characters.",
      length,
    };
  }

  return {
    isValid: true,
    error: null,
    length,
  };
}

/**
 * Builds the batch reallocation payload for conflicting tasks.
 * Skips tasks with action "LEAVE_AS_IS" or empty actions.
 * Correctly formats REASSIGN and EXTEND_DEADLINE action items.
 *
 * @param {Array<Object>|Record<string|number, Object>} selections
 * @param {string} [defaultReason="Reallocated due to leave coverage"]
 * @returns {{ actions: Array<{ task_id: number, action_type: "REASSIGN"|"EXTEND_DEADLINE", new_assignee_id?: number, new_due_date?: string, reason: string }> }}
 */
export function buildReallocationPayload(selections, defaultReason = "Reallocated due to leave coverage") {
  if (!selections) {
    return { actions: [] };
  }

  const selectionItems = Array.isArray(selections)
    ? selections
    : Object.entries(selections).map(([taskId, item]) => ({
        task_id: Number(taskId),
        ...item,
      }));

  const actions = [];

  for (const item of selectionItems) {
    const actionType = String(item.action || item.action_type || "").toUpperCase();

    // Skip "Leave as is" or unselected
    if (!actionType || actionType === "LEAVE_AS_IS" || actionType === "NONE") {
      continue;
    }

    const taskId = Number(item.task_id);
    if (!taskId) continue;

    const rawReason = item.reason || defaultReason;
    const trimmedReason = typeof rawReason === "string" ? rawReason.trim() : defaultReason;
    const reason = trimmedReason.length >= 10 ? trimmedReason : `${trimmedReason} - leave reassignment`;

    if (actionType === "REASSIGN") {
      const newAssigneeId = item.new_assignee_id !== undefined ? Number(item.new_assignee_id) : item.newAssigneeId !== undefined ? Number(item.newAssigneeId) : null;
      if (newAssigneeId) {
        actions.push({
          task_id: taskId,
          action_type: "REASSIGN",
          new_assignee_id: newAssigneeId,
          reason,
        });
      }
    } else if (actionType === "EXTEND_DEADLINE") {
      const newDueDate = item.new_due_date || item.newDueDate;
      if (newDueDate) {
        actions.push({
          task_id: taskId,
          action_type: "EXTEND_DEADLINE",
          new_due_date: String(newDueDate).trim(),
          reason,
        });
      }
    }
  }

  return { actions };
}

/**
 * Returns user-facing status label for teammate availability/coverage.
 *
 * Formats:
 * - On leave: "On leave"
 * - At capacity: "At capacity (N tasks)"
 * - Available: "Available · N active tasks"
 *
 * @param {Object} member
 * @param {number} [member.active_tasks_count=0]
 * @param {boolean} [member.has_leave_overlap=false]
 * @param {boolean} [member.is_available_for_reassignment=true]
 * @param {number} [member.availability_threshold=5]
 * @returns {string}
 */
export function coverageLabel(member) {
  if (!member) return "Unavailable";

  if (member.has_leave_overlap) {
    return "On leave";
  }

  const activeCount = member.active_tasks_count ?? 0;
  const threshold = member.availability_threshold ?? 5;

  if (member.is_available_for_reassignment === false || activeCount >= threshold) {
    return `At capacity (${activeCount} tasks)`;
  }

  return `Available · ${activeCount} active tasks`;
}
