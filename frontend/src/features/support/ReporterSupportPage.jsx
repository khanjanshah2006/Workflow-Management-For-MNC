import { useState, useEffect, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import { useSession, normalizeRole, IT_STAFF } from "../../auth/session.js";
import { useAuth } from "../../hooks/useAuth.js";
import { supportApi } from "../../api/supportApi.js";
import CreateTicketModal from "./CreateTicketModal.jsx";
import ReopenTicketModal from "./ReopenTicketModal.jsx";
import TicketDetailDrawer from "./TicketDetailDrawer.jsx";
import "./support.css";

/**
 * ReporterSupportPage (US-26: Employee Support Portal / S8-FE-3)
 *
 * Provides internal employees with:
 * - List of their submitted support tickets ("My Tickets")
 * - Live status, priority, and last updated timestamps
 * - "Raise Ticket" modal form
 * - Ticket detail drawer with activity timeline (internal troubleshooting notes masked)
 * - "Reopen Ticket" action for resolved tickets
 */

function formatTimestamp(isoStr) {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoStr;
  }
}

function PriorityBadge({ priority }) {
  const p = (priority || "MEDIUM").toUpperCase();
  const classes = {
    CRITICAL: "badge-priority-critical",
    HIGH: "badge-priority-high",
    MEDIUM: "badge-priority-medium",
    LOW: "badge-priority-low",
  };
  return <span className={`badge-priority ${classes[p] || classes.MEDIUM}`}>{p}</span>;
}

function StatusBadge({ status }) {
  const s = (status || "open").toLowerCase();
  const labels = {
    open: "OPEN",
    in_progress: "IN PROGRESS",
    resolved: "RESOLVED",
    escalated: "ESCALATED",
    closed: "CLOSED",
  };
  const classes = {
    open: "badge-status-open",
    in_progress: "badge-status-in-progress",
    resolved: "badge-status-resolved",
    escalated: "badge-status-escalated",
    closed: "badge-status-closed",
  };
  return (
    <span className={`badge-status ${classes[s] || classes.open}`}>
      {labels[s] || s.toUpperCase()}
    </span>
  );
}

export default function ReporterSupportPage() {
  const session = useSession();
  const auth = useAuth();

  const user = session?.user || auth?.user || null;
  const rawRole = user?.role || user?.user_type || "";
  const role = normalizeRole(rawRole);
  const currentUserId = user?.account_id || user?.id || user?.emp_id || "";
  const isItStaff = IT_STAFF.includes(role);

  const [tickets, setTickets] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [toastMessage, setToastMessage] = useState(null);

  // Filter & Search
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  // Modals & Drawer
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [reopenModalTicket, setReopenModalTicket] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isReopening, setIsReopening] = useState(false);

  // Fetch reporter's tickets
  const fetchMyTickets = useCallback(async () => {
    try {
      setErrorMessage(null);
      const data = await supportApi.getMyTickets();
      const list = Array.isArray(data) ? data : data?.items || [];
      setTickets(list);

      setSelectedTicket((prev) => {
        if (!prev) return null;
        return list.find((t) => t.id === prev.id) || prev;
      });
    } catch (err) {
      setErrorMessage(err?.message || "Failed to load your support tickets.");
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    async function load() {
      try {
        setIsLoading(true);
        const data = await supportApi.getMyTickets();
        if (ignore) return;
        const list = Array.isArray(data) ? data : data?.items || [];
        setTickets(list);
      } catch (err) {
        if (!ignore) {
          setErrorMessage(err?.message || "Failed to load your support tickets.");
        }
      } finally {
        if (!ignore) setIsLoading(false);
      }
    }
    load();
    return () => {
      ignore = true;
    };
  }, []);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchMyTickets();
    setIsRefreshing(false);
  };

  // Toast timer
  useEffect(() => {
    if (!toastMessage) return;
    const t = setTimeout(() => setToastMessage(null), 4500);
    return () => clearTimeout(t);
  }, [toastMessage]);

  // Handle Create Ticket
  const handleCreateTicket = async (payload) => {
    setIsSubmitting(true);
    try {
      const created = await supportApi.createTicket(payload);
      setToastMessage({
        type: "success",
        text: `Ticket #${created.ticket_number} created successfully! IT support has been notified.`,
      });
      setIsCreateOpen(false);
      await fetchMyTickets();
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Reopen Ticket
  const handleConfirmReopen = async ({ ticketId, comment }) => {
    setIsReopening(true);
    try {
      const updated = await supportApi.reopenTicket(ticketId, comment);
      setToastMessage({
        type: "success",
        text: `Ticket #${updated.ticket_number || ticketId} has been reopened and returned to Open status.`,
      });
      setReopenModalTicket(null);
      if (selectedTicket?.id === Number(ticketId)) {
        setSelectedTicket(updated);
      }
      await fetchMyTickets();
    } catch (err) {
      setToastMessage({
        type: "error",
        text: err?.message || "Failed to reopen ticket.",
      });
    } finally {
      setIsReopening(false);
    }
  };

  // Filtered tickets
  const filteredTickets = useMemo(() => {
    let list = [...tickets];
    if (statusFilter !== "ALL") {
      list = list.filter((t) => (t.status || "").toLowerCase() === statusFilter.toLowerCase());
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      list = list.filter(
        (t) =>
          t.ticket_number?.toLowerCase().includes(q) ||
          t.subject?.toLowerCase().includes(q) ||
          t.category?.toLowerCase().includes(q) ||
          t.description?.toLowerCase().includes(q)
      );
    }
    return list;
  }, [tickets, statusFilter, searchQuery]);

  // Metrics summary
  const metrics = useMemo(() => {
    let active = 0;
    let resolved = 0;
    tickets.forEach((t) => {
      const s = (t.status || "").toLowerCase();
      if (s === "open" || s === "in_progress" || s === "escalated") active++;
      if (s === "resolved" || s === "closed") resolved++;
    });
    return { total: tickets.length, active, resolved };
  }, [tickets]);

  return (
    <section className="page support-dashboard-page" aria-label="My Support Tickets">
      {/* Page Header */}
      <header className="support-header">
        <div className="support-header-info">
          <div className="page-eyebrow">EMPLOYEE SELF-SERVICE</div>
          <div className="support-title-row">
            <h1>My Support Tickets</h1>
          </div>
          <p className="page-description">
            Submit service requests to IT Support, check real-time resolution progress,
            and inspect ticket status updates.
          </p>
        </div>
        <div className="support-header-actions">
          {isItStaff && (
            <Link to="/it-support" className="btn-refresh" style={{ textDecoration: "none" }}>
              🛠 Go to IT Triage Queue
            </Link>
          )}
          <button
            type="button"
            className="btn-refresh"
            onClick={handleRefresh}
            disabled={isRefreshing || isLoading}
            title="Refresh ticket list"
          >
            <span aria-hidden="true">{isRefreshing ? "⏳" : "🔄"}</span>
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => setIsCreateOpen(true)}
          >
            + Raise Support Ticket
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

      {/* Summary KPI Cards */}
      <div className="support-metrics-strip" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
        <div className="metric-card">
          <div className="metric-icon-bubble metric-bubble-open" aria-hidden="true">📋</div>
          <div className="metric-details">
            <span className="metric-number">{metrics.total}</span>
            <span className="metric-label">Total Tickets</span>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon-bubble metric-bubble-progress" aria-hidden="true">⚙️</div>
          <div className="metric-details">
            <span className="metric-number">{metrics.active}</span>
            <span className="metric-label">Active / In Progress</span>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon-bubble metric-bubble-resolved" aria-hidden="true">✅</div>
          <div className="metric-details">
            <span className="metric-number">{metrics.resolved}</span>
            <span className="metric-label">Resolved / Closed</span>
          </div>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="ticket-filter-bar" role="search" aria-label="My ticket filters" style={{ marginBottom: "20px" }}>
        <div className="filter-search-group">
          <div className="search-input-wrapper">
            <span className="search-icon" aria-hidden="true">🔍</span>
            <input
              type="search"
              className="filter-search-input"
              placeholder="Search your tickets by # or subject..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search my tickets"
            />
            {searchQuery && (
              <button
                type="button"
                className="clear-search-btn"
                onClick={() => setSearchQuery("")}
                aria-label="Clear search"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        <div className="filter-selects-group">
          <div className="filter-field">
            <label htmlFor="reporter-filter-status" className="filter-label">Status</label>
            <select
              id="reporter-filter-status"
              className="filter-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="ALL">All Statuses</option>
              <option value="open">Open</option>
              <option value="in_progress">In Progress</option>
              <option value="escalated">Escalated</option>
              <option value="resolved">Resolved</option>
              <option value="closed">Closed</option>
            </select>
          </div>

          {(statusFilter !== "ALL" || searchQuery) && (
            <button
              type="button"
              className="btn-reset-filters"
              onClick={() => {
                setStatusFilter("ALL");
                setSearchQuery("");
              }}
            >
              Reset Filters
            </button>
          )}
        </div>

        <div className="filter-results-meta">
          <span className="results-badge">
            Showing <strong>{filteredTickets.length}</strong> of <strong>{tickets.length}</strong> tickets
          </span>
        </div>
      </div>

      {/* Tickets Table */}
      {isLoading ? (
        <div className="table-loading-container" aria-busy="true" aria-live="polite">
          <div className="table-skeleton-row" />
          <div className="table-skeleton-row" />
          <div className="table-skeleton-row" />
          <p className="loading-caption">Loading your support tickets...</p>
        </div>
      ) : filteredTickets.length === 0 ? (
        <div className="table-empty-state">
          <div className="empty-icon" aria-hidden="true">🎫</div>
          <h3>No Support Tickets Found</h3>
          <p>
            {tickets.length === 0
              ? "You haven't submitted any IT support tickets yet. Click 'Raise Support Ticket' to submit one."
              : "No tickets match your filter criteria."}
          </p>
        </div>
      ) : (
        <div className="table-responsive-wrapper">
          <table className="ticket-queue-table" role="table" aria-label="My Support Tickets Table">
            <thead>
              <tr>
                <th scope="col" className="th-ticket">Ticket</th>
                <th scope="col" className="th-priority">Priority</th>
                <th scope="col" className="th-subject">Subject & Category</th>
                <th scope="col" className="th-status">Status</th>
                <th scope="col" className="th-sla">Last Updated</th>
                <th scope="col" className="th-actions">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredTickets.map((ticket) => {
                const isSelected = selectedTicket?.id === ticket.id;
                const isResolved = (ticket.status || "").toLowerCase() === "resolved";

                return (
                  <tr
                    key={ticket.id}
                    className={`ticket-row ${isSelected ? "ticket-row-selected" : ""} status-${ticket.status}`}
                    onClick={() => setSelectedTicket(ticket)}
                    tabIndex={0}
                  >
                    <td className="td-ticket">
                      <div className="ticket-id-cell">
                        <span className="ticket-number-badge">{ticket.ticket_number}</span>
                        <span className="ticket-date-caption">
                          {formatTimestamp(ticket.created_at)}
                        </span>
                      </div>
                    </td>

                    <td className="td-priority">
                      <PriorityBadge priority={ticket.priority} />
                    </td>

                    <td className="td-subject">
                      <div className="subject-cell">
                        <span className="subject-title" title={ticket.subject}>
                          {ticket.subject}
                        </span>
                        <span className="category-tag">
                          {(ticket.category || "other").toUpperCase()}
                        </span>
                      </div>
                    </td>

                    <td className="td-status">
                      <StatusBadge status={ticket.status} />
                    </td>

                    <td className="td-sla">
                      <span style={{ fontSize: "12px", color: "#64748b" }}>
                        {formatTimestamp(ticket.updated_at || ticket.created_at)}
                      </span>
                    </td>

                    <td className="td-actions" onClick={(e) => e.stopPropagation()}>
                      <div className="action-buttons-group">
                        {isResolved && (
                          <button
                            type="button"
                            className="btn-action-takeover"
                            style={{ background: "#fef3c7", borderColor: "#fde68a", color: "#92400e" }}
                            onClick={(e) => {
                              e.stopPropagation();
                              setReopenModalTicket(ticket);
                            }}
                            title="Reopen ticket"
                          >
                            🔄 Reopen
                          </button>
                        )}

                        <button
                          type="button"
                          className="btn-action-inspect"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedTicket(ticket);
                          }}
                          title="View ticket details"
                        >
                          View Details
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Ticket Details Drawer */}
      {selectedTicket && (
        <TicketDetailDrawer
          ticket={selectedTicket}
          onClose={() => setSelectedTicket(null)}
          currentUserId={currentUserId}
          userRole={role}
          isReporter={true}
          onReopenTicket={(t) => setReopenModalTicket(t)}
        />
      )}

      {/* Raise Ticket Modal */}
      <CreateTicketModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSubmit={handleCreateTicket}
        isSubmitting={isSubmitting}
      />

      {/* Reopen Ticket Modal */}
      {reopenModalTicket && (
        <ReopenTicketModal
          ticket={reopenModalTicket}
          onClose={() => setReopenModalTicket(null)}
          onConfirm={handleConfirmReopen}
          isReopening={isReopening}
        />
      )}
    </section>
  );
}
