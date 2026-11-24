/**
 * ticketStatusUtils.js (S8-FE-3 / US-26, US-27, US-28)
 *
 * State machine actions, payload builders, and URL filter helpers
 * for IT Support Triage Queue and Reporter View.
 */

/**
 * Valid action identifiers
 */
export const ACTIONS = Object.freeze({
  ASSIGN_ME: "assign_me",
  ASSIGN_OTHER: "assign_other",
  ADD_NOTE: "add_note",
  RESOLVE: "resolve",
  ESCALATE: "escalate",
  TAKE_OVER: "take_over",
  CLOSE: "close",
  REOPEN: "reopen",
});

/**
 * Returns allowed action IDs for a given ticket and user role.
 *
 * Rules per S8-FE-3:
 * - 'open': Assign to me, Assign to…, Escalate (for IT staff)
 * - 'in_progress': Add note, Resolve (needs resolution note), Escalate (for IT staff)
 * - 'escalated':
 *     - SYSTEM_ADMIN only: Take over (-> in_progress) or Resolve
 *     - IT_SUPPORT: read-only (empty actions, shows 'Awaiting SysAdmin' chip)
 * - 'resolved':
 *     - IT staff: Close (-> closed)
 *     - Reporter: Reopen (-> open)
 * - 'closed': none
 *
 * @param {Object} ticket
 * @param {string} role - User role string (e.g. 'IT_SUPPORT', 'SYSTEM_ADMIN', 'EMPLOYEE', 'reporter')
 * @param {boolean} isReporter - Whether the current user is the reporter of this ticket
 * @returns {string[]} List of allowed action strings
 */
export function allowedActions(ticket, role = "", isReporter = false) {
  if (!ticket) return [];

  const status = (ticket.status || "").toLowerCase();
  const normRole = (role || "").toUpperCase().replace(/\s+/g, "_");

  const isSysAdmin = normRole === "SYSTEM_ADMIN";
  const isItStaff = normRole === "IT_SUPPORT" || normRole === "SYSTEM_ADMIN" || normRole === "ADMIN";
  const isReporterUser = Boolean(isReporter);

  switch (status) {
    case "open":
      if (isItStaff) {
        return [ACTIONS.ASSIGN_ME, ACTIONS.ASSIGN_OTHER, ACTIONS.ESCALATE];
      }
      return [];

    case "in_progress":
      if (isItStaff) {
        return [ACTIONS.ADD_NOTE, ACTIONS.RESOLVE, ACTIONS.ESCALATE];
      }
      return [];

    case "escalated":
      if (isSysAdmin) {
        return [ACTIONS.TAKE_OVER, ACTIONS.RESOLVE];
      }
      // IT_SUPPORT & plain ADMIN are read-only on escalated tickets per #146
      return [];

    case "resolved": {
      const actions = [];
      if (isItStaff) {
        actions.push(ACTIONS.CLOSE);
      }
      if (isReporterUser) {
        actions.push(ACTIONS.REOPEN);
      }
      return actions;
    }

    case "closed":
    default:
      return [];
  }
}

/**
 * Validates mandatory resolution note when resolving a ticket.
 *
 * @param {string} note
 * @returns {{ isValid: boolean, error: string|null }}
 */
export function validateResolutionNote(note) {
  if (!note || typeof note !== "string" || !note.trim()) {
    return {
      isValid: false,
      error: "A resolution note is required when resolving a ticket.",
    };
  }
  return {
    isValid: true,
    error: null,
  };
}

/**
 * Validates internal troubleshooting note (1–2000 characters).
 *
 * @param {string} note
 * @returns {{ isValid: boolean, error: string|null }}
 */
export function validateInternalNote(note) {
  if (!note || typeof note !== "string" || !note.trim()) {
    return {
      isValid: false,
      error: "Note text cannot be empty.",
    };
  }
  if (note.trim().length > 2000) {
    return {
      isValid: false,
      error: "Note cannot exceed 2000 characters.",
    };
  }
  return {
    isValid: true,
    error: null,
  };
}

/**
 * Payload builder for PUT /api/v1/support/tickets/{id}/assign
 * Contract: { assignee_account_id: "<uuid>" }
 *
 * @param {string} assigneeAccountId
 * @returns {{ assignee_account_id: string }}
 */
export function buildAssignPayload(assigneeAccountId) {
  return {
    assignee_account_id: String(assigneeAccountId || "").trim(),
  };
}

/**
 * Payload builder for POST /api/v1/support/tickets/{id}/notes
 * Contract: { note: "1–2000 chars" }
 *
 * @param {string} note
 * @returns {{ note: string }}
 */
export function buildNotePayload(note) {
  return {
    note: String(note || "").trim(),
  };
}

/**
 * Payload builder for PUT /api/v1/support/tickets/{id}/status
 * Contract: { status: "lowercase", resolution_note?: "string" }
 *
 * @param {string} status
 * @param {string} [resolutionNote]
 * @returns {{ status: string, resolution_note?: string }}
 */
export function buildStatusPayload(status, resolutionNote) {
  const payload = {
    status: String(status || "").toLowerCase().trim(),
  };
  if (resolutionNote && String(resolutionNote).trim()) {
    payload.resolution_note = String(resolutionNote).trim();
  }
  return payload;
}

/**
 * Converts triage filter object to URLSearchParams query string.
 *
 * @param {Object} filters
 * @param {string} [filters.status]
 * @param {string} [filters.category]
 * @param {string} [filters.priority]
 * @param {string} [filters.assigned_to]
 * @param {number} [filters.page]
 * @param {number} [filters.limit]
 * @returns {string} e.g. "status=open&priority=CRITICAL&page=1"
 */
export function filtersToQueryString(filters = {}) {
  const params = new URLSearchParams();

  if (filters.status && filters.status !== "ALL" && filters.status !== "all") {
    params.set("status", filters.status.toLowerCase().trim());
  }
  if (filters.category && filters.category !== "ALL" && filters.category !== "all") {
    params.set("category", filters.category.toLowerCase().trim());
  }
  if (filters.priority && filters.priority !== "ALL" && filters.priority !== "all") {
    params.set("priority", filters.priority.toUpperCase().trim());
  }
  if (filters.assigned_to && filters.assigned_to !== "ALL" && filters.assigned_to !== "all") {
    params.set("assigned_to", filters.assigned_to.trim());
  }
  if (filters.page && Number(filters.page) > 1) {
    params.set("page", String(filters.page));
  }
  if (filters.limit && Number(filters.limit) !== 20) {
    params.set("limit", String(filters.limit));
  }

  return params.toString();
}

/**
 * Extracts filter state from URLSearchParams.
 *
 * @param {URLSearchParams|string} search
 * @returns {{ status: string, category: string, priority: string, assigned_to: string, page: number, limit: number }}
 */
export function filtersFromQueryString(search) {
  const params = typeof search === "string" ? new URLSearchParams(search) : search || new URLSearchParams();

  return {
    status: params.get("status") || "ALL",
    category: params.get("category") || "ALL",
    priority: (params.get("priority") || "ALL").toUpperCase(),
    assigned_to: params.get("assigned_to") || "ALL",
    page: Math.max(1, parseInt(params.get("page") || "1", 10) || 1),
    limit: Math.max(1, parseInt(params.get("limit") || "20", 10) || 20),
  };
}

export const ticketStatusUtils = {
  ACTIONS,
  allowedActions,
  validateResolutionNote,
  validateInternalNote,
  buildAssignPayload,
  buildNotePayload,
  buildStatusPayload,
  filtersToQueryString,
  filtersFromQueryString,
};

export default ticketStatusUtils;
