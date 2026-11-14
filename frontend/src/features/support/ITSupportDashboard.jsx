import { useState, useEffect, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import { useSession, normalizeRole } from "../../auth/session.js";
import { useAuth } from "../../hooks/useAuth.js";
import { supportApi, calculateSLA } from "../../api/supportApi.js";
import TicketFilterBar from "./TicketFilterBar.jsx";
import TicketQueueTable from "./TicketQueueTable.jsx";
import TicketDetailDrawer from "./TicketDetailDrawer.jsx";
import AssignTicketModal from "./AssignTicketModal.jsx";
import EscalateTicketModal from "./EscalateTicketModal.jsx";
import "./support.css";

/**
 * ITSupportDashboard (US-27 & US-28 / Issue #76)
 *
 * IT Support Console for inspecting incoming tickets, filtering by category/status,
 * assigning tickets to self or teammates, logging troubleshooting notes,
 * and resolving or escalating to System Administrator.
 */

const ALLOWED_SUPPORT_ROLES = ["IT_SUPPORT", "ADMIN", "SYSTEM_ADMIN"];

// Priority rank order for sorting
const PRIORITY_ORDER = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

// Status rank order for sorting
const STATUS_ORDER = {
  open: 1,
  in_progress: 2,
  escalated: 3,
  resolved: 4,
  closed: 5,
};

export default function ITSupportDashboard() {
  const session = useSession();
  const auth = useAuth();

  // Active user resolution
  const user = session?.user || auth?.user || null;
  const rawRole = user?.role || user?.user_type || "";
  const normalizedUserRole = normalizeRole(rawRole);

  // In DEV environment, allow role switching for testing accessibility
  const [devRoleOverride, setDevRoleOverride] = useState(() => {
    if (typeof window !== "undefined" && window.__wmsDevSupportRole) {
      return window.__wmsDevSupportRole;
    }
    return "";
  });

  const effectiveRole = devRoleOverride || normalizedUserRole;
  const isAuthorized =
    ALLOWED_SUPPORT_ROLES.includes(effectiveRole) ||
    // Default to authorized in DEV mode if no role is explicitly set
    (import.meta.env?.DEV && !effectiveRole);

  // Tickets state
  const [tickets, setTickets] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);

  // Active drawer & modals state
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [assignModalTicket, setAssignModalTicket] = useState(null);
  const [escalateModalTicket, setEscalateModalTicket] = useState(null);
  const [isAssigningId, setIsAssigningId] = useState(null);

  // Filters state
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [priorityFilter, setPriorityFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  // Sort state
  const [sortField, setSortField] = useState("priority");
  const [sortDirection, setSortDirection] = useState("desc");

  // Load tickets from API
  const refreshTickets = useCallback(async () => {
    try {
      setIsRefreshing(true);
      setErrorMessage(null);

      const data = await supportApi.getTickets({
        category: categoryFilter,
        status: statusFilter,
        priority: priorityFilter,
      });

      setTickets(data);

      setSelectedTicket((prev) => {
        if (!prev) return null;
        const fresh = data.find((t) => t.id === prev.id);
        return fresh || prev;
      });
    } catch (err) {
      setErrorMessage(
        err?.message || "Failed to load support tickets. Please check server connection."
      );
    } finally {
      setIsRefreshing(false);
    }
  }, [categoryFilter, statusFilter, priorityFilter]);

  useEffect(() => {
    let ignore = false;

    async function loadInitial() {
      try {
        setIsLoading(true);
        setErrorMessage(null);

        const data = await supportApi.getTickets({
          category: categoryFilter,
          status: statusFilter,
          priority: priorityFilter,
        });

        if (ignore) return;
        setTickets(data);

        setSelectedTicket((prev) => {
          if (!prev) return null;
          const fresh = data.find((t) => t.id === prev.id);
          return fresh || prev;
        });
      } catch (err) {
        if (!ignore) {
          setErrorMessage(
            err?.message || "Failed to load support tickets. Please check server connection."
          );
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    loadInitial();

    return () => {
      ignore = true;
    };
  }, [categoryFilter, statusFilter, priorityFilter]);

  // Auto-dismiss feedback toast
  useEffect(() => {
    if (!toastMessage) return;
    const timer = setTimeout(() => setToastMessage(null), 4000);
    return () => clearTimeout(timer);
  }, [toastMessage]);

  // One-click "Assign to Me" action: updates UI badge to IN_PROGRESS without page reload
  const handleAssignToMe = async (ticket) => {
    const currentEmpId = user?.account_id || user?.emp_id || "IT-101";
    const currentEmail = user?.email || "it.specialist@worksphere.internal";
    const currentName = user?.email
      ? user.email.split("@")[0].replace(".", " ")
      : "IT Specialist";

    setIsAssigningId(ticket.id);

    // 1. Optimistic UI update: update badge to IN_PROGRESS immediately without reload
    const nowIso = new Date().toISOString();
    const optimisticActivity = {
      id: Date.now(),
      activity_id: Date.now(),
      ticket_id: ticket.id,
      actor_id: currentEmpId,
      actor_name: currentName,
      action: "ASSIGNED",
      activity_type: "ASSIGNED",
      note: `Assigned to ${currentName} (${currentEmail})`,
      old_status: ticket.status,
      new_status: "in_progress",
      created_at: nowIso,
    };

    setTickets((prev) =>
      prev.map((t) => {
        if (t.id === ticket.id) {
          return {
            ...t,
            assigned_to: currentEmpId,
            assigned_to_emp_id: currentEmpId,
            assignee_name: currentName,
            assignee_email: currentEmail,
            status: "in_progress",
            updated_at: nowIso,
            activities: [...(t.activities || []), optimisticActivity],
          };
        }
        return t;
      })
    );

    if (selectedTicket?.id === ticket.id) {
      setSelectedTicket((prev) => ({
        ...prev,
        assigned_to: currentEmpId,
        assigned_to_emp_id: currentEmpId,
        assignee_name: currentName,
        assignee_email: currentEmail,
        status: "in_progress",
        updated_at: nowIso,
        activities: [...(prev.activities || []), optimisticActivity],
      }));
    }

    try {
      // 2. API call to persist assignment
      const updated = await supportApi.assignTicket(ticket.id, {
        assigned_to: currentEmpId,
        assigned_to_emp_id: currentEmpId,
        assignee_name: currentName,
        assignee_email: currentEmail,
        reassignment_reason: "Claimed via IT Support Triage Queue (Assign to Me)",
      });

      // Synchronize with server confirmation
      if (updated) {
        setTickets((prev) => prev.map((t) => (t.id === ticket.id ? updated : t)));
        if (selectedTicket?.id === ticket.id) {
          setSelectedTicket(updated);
        }
      }

      setToastMessage({
        type: "success",
        text: `Ticket #${ticket.ticket_number} assigned to you and set to IN_PROGRESS.`,
      });
    } catch (err) {
      // Revert if API failed
      setToastMessage({
        type: "error",
        text: `Failed to assign ticket: ${err.message}`,
      });
      refreshTickets();
    } finally {
      setIsAssigningId(null);
    }
  };

  // Add Internal Note: instantly appends to activity timeline without page reload
  const handleAddInternalNote = async (ticketId, noteText) => {
    const actorName = user?.email
      ? user.email.split("@")[0].replace(".", " ")
      : "IT Specialist";
    const actorId = user?.account_id || user?.emp_id || "current-user";
    const nowIso = new Date().toISOString();

    const optimisticActivity = {
      id: Date.now(),
      activity_id: Date.now(),
      ticket_id: Number(ticketId),
      actor_id: actorId,
      actor_name: actorName,
      action: "NOTE_ADDED",
      activity_type: "NOTE_ADDED",
      note: noteText,
      old_status: null,
      new_status: null,
      created_at: nowIso,
    };

    // Instant append to local state and drawer timeline
    setSelectedTicket((prev) => {
      if (!prev || prev.id !== Number(ticketId)) return prev;
      return {
        ...prev,
        updated_at: nowIso,
        activities: [...(prev.activities || []), optimisticActivity],
      };
    });

    setTickets((prev) =>
      prev.map((t) => {
        if (t.id === Number(ticketId)) {
          return {
            ...t,
            updated_at: nowIso,
            activities: [...(t.activities || []), optimisticActivity],
          };
        }
        return t;
      })
    );

    try {
      const serverActivity = await supportApi.addInternalNote(ticketId, {
        note_text: noteText,
        actor_name: actorName,
        actor_id: actorId,
      });

      // Update with server confirmed activity ID if returned
      if (serverActivity?.id) {
        setSelectedTicket((prev) => {
          if (!prev) return prev;
          const acts = (prev.activities || []).map((a) =>
            a.id === optimisticActivity.id ? { ...a, ...serverActivity } : a
          );
          return { ...prev, activities: acts };
        });
      }

      setToastMessage({
        type: "success",
        text: "Internal note posted and appended to activity timeline.",
      });
    } catch (err) {
      setToastMessage({
        type: "error",
        text: `Failed to save internal note: ${err.message}`,
      });
    }
  };

  // Confirm Assignment from Modal
  const handleConfirmAssignment = async ({ ticketId, assignedTo, assigneeName, reason }) => {
    const nowIso = new Date().toISOString();
    const optimisticActivity = {
      id: Date.now(),
      activity_id: Date.now(),
      ticket_id: Number(ticketId),
      actor_id: assignedTo,
      actor_name: assigneeName,
      action: "ASSIGNED",
      activity_type: "ASSIGNED",
      note: `Assigned to ${assigneeName}${reason ? ` (${reason})` : ""}`,
      old_status: assignModalTicket?.status || "open",
      new_status: "in_progress",
      created_at: nowIso,
    };

    setTickets((prev) =>
      prev.map((t) => {
        if (t.id === Number(ticketId)) {
          return {
            ...t,
            assigned_to: assignedTo,
            assigned_to_emp_id: assignedTo,
            assignee_name: assigneeName,
            status: "in_progress",
            updated_at: nowIso,
            activities: [...(t.activities || []), optimisticActivity],
          };
        }
        return t;
      })
    );

    if (selectedTicket?.id === Number(ticketId)) {
      setSelectedTicket((prev) => ({
        ...prev,
        assigned_to: assignedTo,
        assigned_to_emp_id: assignedTo,
        assignee_name: assigneeName,
        status: "in_progress",
        updated_at: nowIso,
        activities: [...(prev.activities || []), optimisticActivity],
      }));
    }

    try {
      const updated = await supportApi.assignTicket(ticketId, {
        assigned_to: assignedTo,
        assigned_to_emp_id: assignedTo,
        assignee_name: assigneeName,
        reassignment_reason: reason,
      });

      if (updated) {
        setTickets((prev) => prev.map((t) => (t.id === Number(ticketId) ? updated : t)));
        if (selectedTicket?.id === Number(ticketId)) {
          setSelectedTicket(updated);
        }
      }

      setToastMessage({
        type: "success",
        text: `Ticket assigned to ${assigneeName}.`,
      });
    } catch (err) {
      setToastMessage({
        type: "error",
        text: `Assignment failed: ${err.message}`,
      });
      refreshTickets();
    }
  };

  // Confirm Escalation to SysAdmin with required reason
  const handleConfirmEscalation = async ({ ticketId, escalationReason }) => {
    const actorName = user?.email
      ? user.email.split("@")[0].replace(".", " ")
      : "IT Specialist";
    const nowIso = new Date().toISOString();

    const optimisticActivity = {
      id: Date.now(),
      activity_id: Date.now(),
      ticket_id: Number(ticketId),
      actor_id: user?.account_id || "current-user",
      actor_name: actorName,
      action: "ESCALATED",
      activity_type: "ESCALATED",
      note: `Escalated to SysAdmin: ${escalationReason}`,
      old_status: escalateModalTicket?.status || "open",
      new_status: "escalated",
      created_at: nowIso,
    };

    setTickets((prev) =>
      prev.map((t) => {
        if (t.id === Number(ticketId)) {
          return {
            ...t,
            status: "escalated",
            updated_at: nowIso,
            activities: [...(t.activities || []), optimisticActivity],
          };
        }
        return t;
      })
    );

    if (selectedTicket?.id === Number(ticketId)) {
      setSelectedTicket((prev) => ({
        ...prev,
        status: "escalated",
        updated_at: nowIso,
        activities: [...(prev.activities || []), optimisticActivity],
      }));
    }

    try {
      const updated = await supportApi.escalateTicket(ticketId, {
        escalation_reason: escalationReason,
        actor_name: actorName,
        actor_id: user?.account_id,
      });

      if (updated) {
        setTickets((prev) => prev.map((t) => (t.id === Number(ticketId) ? updated : t)));
        if (selectedTicket?.id === Number(ticketId)) {
          setSelectedTicket(updated);
        }
      }

      setToastMessage({
        type: "success",
        text: "Ticket successfully escalated to System Administrator.",
      });
    } catch (err) {
      setToastMessage({
        type: "error",
        text: `Escalation failed: ${err.message}`,
      });
      refreshTickets();
    }
  };

  // Direct status resolution
  const handleResolveTicket = async (ticketId, resolutionNotes) => {
    const actorName = user?.email
      ? user.email.split("@")[0].replace(".", " ")
      : "IT Specialist";
    const nowIso = new Date().toISOString();

    setTickets((prev) =>
      prev.map((t) => {
        if (t.id === Number(ticketId)) {
          return {
            ...t,
            status: "resolved",
            resolved_at: nowIso,
            updated_at: nowIso,
          };
        }
        return t;
      })
    );

    if (selectedTicket?.id === Number(ticketId)) {
      setSelectedTicket((prev) => ({
        ...prev,
        status: "resolved",
        resolved_at: nowIso,
        updated_at: nowIso,
      }));
    }

    try {
      const updated = await supportApi.updateTicketStatus(ticketId, {
        status: "resolved",
        resolution_notes: resolutionNotes || "Issue resolved by IT specialist",
        actor_name: actorName,
        actor_id: user?.account_id,
      });

      if (updated) {
        setTickets((prev) => prev.map((t) => (t.id === Number(ticketId) ? updated : t)));
        if (selectedTicket?.id === Number(ticketId)) {
          setSelectedTicket(updated);
        }
      }

      setToastMessage({
        type: "success",
        text: "Ticket marked as RESOLVED.",
      });
    } catch (err) {
      setToastMessage({
        type: "error",
        text: `Resolution failed: ${err.message}`,
      });
      refreshTickets();
    }
  };

  // Sorting handler
  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  // Reset filters
  const handleResetFilters = () => {
    setCategoryFilter("ALL");
    setStatusFilter("ALL");
    setPriorityFilter("ALL");
    setSearchQuery("");
  };

  // Filtered and sorted tickets
  const filteredTickets = useMemo(() => {
    let result = [...tickets];

    // Search query
    if (searchQuery.trim()) {
      const query = searchQuery.trim().toLowerCase();
      result = result.filter(
        (t) =>
          t.ticket_number?.toLowerCase().includes(query) ||
          t.subject?.toLowerCase().includes(query) ||
          t.reporter_name?.toLowerCase().includes(query) ||
          t.reporter_email?.toLowerCase().includes(query) ||
          t.description?.toLowerCase().includes(query)
      );
    }

    // Sort
    result.sort((a, b) => {
      let valA, valB;

      switch (sortField) {
        case "ticket_number":
          valA = a.ticket_number || "";
          valB = b.ticket_number || "";
          return sortDirection === "asc"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);

        case "priority":
          valA = PRIORITY_ORDER[a.priority?.toUpperCase()] || 0;
          valB = PRIORITY_ORDER[b.priority?.toUpperCase()] || 0;
          return sortDirection === "asc" ? valA - valB : valB - valA;

        case "status":
          valA = STATUS_ORDER[a.status?.toLowerCase()] || 0;
          valB = STATUS_ORDER[b.status?.toLowerCase()] || 0;
          return sortDirection === "asc" ? valA - valB : valB - valA;

        case "subject":
          valA = a.subject || "";
          valB = b.subject || "";
          return sortDirection === "asc"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);

        case "sla": {
          const slaA = calculateSLA(a);
          const slaB = calculateSLA(b);
          valA = slaA.deadlineDate ? slaA.deadlineDate.getTime() : Infinity;
          valB = slaB.deadlineDate ? slaB.deadlineDate.getTime() : Infinity;
          return sortDirection === "asc" ? valA - valB : valB - valA;
        }

        case "created_at":
        default:
          valA = new Date(a.created_at || 0).getTime();
          valB = new Date(b.created_at || 0).getTime();
          return sortDirection === "asc" ? valA - valB : valB - valA;
      }
    });

    return result;
  }, [tickets, searchQuery, sortField, sortDirection]);

  // Aggregate metrics
  const metrics = useMemo(() => {
    let openCount = 0;
    let inProgressCount = 0;
    let escalatedCount = 0;
    let breachedCount = 0;
    let resolvedCount = 0;

    tickets.forEach((t) => {
      const s = (t.status || "").toLowerCase();
      if (s === "open") openCount++;
      if (s === "in_progress") inProgressCount++;
      if (s === "escalated") escalatedCount++;
      if (s === "resolved" || s === "closed") resolvedCount++;

      const sla = calculateSLA(t);
      if (sla.isBreached) breachedCount++;
    });

    return {
      open: openCount,
      inProgress: inProgressCount,
      escalated: escalatedCount,
      breached: breachedCount,
      resolved: resolvedCount,
      total: tickets.length,
    };
  }, [tickets]);

  // Role Guard View
  if (!isAuthorized) {
    return (
      <section className="page support-dashboard-page">
        <div className="role-denied-container">
          <div className="role-denied-icon" aria-hidden="true">🔒</div>
          <h2>Restricted Access: IT Support Only</h2>
          <p>
            You are currently logged in with role <strong>{rawRole || "EMPLOYEE"}</strong>.
            The IT Support Triage Queue and Console is strictly restricted to personnel
            holding the <strong>IT_SUPPORT</strong> or <strong>ADMIN</strong> role.
          </p>
          <div className="role-denied-actions">
            <Link to="/dashboard" className="btn-primary">
              Return to Dashboard
            </Link>
            {import.meta.env?.DEV && (
              <button
                type="button"
                className="btn-refresh"
                onClick={() => {
                  setDevRoleOverride("IT_SUPPORT");
                  if (typeof window !== "undefined") {
                    window.__wmsDevSupportRole = "IT_SUPPORT";
                  }
                }}
              >
                Switch to IT_SUPPORT (Dev Preview)
              </button>
            )}
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="page support-dashboard-page" aria-label="IT Support Triage Console">
      {/* Dev role banner */}
      {import.meta.env?.DEV && (
        <div className="dev-role-switcher" role="region" aria-label="Development Role Switcher">
          <span>🛠 Dev Mode: Viewing console as <strong>{effectiveRole || "IT_SUPPORT"}</strong></span>
          <div className="dev-role-controls">
            <label htmlFor="dev-role-select">Role Simulation:</label>
            <select
              id="dev-role-select"
              className="dev-role-select"
              value={effectiveRole}
              onChange={(e) => {
                setDevRoleOverride(e.target.value);
                if (typeof window !== "undefined") {
                  window.__wmsDevSupportRole = e.target.value;
                }
              }}
            >
              <option value="IT_SUPPORT">IT_SUPPORT</option>
              <option value="ADMIN">ADMIN</option>
              <option value="SYSTEM_ADMIN">SYSTEM_ADMIN</option>
              <option value="EMPLOYEE">EMPLOYEE (Test Unauthorized)</option>
            </select>
          </div>
        </div>
      )}

      {/* Page Header */}
      <header className="support-header">
        <div className="support-header-info">
          <div className="page-eyebrow">IT OPERATIONS</div>
          <div className="support-title-row">
            <h1>IT Support Triage Queue</h1>
          </div>
          <p className="page-description">
            Inspect incoming service requests, monitor SLA deadlines, claim tickets, append
            internal investigation notes, and escalate complex issues.
          </p>
        </div>
        <div className="support-header-actions">
          <button
            type="button"
            className="btn-refresh"
            onClick={() => refreshTickets()}
            disabled={isRefreshing || isLoading}
            title="Refresh ticket queue from server"
          >
            <span aria-hidden="true">{isRefreshing ? "⏳" : "🔄"}</span>
            {isRefreshing ? "Refreshing..." : "Refresh Queue"}
          </button>
        </div>
      </header>

      {/* Toast Feedback */}
      {toastMessage && (
        <div className={`support-alert-banner alert-${toastMessage.type}`} role="status">
          <span>{toastMessage.text}</span>
          <button
            type="button"
            className="alert-close-btn"
            onClick={() => setToastMessage(null)}
            aria-label="Dismiss message"
          >
            ✕
          </button>
        </div>
      )}

      {/* Error Banner */}
      {errorMessage && (
        <div className="support-alert-banner alert-error" role="alert">
          <span>{errorMessage}</span>
          <button
            type="button"
            className="alert-close-btn"
            onClick={() => setErrorMessage(null)}
            aria-label="Dismiss error"
          >
            ✕
          </button>
        </div>
      )}

      {/* KPI Metrics Strip */}
      <div className="support-metrics-strip" aria-label="Triage Queue KPI Summary">
        <div className="metric-card">
          <div className="metric-icon-bubble metric-bubble-open" aria-hidden="true">📥</div>
          <div className="metric-details">
            <span className="metric-number">{metrics.open}</span>
            <span className="metric-label">Open Tickets</span>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon-bubble metric-bubble-progress" aria-hidden="true">⚙️</div>
          <div className="metric-details">
            <span className="metric-number">{metrics.inProgress}</span>
            <span className="metric-label">In Progress</span>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon-bubble metric-bubble-breached" aria-hidden="true">⏱️</div>
          <div className="metric-details">
            <span className="metric-number">{metrics.breached}</span>
            <span className="metric-label">SLA Breached</span>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon-bubble metric-bubble-escalated" aria-hidden="true">⚠️</div>
          <div className="metric-details">
            <span className="metric-number">{metrics.escalated}</span>
            <span className="metric-label">Escalated</span>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon-bubble metric-bubble-resolved" aria-hidden="true">✅</div>
          <div className="metric-details">
            <span className="metric-number">{metrics.resolved}</span>
            <span className="metric-label">Resolved</span>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <TicketFilterBar
        categoryFilter={categoryFilter}
        onCategoryChange={setCategoryFilter}
        statusFilter={statusFilter}
        onStatusChange={setStatusFilter}
        priorityFilter={priorityFilter}
        onPriorityChange={setPriorityFilter}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onResetFilters={handleResetFilters}
        totalCount={tickets.length}
        filteredCount={filteredTickets.length}
      />

      {/* Triage Queue Table */}
      <TicketQueueTable
        tickets={filteredTickets}
        isLoading={isLoading}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={handleSort}
        onSelectTicket={(ticket) => setSelectedTicket(ticket)}
        selectedTicketId={selectedTicket?.id}
        currentUserId={user?.account_id || user?.emp_id}
        onAssignToMe={handleAssignToMe}
        onOpenAssignModal={(ticket) => setAssignModalTicket(ticket)}
        onOpenEscalateModal={(ticket) => setEscalateModalTicket(ticket)}
        isAssigningId={isAssigningId}
      />

      {/* Slide-out Drawer */}
      {selectedTicket && (
        <TicketDetailDrawer
          ticket={selectedTicket}
          onClose={() => setSelectedTicket(null)}
          currentUserId={user?.account_id || user?.emp_id}
          onAssignToMe={handleAssignToMe}
          onOpenAssignModal={(ticket) => setAssignModalTicket(ticket)}
          onOpenEscalateModal={(ticket) => setEscalateModalTicket(ticket)}
          onResolveTicket={handleResolveTicket}
          onAddNote={handleAddInternalNote}
          isAssigning={isAssigningId === selectedTicket.id}
        />
      )}

      {/* Assign Modal */}
      {assignModalTicket && (
        <AssignTicketModal
          ticket={assignModalTicket}
          currentUserId={user?.account_id || user?.emp_id}
          currentUserEmail={user?.email}
          onClose={() => setAssignModalTicket(null)}
          onConfirm={handleConfirmAssignment}
        />
      )}

      {/* Escalate to SysAdmin Modal */}
      {escalateModalTicket && (
        <EscalateTicketModal
          ticket={escalateModalTicket}
          onClose={() => setEscalateModalTicket(null)}
          onConfirm={handleConfirmEscalation}
        />
      )}
    </section>
  );
}
