import { apiClient } from "./client.js";

/**
 * Support Console API Service (S8: US-26, US-27, US-28)
 *
 * Implements API wiring for IT Support Triage Queue and Reporter View:
 * - GET /api/v1/support/tickets (live queue with filters for status, category, priority, assigned_to, page, limit)
 * - GET /api/v1/support/tickets/queue/metrics (aggregate counts by status and unassigned)
 * - GET /api/v1/support/tickets/my (tickets submitted by current user)
 * - POST /api/v1/support/tickets (employee submits new ticket)
 * - GET /api/v1/support/tickets/{id} (detailed ticket with activity history)
 * - PUT /api/v1/support/tickets/{id}/assign (assign to IT staff account: { assignee_account_id })
 * - POST /api/v1/support/tickets/{id}/notes (internal troubleshooting note: { note })
 * - PUT /api/v1/support/tickets/{id}/status (status transition: { status, resolution_note })
 * - PUT /api/v1/support/tickets/{id}/escalate (escalate to SysAdmin: { reason })
 */

// SLA Deadlines by Priority (in milliseconds)
export const SLA_HOURS = {
  CRITICAL: 4,
  HIGH: 8,
  MEDIUM: 24,
  LOW: 48,
};

/**
 * Calculates SLA metrics for a given ticket.
 * @param {Object} ticket
 * @returns {{
 *   status: "ON_TRACK" | "WARNING" | "BREACHED" | "RESOLVED",
 *   label: string,
 *   timeRemainingText: string,
 *   isBreached: boolean,
 *   isAtRisk: boolean,
 *   deadlineDate: Date|null
 * }}
 */
export function calculateSLA(ticket) {
  if (!ticket) {
    return {
      status: "ON_TRACK",
      label: "On Track",
      timeRemainingText: "—",
      isBreached: false,
      isAtRisk: false,
      deadlineDate: null,
    };
  }

  const status = (ticket.status || "").toLowerCase();
  if (status === "resolved" || status === "closed") {
    return {
      status: "RESOLVED",
      label: "Resolved",
      timeRemainingText: "Met SLA",
      isBreached: false,
      isAtRisk: false,
      deadlineDate: null,
    };
  }

  const priority = (ticket.priority || "MEDIUM").toUpperCase();
  const maxHours = SLA_HOURS[priority] || 24;
  const maxMs = maxHours * 3600 * 1000;

  const createdAtTime = new Date(ticket.created_at || Date.now()).getTime();
  const deadlineTime = createdAtTime + maxMs;
  const deadlineDate = new Date(deadlineTime);

  const diffMs = deadlineTime - Date.now();

  if (diffMs <= 0) {
    const overdueMs = Math.abs(diffMs);
    const overdueHours = Math.floor(overdueMs / (3600 * 1000));
    const overdueMins = Math.floor((overdueMs % (3600 * 1000)) / (60 * 1000));
    const formatted =
      overdueHours > 0
        ? `Overdue by ${overdueHours}h ${overdueMins}m`
        : `Overdue by ${overdueMins}m`;

    return {
      status: "BREACHED",
      label: "SLA Breached",
      timeRemainingText: formatted,
      isBreached: true,
      isAtRisk: false,
      deadlineDate,
    };
  }

  // At risk if less than 25% of SLA window or under 2 hours remaining
  const isAtRisk = diffMs < maxMs * 0.25 || diffMs < 2 * 3600 * 1000;
  const remHours = Math.floor(diffMs / (3600 * 1000));
  const remMins = Math.floor((diffMs % (3600 * 1000)) / (60 * 1000));
  const formatted =
    remHours > 0 ? `${remHours}h ${remMins}m left` : `${remMins}m left`;

  return {
    status: isAtRisk ? "WARNING" : "ON_TRACK",
    label: isAtRisk ? "At Risk" : "On Track",
    timeRemainingText: formatted,
    isBreached: false,
    isAtRisk,
    deadlineDate,
  };
}

/**
 * Normalizes a ticket record from the API to guarantee consistent UI properties.
 */
export function normalizeTicket(raw) {
  if (!raw) return null;

  const id = raw.id ?? raw.ticket_id;
  const number = raw.ticket_number || `TKT-${String(id || "").padStart(3, "0")}`;
  const subject = raw.subject || raw.title || "Support Ticket";
  const priority = (raw.priority || "MEDIUM").toUpperCase();
  const status = (raw.status || "open").toLowerCase();
  const category = (raw.category || "other").toLowerCase();

  return {
    id,
    ticket_id: id,
    ticket_number: number,
    subject,
    title: subject,
    description: raw.description || "",
    category,
    priority,
    status,
    escalation_reason: raw.escalation_reason || null,
    reporter_id: raw.reporter_id || "",
    reporter_name: raw.reporter_name || raw.reporter?.full_name || (raw.reporter_id ? `Employee #${String(raw.reporter_id).slice(0, 8)}` : "Employee"),
    reporter_email: raw.reporter_email || raw.reporter?.email || "",
    reporter_department: raw.reporter_department || raw.reporter?.department || "General",
    assigned_to: raw.assigned_to || null,
    assigned_to_emp_id: raw.assigned_to || raw.assigned_to_emp_id || raw.assignee?.emp_id || null,
    assignee_name: raw.assignee_name || raw.assignee?.full_name || (raw.assigned_to ? "IT Specialist" : null),
    assignee_email: raw.assignee_email || raw.assignee?.email || null,
    created_at: raw.created_at || new Date().toISOString(),
    updated_at: raw.updated_at || raw.created_at || new Date().toISOString(),
    resolved_at: raw.resolved_at || null,
    activities: Array.isArray(raw.activities) ? raw.activities : [],
  };
}

export const supportApi = {
  /**
   * Fetch aggregate triage queue metrics for dashboard header.
   * Endpoint: GET /api/v1/support/tickets/queue/metrics
   * @returns {Promise<{ open: number, in_progress: number, resolved: number, closed: number, escalated: number, unassigned: number, total: number }>}
   */
  getQueueMetrics: async () => {
    const response = await apiClient.get("/api/v1/support/tickets/queue/metrics");
    return {
      open: response?.open ?? 0,
      in_progress: response?.in_progress ?? 0,
      resolved: response?.resolved ?? 0,
      closed: response?.closed ?? 0,
      escalated: response?.escalated ?? 0,
      unassigned: response?.unassigned ?? 0,
      total: response?.total ?? 0,
    };
  },

  /**
   * Fetch live tickets with server-side filtering, priority sorting, and pagination.
   * Primary: GET /api/v1/support/tickets
   * @param {{ status?: string, category?: string, priority?: string, assigned_to?: string, page?: number, limit?: number }} filters
   * @returns {Promise<{ items: Array<Object>, total: number, page: number, limit: number }>}
   */
  getTickets: async (filters = {}) => {
    const params = new URLSearchParams();

    if (filters.status && filters.status !== "ALL" && filters.status !== "all") {
      params.append("status", filters.status.toLowerCase().trim());
    }
    if (filters.category && filters.category !== "ALL" && filters.category !== "all") {
      params.append("category", filters.category.toLowerCase().trim());
    }
    if (filters.priority && filters.priority !== "ALL" && filters.priority !== "all") {
      params.append("priority", filters.priority.toUpperCase().trim());
    }
    if (filters.assigned_to && filters.assigned_to !== "ALL" && filters.assigned_to !== "all") {
      params.append("assigned_to", filters.assigned_to.trim());
    }
    if (filters.page !== undefined && Number(filters.page) >= 1) {
      params.append("page", String(filters.page));
    }
    if (filters.limit !== undefined && Number(filters.limit) >= 1) {
      params.append("limit", String(filters.limit));
    }

    const queryString = params.toString();
    const endpoint = `/api/v1/support/tickets${queryString ? `?${queryString}` : ""}`;

    const response = await apiClient.get(endpoint);

    const rawList = Array.isArray(response)
      ? response
      : response?.items || response?.tickets || [];

    const normalizedItems = rawList.map(normalizeTicket);

    return {
      items: normalizedItems,
      total: response?.total ?? normalizedItems.length,
      page: response?.page ?? Number(filters.page || 1),
      limit: response?.limit ?? Number(filters.limit || 20),
      // Retain array behavior if caller iterates directly over result
      [Symbol.iterator]: function* () {
        yield* normalizedItems;
      },
    };
  },

  /**
   * Retrieve all support tickets reported by the currently authenticated user (US-26).
   * Endpoint: GET /api/v1/support/tickets/my
   * @returns {Promise<Array<Object>>}
   */
  getMyTickets: async () => {
    const response = await apiClient.get("/api/v1/support/tickets/my");
    const list = Array.isArray(response) ? response : response?.tickets || [];
    return list.map(normalizeTicket);
  },

  /**
   * Submit a new support ticket as an employee (US-26).
   * Endpoint: POST /api/v1/support/tickets
   * @param {{ subject?: string, title?: string, description: string, category?: string, priority?: string }} payload
   * @returns {Promise<Object>}
   */
  createTicket: async ({ subject, title, description, category = "other", priority = "MEDIUM" }) => {
    const textSubject = (subject || title || "").trim();
    const payload = {
      subject: textSubject,
      title: textSubject,
      description: (description || "").trim(),
      category: (category || "other").toLowerCase(),
      priority: (priority || "MEDIUM").toUpperCase(),
    };
    const response = await apiClient.post("/api/v1/support/tickets", payload);
    return normalizeTicket(response);
  },

  /**
   * Fetch single ticket details by ID with chronological activities.
   * Primary: GET /api/v1/support/tickets/{id}
   * @param {number|string} ticketId
   * @returns {Promise<Object>}
   */
  getTicketDetail: async (ticketId) => {
    const response = await apiClient.get(`/api/v1/support/tickets/${ticketId}`);
    return normalizeTicket(response);
  },

  getTicket: async (ticketId) => {
    return supportApi.getTicketDetail(ticketId);
  },

  /**
   * Assign a support ticket to an IT specialist account (UUID).
   * Contract: PUT /api/v1/support/tickets/{id}/assign -> { assignee_account_id: "<uuid>" }
   * @param {number|string} ticketId
   * @param {{ assignee_account_id?: string, assigned_to?: string, assigned_to_emp_id?: string }} params
   * @returns {Promise<Object>}
   */
  assignTicket: async (ticketId, { assignee_account_id, assigned_to, assigned_to_emp_id }) => {
    const accountId = assignee_account_id || assigned_to || assigned_to_emp_id;
    const payload = {
      assignee_account_id: String(accountId || "").trim(),
    };

    const response = await apiClient.put(`/api/v1/support/tickets/${ticketId}/assign`, payload);
    return normalizeTicket(response);
  },

  /**
   * Append an internal troubleshooting note to a ticket (1–2000 characters).
   * Contract: POST /api/v1/support/tickets/{id}/notes -> { note: "1–2000 chars" }
   * @param {number|string} ticketId
   * @param {{ note?: string, note_text?: string }} params
   * @returns {Promise<Object>}
   */
  addInternalNote: async (ticketId, { note, note_text }) => {
    const text = (note !== undefined ? note : note_text) || "";
    const payload = {
      note: String(text).trim(),
    };

    return await apiClient.post(`/api/v1/support/tickets/${ticketId}/notes`, payload);
  },

  /**
   * Transition ticket status according to state machine rules.
   * Contract: PUT /api/v1/support/tickets/{id}/status -> { status: "lowercase", resolution_note?: "string" }
   * @param {number|string} ticketId
   * @param {{ status: string, resolution_note?: string, resolution_notes?: string }} params
   * @returns {Promise<Object>}
   */
  updateTicketStatus: async (ticketId, { status, resolution_note, resolution_notes }) => {
    const resNote = (resolution_note !== undefined ? resolution_note : resolution_notes) || "";
    const payload = {
      status: String(status || "").toLowerCase().trim(),
    };
    if (resNote && String(resNote).trim()) {
      payload.resolution_note = String(resNote).trim();
    }

    const response = await apiClient.put(`/api/v1/support/tickets/${ticketId}/status`, payload);
    return normalizeTicket(response);
  },

  /**
   * Reopen a resolved ticket (reporter view).
   * Contract: PUT /api/v1/support/tickets/{id}/status -> { status: "open", resolution_note?: comment }
   * @param {number|string} ticketId
   * @param {string} [comment]
   * @returns {Promise<Object>}
   */
  reopenTicket: async (ticketId, comment = "") => {
    const payload = {
      status: "open",
    };
    if (comment && String(comment).trim()) {
      payload.resolution_note = String(comment).trim();
    }
    const response = await apiClient.put(`/api/v1/support/tickets/${ticketId}/status`, payload);
    return normalizeTicket(response);
  },

  /**
   * Escalate ticket to System Admin with required reason.
   * Contract: PUT /api/v1/support/tickets/{id}/escalate -> { reason: "string" }
   * @param {number|string} ticketId
   * @param {{ reason?: string, escalation_reason?: string }} params
   * @returns {Promise<Object>}
   */
  escalateTicket: async (ticketId, { reason, escalation_reason }) => {
    const escalationText = (reason !== undefined ? reason : escalation_reason) || "";
    const payload = {
      reason: String(escalationText).trim(),
    };

    const response = await apiClient.put(`/api/v1/support/tickets/${ticketId}/escalate`, payload);
    return normalizeTicket(response);
  },
};

export default supportApi;
