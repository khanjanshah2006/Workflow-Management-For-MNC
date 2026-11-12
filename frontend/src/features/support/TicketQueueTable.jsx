import { calculateSLA } from "../../api/supportApi.js";

/**
 * TicketQueueTable Component (US-27)
 *
 * Displays sortable, responsive IT support triage queue table with:
 * - Priority badges (CRITICAL, HIGH, MEDIUM, LOW)
 * - Dynamic SLA indicators (On Track, At Risk, Breached)
 * - Status badges (open, in_progress, resolved, escalated)
 * - Interactive sorting by columns
 * - One-click "Assign to Me" that updates UI badge to IN_PROGRESS without page reload
 * - Drawer inspection trigger
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
  onAssignToMe,
  onOpenAssignModal,
  onOpenEscalateModal,
  isAssigningId,
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
                ticket.assigned_to_emp_id === currentUserId);
            const isAssigningThis = isAssigningId === ticket.id;

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
                      {ticket.category.toUpperCase()}
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
                  <StatusBadge status={ticket.status} />
                </td>

                {/* Assignee */}
                <td className="td-assignee">
                  <div className="assignee-cell">
                    {ticket.assigned_to ? (
                      <span className="assignee-name" title={ticket.assignee_email || ""}>
                        👤 {ticket.assignee_name || "Assigned Specialist"}
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
                    {/* Assign to Me button: updates badge to IN_PROGRESS without page reload */}
                    {!isAssignedToMe && ticket.status !== "resolved" && (
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

                    {/* Reassign button if already assigned or resolved */}
                    {isAssignedToMe && ticket.status !== "resolved" && (
                      <button
                        type="button"
                        className="btn-action-inspect"
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenAssignModal(ticket);
                        }}
                        title="Reassign ticket to teammate"
                      >
                        Reassign
                      </button>
                    )}

                    {/* Inspect button opens slide-out drawer */}
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

                    {/* Escalate button */}
                    {ticket.status !== "resolved" && ticket.status !== "escalated" && (
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
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
