import { useState } from "react";

/**
 * EscalateTicketModal Component (US-28: Escalate Support Issue to SysAdmin)
 *
 * Modal to escalate ticket to System Administrator with a mandatory reason.
 * Acceptance criteria:
 * - "Escalate to SysAdmin" modal requires escalation reason.
 * - API wiring: PUT /api/v1/support/tickets/{id}/escalate -> { "escalation_reason": "string" }
 */
export default function EscalateTicketModal({ ticket, onClose, onConfirm }) {
  const [escalationReason, setEscalationReason] = useState("");
  const [touched, setTouched] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const trimmed = escalationReason.trim();
  const isValid = trimmed.length >= 5;
  const showError = touched && !isValid;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setTouched(true);

    if (!isValid) return;

    setIsSubmitting(true);
    try {
      await onConfirm({
        ticketId: ticket.id,
        escalationReason: trimmed,
      });
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="escalate-modal-title"
    >
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <h3 id="escalate-modal-title">Escalate Ticket to SysAdmin</h3>
          <button
            type="button"
            className="btn-modal-close"
            onClick={onClose}
            aria-label="Close modal"
          >
            ✕
          </button>
        </header>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="escalate-callout">
              ⚠️ <strong>Elevated Resolution Required:</strong> Escalating ticket{" "}
              <strong>{ticket.ticket_number}</strong> flags it for immediate System Administrator review,
              transitions its status to <strong>ESCALATED</strong>, and dispatches a high-priority notification.
            </div>

            <div className="modal-ticket-summary">
              <strong>Issue:</strong> {ticket.subject} ({ticket.category.toUpperCase()} · {ticket.priority} Priority)
            </div>

            <div className="modal-field">
              <label htmlFor="escalation-reason-input">
                Escalation Reason <span style={{ color: "#dc2626" }}>*</span>
              </label>
              <textarea
                id="escalation-reason-input"
                rows={4}
                placeholder="Explain why this issue requires SysAdmin privileges or infrastructure intervention (e.g. production database outage, IAM permission root grant, hardware server fault)..."
                value={escalationReason}
                onChange={(e) => {
                  setEscalationReason(e.target.value);
                  if (!touched) setTouched(true);
                }}
                disabled={isSubmitting}
                required
                aria-required="true"
                aria-invalid={showError}
              />
              {showError && (
                <span className="modal-field-error">
                  A detailed escalation reason (at least 5 characters) is strictly required to notify the System Administrator.
                </span>
              )}
            </div>
          </div>

          <footer className="modal-footer">
            <button
              type="button"
              className="btn-modal-cancel"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-modal-escalate-confirm"
              disabled={!isValid || isSubmitting}
            >
              {isSubmitting ? "Escalating..." : "Confirm Escalation"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
