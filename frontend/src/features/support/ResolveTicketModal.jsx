import { useState } from "react";
import { validateResolutionNote } from "./ticketStatusUtils.js";

/**
 * ResolveTicketModal Component (US-27 & US-28)
 *
 * Prompts IT Specialist or System Admin for mandatory resolution note
 * before marking a ticket as RESOLVED.
 */
export default function ResolveTicketModal({
  ticket,
  onClose,
  onConfirm,
  isResolving = false,
}) {
  const [resolutionNote, setResolutionNote] = useState("");
  const [validationError, setValidationError] = useState(null);

  if (!ticket) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    const validation = validateResolutionNote(resolutionNote);
    if (!validation.isValid) {
      setValidationError(validation.error);
      return;
    }

    setValidationError(null);
    onConfirm({
      ticketId: ticket.id,
      resolutionNote: resolutionNote.trim(),
    });
  };

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="resolve-modal-title"
    >
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <h3 id="resolve-modal-title">Resolve Ticket #{ticket.ticket_number}</h3>
          <button
            type="button"
            className="btn-modal-close"
            onClick={onClose}
            aria-label="Close resolve modal"
            disabled={isResolving}
          >
            ✕
          </button>
        </header>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="modal-body">
            <div className="ticket-summary-box">
              <span className="summary-subject">{ticket.subject}</span>
              <span className="summary-meta">
                Category: <strong>{(ticket.category || "other").toUpperCase()}</strong> · Requester:{" "}
                <strong>{ticket.reporter_name || "Employee"}</strong>
              </span>
            </div>

            <div className="form-group" style={{ marginTop: "16px" }}>
              <label htmlFor="resolution-note" className="form-label">
                Resolution Note <span className="required-asterisk">*</span>
              </label>
              <p className="form-hint" style={{ fontSize: "12px", color: "#64748b", margin: "2px 0 8px" }}>
                Explain what actions were taken to resolve the issue. This note will be recorded in the ticket history.
              </p>
              <textarea
                id="resolution-note"
                className={`form-textarea ${validationError ? "input-error" : ""}`}
                rows={4}
                placeholder="Describe how the problem was resolved..."
                value={resolutionNote}
                onChange={(e) => {
                  setResolutionNote(e.target.value);
                  if (validationError) setValidationError(null);
                }}
                disabled={isResolving}
                required
                autoFocus
              />
              {validationError && (
                <span className="form-error-msg" role="alert" style={{ color: "#ef4444", fontSize: "12px", marginTop: "4px", display: "block" }}>
                  {validationError}
                </span>
              )}
            </div>
          </div>

          <footer className="modal-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "20px" }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={isResolving}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              style={{ background: "#10b981", borderColor: "#059669", color: "#ffffff" }}
              disabled={isResolving || !resolutionNote.trim()}
            >
              {isResolving ? "Resolving..." : "Confirm Resolution"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
