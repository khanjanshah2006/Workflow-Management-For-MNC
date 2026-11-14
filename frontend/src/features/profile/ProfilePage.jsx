import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { profileApi } from "../../api/profileApi";
import { useAuth } from "../../hooks/useAuth";
import "./profile.css";

/**
 * Validates telephone number according to international and domestic standards (E.164).
 * Requires 7 to 15 digits, allowing standard punctuation (+, spaces, hyphens, parentheses, dots).
 *
 * @param {string} phone
 * @returns {string|null} Error message or null if valid
 */
export function validatePhoneNumber(phone) {
  if (phone === null || phone === undefined) {
    return "Phone number is required.";
  }
  const str = String(phone).trim();
  if (!str) {
    return "Phone number is required.";
  }

  // Basic format check (only allows digits, +, spaces, hyphens, parentheses, and dots)
  const phonePattern = /^\+?[0-9\s\-().]{7,25}$/;
  if (!phonePattern.test(str)) {
    return "Please enter a valid phone number (e.g. +1 555-123-4567).";
  }

  // Count raw digits (must be 7-15 digits per ITU E.164 standard)
  const digitsOnly = str.replace(/\D/g, "");
  if (digitsOnly.length < 7 || digitsOnly.length > 15) {
    return "Phone number must contain between 7 and 15 digits.";
  }

  return null;
}

/**
 * Formats ISO date string into readable display format (e.g., "Mar 15, 2023").
 * Supports both "YYYY-MM-DD" and full ISO timestamps.
 *
 * @param {string} dateStr
 * @returns {string}
 */
export function formatJoiningDate(dateStr) {
  if (!dateStr) return "—";
  try {
    const cleanStr = String(dateStr).split("T")[0];
    const [year, month, day] = cleanStr.split("-");
    if (!year || !month || !day) return String(dateStr);
    const date = new Date(Number(year), Number(month) - 1, Number(day));
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

/**
 * Generates 1-2 letter uppercase initials from full name.
 * @param {string} name
 * @returns {string}
 */
export function getInitials(name) {
  if (!name || typeof name !== "string") return "EM";
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name.trim().slice(0, 2).toUpperCase();
}

/**
 * ProfilePage (US-03 / Issue #39: Employee Self-Service Profile Page)
 *
 * Features:
 * - Read-only display of Employee code, Department, Designation, Joining date, Email.
 * - "Edit Profile" toggle for Phone, Emergency contact, and Bio.
 * - Phone number validation before submitting.
 * - Updates editable fields via PUT /api/v1/profile/me.
 * - Success and error toasts on submission.
 * - Loading skeleton, Error state with retry, and Empty state.
 */
export default function ProfilePage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const phoneInputRef = useRef(null);

  // Edit toggle state (Requirement 2)
  const [isEditing, setIsEditing] = useState(false);

  // Form input state for editable fields (Phone, Emergency contact, Bio)
  const [formData, setFormData] = useState({
    phone: "",
    emergency_contact: "",
    bio: "",
  });

  // Validation errors
  const [fieldErrors, setFieldErrors] = useState({});

  // Toast state: { type: 'success' | 'error', title: string, message: string, id: number } | null
  const [toast, setToast] = useState(null);
  const toastTimerRef = useRef(null);

  const showToast = (type, title, message) => {
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
    }
    setToast({ type, title, message, id: Date.now() });
    toastTimerRef.current = setTimeout(
      () => {
        setToast(null);
      },
      type === "error" ? 6000 : 4500
    );
  };

  const dismissToast = () => {
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
    }
    setToast(null);
  };

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    };
  }, []);

  // 1. Fetch current employee profile: GET /api/v1/profile/me
  const {
    data: profile,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["profile", "me"],
    queryFn: profileApi.getMyProfile,
    retry: 1,
  });

  // Synchronize form data when profile loads or updates (only when not actively editing)
  useEffect(() => {
    if (profile && !isEditing) {
      setFormData({
        phone: profile.phone || "",
        emergency_contact: profile.emergency_contact || "",
        bio: profile.bio || "",
      });
    }
  }, [profile, isEditing]);

  // Focus phone input when entering edit mode
  useEffect(() => {
    if (isEditing && phoneInputRef.current) {
      phoneInputRef.current.focus();
    }
  }, [isEditing]);

  // 2. Mutation for updating profile: PUT /api/v1/profile/me (Requirement 4)
  const updateMutation = useMutation({
    mutationFn: (payload) => profileApi.updateMyProfile(payload),
    onSuccess: (updatedData) => {
      // Invalidate and optimistically update React Query cache
      queryClient.setQueryData(["profile", "me"], updatedData);
      queryClient.invalidateQueries({ queryKey: ["profile", "me"] });

      setIsEditing(false);
      setFieldErrors({});

      // Show success toast (Requirement 5)
      showToast(
        "success",
        "Profile Updated",
        "Your contact information and bio have been successfully saved."
      );
    },
    onError: (err) => {
      // Show error toast (Requirement 6)
      const message =
        err?.message ||
        err?.data?.detail ||
        "An unexpected error occurred while saving your profile. Please try again.";
      showToast("error", "Update Failed", message);
    },
  });

  const handleStartEdit = () => {
    if (profile) {
      setFormData({
        phone: profile.phone || "",
        emergency_contact: profile.emergency_contact || "",
        bio: profile.bio || "",
      });
    }
    setFieldErrors({});
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    if (profile) {
      setFormData({
        phone: profile.phone || "",
        emergency_contact: profile.emergency_contact || "",
        bio: profile.bio || "",
      });
    }
    setFieldErrors({});
    setIsEditing(false);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    // Clear field-level error upon typing
    if (fieldErrors[name]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (updateMutation.isPending) return;

    // Validate phone number before submitting (Requirement 3)
    const errors = {};
    const phoneError = validatePhoneNumber(formData.phone);
    if (phoneError) {
      errors.phone = phoneError;
    }

    if (formData.emergency_contact && formData.emergency_contact.length > 100) {
      errors.emergency_contact = "Emergency contact must not exceed 100 characters.";
    }

    if (formData.bio && formData.bio.length > 500) {
      errors.bio = "Bio must not exceed 500 characters.";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      if (errors.phone && phoneInputRef.current) {
        phoneInputRef.current.focus();
      }
      return;
    }

    setFieldErrors({});

    // Submit PUT API (Requirement 4)
    updateMutation.mutate({
      phone: formData.phone.trim(),
      emergency_contact: formData.emergency_contact.trim(),
      bio: formData.bio.trim(),
    });
  };

  // RBAC Client Guard (Client role has no internal employee profile)
  if (user?.role === "CLIENT") {
    return (
      <section className="page profile-page-container">
        <div className="profile-header-row">
          <div className="profile-header-info">
            <div className="page-eyebrow">WORKSPACE / EMPLOYEE SELF-SERVICE</div>
            <h1>Employee Profile</h1>
          </div>
        </div>

        <div className="placeholder-panel">
          <div className="placeholder-symbol">🔒</div>
          <h2>Access Restricted</h2>
          <p>
            Client portal accounts do not have an internal employee profile.
          </p>
          <span className="status-label" style={{ marginTop: 24 }}>
            RBAC Protected · Internal Employees Only
          </span>
        </div>
      </section>
    );
  }

  // Unauthenticated 401 State
  if (!isLoading && isError && error?.status === 401) {
    return (
      <section className="page profile-page-container">
        <div className="profile-header-row">
          <div className="profile-header-info">
            <div className="page-eyebrow">WORKSPACE / EMPLOYEE SELF-SERVICE</div>
            <h1>Employee Profile</h1>
            <p className="page-description">
              View your organizational profile and manage your personal contact information.
            </p>
          </div>
        </div>

        <div className="placeholder-panel">
          <div className="placeholder-symbol">🔒</div>
          <h2>Authentication Required</h2>
          <p>
            You must be signed in to view and manage your employee profile.
          </p>
          <div style={{ marginTop: 20 }}>
            <Link to="/login" className="btn-primary" style={{ textDecoration: "none" }}>
              Go to Sign In →
            </Link>
          </div>
          <span className="status-label" style={{ marginTop: 24 }}>
            RBAC Protected · Active Session Required
          </span>
        </div>
      </section>
    );
  }

  const departmentName =
    (typeof profile?.department === "string" ? profile.department : null) ||
    profile?.department?.name ||
    profile?.department?.description ||
    "Not assigned";
  const initials = getInitials(profile?.full_name);
  const isActive = (profile?.status || "ACTIVE").toUpperCase() === "ACTIVE";

  return (
    <section className="page profile-page-container">
      {/* Toast Notification Element (Requirements 5 & 6) */}
      {toast && (
        <div className="profile-toast-container" aria-live="polite">
          <div
            className={`profile-toast profile-toast-${toast.type}`}
            role={toast.type === "error" ? "alert" : "status"}
          >
            <span className="profile-toast-icon" aria-hidden="true">
              {toast.type === "success" ? "✓" : "⚠"}
            </span>
            <div className="profile-toast-content">
              <div className="profile-toast-title">{toast.title}</div>
              <div className="profile-toast-message">{toast.message}</div>
            </div>
            <button
              type="button"
              className="profile-toast-close"
              onClick={dismissToast}
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Page Header */}
      <div className="profile-header-row">
        <div className="profile-header-info">
          <div className="page-eyebrow">WORKSPACE / EMPLOYEE SELF-SERVICE</div>
          <h1>My Profile</h1>
          <p className="page-description">
            Review organizational assignment details and maintain your self-service contact records.
          </p>
        </div>

        {/* Global Refresh Button */}
        {!isLoading && !isError && (
          <button
            type="button"
            className="btn-secondary"
            onClick={() => refetch()}
            disabled={isFetching || updateMutation.isPending}
            title="Refresh profile data from server"
          >
            {isFetching ? "Refreshing..." : "↻ Refresh"}
          </button>
        )}
      </div>

      {/* Loading Skeletons */}
      {isLoading && (
        <div className="profile-skeleton-card" aria-busy="true" aria-label="Loading profile details">
          <div style={{ display: "flex", gap: "20px", alignItems: "center", marginBottom: "28px" }}>
            <div className="profile-skeleton-line" style={{ width: "72px", height: "72px", borderRadius: "50%" }} />
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", flex: 1 }}>
              <div className="profile-skeleton-line" style={{ width: "240px", height: "24px" }} />
              <div className="profile-skeleton-line" style={{ width: "160px", height: "16px" }} />
            </div>
          </div>
          <div className="profile-sections-grid">
            <div className="profile-skeleton-line" style={{ height: "300px" }} />
            <div className="profile-skeleton-line" style={{ height: "300px" }} />
          </div>
        </div>
      )}

      {/* Error State with Retry (Non-401 errors) */}
      {!isLoading && isError && (
        <div className="profile-error-banner" role="alert">
          <div className="profile-error-banner-content">
            <span className="profile-error-banner-icon" aria-hidden="true">⚠</span>
            <div>
              <strong>Unable to load employee profile</strong>
              <div style={{ fontSize: "12.5px", marginTop: "2px" }}>
                {error?.message || "Could not retrieve your employee profile. Please verify your connection."}
              </div>
            </div>
          </div>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => refetch()}
          >
            Try Again
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !isError && !profile && (
        <div className="placeholder-panel">
          <div className="placeholder-symbol">👤</div>
          <h2>No Profile Record Found</h2>
          <p>We could not find an employee profile associated with your account.</p>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => refetch()}
            style={{ marginTop: 16 }}
          >
            Refresh
          </button>
        </div>
      )}

      {/* Main Profile View & Edit Form */}
      {!isLoading && !isError && profile && (
        <>
          {/* Profile Hero Summary Card */}
          <div className="profile-hero-card">
            <div className="profile-hero-identity">
              <div className="profile-avatar-large" aria-hidden="true">
                {initials}
              </div>
              <div className="profile-hero-details">
                <h2>{profile.full_name || "Employee"}</h2>
                <div className="profile-hero-sub">
                  <span>{profile.designation || "Designation unspecified"}</span>
                  <span className="profile-hero-sub-sep" aria-hidden="true">•</span>
                  <span>{departmentName}</span>
                </div>
                <div className="profile-badges-row">
                  <span
                    className={`profile-status-badge ${
                      isActive ? "profile-status-active" : "profile-status-inactive"
                    }`}
                  >
                    <span className="profile-status-dot" aria-hidden="true" />
                    {profile.status || "ACTIVE"}
                  </span>
                  <span className="profile-code-chip" title="Employee Identification Code">
                    {profile.emp_code}
                  </span>
                </div>
              </div>
            </div>

            {/* Edit Profile Toggle Button (Requirement 2) */}
            <div className="profile-hero-actions">
              {!isEditing ? (
                <button
                  type="button"
                  id="edit-profile-btn"
                  className="btn-primary"
                  onClick={handleStartEdit}
                  aria-label="Edit personal contact information"
                >
                  <span aria-hidden="true">✎</span> Edit Profile
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handleCancelEdit}
                  disabled={updateMutation.isPending}
                >
                  Cancel Editing
                </button>
              )}
            </div>
          </div>

          {/* Form wrapper for editable fields */}
          <form onSubmit={handleSubmit} noValidate>
            <div className="profile-sections-grid">
              {/* ============================================================== */}
              {/* SECTION 1: READ-ONLY ORGANIZATIONAL FIELDS (Requirement 1)      */}
              {/* ============================================================== */}
              <div className="profile-card">
                <div className="profile-card-header">
                  <div className="profile-card-title-group">
                    <h3>
                      <span aria-hidden="true">🏢</span> Organizational Information
                    </h3>
                    <p className="profile-card-subtitle">
                      Managed by Human Resources & Administration
                    </p>
                  </div>
                  <span className="profile-readonly-badge" title="These fields cannot be self-edited">
                    <span aria-hidden="true">🔒</span> Read-only
                  </span>
                </div>

                <div className="profile-card-body">
                  {/* 1. Employee Code */}
                  <div className="profile-field">
                    <label className="profile-field-label" htmlFor="read-emp-code">
                      Employee Code
                    </label>
                    <div
                      id="read-emp-code"
                      className="profile-field-readonly-box profile-field-code"
                      aria-readonly="true"
                    >
                      <span>{profile.emp_code}</span>
                      <span className="profile-field-readonly-tag">System ID</span>
                    </div>
                  </div>

                  {/* 2. Department */}
                  <div className="profile-field">
                    <label className="profile-field-label" htmlFor="read-dept">
                      Department
                    </label>
                    <div
                      id="read-dept"
                      className="profile-field-readonly-box"
                      aria-readonly="true"
                    >
                      <span>{departmentName}</span>
                      <span className="profile-field-readonly-tag">Assigned</span>
                    </div>
                  </div>

                  {/* 3. Designation */}
                  <div className="profile-field">
                    <label className="profile-field-label" htmlFor="read-designation">
                      Designation
                    </label>
                    <div
                      id="read-designation"
                      className="profile-field-readonly-box"
                      aria-readonly="true"
                    >
                      <span>{profile.designation || "—"}</span>
                      <span className="profile-field-readonly-tag">Official</span>
                    </div>
                  </div>

                  {/* 4. Joining Date */}
                  <div className="profile-field">
                    <label className="profile-field-label" htmlFor="read-doj">
                      Joining Date
                    </label>
                    <div
                      id="read-doj"
                      className="profile-field-readonly-box"
                      aria-readonly="true"
                    >
                      <span>{formatJoiningDate(profile.date_of_joining)}</span>
                      <span className="profile-field-readonly-tag">Employment Start</span>
                    </div>
                  </div>

                  {/* 5. Email */}
                  <div className="profile-field">
                    <label className="profile-field-label" htmlFor="read-email">
                      Official Email
                    </label>
                    <div
                      id="read-email"
                      className="profile-field-readonly-box"
                      aria-readonly="true"
                    >
                      <span>{profile.email}</span>
                      <span className="profile-field-readonly-tag">Corporate SSO</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* ============================================================== */}
              {/* SECTION 2: EDITABLE PERSONAL & CONTACT FIELDS (Requirements 2-4)*/}
              {/* ============================================================== */}
              <div className="profile-card">
                <div className="profile-card-header">
                  <div className="profile-card-title-group">
                    <h3>
                      <span aria-hidden="true">📱</span> Personal & Contact Details
                    </h3>
                    <p className="profile-card-subtitle">
                      {isEditing
                        ? "Editing personal contact info and biography"
                        : "Self-service contact and communication details"}
                    </p>
                  </div>
                  {!isEditing && (
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={handleStartEdit}
                      style={{ fontSize: "12px", padding: "5px 12px" }}
                    >
                      Edit
                    </button>
                  )}
                </div>

                <div className="profile-card-body">
                  {/* 1. Phone Field */}
                  <div className="profile-field">
                    <label className="profile-field-label" htmlFor="profile-phone">
                      Phone Number {isEditing && <span style={{ color: "#d92d20" }}>*</span>}
                    </label>
                    {isEditing ? (
                      <>
                        <input
                          ref={phoneInputRef}
                          id="profile-phone"
                          name="phone"
                          type="tel"
                          className={`profile-input ${fieldErrors.phone ? "profile-input-error" : ""}`}
                          placeholder="+1 555-123-4567"
                          value={formData.phone}
                          onChange={handleChange}
                          disabled={updateMutation.isPending}
                          aria-invalid={Boolean(fieldErrors.phone)}
                          aria-describedby={fieldErrors.phone ? "phone-error-msg" : "phone-hint-msg"}
                          maxLength={50}
                          required
                        />
                        <div className="profile-field-footer">
                          {fieldErrors.phone ? (
                            <span id="phone-error-msg" className="profile-field-error-msg" role="alert">
                              {fieldErrors.phone}
                            </span>
                          ) : (
                            <span id="phone-hint-msg" className="profile-field-hint">
                              Include country code if applicable (e.g. +1 555-123-4567)
                            </span>
                          )}
                        </div>
                      </>
                    ) : (
                      <div className="profile-field-readonly-box">
                        <span>
                          {profile.phone ? (
                            <a
                              href={`tel:${profile.phone}`}
                              style={{ color: "#4456d9", textDecoration: "none" }}
                            >
                              {profile.phone}
                            </a>
                          ) : (
                            <span style={{ color: "#94a3b8", fontStyle: "italic" }}>
                              Not provided
                            </span>
                          )}
                        </span>
                        <span className="profile-field-readonly-tag">Primary Voice</span>
                      </div>
                    )}
                  </div>

                  {/* 2. Emergency Contact Field */}
                  <div className="profile-field">
                    <label className="profile-field-label" htmlFor="profile-emergency-contact">
                      Emergency Contact
                    </label>
                    {isEditing ? (
                      <>
                        <input
                          id="profile-emergency-contact"
                          name="emergency_contact"
                          type="text"
                          className={`profile-input ${
                            fieldErrors.emergency_contact ? "profile-input-error" : ""
                          }`}
                          placeholder="e.g. Jane Doe (Spouse) +1 555-987-6543"
                          value={formData.emergency_contact}
                          onChange={handleChange}
                          disabled={updateMutation.isPending}
                          aria-invalid={Boolean(fieldErrors.emergency_contact)}
                          aria-describedby={
                            fieldErrors.emergency_contact ? "emergency-error-msg" : "emergency-hint-msg"
                          }
                          maxLength={100}
                        />
                        <div className="profile-field-footer">
                          {fieldErrors.emergency_contact ? (
                            <span
                              id="emergency-error-msg"
                              className="profile-field-error-msg"
                              role="alert"
                            >
                              {fieldErrors.emergency_contact}
                            </span>
                          ) : (
                            <span id="emergency-hint-msg" className="profile-field-hint">
                              Name, relationship, and contact telephone
                            </span>
                          )}
                        </div>
                      </>
                    ) : (
                      <div className="profile-field-readonly-box">
                        <span>
                          {profile.emergency_contact ? (
                            profile.emergency_contact
                          ) : (
                            <span style={{ color: "#94a3b8", fontStyle: "italic" }}>
                              Not provided
                            </span>
                          )}
                        </span>
                        <span className="profile-field-readonly-tag">Emergency</span>
                      </div>
                    )}
                  </div>

                  {/* 3. Bio Field */}
                  <div className="profile-field">
                    <label className="profile-field-label" htmlFor="profile-bio">
                      Professional Bio
                    </label>
                    {isEditing ? (
                      <>
                        <textarea
                          id="profile-bio"
                          name="bio"
                          className={`profile-textarea ${fieldErrors.bio ? "profile-input-error" : ""}`}
                          placeholder="Brief summary of your professional background, domain expertise, skills, or personal interests..."
                          value={formData.bio}
                          onChange={handleChange}
                          disabled={updateMutation.isPending}
                          aria-invalid={Boolean(fieldErrors.bio)}
                          aria-describedby={fieldErrors.bio ? "bio-error-msg" : "bio-hint-msg"}
                          maxLength={500}
                          rows={4}
                        />
                        <div className="profile-field-footer">
                          {fieldErrors.bio ? (
                            <span id="bio-error-msg" className="profile-field-error-msg" role="alert">
                              {fieldErrors.bio}
                            </span>
                          ) : (
                            <span id="bio-hint-msg" className="profile-field-hint">
                              Visible across team collaboration views
                            </span>
                          )}
                          <span className="profile-char-count">
                            {(formData.bio || "").length}/500
                          </span>
                        </div>
                      </>
                    ) : (
                      <div
                        className="profile-field-readonly-box"
                        style={{ minHeight: "80px", alignItems: "flex-start", whiteSpace: "pre-wrap" }}
                      >
                        {profile.bio ? (
                          <span>{profile.bio}</span>
                        ) : (
                          <span style={{ color: "#94a3b8", fontStyle: "italic" }}>
                            No biography provided yet. Click "Edit Profile" to add one.
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Form Footer Action Buttons (Visible only when in edit mode) */}
                {isEditing && (
                  <div className="profile-card-footer">
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={handleCancelEdit}
                      disabled={updateMutation.isPending}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      id="save-profile-btn"
                      className="btn-primary btn-save-profile"
                      disabled={updateMutation.isPending}
                    >
                      {updateMutation.isPending ? (
                        <>
                          <span className="profile-spinner" aria-hidden="true" />
                          <span>Saving Changes...</span>
                        </>
                      ) : (
                        "Save Changes"
                      )}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </form>
        </>
      )}
    </section>
  );
}
