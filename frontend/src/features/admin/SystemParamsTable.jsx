import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "../../api/adminApi";
import { useAuth, normalizeRole } from "../../hooks/useAuth";

/**
 * Validates parameter value against its declared backend value_type (US-46).
 * @param {string} valueType - 'integer' | 'boolean' | 'json' | 'string'
 * @param {string} value - String value to validate
 * @returns {string|null} Error message or null if valid
 */
export function validateParameterValue(valueType, value) {
  if (value === undefined || value === null || String(value).trim() === "") {
    return "Parameter value is required.";
  }

  const vType = (valueType || "string").trim().toLowerCase();
  const trimmed = String(value).trim();

  if (vType === "integer") {
    if (!/^-?\d+$/.test(trimmed)) {
      return "Value must be a valid integer.";
    }
  } else if (vType === "boolean") {
    const lower = trimmed.toLowerCase();
    if (lower !== "true" && lower !== "false" && lower !== "1" && lower !== "0") {
      return "Value must be a valid boolean ('true' or 'false').";
    }
  } else if (vType === "json") {
    try {
      JSON.parse(trimmed);
    } catch {
      return "Value must be valid JSON syntax (e.g. [\"A\",\"B\"]).";
    }
  } else if (vType === "string") {
    if (trimmed.length > 500) {
      return "Value must not exceed 500 characters.";
    }
  }

  return null;
}

/**
 * SystemParamsTable Component (US-46 / Issue #81)
 *
 * Displays all global system parameters with type badges and provides inline editing
 * with strict frontend type validation before submitting PUT /api/v1/admin/system-params/:key.
 */
export default function SystemParamsTable() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const isSystemAdmin = normalizeRole(user?.role || user?.user_type) === "SYSTEM_ADMIN";

  const [editingKey, setEditingKey] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [feedback, setFeedback] = useState(null); // { type: 'success' | 'error', text: string }

  // 1. Fetch system parameters: GET /api/v1/admin/system-params
  const {
    data: params = [],
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["admin", "system-params"],
    queryFn: adminApi.getSystemParams,
    retry: 1,
  });

  // 2. Mutation: PUT /api/v1/admin/system-params/:key
  const updateMutation = useMutation({
    mutationFn: ({ key, value }) => adminApi.updateSystemParam(key, value),
    onSuccess: (updatedParam) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "system-params"] });
      setEditingKey(null);
      setEditValue("");
      setFieldError("");
      setFeedback({
        type: "success",
        text: `Parameter "${updatedParam?.key || editingKey}" successfully updated.`,
      });
      setTimeout(() => setFeedback(null), 4500);
    },
    onError: (err) => {
      const msg = err?.message || "Failed to update system parameter.";
      setFieldError(msg);
      setFeedback({ type: "error", text: msg });
    },
  });

  const handleStartEdit = (param) => {
    if (!isSystemAdmin) return;
    setEditingKey(param.key);
    setEditValue(param.value);
    setFieldError("");
    setFeedback(null);
  };

  const handleCancelEdit = () => {
    setEditingKey(null);
    setEditValue("");
    setFieldError("");
  };

  const handleSaveEdit = (param) => {
    if (!isSystemAdmin) {
      setFieldError("Permission denied. Only SYSTEM_ADMIN can update system parameters.");
      return;
    }

    // Validate value based on actual parameter data type before sending PUT request
    const validationError = validateParameterValue(param.value_type, editValue);
    if (validationError) {
      setFieldError(validationError);
      return;
    }

    setFieldError("");
    updateMutation.mutate({
      key: param.key,
      value: editValue.trim(),
    });
  };

  return (
    <div className="admin-card">
      <div className="admin-card-header">
        <div className="admin-card-title-group">
          <h2>
            <span aria-hidden="true">⚙️</span> Global System Parameters
          </h2>
          <p className="admin-card-subtitle">
            Configure system-wide operational thresholds, session constraints, and security limits.
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="admin-card-badge">
            {params.length} {params.length === 1 ? "Parameter" : "Parameters"}
          </span>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => refetch()}
            disabled={isFetching || updateMutation.isPending}
            style={{ fontSize: "12px", padding: "6px 12px" }}
            title="Refresh parameters from server"
          >
            {isFetching ? "Refreshing..." : "↻ Refresh"}
          </button>
        </div>
      </div>

      {feedback && (
        <div
          className={feedback.type === "success" ? "modal-alert-success" : "modal-alert-error"}
          style={{ margin: "16px 24px 0" }}
          role={feedback.type === "error" ? "alert" : "status"}
        >
          <span>{feedback.type === "success" ? "✓" : "⚠"}</span>
          <span>{feedback.text}</span>
        </div>
      )}

      {/* Loading Skeletons */}
      {isLoading && (
        <div style={{ padding: 24 }} aria-busy="true" aria-label="Loading system parameters">
          <div className="skeleton-line" style={{ height: 28, marginBottom: 12, width: "100%" }} />
          <div className="skeleton-line" style={{ height: 36, marginBottom: 8, width: "100%" }} />
          <div className="skeleton-line" style={{ height: 36, marginBottom: 8, width: "100%" }} />
          <div className="skeleton-line" style={{ height: 36, width: "100%" }} />
        </div>
      )}

      {/* Error State with Retry */}
      {!isLoading && isError && (
        <div style={{ padding: 24 }}>
          <div className="profile-error-banner" role="alert">
            <div className="profile-error-banner-content">
              <span className="profile-error-banner-icon" aria-hidden="true">⚠</span>
              <div>
                <strong>Failed to load system parameters</strong>
                <div style={{ fontSize: "12.5px", marginTop: "2px" }}>
                  {error?.message || "Could not retrieve operational parameters."}
                </div>
              </div>
            </div>
            <button type="button" className="btn-secondary" onClick={() => refetch()}>
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !isError && params.length === 0 && (
        <div style={{ padding: 36, textAlign: "center" }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>⚙️</div>
          <h3 style={{ margin: "0 0 6px", fontSize: 15, fontWeight: 700, color: "#1e293b" }}>
            No System Parameters Found
          </h3>
          <p style={{ margin: 0, fontSize: 13, color: "#64748b" }}>
            There are currently no operational parameters seeded in the system.
          </p>
        </div>
      )}

      {/* Parameters Table */}
      {!isLoading && !isError && params.length > 0 && (
        <div className="admin-table-container">
          <table className="admin-table" aria-label="Global system parameters table">
            <thead>
              <tr>
                <th scope="col" style={{ width: "28%" }}>Parameter Key</th>
                <th scope="col" style={{ width: "14%" }}>Data Type</th>
                <th scope="col" style={{ width: "38%" }}>Configuration Value</th>
                <th scope="col" style={{ width: "20%", textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {params.map((param) => {
                const isEditingThis = editingKey === param.key;
                const typeKey = (param.value_type || "string").toLowerCase();

                return (
                  <tr key={param.key}>
                    {/* Parameter Identity */}
                    <td>
                      <div className="param-key">{param.key}</div>
                      {param.description && (
                        <div className="param-desc" title={param.description}>
                          {param.description}
                        </div>
                      )}
                    </td>

                    {/* Data Type Pill */}
                    <td>
                      <span className={`type-pill type-pill-${typeKey}`}>
                        {param.value_type || "string"}
                      </span>
                    </td>

                    {/* Value / Inline Editing */}
                    <td>
                      {isEditingThis ? (
                        <div>
                          <div className="inline-edit-wrapper">
                            {typeKey === "boolean" ? (
                              <select
                                className="inline-input-select"
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                disabled={updateMutation.isPending}
                                autoFocus
                              >
                                <option value="true">true</option>
                                <option value="false">false</option>
                              </select>
                            ) : typeKey === "integer" ? (
                              <input
                                type="number"
                                step="1"
                                className={`inline-input ${fieldError ? "inline-input-error" : ""}`}
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                disabled={updateMutation.isPending}
                                autoFocus
                              />
                            ) : (
                              <input
                                type="text"
                                className={`inline-input ${fieldError ? "inline-input-error" : ""}`}
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                disabled={updateMutation.isPending}
                                maxLength={500}
                                autoFocus
                              />
                            )}
                          </div>
                          {fieldError && (
                            <span className="inline-error-msg" role="alert">
                              {fieldError}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span
                          style={{
                            fontFamily:
                              typeKey === "integer" || typeKey === "json"
                                ? "ui-monospace, monospace"
                                : "inherit",
                            fontWeight: 600,
                            color: typeKey === "boolean" && param.value === "true" ? "#047857" : "#1e293b",
                          }}
                        >
                          {param.value}
                        </span>
                      )}
                    </td>

                    {/* Actions */}
                    <td style={{ textAlign: "right" }}>
                      {!isSystemAdmin ? (
                        <span style={{ fontSize: "12px", color: "#94a3b8" }}>
                          Read-only
                        </span>
                      ) : isEditingThis ? (
                        <div style={{ display: "inline-flex", gap: 6 }}>
                          <button
                            type="button"
                            className="btn-inline-save"
                            onClick={() => handleSaveEdit(param)}
                            disabled={updateMutation.isPending}
                            title="Save parameter changes"
                          >
                            {updateMutation.isPending ? "Saving..." : "✓ Save"}
                          </button>
                          <button
                            type="button"
                            className="btn-inline-cancel"
                            onClick={handleCancelEdit}
                            disabled={updateMutation.isPending}
                            title="Cancel editing"
                          >
                            ✕
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={() => handleStartEdit(param)}
                          disabled={Boolean(editingKey)}
                          style={{ fontSize: "12px", padding: "4px 10px" }}
                          aria-label={`Edit ${param.key}`}
                        >
                          ✎ Edit
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

