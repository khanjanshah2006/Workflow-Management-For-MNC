import { apiClient } from "./client.js";
import {
  getMockTickets,
  updateMockTicket,
} from "../features/support/mockSupportData.js";

/**
 * Support Console API Service (S8: US-27 & US-28)
 *
 * Implements API wiring for IT Support Triage Queue:
 * - GET /api/v1/support/tickets (with filters for status, category, priority, assignee)
 * - GET /api/v1/support/tickets/{id} (detailed ticket with activity history)
 * - PUT /api/v1/support/tickets/{id}/assign (assign to self or teammate)
 * - POST /api/v1/support/tickets/{id}/notes (internal troubleshooting notes)
 * - PUT /api/v1/support/tickets/{id}/status (status transition e.g. RESOLVED)
 * - PUT /api/v1/support/tickets/{id}/escalate (escalate to SysAdmin)
 *
 * Includes graceful DEV fallback to mock data when backend is not running or endpoints return 404.
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
    reporter_id: raw.reporter_id || "",
    reporter_name: raw.reporter_name || raw.reporter?.full_name || `Employee #${String(raw.reporter_id || "").slice(0, 6)}`,
    reporter_email: raw.reporter_email || raw.reporter?.email || "",
    reporter_department: raw.reporter_department || raw.reporter?.department || "General",
    assigned_to: raw.assigned_to || null,
    assigned_to_emp_id: raw.assigned_to_emp_id || raw.assignee?.emp_id || null,
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
   * Fetch all tickets with optional filtering by category, status, priority, and assignee.
   * Primary: GET /api/v1/support/tickets
   */
  getTickets: async (filters = {}) => {
    const params = new URLSearchParams();

    if (filters.status && filters.status !== "ALL" && filters.status !== "all") {
      params.append("status", filters.status.toLowerCase());
    }
    if (filters.category && filters.category !== "ALL" && filters.category !== "all") {
      params.append("category", filters.category.toLowerCase());
    }
    if (filters.priority && filters.priority !== "ALL" && filters.priority !== "all") {
      params.append("priority", filters.priority.toUpperCase());
    }
    if (filters.assigned_to) {
      params.append("assigned_to", filters.assigned_to);
    }
    if (filters.skip !== undefined) {
      params.append("skip", String(filters.skip));
    }
    if (filters.limit !== undefined) {
      params.append("limit", String(filters.limit));
    }

    const queryString = params.toString();
    const endpoint = `/api/v1/support/tickets${queryString ? `?${queryString}` : ""}`;

    try {
      const response = await apiClient.get(endpoint);
      const rawList = Array.isArray(response)
        ? response
        : response?.tickets || [];

      return rawList.map(normalizeTicket);
    } catch (err) {
      // In DEV mode, fallback to rich mock data if backend is offline or endpoint 404
      if (import.meta.env?.DEV && (err.status === 0 || err.status === 404)) {
        let list = getMockTickets();
        if (filters.status && filters.status !== "ALL" && filters.status !== "all") {
          list = list.filter((t) => t.status.toLowerCase() === filters.status.toLowerCase());
        }
        if (filters.category && filters.category !== "ALL" && filters.category !== "all") {
          list = list.filter((t) => t.category.toLowerCase() === filters.category.toLowerCase());
        }
        if (filters.priority && filters.priority !== "ALL" && filters.priority !== "all") {
          list = list.filter((t) => t.priority.toUpperCase() === filters.priority.toUpperCase());
        }
        return list.map(normalizeTicket);
      }
      throw err;
    }
  },

  /**
   * Fetch single ticket details by ID with chronological activities.
   * Primary: GET /api/v1/support/tickets/{id}
   */
  getTicketDetail: async (ticketId) => {
    try {
      const response = await apiClient.get(`/api/v1/support/tickets/${ticketId}`);
      return normalizeTicket(response);
    } catch (err) {
      if (import.meta.env?.DEV && (err.status === 0 || err.status === 404)) {
        const mock = getMockTickets().find((t) => t.id === Number(ticketId));
        if (mock) return normalizeTicket(mock);
      }
      throw err;
    }
  },

  /**
   * Assign a support ticket to an IT specialist or self.
   * Wiring: PUT /api/v1/support/tickets/{id}/assign -> { "assigned_to_emp_id": current_user.emp_id }
   */
  assignTicket: async (ticketId, { assigned_to, assigned_to_emp_id, assignee_name, assignee_email, reassignment_reason }) => {
    const payload = {
      assigned_to: assigned_to || assigned_to_emp_id,
      assigned_to_emp_id: assigned_to_emp_id || assigned_to,
      reassignment_reason: reassignment_reason || "Assigned via IT Support Console",
    };

    try {
      const response = await apiClient.put(`/api/v1/support/tickets/${ticketId}/assign`, payload);
      return normalizeTicket(response);
    } catch (err) {
      if (import.meta.env?.DEV && (err.status === 0 || err.status === 404)) {
        const updated = updateMockTicket(ticketId, (ticket) => {
          const nowIso = new Date().toISOString();
          const newActivities = [
            ...(ticket.activities || []),
            {
              id: Date.now(),
              activity_id: Date.now(),
              ticket_id: ticket.id,
              actor_id: assigned_to || "it-support-agent",
              actor_name: assignee_name || "IT Support Specialist",
              action: "ASSIGNED",
              activity_type: "ASSIGNED",
              note: `Assigned to ${assignee_name || assignee_email || assigned_to_emp_id || "IT Specialist"}${reassignment_reason ? ` (${reassignment_reason})` : ""}`,
              old_status: ticket.status,
              new_status: ticket.status === "open" ? "in_progress" : ticket.status,
              created_at: nowIso,
            },
          ];

          return {
            ...ticket,
            assigned_to: assigned_to || assigned_to_emp_id,
            assigned_to_emp_id: assigned_to_emp_id || assigned_to,
            assignee_name: assignee_name || "IT Support Specialist",
            assignee_email: assignee_email || "",
            status: ticket.status === "open" ? "in_progress" : ticket.status,
            updated_at: nowIso,
            activities: newActivities,
          };
        });
        return normalizeTicket(updated);
      }
      throw err;
    }
  },

  /**
   * Append an internal troubleshooting note to a ticket.
   * Wiring: POST /api/v1/support/tickets/{id}/notes -> { "note_text": "string" }
   */
  addInternalNote: async (ticketId, { note_text, note, actor_name, actor_id }) => {
    const text = note_text || note;
    const payload = {
      note_text: text,
      note: text,
    };

    try {
      const response = await apiClient.post(`/api/v1/support/tickets/${ticketId}/notes`, payload);
      return response;
    } catch (err) {
      if (import.meta.env?.DEV && (err.status === 0 || err.status === 404)) {
        const nowIso = new Date().toISOString();
        const newActivity = {
          id: Date.now(),
          activity_id: Date.now(),
          ticket_id: Number(ticketId),
          actor_id: actor_id || "current-user",
          actor_name: actor_name || "IT Support Specialist",
          action: "NOTE_ADDED",
          activity_type: "NOTE_ADDED",
          note: text,
          old_status: null,
          new_status: null,
          created_at: nowIso,
        };

        updateMockTicket(ticketId, (ticket) => ({
          ...ticket,
          updated_at: nowIso,
          activities: [...(ticket.activities || []), newActivity],
        }));

        return newActivity;
      }
      throw err;
    }
  },

  /**
   * Transition ticket status (e.g. to in_progress, resolved).
   * Wiring: PUT /api/v1/support/tickets/{id}/status -> { "status": "RESOLVED", "resolution_notes": "..." }
   */
  updateTicketStatus: async (ticketId, { status, resolution_notes, actor_name, actor_id }) => {
    const payload = {
      status: status.toLowerCase(),
      resolution_notes: resolution_notes || undefined,
    };

    try {
      const response = await apiClient.put(`/api/v1/support/tickets/${ticketId}/status`, payload);
      return normalizeTicket(response);
    } catch (err) {
      if (import.meta.env?.DEV && (err.status === 0 || err.status === 404)) {
        const updated = updateMockTicket(ticketId, (ticket) => {
          const nowIso = new Date().toISOString();
          const isResolved = status.toLowerCase() === "resolved";
          const newActivities = [
            ...(ticket.activities || []),
            {
              id: Date.now(),
              activity_id: Date.now(),
              ticket_id: ticket.id,
              actor_id: actor_id || "current-user",
              actor_name: actor_name || "IT Support Specialist",
              action: "STATUS_CHANGED",
              activity_type: "STATUS_CHANGED",
              note: resolution_notes || `Status changed from ${ticket.status} to ${status.toLowerCase()}`,
              old_status: ticket.status,
              new_status: status.toLowerCase(),
              created_at: nowIso,
            },
          ];

          return {
            ...ticket,
            status: status.toLowerCase(),
            resolved_at: isResolved ? nowIso : ticket.resolved_at,
            updated_at: nowIso,
            activities: newActivities,
          };
        });
        return normalizeTicket(updated);
      }
      throw err;
    }
  },

  /**
   * Escalate ticket to System Admin with required reason.
   * Wiring: PUT /api/v1/support/tickets/{id}/escalate -> { "escalation_reason": "string" }
   */
  escalateTicket: async (ticketId, { escalation_reason, reason, actor_name, actor_id }) => {
    const escalationText = escalation_reason || reason;
    const payload = {
      escalation_reason: escalationText,
      reason: escalationText,
    };

    try {
      try {
        const response = await apiClient.put(`/api/v1/support/tickets/${ticketId}/escalate`, payload);
        return normalizeTicket(response);
      } catch (firstErr) {
        // If /escalate route returns 404 or 405, fallback to status transition with "escalated"
        if (firstErr.status === 404 || firstErr.status === 405) {
          const fallbackRes = await apiClient.put(`/api/v1/support/tickets/${ticketId}/status`, {
            status: "escalated",
            resolution_notes: `Escalated to SysAdmin: ${escalationText}`,
          });
          return normalizeTicket(fallbackRes);
        }
        throw firstErr;
      }
    } catch (err) {
      if (import.meta.env?.DEV && (err.status === 0 || err.status === 404)) {
        const updated = updateMockTicket(ticketId, (ticket) => {
          const nowIso = new Date().toISOString();
          const newActivities = [
            ...(ticket.activities || []),
            {
              id: Date.now(),
              activity_id: Date.now(),
              ticket_id: ticket.id,
              actor_id: actor_id || "current-user",
              actor_name: actor_name || "IT Support Specialist",
              action: "ESCALATED",
              activity_type: "ESCALATED",
              note: `Escalated to SysAdmin: ${escalationText}`,
              old_status: ticket.status,
              new_status: "escalated",
              created_at: nowIso,
            },
          ];

          return {
            ...ticket,
            status: "escalated",
            updated_at: nowIso,
            activities: newActivities,
          };
        });
        return normalizeTicket(updated);
      }
      throw err;
    }
  },
};
