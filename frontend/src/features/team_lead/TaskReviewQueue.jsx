import { useState, useMemo, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getReviewQueue, openDeliverable } from "../../api/tasksApi";

/**
 * TaskReviewQueue Component (US-12 & US-13)
 *
 * Team Lead consolidated review triage queue:
 * - Lists tasks currently awaiting inspection (status == IN_REVIEW)
 * - Highlights submission timestamp, submitter identity, and deliverable links
 * - Filterable by priority level and searchable by title/assignee
 * - Quick action trigger for reviewing and deciding approval/rejection
 *
 * @param {Object} props
 * @param {(task: Object) => void} props.onReviewTask Callback opening ReviewDecisionModal
 */
export default function TaskReviewQueue({ onReviewTask }) {
  const [priorityFilter, setPriorityFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [downloadingUrl, setDownloadingUrl] = useState(null);
  const [downloadToast, setDownloadToast] = useState(null);

  useEffect(() => {
    if (!downloadToast) return;
    const timer = setTimeout(() => setDownloadToast(null), 4000);
    return () => clearTimeout(timer);
  }, [downloadToast]);

  const handleOpenDeliverable = async (e, url, fallbackName) => {
    e.preventDefault();
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

  const {
    data: queueItems = [],
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["tasks", "review-queue", priorityFilter],
    queryFn: () => getReviewQueue({ priority: priorityFilter }),
  });

  // Client-side filtering for fast searching across title, assignee, and task ID
  const filteredItems = useMemo(() => {
    if (!Array.isArray(queueItems)) return [];
    if (!searchQuery.trim()) return queueItems;

    const q = searchQuery.toLowerCase().trim();
    return queueItems.filter((item) => {
      const titleMatch = Boolean(item.title && item.title.toLowerCase().includes(q));
      const idMatch = String(item.task_id).includes(q);
      const assigneeMatch = Boolean(
        item.assignee_name && item.assignee_name.toLowerCase().includes(q)
      );
      const remarksMatch = Boolean(
        item.submission_remarks && item.submission_remarks.toLowerCase().includes(q)
      );
      return titleMatch || idMatch || assigneeMatch || remarksMatch;
    });
  }, [queueItems, searchQuery]);

  const priorityTabs = ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"];

  return (
    <div className="review-queue-container">
      {/* Queue Toolbar: Search, Filters, and Refresh */}
      <div className="review-queue-toolbar">
        <div className="toolbar-search-wrapper">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            className="form-control queue-search-input"
            placeholder="Search pending reviews by title, task ID, or submitter..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              className="clear-search-btn"
              onClick={() => setSearchQuery("")}
              title="Clear search"
            >
              ✕
            </button>
          )}
        </div>

        <div className="toolbar-actions">
          <div className="priority-pills-group" role="radiogroup" aria-label="Filter by priority">
            {priorityTabs.map((p) => (
              <button
                key={p}
                className={`priority-pill ${priorityFilter === p ? "priority-pill-active" : ""}`}
                onClick={() => setPriorityFilter(p)}
                type="button"
              >
                {p === "ALL" ? "All Priorities" : p}
              </button>
            ))}
          </div>

          <button
            className="btn btn-outline-secondary btn-sm"
            onClick={() => refetch()}
            disabled={isFetching}
            title="Refresh review queue"
          >
            {isFetching ? "Refreshing..." : "↻ Refresh"}
          </button>
        </div>
      </div>

      {/* Toast Feedback for authenticated download */}
      {downloadToast && (
        <div
          className={`alert-banner ${
            downloadToast.type === "error"
              ? "alert-banner-danger"
              : "alert-banner-success"
          }`}
          role="alert"
          style={{ marginBottom: 16 }}
        >
          <span className="alert-icon">
            {downloadToast.type === "error" ? "⚠️" : "✓"}
          </span>
          <span>{downloadToast.message}</span>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="queue-loading-state">
          <div className="spinner-border" role="status" />
          <p>Loading review triage queue...</p>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="alert-banner alert-banner-danger" role="alert">
          <span className="alert-icon">⚠️</span>
          <div className="alert-body">
            <strong>Failed to load review queue:</strong>
            <span>{error?.message || "Ensure you are authenticated as a Team Lead or PM."}</span>
          </div>
          <button className="btn btn-secondary btn-xs" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !isError && filteredItems.length === 0 && (
        <div className="queue-empty-card">
          <div className="empty-icon-circle">✓</div>
          <h3>All Clear! No deliverables awaiting review</h3>
          <p>
            {searchQuery || priorityFilter !== "ALL"
              ? "No pending tasks match your active filters. Try adjusting your search query or priority filter."
              : "When team members submit task deliverables for review, they will appear here in chronological order for your inspection and sign-off."}
          </p>
        </div>
      )}

      {/* Queue List Cards */}
      {!isLoading && !isError && filteredItems.length > 0 && (
        <div className="review-queue-list">
          {filteredItems.map((item) => {
            const priorityLower = (item.priority || "MEDIUM").toLowerCase();
            const deliverableUrl = item.deliverable_file_url || item.file_url;
            const formattedTime = item.submission_timestamp
              ? new Date(item.submission_timestamp).toLocaleString(undefined, {
                  dateStyle: "medium",
                  timeStyle: "short",
                })
              : "Pending inspection";

            return (
              <div key={item.task_id} className="review-queue-card">
                <div className="queue-card-header">
                  <div className="queue-card-meta">
                    <span className="task-id-badge">#{item.task_id}</span>
                    <span className={`badge-pill badge-priority-${priorityLower}`}>
                      {item.priority || "MEDIUM"}
                    </span>
                    {item.project_id && (
                      <span className="project-tag">Project #{item.project_id}</span>
                    )}
                  </div>
                  <div className="submission-time-indicator">
                    <span className="time-icon">🕒</span>
                    <span>Submitted {formattedTime}</span>
                  </div>
                </div>

                <div className="queue-card-body">
                  <h3 className="queue-card-title">{item.title}</h3>
                  {item.description && (
                    <p className="queue-card-description">{item.description}</p>
                  )}

                  {/* Submitter & Remarks Box */}
                  <div className="queue-submitter-block">
                    <div className="submitter-pill">
                      <span className="submitter-avatar">
                        {(item.assignee_name || "E").charAt(0).toUpperCase()}
                      </span>
                      <span className="submitter-name">
                        {item.assignee_name || (item.assigned_to ? `Employee #${item.assigned_to}` : "Team Member")}
                      </span>
                    </div>

                    {item.submission_remarks && (
                      <div className="queue-remarks-snippet">
                        <span className="remarks-quote-mark">“</span>
                        <span>{item.submission_remarks}</span>
                        <span className="remarks-quote-mark">”</span>
                      </div>
                    )}
                  </div>

                  {/* Deliverable Link Preview */}
                  {deliverableUrl ? (
                    <div className="queue-deliverable-attachment">
                      <span className="attachment-label">Attached Deliverable:</span>
                      <button
                        type="button"
                        onClick={(e) =>
                          handleOpenDeliverable(
                            e,
                            deliverableUrl,
                            `deliverable-task-${item.task_id}`
                          )
                        }
                        className="attachment-link"
                        disabled={downloadingUrl === deliverableUrl}
                        title={
                          downloadingUrl === deliverableUrl
                            ? "Downloading..."
                            : "Download or open deliverable"
                        }
                        style={{
                          background: "none",
                          border: "none",
                          padding: 0,
                          cursor: downloadingUrl === deliverableUrl ? "wait" : "pointer",
                          font: "inherit",
                          textAlign: "left",
                        }}
                      >
                        <span className="attachment-icon">
                          {downloadingUrl === deliverableUrl ? "⏳" : "📁"}
                        </span>
                        <span className="attachment-name">
                          {downloadingUrl === deliverableUrl
                            ? "Downloading file..."
                            : deliverableUrl.split("/").pop()}
                        </span>
                        <span className="attachment-arrow">↗</span>
                      </button>
                    </div>
                  ) : (
                    <div className="queue-no-deliverable">
                      <span className="text-muted-italic">No external file attached</span>
                    </div>
                  )}
                </div>

                <div className="queue-card-footer">
                  <span className="status-indicator-badge">
                    <span className="status-dot-pulse" />
                    Awaiting Sign-off
                  </span>

                  <button
                    className="btn btn-review-action"
                    onClick={() => onReviewTask(item)}
                  >
                    Evaluate Deliverable →
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
