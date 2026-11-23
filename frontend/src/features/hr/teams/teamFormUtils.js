/**
 * Team Form Utilities (Issue #160 — HR Department Teams Console)
 *
 * Pure validation, payload building, and member-diff helpers.
 */

/**
 * Validate team form fields.
 * @param {{ name: string, description: string, leadEmpId: number|null }} fields
 * @returns {{ valid: boolean, errors: Record<string, string> }}
 */
export function validateTeamForm({ name, description, leadEmpId }) {
  const errors = {};

  const trimmedName = typeof name === "string" ? name.trim() : "";
  if (!trimmedName) {
    errors.name = "Team name is required";
  } else if (trimmedName.length < 2) {
    errors.name = "Team name must be at least 2 characters";
  } else if (trimmedName.length > 100) {
    errors.name = "Team name must not exceed 100 characters";
  }

  const trimmedDesc = typeof description === "string" ? description.trim() : "";
  if (trimmedDesc.length > 500) {
    errors.description = "Description must not exceed 500 characters";
  }

  if (!leadEmpId && leadEmpId !== 0) {
    errors.leadEmpId = "A team lead must be selected";
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  };
}

/**
 * Build the create-team payload for POST /api/v1/departments/{deptId}/teams.
 * Always includes lead in member_emp_ids and removes duplicates.
 * @param {{ name: string, description: string, leadEmpId: number, memberEmpIds: number[] }} fields
 * @returns {{ name: string, description: string, lead_emp_id: number, member_emp_ids: number[] }}
 */
export function buildCreatePayload({ name, description, leadEmpId, memberEmpIds = [] }) {
  const allIds = new Set([leadEmpId, ...memberEmpIds].filter((id) => id != null));
  return {
    name: (name || "").trim(),
    description: (description || "").trim() || null,
    lead_emp_id: leadEmpId,
    member_emp_ids: [...allIds],
  };
}

/**
 * Calculate members to add and remove given before/after arrays of emp IDs.
 * Never removes the currentLeadId.
 * @param {number[]} before
 * @param {number[]} after
 * @param {number|null} currentLeadId
 * @returns {{ toAdd: number[], toRemove: number[] }}
 */
export function diffMembers(before = [], after = [], currentLeadId = null) {
  const beforeSet = new Set(before || []);
  const afterSet = new Set(after || []);

  const toAdd = [...afterSet].filter((id) => !beforeSet.has(id));
  const toRemove = [...beforeSet].filter((id) => {
    if (id === currentLeadId) return false; // never remove lead
    return !afterSet.has(id);
  });

  return { toAdd, toRemove };
}
