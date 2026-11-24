import { calculateSLA } from "../../api/supportApi.js";
import { allowedActions, ACTIONS } from "./ticketStatusUtils.js";

/**
 * TicketQueueTable Component (US-27: IT Support Triage Queue)
 *
 * Displays sortable, responsive IT support triage queue table with:
 * - Priority badges (CRITICAL, HIGH, MEDIUM, LOW)
 * - Dynamic SLA indicators (On Track, At Risk, Breached)
 * - Status badges (open, in_progress, escalated, resolved, closed)
 * - Interactive sorting by columns
 * - Actions governed strictly by allowedActions(ticket, userRole)
 * - "Awaiting SysAdmin" chip for escalated tickets when viewed by IT_SUPPORT
 * - Drawer inspection trigger
 * - Integrated pagination controls
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

  const icons = {
    CRITICAL: "🔴",
    HIGH: "🟠",
    MEDIUM: "🔵",
    LOW: "⚪",
  };

  return (
    <span className={`badge-priority ${classes[p] || classes.MEDIUM}`} title={`Priority: ${p}`}>
      <span className="badge-dot" aria-hidden="true">{icons[p]}</span>
      {p}
    </span>
  );
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

function SlaIndicator({ ticket }) {
  const sla = calculateSLA(ticket);

  const classes = {
    ON_TRACK: "sla-on-track",
    WARNING: "sla-at-risk",
    BREACHED: "sla-breached",
    RESOLVED: "sla-resolved",
  };

  return (
    <div className={`sla-pill ${classes[sla.status]}`} title={sla.label}>
      <span className="sla-dot" aria-hidden="true" />
      <span className="sla-text">{sla.timeRemainingText}</span>
    </div>
  );
}

export default function TicketQueueTable({
  tickets,
  isLoading,
  sortField,
  sortDirection,
  onSort,
  onSelectTicket,
  selectedTicketId,
  currentUserId,
  userRole = "IT_SUPPORT",
  onAssignToMe,
  onOpenAssignModal,
  onOpenEscalateModal,
  onOpenResolveModal,
  onTakeOver,
  onCloseTicket,
  isAssigningId,
  page = 1,
  totalPages = 1,
  onPageChange,
}) {
  const renderSortIndicator = (field) => {
    if (sortField !== field) {
      return <span className="sort-arrow sort-arrow-neutral" aria-hidden="true">↕</span>;
    }
    return (
      <span className="sort-arrow sort-arrow-active" aria-hidden="true">
        {sortDirection === "asc" ? "▲" : "▼"}
      </span>
    );
  };

  if (isLoading) {
    return (
      <div className="table-loading-container" aria-busy="true" aria-live="polite">
        <div className="table-skeleton-row" />
        <div className="table-skeleton-row" />
        <div className="table-skeleton-row" />
        <div className="table-skeleton-row" />
        <div className="table-skeleton-row" />
        <p className="loading-caption">Loading IT support triage queue...</p>
      </div>
    );
  }

  if (!tickets || tickets.length === 0) {
    return (
      <div className="table-empty-state">
        <div className="empty-icon" aria-hidden="true">📋</div>
        <h3>No Tickets Found</h3>
        <p>No support tickets match your active filter criteria. Try adjusting your filters or search terms.</p>
      </div>
    );
  }

  return (
    <div className="table-wrapper">
      <div className="table-responsive-wrapper">
        <table className="ticket-queue-table" role="table" aria-label="IT Support Triage Queue">
          <thead>
            <tr>
              <th
                scope="col"
                className="th-sortable th-ticket"
                onClick={() => onSort("ticket_number")}
                title="Sort by ticket number"
              >
                <div className="th-content">
                  <span>Ticket</span>
                  {renderSortIndicator("ticket_number")}
                </div>
              </th>
              <th
                scope="col"
                className="th-sortable th-priority"
                onClick={() => onSort("priority")}
                title="Sort by priority"
              >
                <div className="th-content">
                  <span>Priority</span>
                  {renderSortIndicator("priority")}
                </div>
              </th>
              <th
                scope="col"
                className="th-sortable th-subject"
                onClick={() => onSort("subject")}
                title="Sort by subject"
              >
                <div className="th-content">
                  <span>Subject & Category</span>
                  {renderSortIndicator("subject")}
                </div>
              </th>
              <th scope="col" className="th-requester">
                <span>Requester</span>
              </th>
              <th
                scope="col"
                className="th-sortable th-sla"
                onClick={() => onSort("sla")}
                title="Sort by SLA"
              >
                <div className="th-content">
                  <span>SLA Target</span>
                  {renderSortIndicator("sla")}
                </div>
              </th>
              <th
                scope="col"
                className="th-sortable th-status"
                onClick={() => onSort("status")}
                title="Sort by status"
              >
                <div className="th-content">
                  <span>Status</span>
                  {renderSortIndicator("status")}
                </div>
              </th>
              <th scope="col" className="th-assignee">
                <span>Assignee</span>
              </th>
              <th scope="col" className="th-actions">
                <span>Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((ticket) => {
              const isSelected = selectedTicketId === ticket.id;
              const isAssignedToMe =
                Boolean(currentUserId) &&
                (ticket.assigned_to === currentUserId ||
                  ticket.assigned_to_emp_id === currentUserId ||
                  ticket.assignee_account_id === currentUserId);
              const isAssigningThis = isAssigningId === ticket.id;

              const isReporter =
                Boolean(currentUserId) &&
                (ticket.reporter_id === currentUserId ||
                  ticket.reporter_account_id === currentUserId);

              const actions = allowedActions(ticket, userRole, isReporter);
              const isEscalatedWaiting =
                ticket.status === "escalated" &&
                !actions.includes(ACTIONS.TAKE_OVER) &&
                !actions.includes(ACTIONS.RESOLVE);

              return (
                <tr
                  key={ticket.id}
                  className={`ticket-row ${isSelected ? "ticket-row-selected" : ""} status-${ticket.status}`}
                  onClick={() => onSelectTicket(ticket)}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelectTicket(ticket);
                    }
                  }}
                >
                  {/* Ticket # */}
                  <td className="td-ticket">
                    <div className="ticket-id-cell">
                      <span className="ticket-number-badge">{ticket.ticket_number}</span>
                      <span className="ticket-date-caption">
                        {formatTimestamp(ticket.created_at)}
                      </span>
                    </div>
                  </td>

                  {/* Priority */}
                  <td className="td-priority">
                    <PriorityBadge priority={ticket.priority} />
                  </td>

                  {/* Subject & Category */}
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

                  {/* Requester */}
                  <td className="td-requester">
                    <div className="requester-cell">
                      <span className="requester-name">
                        {ticket.reporter_name || "Employee"}
                      </span>
                      <span className="requester-dept">
                        {ticket.reporter_department || ticket.reporter_email || "General"}
                      </span>
                    </div>
                  </td>

                  {/* SLA Target */}
                  <td className="td-sla">
                    <SlaIndicator ticket={ticket} />
                  </td>

                  {/* Status */}
                  <td className="td-status">
                    <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                      <StatusBadge status={ticket.status} />
                      {isEscalatedWaiting && (
                        <span className="badge-awaiting-sysadmin" title="Awaiting SysAdmin resolution or takeover">
                          ⏳ Awaiting SysAdmin
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Assignee */}
                  <td className="td-assignee">
                    <div className="assignee-cell">
                      {ticket.assigned_to || ticket.assignee_name ? (
                        <span className="assignee-name" title={ticket.assignee_email || ""}>
                          👤 {ticket.assignee_name || "Specialist"}
                          {isAssignedToMe && <span className="assignee-self-badge">(You)</span>}
                        </span>
                      ) : (
                        <span className="unassigned-label">Unassigned</span>
                      )}
                    </div>
                  </td>

                  {/* Actions */}
                  <td className="td-actions" onClick={(e) => e.stopPropagation()}>
                    <div className="action-buttons-group">
                      {/* Assign to Me button */}
                      {actions.includes(ACTIONS.ASSIGN_ME) && !isAssignedToMe && (
                        <button
                          type="button"
                          className="btn-action-assign"
                          onClick={(e) => {
                            e.stopPropagation();
                            onAssignToMe(ticket);
                          }}
                          disabled={isAssigningThis}
                          title="Assign ticket to myself and set status to In Progress"
                        >
                          {isAssigningThis ? "Assigning..." : "Assign to Me"}
                        </button>
                      )}

                      {/* Assign / Reassign button */}
                      {actions.includes(ACTIONS.ASSIGN_OTHER) && (
                        <button
                          type="button"
                          className="btn-action-inspect"
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenAssignModal(ticket);
                          }}
                          title="Assign ticket to specialist"
                        >
                          {ticket.assigned_to ? "Reassign" : "Assign..."}
                        </button>
                      )}

                      {/* SysAdmin Take Over button for escalated tickets */}
                      {actions.includes(ACTIONS.TAKE_OVER) && (
                        <button
                          type="button"
                          className="btn-action-assign"
                          onClick={(e) => {
                            e.stopPropagation();
                            onTakeOver?.(ticket);
                          }}
                          title="Take over escalated ticket (moves to In Progress)"
                        >
                          Take Over
                        </button>
                      )}

                      {/* Resolve button */}
                      {actions.includes(ACTIONS.RESOLVE) && (
                        <button
                          type="button"
                          className="btn-action-resolve"
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenResolveModal?.(ticket);
                          }}
                          title="Resolve ticket (requires resolution note)"
                        >
                          Resolve
                        </button>
                      )}

                      {/* Close button for resolved tickets */}
                      {actions.includes(ACTIONS.CLOSE) && (
                        <button
                          type="button"
                          className="btn-action-close"
                          onClick={(e) => {
                            e.stopPropagation();
                            onCloseTicket?.(ticket);
                          }}
                          title="Close resolved ticket"
                        >
                          Close
                        </button>
                      )}

                      {/* Escalate button */}
                      {actions.includes(ACTIONS.ESCALATE) && (
                        <button
                          type="button"
                          className="btn-action-escalate"
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenEscalateModal(ticket);
                          }}
                          title="Escalate ticket to System Administrator"
                        >
                          Escalate
                        </button>
                      )}

                      {/* Inspect button always available */}
                      <button
                        type="button"
                        className="btn-action-inspect"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectTicket(ticket);
                        }}
                        title="Inspect ticket details and internal notes"
                      >
                        Inspect
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {onPageChange && totalPages > 1 && (
        <div className="table-pagination-bar" role="navigation" aria-label="Ticket queue pagination">
          <button
            type="button"
            className="btn-page"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            aria-label="Previous page"
          >
            ‹ Previous
          </button>
          <span className="page-indicator">
            Page <strong>{page}</strong> of <strong>{totalPages || 1}</strong>
          </span>
          <button
            type="button"
            className="btn-page"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            aria-label="Next page"
          >
            Next ›
          </button>
        </div>
      )}
    </div>
  );
}
