import { useState, useEffect, useMemo, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useSession, normalizeRole, IT_STAFF } from "../../auth/session.js";
import { useAuth } from "../../hooks/useAuth.js";
import { supportApi, calculateSLA } from "../../api/supportApi.js";
import {
  buildAssignPayload,
  buildNotePayload,
  buildStatusPayload,
  filtersToQueryString,
  filtersFromQueryString,
} from "./ticketStatusUtils.js";
import TicketFilterBar from "./TicketFilterBar.jsx";
import TicketQueueTable from "./TicketQueueTable.jsx";
import TicketDetailDrawer from "./TicketDetailDrawer.jsx";
import AssignTicketModal from "./AssignTicketModal.jsx";
import EscalateTicketModal from "./EscalateTicketModal.jsx";
import ResolveTicketModal from "./ResolveTicketModal.jsx";
import "./support.css";

/**
 * ITSupportDashboard (US-27 & US-28 / Issue #163)
 *
 * IT Support Console for inspecting incoming tickets, filtering by category/status,
 * assigning tickets to self or teammates, logging troubleshooting notes,
 * and resolving or escalating to System Administrator.
 */

const ALLOWED_SUPPORT_ROLES = IT_STAFF;

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
  const [searchParams, setSearchParams] = useSearchParams();

  // Active user resolution
  const user = session?.user || auth?.user || null;
  const rawRole = user?.role || user?.user_type || "";
  const normalizedUserRole = normalizeRole(rawRole);
  const effectiveRole = normalizedUserRole;
  const isAuthorized = ALLOWED_SUPPORT_ROLES.includes(effectiveRole);
  const currentUserId = user?.account_id || user?.id || user?.emp_id || "";

  // Parse filters from URL query string
  const urlFilters = useMemo(() => filtersFromQueryString(searchParams), [searchParams]);

  const [categoryFilter, setCategoryFilter] = useState(urlFilters.category);
  const [statusFilter, setStatusFilter] = useState(urlFilters.status);
  const [priorityFilter, setPriorityFilter] = useState(urlFilters.priority);
  const [assignedToFilter, setAssignedToFilter] = useState(urlFilters.assigned_to);
  const [page, setPage] = useState(urlFilters.page);
  const [limit, setLimit] = useState(urlFilters.limit);
  const [searchQuery, setSearchQuery] = useState("");

  // Keep state in sync with URL searchParams
  useEffect(() => {
    setCategoryFilter(urlFilters.category);
    setStatusFilter(urlFilters.status);
    setPriorityFilter(urlFilters.priority);
    setAssignedToFilter(urlFilters.assigned_to);
    setPage(urlFilters.page);
    setLimit(urlFilters.limit);
  }, [urlFilters]);

  // Synchronize state changes to URL query string
  const syncFiltersToUrl = useCallback(
    (overrides = {}) => {
      const merged = {
        category: categoryFilter,
        status: statusFilter,
        priority: priorityFilter,
        assigned_to: assignedToFilter,
        page,
        limit,
        ...overrides,
      };
      const qs = filtersToQueryString(merged);
      setSearchParams(qs ? new URLSearchParams(qs) : new URLSearchParams(), { replace: true });
    },
    [categoryFilter, statusFilter, priorityFilter, assignedToFilter, page, limit, setSearchParams]
  );

  // Tickets & Metrics state
  const [tickets, setTickets] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [metrics, setMetrics] = useState({
    open: 0,
    in_progress: 0,
    escalated: 0,
    resolved: 0,
    closed: 0,
    unassigned: 0,
    total: 0,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);

  // Active drawer & modals state
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [assignModalTicket, setAssignModalTicket] = useState(null);
  const [escalateModalTicket, setEscalateModalTicket] = useState(null);
  const [resolveModalTicket, setResolveModalTicket] = useState(null);
  const [isAssigningId, setIsAssigningId] = useState(null);

  // Sort state
  const [sortField, setSortField] = useState("priority");
  const [sortDirection, setSortDirection] = useState("desc");

  // Load server-side metrics
  const fetchMetrics = useCallback(async () => {
    try {
      const data = await supportApi.getQueueMetrics();
      if (data) {
        setMetrics({
          open: data.open || 0,
          in_progress: data.in_progress || 0,
          escalated: data.escalated || 0,
          resolved: data.resolved || 0,
          closed: data.closed || 0,
          unassigned: data.unassigned || 0,
          total: data.total || 0,
        });
      }
    } catch {
      // Non-fatal if metrics fails
    }
  }, []);

  // Load tickets from API
  const refreshTickets = useCallback(async () => {
    try {
      setIsRefreshing(true);
      setErrorMessage(null);

      const params = {
        category: categoryFilter,
        status: statusFilter,
        priority: priorityFilter,
        assigned_to: assignedToFilter,
        page,
        limit,
      };

      const result = await supportApi.getTickets(params);

      const items = Array.isArray(result) ? result : result.items || [];
      const total = typeof result.total === "number" ? result.total : items.length;

      setTickets(items);
      setTotalCount(total);

      setSelectedTicket((prev) => {
        if (!prev) return null;
        const fresh = items.find((t) => t.id === prev.id);
        return fresh || prev;
      });

      // Refetch metrics in parallel
      fetchMetrics();
    } catch (err) {
      setErrorMessage(
        err?.message || "Failed to load support tickets. Please check server connection."
      );
    } finally {
      setIsRefreshing(false);
    }
  }, [categoryFilter, statusFilter, priorityFilter, assignedToFilter, page, limit, fetchMetrics]);

  useEffect(() => {
    let ignore = false;

    async function loadInitial() {
      try {
        setIsLoading(true);
        setErrorMessage(null);

        const params = {
          category: categoryFilter,
          status: statusFilter,
          priority: priorityFilter,
          assigned_to: assignedToFilter,
          page,
          limit,
        };

        const [result] = await Promise.all([
          supportApi.getTickets(params),
          fetchMetrics(),
        ]);

        if (ignore) return;
        const items = Array.isArray(result) ? result : result.items || [];
        const total = typeof result.total === "number" ? result.total : items.length;

        setTickets(items);
        setTotalCount(total);

        setSelectedTicket((prev) => {
          if (!prev) return null;
          const fresh = items.find((t) => t.id === prev.id);
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
  }, [categoryFilter, statusFilter, priorityFilter, assignedToFilter, page, limit, fetchMetrics]);

  // Auto-dismiss feedback toast
  useEffect(() => {
    if (!toastMessage) return;
    const timer = setTimeout(() => setToastMessage(null), 4500);
    return () => clearTimeout(timer);
  }, [toastMessage]);

  // Error dispatcher handling 409 conflict & 400 assign errors
  const handleActionError = (err, context = "action") => {
    const status = err?.status || err?.response?.status;
    const msg = String(err?.message || "");

    if (status === 409 || msg.includes("409") || msg.toLowerCase().includes("conflict") || msg.toLowerCase().includes("invalid status")) {
      setToastMessage({
        type: "error",
        text: "Ticket state changed or conflict occurred. Refreshing ticket...",
      });
      refreshTickets();
      return;
    }

    if (context === "assign" && (status === 400 || msg.toLowerCase().includes("it staff") || msg.toLowerCase().includes("assignee"))) {
      setToastMessage({
        type: "error",
        text: "Assignee must be IT staff",
      });
      return;
    }

    setToastMessage({
      type: "error",
      text: msg || `Failed to perform ${context}.`,
    });
  };

  // Filter change handlers syncing to URL
  const handleCategoryChange = (val) => {
    setCategoryFilter(val);
    setPage(1);
    syncFiltersToUrl({ category: val, page: 1 });
  };

  const handleStatusChange = (val) => {
    setStatusFilter(val);
    setPage(1);
    syncFiltersToUrl({ status: val, page: 1 });
  };

  const handlePriorityChange = (val) => {
    setPriorityFilter(val);
    setPage(1);
    syncFiltersToUrl({ priority: val, page: 1 });
  };

  const handleAssignedToChange = (val) => {
    setAssignedToFilter(val);
    setPage(1);
    syncFiltersToUrl({ assigned_to: val, page: 1 });
  };

  const handlePageChange = (newPage) => {
    setPage(newPage);
    syncFiltersToUrl({ page: newPage });
  };

  const handleResetFilters = () => {
    setCategoryFilter("ALL");
    setStatusFilter("ALL");
    setPriorityFilter("ALL");
    setAssignedToFilter("ALL");
    setSearchQuery("");
    setPage(1);
    syncFiltersToUrl({
      category: "ALL",
      status: "ALL",
      priority: "ALL",
      assigned_to: "ALL",
      page: 1,
    });
  };

  // One-click "Assign to Me" action
  const handleAssignToMe = async (ticket) => {
    if (!currentUserId) {
      setToastMessage({ type: "error", text: "Unable to identify current user account." });
      return;
    }

    setIsAssigningId(ticket.id);

    try {
      const payload = buildAssignPayload(currentUserId);
      const updated = await supportApi.assignTicket(ticket.id, payload);

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
      fetchMetrics();
    } catch (err) {
      handleActionError(err, "assign");
    } finally {
      setIsAssigningId(null);
    }
  };

  // Confirm Assignment from Modal
  const handleConfirmAssignment = async ({ ticketId, assignedTo, assigneeName }) => {
    try {
      const payload = buildAssignPayload(assignedTo);
      const updated = await supportApi.assignTicket(ticketId, payload);

      if (updated) {
        setTickets((prev) => prev.map((t) => (t.id === Number(ticketId) ? updated : t)));
        if (selectedTicket?.id === Number(ticketId)) {
          setSelectedTicket(updated);
        }
      }

      setToastMessage({
        type: "success",
        text: `Ticket assigned to ${assigneeName || "IT specialist"}.`,
      });
      setAssignModalTicket(null);
      fetchMetrics();
    } catch (err) {
      handleActionError(err, "assign");
    }
  };

  // Confirm Escalation to SysAdmin
  const handleConfirmEscalation = async ({ ticketId, escalationReason }) => {
    try {
      const updated = await supportApi.escalateTicket(ticketId, {
        reason: escalationReason,
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
      setEscalateModalTicket(null);
      fetchMetrics();
    } catch (err) {
      handleActionError(err, "escalate");
    }
  };

  // Confirm Ticket Resolution
  const handleConfirmResolution = async ({ ticketId, resolutionNote }) => {
    try {
      const payload = buildStatusPayload("resolved", resolutionNote);
      const updated = await supportApi.updateTicketStatus(ticketId, payload);

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
      setResolveModalTicket(null);
      fetchMetrics();
    } catch (err) {
      handleActionError(err, "resolve");
    }
  };

  // SysAdmin Take Over escalated ticket
  const handleTakeOver = async (ticket) => {
    try {
      const payload = buildStatusPayload("in_progress");
      const updated = await supportApi.updateTicketStatus(ticket.id, payload);

      if (updated) {
        setTickets((prev) => prev.map((t) => (t.id === ticket.id ? updated : t)));
        if (selectedTicket?.id === ticket.id) {
          setSelectedTicket(updated);
        }
      }

      setToastMessage({
        type: "success",
        text: `Ticket #${ticket.ticket_number} taken over and set to IN_PROGRESS.`,
      });
      fetchMetrics();
    } catch (err) {
      handleActionError(err, "take_over");
    }
  };

  // Close resolved ticket
  const handleCloseTicket = async (ticket) => {
    try {
      const payload = buildStatusPayload("closed");
      const updated = await supportApi.updateTicketStatus(ticket.id, payload);

      if (updated) {
        setTickets((prev) => prev.map((t) => (t.id === ticket.id ? updated : t)));
        if (selectedTicket?.id === ticket.id) {
          setSelectedTicket(updated);
        }
      }

      setToastMessage({
        type: "success",
        text: `Ticket #${ticket.ticket_number} marked as CLOSED.`,
      });
      fetchMetrics();
    } catch (err) {
      handleActionError(err, "close");
    }
  };

  // Add Internal Troubleshooting Note
  const handleAddInternalNote = async (ticketId, noteText) => {
    try {
      const payload = buildNotePayload(noteText);
      await supportApi.addInternalNote(ticketId, payload);

      // Refresh ticket details to retrieve updated timeline
      const freshTicket = await supportApi.getTicket(ticketId);
      if (freshTicket) {
        setTickets((prev) => prev.map((t) => (t.id === Number(ticketId) ? freshTicket : t)));
        if (selectedTicket?.id === Number(ticketId)) {
          setSelectedTicket(freshTicket);
        }
      }

      setToastMessage({
        type: "success",
        text: "Internal note posted and appended to activity timeline.",
      });
    } catch (err) {
      handleActionError(err, "add_note");
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

  // Filtered and sorted tickets
  const filteredTickets = useMemo(() => {
    let result = [...tickets];

    // Client-side text search query
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

  const totalPages = Math.max(1, Math.ceil(totalCount / limit));

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
            holding the <strong>IT_SUPPORT</strong> or <strong>SYSTEM_ADMIN</strong> role.
          </p>
          <div className="role-denied-actions">
            <Link to="/support" className="btn-primary">
              Go to My Support Tickets
            </Link>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="page support-dashboard-page" aria-label="IT Support Triage Console">
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

      {/* Server-Side KPI Metrics Strip */}
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
            <span className="metric-number">{metrics.in_progress}</span>
            <span className="metric-label">In Progress</span>
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

        <div className="metric-card">
          <div className="metric-icon-bubble metric-bubble-unassigned" aria-hidden="true">👤</div>
          <div className="metric-details">
            <span className="metric-number">{metrics.unassigned}</span>
            <span className="metric-label">Unassigned</span>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <TicketFilterBar
        categoryFilter={categoryFilter}
        onCategoryChange={handleCategoryChange}
        statusFilter={statusFilter}
        onStatusChange={handleStatusChange}
        priorityFilter={priorityFilter}
        onPriorityChange={handlePriorityChange}
        assignedToFilter={assignedToFilter}
        onAssignedToChange={handleAssignedToChange}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onResetFilters={handleResetFilters}
        totalCount={totalCount}
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
        currentUserId={currentUserId}
        userRole={effectiveRole}
        onAssignToMe={handleAssignToMe}
        onOpenAssignModal={(ticket) => setAssignModalTicket(ticket)}
        onOpenEscalateModal={(ticket) => setEscalateModalTicket(ticket)}
        onOpenResolveModal={(ticket) => setResolveModalTicket(ticket)}
        onTakeOver={handleTakeOver}
        onCloseTicket={handleCloseTicket}
        isAssigningId={isAssigningId}
        page={page}
        totalPages={totalPages}
        onPageChange={handlePageChange}
      />

      {/* Slide-out Drawer */}
      {selectedTicket && (
        <TicketDetailDrawer
          ticket={selectedTicket}
          onClose={() => setSelectedTicket(null)}
          currentUserId={currentUserId}
          userRole={effectiveRole}
          onAssignToMe={handleAssignToMe}
          onOpenAssignModal={(ticket) => setAssignModalTicket(ticket)}
          onOpenEscalateModal={(ticket) => setEscalateModalTicket(ticket)}
          onOpenResolveModal={(ticket) => setResolveModalTicket(ticket)}
          onTakeOver={handleTakeOver}
          onCloseTicket={handleCloseTicket}
          onAddNote={handleAddInternalNote}
          isAssigning={isAssigningId === selectedTicket.id}
        />
      )}

      {/* Assign Modal */}
      {assignModalTicket && (
        <AssignTicketModal
          ticket={assignModalTicket}
          currentUserId={currentUserId}
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

      {/* Resolve Ticket Modal */}
      {resolveModalTicket && (
        <ResolveTicketModal
          ticket={resolveModalTicket}
          onClose={() => setResolveModalTicket(null)}
          onConfirm={handleConfirmResolution}
        />
      )}
    </section>
  );
}
