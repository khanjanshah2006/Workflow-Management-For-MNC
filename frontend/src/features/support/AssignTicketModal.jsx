import { useState, useEffect } from "react";
import { adminApi } from "../../api/adminApi.js";

/**
 * AssignTicketModal Component (S8-FE-3: Assign IT Support Ticket)
 *
 * Modal to assign ticket to self or teammate.
 * - SYSTEM_ADMIN can pick from dynamic IT staff accounts (GET /admin/users?user_type=IT_SUPPORT)
 * - IT_SUPPORT can assign to themselves or a teammate
 * - Contract: PUT /api/v1/support/tickets/{id}/assign -> { assignee_account_id: "<uuid>" }
 */

const DEFAULT_IT_TEAM_MEMBERS = [
  { id: "e5678901-2345-6789-abcd-ef0123456789", name: "Marcus Vance", email: "marcus.vance@worksphere.internal" },
  { id: "f6789012-3456-789a-bcde-f0123456789a", name: "Ananya Sharma", email: "ananya.sharma@worksphere.internal" },
  { id: "b7890123-4567-89ab-cdef-0123456789ab", name: "Lucas Rodriguez", email: "lucas.rodriguez@worksphere.internal" },
  { id: "c8901234-5678-9abc-def0-123456789abc", name: "Maya Patel", email: "maya.patel@worksphere.internal" },
];

export default function AssignTicketModal({
  ticket,
  currentUserId,
  currentUserEmail,
  currentUserRole = "",
  onClose,
  onConfirm,
}) {
  const currentUserName = currentUserEmail
    ? currentUserEmail.split("@")[0].replace(".", " ")
    : "Myself";

  const normRole = (currentUserRole || "").toUpperCase();
  const isSysAdmin = normRole === "SYSTEM_ADMIN" || normRole === "ADMIN";

  const [assigneeType, setAssigneeType] = useState("self");
  const [itStaffList, setItStaffList] = useState(DEFAULT_IT_TEAM_MEMBERS);
  const [selectedStaffId, setSelectedStaffId] = useState("");
  const [customAccountId, setCustomAccountId] = useState("");
  const [reassignmentReason, setReassignmentReason] = useState("");
  const [isLoadingStaff, setIsLoadingStaff] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // Fetch IT staff accounts for picker
  useEffect(() => {
    let ignore = false;
    async function fetchITStaff() {
      setIsLoadingStaff(true);
      try {
        const res = await adminApi.getUsers({ user_type: "IT_SUPPORT", is_active: true, limit: 50 });
        if (!ignore && res?.items && res.items.length > 0) {
          const formatted = res.items.map((u) => ({
            id: u.account_id || u.id,
            name: u.full_name || u.email?.split("@")[0].replace(".", " ") || u.email,
            email: u.email,
          }));
          setItStaffList(formatted);
          if (formatted.length > 0) {
            setSelectedStaffId(formatted[0].id);
          }
        }
      } catch {
        // Fallback to default list if not authorized to fetch admin users
        if (!ignore) {
          setSelectedStaffId(DEFAULT_IT_TEAM_MEMBERS[0].id);
        }
      } finally {
        if (!ignore) setIsLoadingStaff(false);
      }
    }

    fetchITStaff();

    return () => {
      ignore = true;
    };
  }, [isSysAdmin]);

  const handleConfirm = async (e) => {
    e.preventDefault();
    setErrorMessage(null);

    let targetId = currentUserId;
    let targetName = currentUserName;

    if (assigneeType === "staff") {
      const found = itStaffList.find((m) => m.id === selectedStaffId);
      targetId = selectedStaffId;
      targetName = found ? found.name : selectedStaffId;
    } else if (assigneeType === "custom") {
      targetId = customAccountId.trim();
      targetName = `IT Staff (${targetId})`;
    }

    if (!targetId) {
      setErrorMessage("Please select or provide an IT staff account ID.");
      return;
    }

    setIsSubmitting(true);
    try {
      await onConfirm({
        ticketId: ticket.id,
        assigneeAccountId: targetId,
        assigneeName: targetName,
        reason: reassignmentReason.trim() || undefined,
      });
      onClose();
    } catch (err) {
      setErrorMessage(err.message || "Failed to assign ticket.");
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

            {errorMessage && (
              <div className="support-alert-banner alert-error" role="alert" style={{ marginBottom: "12px" }}>
                <span>{errorMessage}</span>
              </div>
            )}

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
                    value="staff"
                    checked={assigneeType === "staff"}
                    onChange={() => setAssigneeType("staff")}
                  />
                  <span>Assign to IT Staff Member {isLoadingStaff && "(Loading...)"}</span>
                </label>

                {assigneeType === "staff" && (
                  <div style={{ paddingLeft: "24px", marginTop: "4px" }}>
                    <select
                      className="filter-select"
                      style={{ width: "100%" }}
                      value={selectedStaffId}
                      onChange={(e) => setSelectedStaffId(e.target.value)}
                    >
                      {itStaffList.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name} ({m.email})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: "normal", cursor: "pointer" }}>
                  <input
                    type="radio"
                    name="assigneeType"
                    value="custom"
                    checked={assigneeType === "custom"}
                    onChange={() => setAssigneeType("custom")}
                  />
                  <span>Specify Account UUID manually</span>
                </label>

                {assigneeType === "custom" && (
                  <div style={{ paddingLeft: "24px", marginTop: "4px" }}>
                    <input
                      type="text"
                      className="filter-search-input"
                      placeholder="e.g. b0000002-0000-0000-0000-000000000002"
                      value={customAccountId}
                      onChange={(e) => setCustomAccountId(e.target.value)}
                      style={{ width: "100%", fontSize: "13px" }}
                    />
                  </div>
                )}
              </div>
            </div>

            <div className="modal-field">
              <label htmlFor="reassign-reason">Assignment Note / Reason (Optional)</label>
              <textarea
                id="reassign-reason"
                className="modal-textarea"
                rows={3}
                placeholder="Optional assignment or transfer context..."
                value={reassignmentReason}
                onChange={(e) => setReassignmentReason(e.target.value)}
              />
            </div>
          </div>

          <footer className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? "Assigning..." : "Confirm Assignment"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
