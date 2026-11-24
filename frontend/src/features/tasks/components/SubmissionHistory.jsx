import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getTaskSubmissions, openDeliverable } from "../../../api/tasksApi";
import { useAuth, normalizeRole } from "../../../hooks/useAuth";

/**
 * Formats ISO date/time into user-friendly display format.
 * @param {string} dateStr
 * @returns {string}
 */
function formatSubmissionDate(dateStr) {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return dateStr;
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

/**
 * Format bytes into readable format.
 * @param {number} bytes
 * @returns {string}
 */
function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `(${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]})`;
}

/**
 * SubmissionHistory Component (US-11, US-12, US-13 / Issue #162)
 *
 * Renders chronological task submission attempts for:
 * - The Task Assignee
 * - The Team Lead
 * - The Project Manager (PM)
 * - System Administrators
 *
 * Each attempt displays:
 * - Attempt number (1-based index)
 * - Submission date and time
 * - Submitter remarks
 * - Evaluation status (Approved / Rejected / Pending)
 * - Reviewer feedback on returned/rejected submissions
 * - Deliverable attachment download with auth token support via openDeliverable
 *
 * @param {Object} props
 * @param {number|string} props.taskId
 * @param {Object} props.task Current TaskDetailResponse object
 */
export default function SubmissionHistory({ taskId, task }) {
  const { user } = useAuth();
  const [downloadingUrl, setDownloadingUrl] = useState(null);
  const [downloadToast, setDownloadToast] = useState(null);

  // Auto-dismiss download toast
  useEffect(() => {
    if (!downloadToast) return;
    const timer = setTimeout(() => setDownloadToast(null), 4000);
    return () => clearTimeout(timer);
  }, [downloadToast]);

  // RBAC Check: Assignee, Team Lead, PM, Admin
  const role = normalizeRole(user?.role || user?.user_type || "");
  const isTL = role === "TEAM_LEAD" || role === "LEAD";
  const isPM = role === "PM" || role === "PROJECT_MANAGER";
  const isAdminRole = role === "ADMIN" || role === "SYSTEM_ADMIN";
  const isAssignee = Boolean(
    user &&
      task &&
      (user.account_id === task.assigned_to ||
        user.emp_id === task.assigned_to ||
        user.employee_id === task.assigned_to ||
        user.email === task.assignee?.email ||
        user.account_id === task.assignee?.account_id)
  );

  const canViewHistory = isAssignee || isTL || isPM || isAdminRole || !user;

  const {
    data,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["task-submissions", taskId],
    queryFn: () => getTaskSubmissions(taskId),
    enabled: Boolean(taskId) && canViewHistory,
    retry: 1,
  });

  if (!canViewHistory) {
    return null;
  }

  const handleDownload = async (url, fallbackName) => {
    if (!url || downloadingUrl) return;
    setDownloadingUrl(url);
    try {
      await openDeliverable(url, fallbackName);
    } catch (err) {
      if (err?.status === 403 || err?.message?.includes("403")) {
        setDownloadToast({
          type: "error",
          message: "You don't have access to this file",
        });
      } else if (err?.status === 404 || err?.message?.includes("404")) {
        setDownloadToast({
          type: "error",
          message: "File not found",
        });
      } else {
        setDownloadToast({
          type: "error",
          message: err?.message || "Failed to download deliverable",
        });
      }
    } finally {
      setDownloadingUrl(null);
    }
  };

  // Normalize array from response
  const rawSubmissions = Array.isArray(data)
    ? data
    : Array.isArray(data?.submissions)
    ? data.submissions
    : [];

  // Sort chronological (oldest to newest)
  const submissions = [...rawSubmissions].sort((a, b) => {
    const timeA = new Date(a.submitted_at || 0).getTime();
    const timeB = new Date(b.submitted_at || 0).getTime();
    return timeA - timeB;
  });

  return (
    <div className="drawer-section submission-history-section" aria-label="Submission History">
      <div className="submission-history-header">
        <h3 className="drawer-section-title">Submission History</h3>
        {submissions.length > 0 && (
          <span className="submission-count-badge">
            {submissions.length} {submissions.length === 1 ? "attempt" : "attempts"}
          </span>
        )}
      </div>

      {/* Download error toast */}
      {downloadToast && (
        <div
          className={`tasks-toast ${
            downloadToast.type === "error" ? "toast-error" : "toast-success"
          }`}
          style={{ position: "static", marginBottom: 12, width: "100%" }}
          role="status"
        >
          <span aria-hidden="true">
            {downloadToast.type === "error" ? "⚠️" : "✓"}
          </span>
          <span>{downloadToast.message}</span>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="submission-loading">
          <span className="submission-spinner" aria-hidden="true" />
          <span>Loading submission history...</span>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="submission-empty">
          <span style={{ color: "#dc2626" }}>⚠️ Unable to load submission history.</span>
          <button
            type="button"
            className="btn-link-unstyled"
            style={{ color: "#2563eb", textDecoration: "underline", marginLeft: 8 }}
            onClick={() => refetch()}
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && submissions.length === 0 && (
        <p className="submission-empty-text">
          No submission attempts recorded yet for this task.
        </p>
      )}

      {/* Chronological attempts list */}
      {!isLoading && !isError && submissions.length > 0 && (
        <div className="submission-attempts-list">
          {submissions.map((sub, index) => {
            const attemptNumber = index + 1;
            const isLatest = index === submissions.length - 1;

            // Determine status
            let statusLabel = "Submitted";
            let statusClass = "badge-status-in_review";

            if (!isLatest) {
              // Prior attempts before another submission are considered rejected
              statusLabel = "Rejected";
              statusClass = "badge-status-rejected";
            } else {
              // Latest attempt reflects current task state
              if (task?.status === "DONE") {
                statusLabel = "Approved";
                statusClass = "badge-status-done";
              } else if (task?.status === "REJECTED") {
                statusLabel = "Rejected";
                statusClass = "badge-status-rejected";
              } else if (task?.status === "IN_REVIEW") {
                statusLabel = "Pending";
                statusClass = "badge-status-in_review";
              } else {
                statusLabel = "Submitted";
                statusClass = "badge-status-in_progress";
              }
            }

            // Reviewer feedback (for rejected attempts)
            const showFeedback =
              (statusLabel === "Rejected" || !isLatest) &&
              (sub.rejection_feedback || (isLatest && task?.rejection_feedback));
            const feedbackText =
              sub.rejection_feedback || (isLatest && task?.rejection_feedback);

            const deliverableUrl = sub.file_url;
            const isCurrentlyDownloading = downloadingUrl === deliverableUrl;
            const downloadFilename =
              sub.file_name || `task-${taskId}-deliverable-attempt-${attemptNumber}`;

            return (
              <div
                key={sub.submission_id || index}
                className={`submission-attempt-card ${
                  isLatest ? "submission-attempt-latest" : ""
                }`}
              >
                <div className="submission-attempt-header">
                  <div className="submission-attempt-title">
                    <span className="submission-attempt-number">
                      Attempt #{attemptNumber}
                    </span>
                    <span className={`badge-status ${statusClass}`}>
                      <span className="badge-dot" aria-hidden="true" />
                      {statusLabel}
                    </span>
                  </div>
                  <span className="submission-attempt-date">
                    🕒 {formatSubmissionDate(sub.submitted_at)}
                  </span>
                </div>

                {/* Submitter Remarks */}
                <div className="submission-remarks-block">
                  <span className="submission-field-label">Remarks:</span>
                  <div className="submission-remarks-text">
                    {sub.remarks ? (
                      `“${sub.remarks}”`
                    ) : (
                      <span style={{ color: "#94a3b8", fontStyle: "italic" }}>
                        No remarks provided
                      </span>
                    )}
                  </div>
                </div>

                {/* Reviewer Feedback if Rejected */}
                {showFeedback && feedbackText && (
                  <div className="submission-feedback-block">
                    <div className="submission-feedback-title">
                      <span aria-hidden="true">↩</span>
                      <span>Reviewer Feedback:</span>
                    </div>
                    <div className="submission-feedback-text">{feedbackText}</div>
                  </div>
                )}

                {/* Attached Deliverable with Authenticated Download */}
                {deliverableUrl ? (
                  <div className="submission-download-row">
                    <button
                      type="button"
                      className="btn-download-deliverable"
                      onClick={() => handleDownload(deliverableUrl, downloadFilename)}
                      disabled={isCurrentlyDownloading}
                      title={`Download deliverable from Attempt #${attemptNumber}`}
                    >
                      <span aria-hidden="true">
                        {isCurrentlyDownloading ? "⏳" : "⬇"}
                      </span>
                      <span>
                        {isCurrentlyDownloading
                          ? "Downloading file..."
                          : sub.file_name || "Download Deliverable"}
                      </span>
                      {sub.file_size_bytes && (
                        <span className="submission-file-size">
                          {formatBytes(sub.file_size_bytes)}
                        </span>
                      )}
                    </button>
                  </div>
                ) : (
                  <div className="submission-no-file">
                    <span style={{ fontSize: 11.5, color: "#94a3b8", fontStyle: "italic" }}>
                      No attachment uploaded with this attempt
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

