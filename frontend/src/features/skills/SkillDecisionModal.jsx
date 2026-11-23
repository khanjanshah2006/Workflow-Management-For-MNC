import React from "react";

/**
 * SkillDecisionModal Component (US-34 / Issue #161)
 * Placeholder component for Commit 3; fully implemented in Commit 4.
 */
export default function SkillDecisionModal({
  isOpen = false,
  action = "APPROVE",
  request = null,
  onClose,
}) {
  if (!isOpen || !request) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="skill-decision-modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="skill-modal-header">
          <h2 className="skill-modal-title">
            {action === "APPROVE" ? "Approve Skill Proposal" : "Reject Skill Proposal"}
          </h2>
          <button type="button" className="skill-modal-close-btn" onClick={onClose}>
            ×
          </button>
        </div>
      </div>
    </div>
  );
}
