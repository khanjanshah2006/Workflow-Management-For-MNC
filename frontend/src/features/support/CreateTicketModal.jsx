import { useState } from "react";

/**
 * CreateTicketModal Component (US-26: Employee Support Portal)
 *
 * Form for submitting a new IT support service request:
 * - Subject (5-200 chars)
 * - Category (hardware, software, network, access, other)
 * - Priority (LOW, MEDIUM, HIGH, CRITICAL)
 * - Description (10-2000 chars)
 */

const CATEGORIES = [
  { value: "software", label: "Software / Application" },
  { value: "hardware", label: "Hardware / Equipment" },
  { value: "network", label: "Network & VPN" },
  { value: "access", label: "Access & IAM" },
  { value: "other", label: "Other" },
];

const PRIORITIES = [
  { value: "LOW", label: "Low (General question / Minor inconvenience)" },
  { value: "MEDIUM", label: "Medium (Standard issue / Workaround exists)" },
  { value: "HIGH", label: "High (Significant productivity impact)" },
  { value: "CRITICAL", label: "Critical (Complete work stoppage / Outage)" },
];

export default function CreateTicketModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
}) {
  const [subject, setSubject] = useState("");
  const [category, setCategory] = useState("software");
  const [priority, setPriority] = useState("MEDIUM");
  const [description, setDescription] = useState("");
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!subject.trim() || subject.trim().length < 5) {
      setError("Subject must be at least 5 characters long.");
      return;
    }
    if (subject.trim().length > 200) {
      setError("Subject cannot exceed 200 characters.");
      return;
    }
    if (!description.trim() || description.trim().length < 10) {
      setError("Description must be at least 10 characters long.");
      return;
    }
    if (description.trim().length > 2000) {
      setError("Description cannot exceed 2000 characters.");
      return;
    }

    setError(null);
    try {
      await onSubmit({
        subject: subject.trim(),
        category,
        priority,
        description: description.trim(),
      });
      // Reset form
      setSubject("");
      setCategory("software");
      setPriority("MEDIUM");
      setDescription("");
    } catch (err) {
      setError(err?.message || "Failed to submit ticket.");
    }
  };

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-ticket-title"
    >
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "560px" }}>
        <header className="modal-header">
          <h3 id="create-ticket-title">Raise New Support Ticket</h3>
          <button
            type="button"
            className="btn-modal-close"
            onClick={onClose}
            aria-label="Close modal"
            disabled={isSubmitting}
          >
            ✕
          </button>
        </header>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {error && (
              <div className="support-alert-banner alert-error" role="alert" style={{ margin: "0" }}>
                <span>{error}</span>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="ticket-subject" className="form-label">
                Subject <span className="required-asterisk">*</span>
              </label>
              <input
                id="ticket-subject"
                type="text"
                className="form-input"
                placeholder="Brief summary of the issue (e.g. Cannot connect to VPN)"
                value={subject}
                onChange={(e) => {
                  setSubject(e.target.value);
                  if (error) setError(null);
                }}
                disabled={isSubmitting}
                maxLength={200}
                required
                autoFocus
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <div className="form-group">
                <label htmlFor="ticket-category" className="form-label">Category</label>
                <select
                  id="ticket-category"
                  className="form-select"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  disabled={isSubmitting}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="ticket-priority" className="form-label">Priority</label>
                <select
                  id="ticket-priority"
                  className="form-select"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  disabled={isSubmitting}
                >
                  {PRIORITIES.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="ticket-description" className="form-label">
                Problem Description <span className="required-asterisk">*</span>
              </label>
              <textarea
                id="ticket-description"
                className="form-textarea"
                rows={5}
                placeholder="Please describe what happened, steps to reproduce, and any error messages..."
                value={description}
                onChange={(e) => {
                  setDescription(e.target.value);
                  if (error) setError(null);
                }}
                disabled={isSubmitting}
                maxLength={2000}
                required
              />
              <span style={{ fontSize: "11px", color: "#64748b", alignSelf: "flex-end" }}>
                {description.length} / 2000 characters
              </span>
            </div>
          </div>

          <footer className="modal-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "16px" }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={isSubmitting || !subject.trim() || !description.trim()}
            >
              {isSubmitting ? "Submitting..." : "Submit Ticket"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
