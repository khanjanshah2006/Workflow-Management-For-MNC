import { useState } from "react";

/**
 * InternalNoteComposer Component (US-27: Add Internal Troubleshooting Note)
 *
 * Textarea note composer with "Post Note" button.
 * Adding an internal note instantly appends it to the activity timeline.
 * API payload: POST /api/v1/support/tickets/{id}/notes -> { "note_text": "string" }
 */
export default function InternalNoteComposer({ onAddNote, isSubmitting = false }) {
  const [noteText, setNoteText] = useState("");

  const trimmed = noteText.trim();
  const canSubmit = trimmed.length > 0 && !isSubmitting;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit) return;

    await onAddNote(trimmed);
    setNoteText("");
  };

  return (
    <form className="note-composer-card" onSubmit={handleSubmit} aria-label="Internal Troubleshooting Note Form">
      <textarea
        className="note-composer-textarea"
        placeholder="Add an internal troubleshooting note, diagnostic findings, or resolution update..."
        value={noteText}
        onChange={(e) => setNoteText(e.target.value)}
        rows={3}
        disabled={isSubmitting}
        aria-label="Internal note text"
      />

      <div className="note-composer-footer">
        <span className="composer-hint">
          {trimmed.length > 0
            ? `${trimmed.length} character${trimmed.length === 1 ? "" : "s"}`
            : "Visible to IT staff and System Admins only"}
        </span>

        <button
          type="submit"
          className="btn-post-note"
          disabled={!canSubmit}
        >
          {isSubmitting ? "Posting Note..." : "Post Note"}
        </button>
      </div>
    </form>
  );
}
