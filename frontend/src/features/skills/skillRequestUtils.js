import { ROUTES } from "../../constants/routes.js";

export { ROUTES };

export const SKILL_ACTIONS = Object.freeze({
  ADD: "ADD",
  UPDATE: "UPDATE",
  REMOVE: "REMOVE",
});

export const SKILL_PROFICIENCIES = Object.freeze([
  "BEGINNER",
  "INTERMEDIATE",
  "EXPERT",
]);

export const SKILL_STATUSES = Object.freeze({
  PENDING: "PENDING",
  APPROVED: "APPROVED",
  REJECTED: "REJECTED",
});

export const PROFICIENCY_LABELS = Object.freeze({
  BEGINNER: "Beginner",
  INTERMEDIATE: "Intermediate",
  EXPERT: "Expert",
});

/**
 * Common catalog skill names available for quick selection in ADD mode.
 * Contains standard technical, cloud, data, quality and leadership skills matching backend seeds.
 * Does not contain hardcoded IDs to ensure consistent name-based proposal creation.
 */
export const DEFAULT_CATALOG_SKILLS = Object.freeze([
  "Python",
  "Java",
  "React",
  "TypeScript",
  "Kotlin",
  "Swift",
  "SQL",
  "Apache Spark",
  "Power BI",
  "Selenium",
  "AWS",
  "Kubernetes",
  "Terraform",
  "Penetration Testing",
  "ITIL",
  "Docker",
  "Node.js",
  "FastAPI",
  "PostgreSQL",
  "Git",
  "System Design",
  "Agile / Scrum",
  "Project Management",
]);

/**
 * Validates a skill change proposal form according to action mode and business rules.
 *
 * @param {"ADD"|"UPDATE"|"REMOVE"} mode Proposal mode
 * @param {Object} form Form state values
 * @param {number|string} [form.skill_id] Selected skill ID
 * @param {string} [form.proposed_skill_name] Custom new skill name (ADD mode)
 * @param {string} [form.proficiency] Selected proficiency level
 * @param {number|string} [form.years_of_experience] Years with skill (0-50)
 * @param {string} [form.justification] Proposal justification (10-500 chars)
 * @returns {{ isValid: boolean, errors: Record<string, string> }} Validation result
 */
export function validateProposal(mode, form = {}) {
  const errors = {};
  const currentMode = String(mode || "ADD").toUpperCase();

  // 1. Skill identifier validation
  if (currentMode === SKILL_ACTIONS.ADD) {
    const hasSkillId = Boolean(form.skill_id && Number(form.skill_id) > 0);
    const hasSkillName = Boolean(form.proposed_skill_name && String(form.proposed_skill_name).trim().length > 0);

    if (!hasSkillId && !hasSkillName) {
      errors.skill = "Please select an existing skill or enter a new skill name.";
    } else if (hasSkillName && !hasSkillId) {
      const cleanName = String(form.proposed_skill_name).trim();
      if (cleanName.length < 2) {
        errors.proposed_skill_name = "Skill name must be at least 2 characters.";
      } else if (cleanName.length > 100) {
        errors.proposed_skill_name = "Skill name cannot exceed 100 characters.";
      }
    }
  } else {
    // UPDATE and REMOVE require an existing assigned skill_id
    if (!form.skill_id || Number(form.skill_id) <= 0) {
      errors.skill_id = "An existing assigned skill is required.";
    }
  }

  // 2. Proficiency validation (Required for ADD and UPDATE)
  if (currentMode === SKILL_ACTIONS.ADD || currentMode === SKILL_ACTIONS.UPDATE) {
    if (!form.proficiency || !SKILL_PROFICIENCIES.includes(String(form.proficiency).toUpperCase())) {
      errors.proficiency = "Please select a valid proficiency level (Beginner, Intermediate, or Expert).";
    }
  }

  // 3. Years of experience validation (Required for ADD and UPDATE, 0-50 range)
  if (currentMode === SKILL_ACTIONS.ADD || currentMode === SKILL_ACTIONS.UPDATE) {
    const rawYears = form.years_of_experience;
    if (rawYears === undefined || rawYears === null || String(rawYears).trim() === "") {
      errors.years_of_experience = "Years of experience is required (0 to 50).";
    } else {
      const numYears = Number(rawYears);
      if (isNaN(numYears) || !Number.isInteger(numYears) || numYears < 0 || numYears > 50) {
        errors.years_of_experience = "Years of experience must be an integer between 0 and 50.";
      }
    }
  }

  // 4. Justification validation (Mandatory 10-500 characters for all modes)
  const rawJustification = form.justification !== undefined && form.justification !== null
    ? String(form.justification).trim()
    : "";

  if (!rawJustification) {
    errors.justification = "Justification is required (10–500 characters).";
  } else if (rawJustification.length < 10) {
    errors.justification = "Justification must be at least 10 characters.";
  } else if (rawJustification.length > 500) {
    errors.justification = "Justification cannot exceed 500 characters.";
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}

/**
 * Validates decision remarks for rejecting a skill change request.
 * Remarks are mandatory and must be at least 5 characters.
 *
 * @param {string} remarks
 * @returns {{ isValid: boolean, error: string|null }}
 */
export function validateRejectionRemarks(remarks) {
  const str = remarks !== undefined && remarks !== null ? String(remarks).trim() : "";
  if (!str) {
    return {
      isValid: false,
      error: "Remarks are mandatory when rejecting a proposal.",
    };
  }
  if (str.length < 5) {
    return {
      isValid: false,
      error: "Rejection remarks must be at least 5 characters.",
    };
  }
  if (str.length > 1000) {
    return {
      isValid: false,
      error: "Remarks cannot exceed 1000 characters.",
    };
  }
  return {
    isValid: true,
    error: null,
  };
}

/**
 * Describes a skill proposal change cleanly for presentation.
 * Formats:
 * - ADD: "Add {skill} ({proficiency}, {years} yrs)"
 * - UPDATE: "{skill} → {new_skill|proficiency} ({years} yrs)"
 * - REMOVE: "Remove {skill}"
 *
 * @param {Object} request SkillChangeRequest representation
 * @returns {string} Human-readable summary
 */
export function describeChange(request) {
  if (!request) return "—";

  const skillName = request.skill_name || request.proposed_skill_name || "Skill";
  const action = (request.action || "").toUpperCase();
  const proficiency = request.proficiency
    ? PROFICIENCY_LABELS[request.proficiency] || request.proficiency
    : "";
  const years = request.years_of_experience != null ? `${request.years_of_experience} yrs` : "";

  if (action === SKILL_ACTIONS.ADD) {
    const details = [proficiency, years].filter(Boolean).join(", ");
    return `Add ${skillName}${details ? ` (${details})` : ""}`;
  }

  if (action === SKILL_ACTIONS.UPDATE) {
    if (request.proposed_skill_name && request.proposed_skill_name !== request.skill_name) {
      const details = [proficiency, years].filter(Boolean).join(", ");
      return `${request.skill_name || "Current"} → ${request.proposed_skill_name}${details ? ` (${details})` : ""}`;
    }
    const details = [proficiency, years].filter(Boolean).join(", ");
    return `${skillName} → ${details || "Updated"}`;
  }

  if (action === SKILL_ACTIONS.REMOVE) {
    return `Remove ${skillName}`;
  }

  return skillName;
}

/**
 * Formats a date string into readable display format (e.g. "Nov 23, 2026").
 *
 * @param {string|Date} dateStr
 * @returns {string}
 */
export function formatSkillDate(dateStr) {
  if (!dateStr) return "—";
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return String(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return String(dateStr);
  }
}
