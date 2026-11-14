import { useEffect } from "react";
import { calculateSLA } from "../../api/supportApi.js";
import InternalNoteComposer from "./InternalNoteComposer.jsx";

/**
 * TicketDetailDrawer Component (US-27: Inspect Support Ticket & Notes Console)
 *
 * Slide-out drawer displaying comprehensive ticket details:
 * - Requester info (name, email, department)
 * - Detailed problem description
 * - Chronological activity timeline with real-time updates
 * - Embedded internal troubleshooting note composer
 * - Direct actions: Assign to Me, Reassign, Resolve, Escalate
 */

function formatTimestamp(isoStr) {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
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
  const classes = {
    open: "badge-status-open",
    in_progress: "badge-status-in-progress",
    resolved: "badge-status-resolved",
    escalated: "badge-status-escalated",
    closed: "badge-status-closed",
  };
  return <span className={`badge-status ${classes[s] || classes.open}`}>{s.replace("_", " ")}</span>;
}

function ActivityTimelineItem({ activity }) {
  const action = (activity.action || activity.activity_type || "").toUpperCase();

  const nodeIcons = {
    CREATED: { icon: "📝", class: "node-created", label: "Ticket Created" },
    ASSIGNED: { icon: "👤", class: "node-assigned", label: "Ticket Assigned" },
    NOTE_ADDED: { icon: "💬", class: "node-note", label: "Internal Troubleshooting Note" },
    STATUS_CHANGED: { icon: "🔄", class: "node-status", label: "Status Updated" },
    ESCALATED: { icon: "🚨", class: "node-escalated", label: "Escalated to SysAdmin" },
  };

  const config = nodeIcons[action] || {
    icon: "📌",
    class: "node-status",
    label: action.replace("_", " "),
  };

  return (
    <div className="timeline-item">
      <div className={`timeline-icon-node ${config.class}`} aria-hidden="true">
        {config.icon}
      </div>
      <div className="timeline-content">
        <div className="timeline-meta">
          <span className="timeline-action-label">{config.label}</span>
          <span className="timeline-time">{formatTimestamp(activity.created_at)}</span>
        </div>
        {activity.note && (
          <p className="timeline-note-text">{activity.note}</p>
        )}
        {activity.actor_name && (
          <div className="timeline-actor-caption">
            by <strong>{activity.actor_name}</strong>
          </div>
        )}
      </div>
    </div>
  );
}

export default function TicketDetailDrawer({
  ticket,
  onClose,
  currentUserId,
  onAssignToMe,
  onOpenAssignModal,
  onOpenEscalateModal,
  onResolveTicket,
  onAddNote,
  isAssigning = false,
}) {
  // Close drawer on Escape key press
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!ticket) return null;

  const isAssignedToMe =
    Boolean(currentUserId) &&
    (ticket.assigned_to === currentUserId ||
      ticket.assigned_to_emp_id === currentUserId);

  const sla = calculateSLA(ticket);
  const activities = ticket.activities || [];

  return (
    <div
      className="drawer-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Details for Ticket ${ticket.ticket_number}`}
    >
      <div className="ticket-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Drawer Header */}
        <header className="drawer-header">
          <div className="drawer-title-block">
            <span className="drawer-ticket-number">{ticket.ticket_number}</span>
            <div className="drawer-badges-row">
              <StatusBadge status={ticket.status} />
              <PriorityBadge priority={ticket.priority} />
              <span className="category-tag">{ticket.category.toUpperCase()}</span>
            </div>
          </div>
          <button
            type="button"
            className="btn-drawer-close"
            onClick={onClose}
            aria-label="Close details drawer"
          >
            ✕
          </button>
        </header>

        {/* Drawer Action Bar */}
        <div className="drawer-action-bar">
          {!isAssignedToMe && ticket.status !== "resolved" && (
            <button
              type="button"
              className="btn-drawer-action btn-drawer-action-primary"
              onClick={() => onAssignToMe(ticket)}
              disabled={isAssigning}
              title="Assign this ticket to myself and set status to In Progress"
            >
              {isAssigning ? "Assigning..." : "Assign to Me"}
            </button>
          )}

          <button
            type="button"
            className="btn-drawer-action btn-drawer-action-secondary"
            onClick={() => onOpenAssignModal(ticket)}
            title="Assign or reassign ticket to IT specialist"
          >
            {ticket.assigned_to ? "Reassign" : "Assign..."}
          </button>

          {ticket.status !== "resolved" && (
            <button
              type="button"
              className="btn-drawer-action btn-drawer-action-success"
              onClick={() => onResolveTicket(ticket.id, "Resolved via IT Support Console")}
              title="Mark ticket as resolved"
            >
              ✓ Resolve
            </button>
          )}

          {ticket.status !== "resolved" && ticket.status !== "escalated" && (
            <button
              type="button"
              className="btn-drawer-action btn-drawer-action-warning"
              onClick={() => onOpenEscalateModal(ticket)}
              title="Escalate ticket to System Administrator"
            >
              ⚠️ Escalate to SysAdmin
            </button>
          )}
        </div>

        {/* Drawer Body */}
        <div className="drawer-body-scrollable">
          {/* Section: Subject & Summary */}
          <section className="drawer-section">
            <h4 className="drawer-section-title">Ticket Subject</h4>
            <div style={{ fontSize: "15px", fontWeight: "700", color: "#0f172a", lineHeight: "1.4" }}>
              {ticket.subject}
            </div>
          </section>

          {/* Section: Requester & Assignment Metadata */}
          <section className="drawer-section">
            <h4 className="drawer-section-title">Requester & SLA Overview</h4>
            <div className="drawer-info-grid">
              <div className="info-item">
                <span className="info-label">Requester</span>
                <span className="info-value">{ticket.reporter_name || "Employee"}</span>
                <span style={{ fontSize: "11px", color: "#64748b" }}>
                  {ticket.reporter_department} {ticket.reporter_email && `· ${ticket.reporter_email}`}
                </span>
              </div>

              <div className="info-item">
                <span className="info-label">Current Assignee</span>
                <span className="info-value">
                  {ticket.assignee_name || (ticket.assigned_to ? "IT Specialist" : "Unassigned")}
                  {isAssignedToMe && " (You)"}
                </span>
              </div>

              <div className="info-item">
                <span className="info-label">Submitted On</span>
                <span className="info-value">{formatTimestamp(ticket.created_at)}</span>
              </div>

              <div className="info-item">
                <span className="info-label">SLA Target</span>
                <span className="info-value">
                  <span className={`sla-pill sla-${sla.status.toLowerCase().replace("_", "-")}`}>
                    <span className="sla-dot" aria-hidden="true" />
                    {sla.label} ({sla.timeRemainingText})
                  </span>
                </span>
              </div>
            </div>
          </section>

          {/* Section: Problem Description */}
          <section className="drawer-section">
            <h4 className="drawer-section-title">Problem Description</h4>
            <div className="drawer-description-box">
              {ticket.description || "No description provided."}
            </div>
          </section>

          {/* Section: Internal Notes Composer */}
          <section className="drawer-section">
            <h4 className="drawer-section-title">Add Internal Troubleshooting Note</h4>
            <InternalNoteComposer
              onAddNote={(noteText) => onAddNote(ticket.id, noteText)}
            />
          </section>

          {/* Section: Activity & Notes Timeline */}
          <section className="drawer-section">
            <h4 className="drawer-section-title">
              Activity History & Investigation Notes ({activities.length})
            </h4>

            {activities.length === 0 ? (
              <p style={{ color: "#94a3b8", fontSize: "13px", fontStyle: "italic", margin: "4px 0" }}>
                No recorded activity yet for this ticket.
              </p>
            ) : (
              <div className="timeline-container">
                {activities.map((act) => (
                  <ActivityTimelineItem
                    key={act.id || act.activity_id || `${act.created_at}-${act.action}`}
                    activity={act}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
