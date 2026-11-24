import React, { useState, useEffect, useMemo } from "react";
import {
  SKILL_ACTIONS,
  SKILL_PROFICIENCIES,
  PROFICIENCY_LABELS,
  DEFAULT_CATALOG_SKILLS,
  validateProposal,
} from "../skills/skillRequestUtils.js";
import { proposeSkillChange } from "../../api/profileApi.js";

export { DEFAULT_CATALOG_SKILLS };

/**
 * ProposeSkillModal Component (US-34 / Issue #161)
 *
 * Supports three modes:
 * 1. ADD: Propose a new skill (from existing catalog or custom name), proficiency, years (0-50), and justification (10-500).
 * 2. UPDATE: Propose proficiency and/or years change for an existing assigned skill.
 * 3. REMOVE: Propose skill removal with justification only.
 */
export default function ProposeSkillModal({
  isOpen = false,
  mode = "ADD",
  skill = null,
  availableCatalog = DEFAULT_CATALOG_SKILLS,
  isLoadingCatalog = false,
  onClose,
  onSuccess,
  onError,
}) {
  const currentMode = (mode || "ADD").toUpperCase();

  // Normalize catalog to unique valid skill name strings (no hardcoded IDs)
  const catalogSkills = useMemo(() => {
    if (!Array.isArray(availableCatalog)) return [];
    return availableCatalog
      .map((item) => {
        if (typeof item === "string") return item.trim();
        return (item?.name || item?.proposed_skill_name || item?.skill_name || "").trim();
      })
      .filter((name) => Boolean(name));
  }, [availableCatalog]);

  // Skill entry type for ADD mode: "CATALOG" | "CUSTOM"
  const [skillEntryType, setSkillEntryType] = useState("CATALOG");

  const [formData, setFormData] = useState({
    skill_id: "",
    proposed_skill_name: "",
    proficiency: "INTERMEDIATE",
    years_of_experience: 1,
    justification: "",
  });

  const [fieldErrors, setFieldErrors] = useState({});
  const [serverError, setServerError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Initialize or reset form whenever modal opens or mode/skill changes
  useEffect(() => {
    if (!isOpen) {
      setFieldErrors({});
      setServerError(null);
      setIsSubmitting(false);
      return;
    }

    if (currentMode === SKILL_ACTIONS.UPDATE && skill) {
      setFormData({
        skill_id: skill.skill_id,
        proposed_skill_name: "",
        proficiency: skill.proficiency || "INTERMEDIATE",
        years_of_experience: skill.years_of_experience ?? 0,
        justification: "",
      });
      setSkillEntryType("CATALOG");
    } else if (currentMode === SKILL_ACTIONS.REMOVE && skill) {
      setFormData({
        skill_id: skill.skill_id,
        proposed_skill_name: "",
        proficiency: skill.proficiency || "",
        years_of_experience: skill.years_of_experience ?? 0,
        justification: "",
      });
      setSkillEntryType("CATALOG");
    } else {
      // ADD mode defaults: rely on proposed_skill_name, no hardcoded IDs
      setFormData({
        skill_id: "",
        proposed_skill_name: "",
        proficiency: "INTERMEDIATE",
        years_of_experience: 1,
        justification: "",
      });
      setSkillEntryType(catalogSkills.length > 0 ? "CATALOG" : "CUSTOM");
    }
    setFieldErrors({});
    setServerError(null);
  }, [isOpen, currentMode, skill, catalogSkills.length]);

  if (!isOpen) return null;

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));

    if (name === "years_of_experience") {
      const num = Number(value);
      if (value !== "" && (isNaN(num) || num < 0 || num > 50)) {
        setFieldErrors((prev) => ({
          ...prev,
          years_of_experience: "Years of experience must be an integer between 0 and 50.",
        }));
      } else {
        setFieldErrors((prev) => {
          const next = { ...prev };
          delete next.years_of_experience;
          return next;
        });
      }
    }

    if (
      fieldErrors[name] ||
      fieldErrors.skill ||
      (name === "proposed_skill_name" && (fieldErrors.proposed_skill_name || fieldErrors.skill_id))
    ) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        delete next.skill;
        delete next.proposed_skill_name;
        delete next.skill_id;
        return next;
      });
    }
    setServerError(null);
  };

  const handleEntryTypeChange = (type) => {
    setSkillEntryType(type);
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.skill;
      delete next.proposed_skill_name;
      delete next.skill_id;
      return next;
    });
    setServerError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    setServerError(null);

    // Prepare payload object for validation and API
    const validationForm = {
      justification: formData.justification,
    };

    if (currentMode === SKILL_ACTIONS.ADD) {
      validationForm.proposed_skill_name = formData.proposed_skill_name?.trim() || "";
      validationForm.proficiency = formData.proficiency;
      validationForm.years_of_experience = formData.years_of_experience;
    } else if (currentMode === SKILL_ACTIONS.UPDATE) {
      validationForm.skill_id = Number(skill?.skill_id || formData.skill_id);
      validationForm.proficiency = formData.proficiency;
      validationForm.years_of_experience = formData.years_of_experience;
    } else if (currentMode === SKILL_ACTIONS.REMOVE) {
      validationForm.skill_id = Number(skill?.skill_id || formData.skill_id);
    }

    const validation = validateProposal(currentMode, validationForm);
    if (!validation.isValid) {
      setFieldErrors(validation.errors);
      return;
    }

    setFieldErrors({});
    setIsSubmitting(true);

    try {
      const payload = {
        action: currentMode,
        justification: formData.justification.trim(),
      };

      if (currentMode === SKILL_ACTIONS.ADD) {
        payload.proposed_skill_name = formData.proposed_skill_name.trim();
        payload.proficiency = formData.proficiency;
        payload.years_of_experience = Number(formData.years_of_experience);
      } else if (currentMode === SKILL_ACTIONS.UPDATE) {
        payload.skill_id = Number(skill?.skill_id || formData.skill_id);
        payload.proficiency = formData.proficiency;
        payload.years_of_experience = Number(formData.years_of_experience);
      } else if (currentMode === SKILL_ACTIONS.REMOVE) {
        payload.skill_id = Number(skill?.skill_id || formData.skill_id);
      }

      const result = await proposeSkillChange(payload);

      if (onSuccess) {
        onSuccess(result, currentMode);
      }
      onClose();
    } catch (err) {
      const errMsg =
        err?.data?.detail ||
        err?.message ||
        "An unexpected error occurred while submitting the skill proposal.";
      setServerError(errMsg);
      if (onError) {
        onError(err);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const getModalTitle = () => {
    switch (currentMode) {
      case SKILL_ACTIONS.UPDATE:
        return "Propose Skill Change";
      case SKILL_ACTIONS.REMOVE:
        return "Propose Skill Removal";
      case SKILL_ACTIONS.ADD:
      default:
        return "Propose New Skill";
    }
  };

  const getSubmitButtonLabel = () => {
    if (isSubmitting) return "Submitting...";
    switch (currentMode) {
      case SKILL_ACTIONS.UPDATE:
        return "Submit Update Proposal";
      case SKILL_ACTIONS.REMOVE:
        return "Submit Removal Proposal";
      case SKILL_ACTIONS.ADD:
      default:
        return "Submit Skill Proposal";
    }
  };

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="skill-modal-title"
      data-testid="propose-skill-modal"
    >
      <div
        className="skill-modal-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="skill-modal-header">
          <div>
            <h2 id="skill-modal-title" className="skill-modal-title">
              {getModalTitle()}
            </h2>
            <p className="skill-modal-subtitle">
              {currentMode === SKILL_ACTIONS.REMOVE
                ? "Request the removal of a skill from your profile. Requires lead or HR review."
                : currentMode === SKILL_ACTIONS.UPDATE
                ? `Update proficiency or years of experience for ${skill?.name || "this skill"}.`
                : "Submit a new skill to be reviewed and added to your official profile."}
            </p>
          </div>
          <button
            type="button"
            className="skill-modal-close-btn"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close modal"
          >
            ×
          </button>
        </div>

        {serverError && (
          <div className="skill-alert-banner skill-alert-error" role="alert">
            <span className="skill-alert-icon" aria-hidden="true">⚠️</span>
            <div className="skill-alert-body">
              <strong>Submission Error</strong>
              <p>{serverError}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="skill-modal-body">
            {/* ============================================================== */}
            {/* SKILL NAME / SELECTION                                         */}
            {/* ============================================================== */}
            {currentMode === SKILL_ACTIONS.ADD ? (
              <div className="skill-form-group">
                <label className="skill-form-label">
                  Skill Source <span className="skill-required">*</span>
                </label>
                <div className="skill-entry-type-selector" role="radiogroup" aria-label="Skill source">
                  <label className={`skill-type-option ${skillEntryType === "CATALOG" ? "active" : ""}`}>
                    <input
                      type="radio"
                      name="skillEntryType"
                      value="CATALOG"
                      checked={skillEntryType === "CATALOG"}
                      onChange={() => handleEntryTypeChange("CATALOG")}
                      disabled={isSubmitting}
                    />
                    <span>Select Existing Skill</span>
                  </label>
                  <label className={`skill-type-option ${skillEntryType === "CUSTOM" ? "active" : ""}`}>
                    <input
                      type="radio"
                      name="skillEntryType"
                      value="CUSTOM"
                      checked={skillEntryType === "CUSTOM"}
                      onChange={() => handleEntryTypeChange("CUSTOM")}
                      disabled={isSubmitting}
                    />
                    <span>Enter New Skill Name</span>
                  </label>
                </div>

                {skillEntryType === "CATALOG" ? (
                  <div style={{ marginTop: "10px" }}>
                    {isLoadingCatalog ? (
                      <p style={{ margin: "4px 0", fontSize: "13px", color: "#64748b" }} data-testid="skill-catalog-loading">
                        Loading available skills...
                      </p>
                    ) : catalogSkills.length === 0 ? (
                      <p style={{ margin: "4px 0", fontSize: "13px", color: "#64748b" }} data-testid="skill-catalog-empty">
                        No catalog skills available. Please enter a custom skill name below.
                      </p>
                    ) : (
                      <select
                        id="skill-select-catalog"
                        name="proposed_skill_name"
                        className={`skill-select ${
                          fieldErrors.skill || fieldErrors.proposed_skill_name ? "skill-input-error" : ""
                        }`}
                        value={formData.proposed_skill_name}
                        onChange={handleInputChange}
                        disabled={isSubmitting}
                        aria-invalid={Boolean(fieldErrors.skill || fieldErrors.proposed_skill_name)}
                        data-testid="skill-catalog-select"
                      >
                        <option value="">-- Choose a skill --</option>
                        {catalogSkills.map((skillName) => (
                          <option key={skillName} value={skillName}>
                            {skillName}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                ) : (
                  <div style={{ marginTop: "10px" }}>
                    <input
                      id="skill-input-custom-name"
                      name="proposed_skill_name"
                      type="text"
                      className={`skill-input ${
                        fieldErrors.skill || fieldErrors.proposed_skill_name ? "skill-input-error" : ""
                      }`}
                      placeholder="e.g. Kotlin, Apache Kafka, GraphQL..."
                      value={formData.proposed_skill_name}
                      onChange={handleInputChange}
                      disabled={isSubmitting}
                      maxLength={100}
                      aria-invalid={Boolean(fieldErrors.skill || fieldErrors.proposed_skill_name)}
                      data-testid="skill-custom-name-input"
                    />
                  </div>
                )}

                {(fieldErrors.skill || fieldErrors.proposed_skill_name || fieldErrors.skill_id) && (
                  <span className="skill-field-error-msg" role="alert">
                    {fieldErrors.skill || fieldErrors.proposed_skill_name || fieldErrors.skill_id}
                  </span>
                )}
              </div>
            ) : (
              /* UPDATE and REMOVE modes: Read-only skill identifier */
              <div className="skill-form-group">
                <label className="skill-form-label">Skill</label>
                <div className="skill-readonly-box">
                  <span className="skill-readonly-title">{skill?.name || "Selected Skill"}</span>
                  {skill?.category && (
                    <span className="skill-category-tag">{skill.category}</span>
                  )}
                </div>
              </div>
            )}

            {/* ============================================================== */}
            {/* PROFICIENCY & YEARS (ADD & UPDATE MODES ONLY)                  */}
            {/* ============================================================== */}
            {currentMode !== SKILL_ACTIONS.REMOVE && (
              <div className="skill-form-row">
                <div className="skill-form-group" style={{ flex: 1 }}>
                  <label htmlFor="skill-proficiency" className="skill-form-label">
                    Proficiency <span className="skill-required">*</span>
                  </label>
                  <select
                    id="skill-proficiency"
                    name="proficiency"
                    className={`skill-select ${fieldErrors.proficiency ? "skill-input-error" : ""}`}
                    value={formData.proficiency}
                    onChange={handleInputChange}
                    disabled={isSubmitting}
                    aria-invalid={Boolean(fieldErrors.proficiency)}
                    data-testid="skill-proficiency-select"
                  >
                    {SKILL_PROFICIENCIES.map((prof) => (
                      <option key={prof} value={prof}>
                        {PROFICIENCY_LABELS[prof] || prof}
                      </option>
                    ))}
                  </select>
                  {fieldErrors.proficiency && (
                    <span className="skill-field-error-msg" role="alert">
                      {fieldErrors.proficiency}
                    </span>
                  )}
                </div>

                <div className="skill-form-group" style={{ flex: 1 }}>
                  <label htmlFor="skill-years-exp" className="skill-form-label">
                    Years of Experience (0–50) <span className="skill-required">*</span>
                  </label>
                  <input
                    id="skill-years-exp"
                    name="years_of_experience"
                    type="number"
                    min="0"
                    max="50"
                    step="1"
                    className={`skill-input ${fieldErrors.years_of_experience ? "skill-input-error" : ""}`}
                    value={formData.years_of_experience}
                    onChange={handleInputChange}
                    disabled={isSubmitting}
                    aria-invalid={Boolean(fieldErrors.years_of_experience)}
                    data-testid="skill-years-input"
                  />
                  {fieldErrors.years_of_experience && (
                    <span className="skill-field-error-msg" role="alert">
                      {fieldErrors.years_of_experience}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* ============================================================== */}
            {/* JUSTIFICATION (ALL MODES)                                      */}
            {/* ============================================================== */}
            <div className="skill-form-group">
              <label htmlFor="skill-justification" className="skill-form-label">
                Justification <span className="skill-required">*</span>
                <span className="skill-field-hint-text">
                  (10–500 characters explaining the change or proof of experience)
                </span>
              </label>
              <textarea
                id="skill-justification"
                name="justification"
                className={`skill-textarea ${fieldErrors.justification ? "skill-input-error" : ""}`}
                placeholder={
                  currentMode === SKILL_ACTIONS.REMOVE
                    ? "Explain why this skill should be removed from your profile..."
                    : "Describe projects, responsibilities, or certifications demonstrating this skill level..."
                }
                value={formData.justification}
                onChange={handleInputChange}
                disabled={isSubmitting}
                maxLength={500}
                rows={4}
                aria-invalid={Boolean(fieldErrors.justification)}
                data-testid="skill-justification-textarea"
              />
              <div className="skill-field-footer">
                {fieldErrors.justification ? (
                  <span className="skill-field-error-msg" role="alert">
                    {fieldErrors.justification}
                  </span>
                ) : (
                  <span className="skill-char-hint">Minimum 10 characters</span>
                )}
                <span className="skill-char-count">
                  {(formData.justification || "").length}/500
                </span>
              </div>
            </div>
          </div>

          <div className="skill-modal-footer">
            <button
              type="button"
              className="skill-btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={currentMode === SKILL_ACTIONS.REMOVE ? "skill-btn-danger" : "skill-btn-primary"}
              disabled={isSubmitting}
              data-testid="skill-modal-submit-btn"
            >
              {getSubmitButtonLabel()}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
