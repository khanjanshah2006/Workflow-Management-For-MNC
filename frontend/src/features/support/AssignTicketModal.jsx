import { useState } from "react";

/**
 * AssignTicketModal Component (US-27: Assign IT Support Ticket)
 *
 * Modal to assign ticket to self or teammate.
 * API: PUT /api/v1/support/tickets/{id}/assign -> { "assigned_to_emp_id": current_user.emp_id }
 */

const IT_TEAM_MEMBERS = [
  { id: "e5678901-2345-6789-abcd-ef0123456789", name: "Marcus Vance", email: "marcus.vance@worksphere.internal" },
  { id: "f6789012-3456-789a-bcde-f0123456789a", name: "Ananya Sharma", email: "ananya.sharma@worksphere.internal" },
  { id: "b7890123-4567-89ab-cdef-0123456789ab", name: "Lucas Rodriguez", email: "lucas.rodriguez@worksphere.internal" },
  { id: "c8901234-5678-9abc-def0-123456789abc", name: "Maya Patel", email: "maya.patel@worksphere.internal" },
];

export default function AssignTicketModal({
  ticket,
  currentUserId,
  currentUserEmail,
  onClose,
  onConfirm,
}) {
  const currentUserName = currentUserEmail
    ? currentUserEmail.split("@")[0].replace(".", " ")
    : "Myself";

  const [assigneeType, setAssigneeType] = useState("self");
  const [selectedTeammateId, setSelectedTeammateId] = useState(IT_TEAM_MEMBERS[0].id);
  const [customEmpId, setCustomEmpId] = useState("");
  const [reassignmentReason, setReassignmentReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleConfirm = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    let targetId = currentUserId || "IT-101";
    let targetName = currentUserName;

    if (assigneeType === "teammate") {
      const found = IT_TEAM_MEMBERS.find((m) => m.id === selectedTeammateId);
      targetId = selectedTeammateId;
      targetName = found ? found.name : selectedTeammateId;
    } else if (assigneeType === "custom") {
      targetId = customEmpId.trim() || currentUserId;
      targetName = `IT Staff (${targetId})`;
    }

    try {
      await onConfirm({
        ticketId: ticket.id,
        assignedTo: targetId,
        assigneeName: targetName,
        reason: reassignmentReason.trim() || undefined,
      });
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="assign-modal-title">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <h3 id="assign-modal-title">Assign Support Ticket</h3>
          <button type="button" className="btn-modal-close" onClick={onClose} aria-label="Close modal">
            ✕
          </button>
        </header>

        <form onSubmit={handleConfirm}>
          <div className="modal-body">
            <div className="modal-ticket-summary">
              <strong>{ticket.ticket_number}:</strong> {ticket.subject}
            </div>

            <div className="modal-field">
              <label>Assignment Target</label>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "4px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: "normal", cursor: "pointer" }}>
                  <input
                    type="radio"
                    name="assigneeType"
                    value="self"
                    checked={assigneeType === "self"}
                    onChange={() => setAssigneeType("self")}
                  />
                  <span>Assign to Myself ({currentUserEmail || "current account"})</span>
                </label>

                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: "normal", cursor: "pointer" }}>
                  <input
                    type="radio"
                    name="assigneeType"
                    value="teammate"
                    checked={assigneeType === "teammate"}
                    onChange={() => setAssigneeType("teammate")}
                  />
                  <span>Assign to IT Team Specialist</span>
                </label>

                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: "normal", cursor: "pointer" }}>
                  <input
                    type="radio"
                    name="assigneeType"
                    value="custom"
                    checked={assigneeType === "custom"}
                    onChange={() => setAssigneeType("custom")}
                  />
                  <span>Enter Specific Employee / Account ID</span>
                </label>
              </div>
            </div>

            {assigneeType === "teammate" && (
              <div className="modal-field">
                <label htmlFor="teammate-select">Select IT Specialist</label>
                <select
                  id="teammate-select"
                  value={selectedTeammateId}
                  onChange={(e) => setSelectedTeammateId(e.target.value)}
                >
                  {IT_TEAM_MEMBERS.map((member) => (
                    <option key={member.id} value={member.id}>
                      {member.name} ({member.email})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {assigneeType === "custom" && (
              <div className="modal-field">
                <label htmlFor="custom-emp-id">Employee / Account ID</label>
                <input
                  id="custom-emp-id"
                  type="text"
                  placeholder="e.g. IT-105 or UUID"
                  value={customEmpId}
                  onChange={(e) => setCustomEmpId(e.target.value)}
                  required
                />
              </div>
            )}

            <div className="modal-field">
              <label htmlFor="assign-reason">Notes / Reassignment Reason (Optional)</label>
              <textarea
                id="assign-reason"
                rows={2}
                placeholder="e.g. Tier-2 hardware escalation, handover for shift coverage..."
                value={reassignmentReason}
                onChange={(e) => setReassignmentReason(e.target.value)}
              />
            </div>
          </div>

          <footer className="modal-footer">
            <button type="button" className="btn-modal-cancel" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </button>
            <button type="submit" className="btn-modal-confirm" disabled={isSubmitting}>
              {isSubmitting ? "Assigning..." : "Confirm Assignment"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
