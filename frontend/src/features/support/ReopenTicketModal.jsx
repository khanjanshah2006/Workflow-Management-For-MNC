import { useState } from "react";

/**
 * ReopenTicketModal Component (US-26 & US-28)
 *
 * Allows a reporter to reopen their resolved ticket with an optional comment.
 */
export default function ReopenTicketModal({
  ticket,
  onClose,
  onConfirm,
  isReopening = false,
}) {
  const [comment, setComment] = useState("");

  if (!ticket) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    onConfirm({
      ticketId: ticket.id,
      comment: comment.trim(),
    });
  };

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="reopen-modal-title"
    >
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <h3 id="reopen-modal-title">Reopen Ticket #{ticket.ticket_number}</h3>
          <button
            type="button"
            className="btn-modal-close"
            onClick={onClose}
            aria-label="Close modal"
            disabled={isReopening}
          >
            ✕
          </button>
        </header>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="modal-body">
            <div className="ticket-summary-box">
              <span className="summary-subject">{ticket.subject}</span>
              <span className="summary-meta">
                Status: <strong>RESOLVED</strong> · Category:{" "}
                <strong>{(ticket.category || "other").toUpperCase()}</strong>
              </span>
            </div>

            <div className="form-group" style={{ marginTop: "16px" }}>
              <label htmlFor="reopen-comment" className="form-label">
                Reason for Reopening (Optional)
              </label>
              <p className="form-hint" style={{ fontSize: "12px", color: "#64748b", margin: "2px 0 8px" }}>
                Let the IT support team know why this issue still needs attention or what recurred.
              </p>
              <textarea
                id="reopen-comment"
                className="form-textarea"
                rows={4}
                placeholder="Explain what is still not working or why you are reopening this ticket..."
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                disabled={isReopening}
                maxLength={2000}
                autoFocus
              />
            </div>
          </div>

          <footer className="modal-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "20px" }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={isReopening}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              style={{ background: "#f59e0b", borderColor: "#d97706", color: "#ffffff" }}
              disabled={isReopening}
            >
              {isReopening ? "Reopening..." : "Reopen Ticket"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
