import { useState, useMemo, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchAllMyTasks,
  getProgressFillClass,
  filterTasks,
  computeTaskMetrics,
  calculatePagination,
  getPaginatedItems,
} from "../../api/tasksApi";
import TaskKanbanBoard from "./TaskKanbanBoard";
import TaskDetailDrawer from "./TaskDetailDrawer";
import ProgressUpdateModal from "./ProgressUpdateModal";
import "./tasks.css";

const PAGE_SIZE = 20;

const STATUS_FILTERS = [
  { id: "ALL", label: "All Tasks" },
  { id: "TODO", label: "To Do" },
  { id: "IN_PROGRESS", label: "In Progress" },
  { id: "BLOCKED", label: "Blocked" },
  { id: "IN_REVIEW", label: "In Review" },
  { id: "DONE", label: "Done" },
  { id: "REJECTED", label: "Needs Revision" },
];

/**
 * Format a date string (YYYY-MM-DD) into a human-friendly format.
 */
function formatDate(dateStr) {
  if (!dateStr) return "—";
  try {
    const [year, month, day] = dateStr.split("-");
    if (!year || !month || !day) return dateStr;
    const date = new Date(Number(year), Number(month) - 1, Number(day));
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

/**
 * Checks if a task is overdue.
 */
function isOverdue(dueDateStr, status) {
  if (!dueDateStr || status === "DONE") return false;
  try {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const [year, month, day] = dueDateStr.split("-");
    const due = new Date(Number(year), Number(month) - 1, Number(day));
    return due < today;
  } catch {
    return false;
  }
}

/**
 * Priority Badge
 */
function PriorityBadge({ priority }) {
  const p = (priority || "MEDIUM").toUpperCase();
  const classes = {
    CRITICAL: "badge-priority-critical",
    HIGH: "badge-priority-high",
    MEDIUM: "badge-priority-medium",
    LOW: "badge-priority-low",
  };
  return (
    <span className={`badge-priority ${classes[p] || classes.MEDIUM}`}>
      {p}
    </span>
  );
}

/**
 * Status Badge
 */
function StatusBadge({ status }) {
  const s = (status || "TODO").toUpperCase();
  const formatted = s === "REJECTED" ? "NEEDS REVISION" : s.replace("_", " ");
  const statusKey = s.toLowerCase();
  return (
    <span className={`badge-status badge-status-${statusKey}`}>
      <span className="badge-dot" aria-hidden="true" />
      {formatted}
    </span>
  );
}

/**
 * Visual Progress Bar
 */
function ProgressBar({ pct, status }) {
  const clamped = Math.max(0, Math.min(100, Number(pct) || 0));
  const fillClass = getProgressFillClass(status);

  return (
    <div className="progress-bar-container" title={`${clamped}% completed`}>
      <div className="progress-track" aria-hidden="true">
        <div
          className={`progress-fill ${fillClass}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span className="progress-label">{clamped}%</span>
    </div>
  );
}

/**
 * MyTasksPage Component (US-10 / US-32)
 *
 * Employee Task Workspace providing:
 * - Accurate summary metrics computed from the entire assigned dataset (independent of filter/page)
 * - Comprehensive search covering all assigned tasks
 * - Filterable Kanban Board (5 columns: TODO, IN_PROGRESS, BLOCKED, IN_REVIEW, DONE)
 * - Structured Table view toggle
 * - Universal pagination controls accessible in BOTH Kanban and Table views
 * - Slide-out TaskDetailDrawer
 * - ProgressUpdateModal (0-99% and blocker reason)
 * - Complete loading, empty, and retryable error states
 */
export default function MyTasksPage() {
  // Filter & Search states
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState("kanban"); // 'kanban' | 'table'

  // Modal & Drawer states
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [progressTask, setProgressTask] = useState(null);

  // Notification Toast state
  const [toast, setToast] = useState(null);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  // TanStack Query for full employee assigned tasks dataset
  // Enables complete search coverage and accurate cross-filter metrics
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["my-tasks", "all"],
    queryFn: () => fetchAllMyTasks(),
    retry: 1,
  });

  const allTasks = useMemo(() => data?.items || [], [data?.items]);
  const totalAssigned = data?.total ?? allTasks.length;

  // Accurate summary metrics computed from the complete dataset
  // Stays constant and independent of the active status filter or current page
  const metrics = useMemo(() => {
    return computeTaskMetrics(allTasks, totalAssigned);
  }, [allTasks, totalAssigned]);

  // Comprehensive filter across assigned tasks by status and search query (supported fields: title, task_id, project_id)
  const filteredTasks = useMemo(() => {
    return filterTasks(allTasks, { statusFilter, searchQuery });
  }, [allTasks, statusFilter, searchQuery]);

  // Pagination calculations with automatic clamping to valid range
  const totalFilteredCount = filteredTasks.length;
  const pagination = useMemo(() => {
    return calculatePagination(totalFilteredCount, page, PAGE_SIZE);
  }, [totalFilteredCount, page]);

  const effectivePage = pagination.page;
  const totalPages = pagination.totalPages;

  // When filtered task count changes after a progress update or refetch,
  // clamp active page state to the new valid range during render
  if (page > totalPages) {
    setPage(totalPages);
  }

  // Current page items for rendering in both Kanban and Table views (uses effectivePage)
  const currentPageTasks = useMemo(() => {
    return getPaginatedItems(filteredTasks, effectivePage, PAGE_SIZE);
  }, [filteredTasks, effectivePage]);

  const handleStatusTabClick = (newStatus) => {
    setStatusFilter(newStatus);
    setPage(1); // Reset page on filter change
  };

  const handleSearchChange = (e) => {
    setSearchQuery(e.target.value);
    setPage(1); // Reset page on search change
  };

  const handleClearFilters = () => {
    setStatusFilter("ALL");
    setSearchQuery("");
    setPage(1);
  };

  const handleProgressSuccess = (updatedTask) => {
    setToast({
      text: `Progress updated: "${updatedTask.title}" is now ${updatedTask.progress_pct}% (${updatedTask.status})`,
      type: "success",
    });
  };

  return (
    <section className="page tasks-page-container">
      {/* Toast Notification */}
      {toast && (
        <div
          className={`tasks-toast ${
            toast.type === "error" ? "toast-error" : "toast-success"
          }`}
          role="status"
        >
          <span aria-hidden="true">
            {toast.type === "error" ? "⚠️" : "✓"}
          </span>
          <span>{toast.text}</span>
        </div>
      )}

      {/* Header */}
      <div className="page-eyebrow">WORKSPACE</div>
      <header className="tasks-header">
        <div className="tasks-header-info">
          <div className="tasks-title-row">
            <h1>My Tasks</h1>
            <span className="tasks-count-pill" title="Total assigned tasks in your account">
              {totalAssigned} {totalAssigned === 1 ? "Task" : "Tasks"}
            </span>
          </div>
          <p className="tasks-page-description">
            Track, update, and manage your assigned tasks across active projects and milestones.
          </p>
        </div>
      </header>

      {/* Summary Metrics Bar (Calculated across the entire assigned dataset) */}
      <div className="tasks-metrics-grid" aria-label="Task Summary Metrics">
        <div className="tasks-metric-card">
          <div className="tasks-metric-icon metric-icon-total" aria-hidden="true">
            📋
          </div>
          <div className="tasks-metric-content">
            <span className="tasks-metric-val">{metrics.TOTAL}</span>
            <span className="tasks-metric-label">Total Assigned</span>
          </div>
        </div>

        <div className="tasks-metric-card">
          <div className="tasks-metric-icon metric-icon-inprogress" aria-hidden="true">
            ⚡
          </div>
          <div className="tasks-metric-content">
            <span className="tasks-metric-val">{metrics.IN_PROGRESS}</span>
            <span className="tasks-metric-label">In Progress</span>
          </div>
        </div>

        <div className="tasks-metric-card">
          <div className="tasks-metric-icon metric-icon-blocked" aria-hidden="true">
            🚨
          </div>
          <div className="tasks-metric-content">
            <span className="tasks-metric-val" style={{ color: "#dc2626" }}>
              {metrics.BLOCKED}
            </span>
            <span className="tasks-metric-label">Blocked</span>
          </div>
        </div>

        <div className="tasks-metric-card">
          <div className="tasks-metric-icon metric-icon-review" aria-hidden="true">
            👀
          </div>
          <div className="tasks-metric-content">
            <span className="tasks-metric-val">{metrics.IN_REVIEW}</span>
            <span className="tasks-metric-label">In Review</span>
          </div>
        </div>

        <div className="tasks-metric-card">
          <div className="tasks-metric-icon metric-icon-done" aria-hidden="true">
            ✓
          </div>
          <div className="tasks-metric-content">
            <span className="tasks-metric-val" style={{ color: "#16a34a" }}>
              {metrics.DONE}
            </span>
            <span className="tasks-metric-label">Done</span>
          </div>
        </div>

        {metrics.REJECTED > 0 && (
          <div className="tasks-metric-card" style={{ borderColor: "#fed7aa" }}>
            <div
              className="tasks-metric-icon metric-icon-rejected"
              aria-hidden="true"
            >
              ↩
            </div>
            <div className="tasks-metric-content">
              <span className="tasks-metric-val" style={{ color: "#ea580c" }}>
                {metrics.REJECTED}
              </span>
              <span className="tasks-metric-label">Needs Revision</span>
            </div>
          </div>
        )}
      </div>

      {/* Controls Bar: Search, Status Tabs & View Switcher */}
      <div className="tasks-controls-bar">
        <div className="tasks-controls-left">
          {/* Search Box (Covers all assigned tasks) */}
          <div className="tasks-search-box">
            <span className="tasks-search-icon" aria-hidden="true">
              🔍
            </span>
            <input
              type="text"
              className="tasks-search-input"
              placeholder="Search by title, task ID, project ID..."
              value={searchQuery}
              onChange={handleSearchChange}
              aria-label="Search assigned tasks by title, task ID, or project ID"
            />
            {searchQuery && (
              <button
                type="button"
                className="tasks-search-clear"
                onClick={() => setSearchQuery("")}
                aria-label="Clear search"
              >
                ✕
              </button>
            )}
          </div>

          {/* Status Tabs with Global Counts */}
          <nav className="tasks-status-tabs" aria-label="Filter tasks by status">
            {STATUS_FILTERS.map((filter) => {
              const isActive = statusFilter === filter.id;
              const countVal =
                filter.id === "ALL" ? metrics.TOTAL : metrics[filter.id];
              return (
                <button
                  key={filter.id}
                  type="button"
                  className={`tasks-tab-btn ${isActive ? "active" : ""}`}
                  onClick={() => handleStatusTabClick(filter.id)}
                  aria-pressed={isActive}
                >
                  {filter.label}
                  {countVal !== undefined && (
                    <span className="tab-badge">{countVal}</span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* View Mode Switcher */}
        <div className="tasks-controls-right">
          <div className="tasks-view-toggle" role="group" aria-label="View layout toggle">
            <button
              type="button"
              className={`tasks-view-btn ${viewMode === "kanban" ? "active" : ""}`}
              onClick={() => setViewMode("kanban")}
              aria-pressed={viewMode === "kanban"}
              title="Kanban Board View"
            >
              <span aria-hidden="true">▦</span> Kanban
            </button>
            <button
              type="button"
              className={`tasks-view-btn ${viewMode === "table" ? "active" : ""}`}
              onClick={() => setViewMode("table")}
              aria-pressed={viewMode === "table"}
              title="Table View"
            >
              <span aria-hidden="true">☰</span> Table
            </button>
          </div>
        </div>
      </div>

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="tasks-skeleton-board" aria-label="Loading tasks...">
          {[1, 2, 3, 4, 5].map((col) => (
            <div key={col} className="skeleton-column">
              <div className="skeleton-box" style={{ height: 24, width: "60%" }} />
              <div className="skeleton-box" style={{ height: 110 }} />
              <div className="skeleton-box" style={{ height: 110 }} />
            </div>
          ))}
        </div>
      )}

      {/* API Error State */}
      {!isLoading && isError && (
        <div className="tasks-error-state" role="alert">
          <span className="tasks-error-icon" aria-hidden="true">
            ⚠️
          </span>
          <h2 className="tasks-error-title">Unable to Load Tasks</h2>
          <p className="tasks-error-desc">
            {error?.message ||
              "Could not retrieve assigned tasks from the server. Check your connection or try again."}
          </p>
          <button
            type="button"
            className="btn-retry"
            onClick={() => refetch()}
          >
            Try Again
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !isError && filteredTasks.length === 0 && (
        <div className="tasks-empty-state">
          <span className="tasks-empty-icon" aria-hidden="true">
            📋
          </span>
          <h2 className="tasks-empty-title">
            {searchQuery || statusFilter !== "ALL"
              ? "No Matching Tasks Found"
              : "No Tasks Assigned Yet"}
          </h2>
          <p className="tasks-empty-desc">
            {searchQuery || statusFilter !== "ALL"
              ? "There are no tasks matching your current search or status filter. Try clearing your filters."
              : "You have no tasks assigned to your employee account in this workspace."}
          </p>
          {(searchQuery || statusFilter !== "ALL") && (
            <button
              type="button"
              className="btn-secondary"
              onClick={handleClearFilters}
            >
              Clear Filters
            </button>
          )}
        </div>
      )}

      {/* Data Views: Kanban vs Table */}
      {!isLoading && !isError && filteredTasks.length > 0 && (
        <>
          {viewMode === "kanban" ? (
            <TaskKanbanBoard
              tasks={currentPageTasks}
              onSelectTask={(taskId) => setSelectedTaskId(taskId)}
              onUpdateProgress={(task) => setProgressTask(task)}
            />
          ) : (
            <div className="tasks-table-wrapper">
              <div className="tasks-table-scroll">
                <table className="tasks-table" aria-label="Assigned Tasks Directory">
                  <thead>
                    <tr>
                      <th scope="col">Task</th>
                      <th scope="col">Project</th>
                      <th scope="col">Status</th>
                      <th scope="col">Priority</th>
                      <th scope="col" style={{ width: 140 }}>
                        Progress
                      </th>
                      <th scope="col">Due Date</th>
                      <th scope="col" style={{ textAlign: "right" }}>
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {currentPageTasks.map((task) => {
                      const overdue = isOverdue(task.due_date, task.status);
                      const canUpdate =
                        task.status === "TODO" ||
                        task.status === "IN_PROGRESS" ||
                        task.status === "BLOCKED";

                      return (
                        <tr
                          key={task.task_id}
                          onClick={() => setSelectedTaskId(task.task_id)}
                        >
                          {/* Title & Subtitle */}
                          <td className="tasks-table-title-cell">
                            <div className="tasks-table-title">{task.title}</div>
                            <div className="tasks-table-subtitle">
                              <span>#{task.task_id}</span>
                              {task.status === "BLOCKED" && (
                                <span style={{ color: "#dc2626", fontWeight: 650 }}>
                                  · Blocked
                                </span>
                              )}
                              {task.rejection_count > 0 && task.status !== "DONE" && (
                                <span style={{ color: "#ea580c", fontWeight: 650 }}>
                                  · Returned
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Project Context */}
                          <td>
                            <span style={{ fontWeight: 600, color: "#334155" }}>
                              Project #{task.project_id}
                            </span>
                            {task.milestone_id && (
                              <div style={{ fontSize: 11, color: "#64748b" }}>
                                Milestone #{task.milestone_id}
                              </div>
                            )}
                          </td>

                          {/* Status */}
                          <td>
                            <StatusBadge status={task.status} />
                          </td>

                          {/* Priority */}
                          <td>
                            <PriorityBadge priority={task.priority} />
                          </td>

                          {/* Progress */}
                          <td>
                            <ProgressBar
                              pct={task.progress_pct}
                              status={task.status}
                            />
                          </td>

                          {/* Due Date */}
                          <td>
                            <span
                              style={{
                                color: overdue ? "#dc2626" : "#475569",
                                fontWeight: overdue ? 700 : 500,
                              }}
                            >
                              {formatDate(task.due_date)}
                              {overdue && " (Overdue)"}
                            </span>
                          </td>

                          {/* Actions */}
                          <td style={{ textAlign: "right" }}>
                            <div className="tasks-table-actions">
                              {canUpdate && (
                                <button
                                  type="button"
                                  className="btn-card-quick-action"
                                  style={{ width: "auto" }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setProgressTask(task);
                                  }}
                                  aria-label={`Update progress for ${task.title}`}
                                >
                                  ⚡ Update
                                </button>
                              )}
                              <button
                                type="button"
                                className="btn-secondary"
                                style={{ padding: "4px 10px", fontSize: 11.5 }}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedTaskId(task.task_id);
                                }}
                              >
                                View →
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Universal Pagination Bar (Accessible in BOTH Kanban and Table views) */}
          <div className="tasks-pagination" aria-label="Task pagination navigation">
            <div className="pagination-summary">
              Showing{" "}
              <strong>
                {totalFilteredCount === 0
                  ? "0–0"
                  : `${(effectivePage - 1) * PAGE_SIZE + 1}–${Math.min(
                      effectivePage * PAGE_SIZE,
                      totalFilteredCount
                    )}`}
              </strong>{" "}
              of <strong>{totalFilteredCount}</strong>{" "}
              {statusFilter !== "ALL" || searchQuery.trim()
                ? "matching tasks"
                : "tasks"}
              {totalFilteredCount !== totalAssigned && (
                <span style={{ color: "#8791a5", marginLeft: 4 }}>
                  (filtered from {totalAssigned} total)
                </span>
              )}
              {isFetching && (
                <span style={{ marginLeft: 8, color: "#8791a5" }}>
                  (updating...)
                </span>
              )}
            </div>

            <div className="pagination-actions">
              <button
                type="button"
                className="btn-page"
                disabled={effectivePage <= 1}
                onClick={() => setPage(Math.max(1, effectivePage - 1))}
                aria-label="Previous page"
              >
                ← Previous
              </button>
              <span style={{ fontSize: 12, color: "#647087" }}>
                Page {effectivePage} of {totalPages}
              </span>
              <button
                type="button"
                className="btn-page"
                disabled={effectivePage >= totalPages}
                onClick={() => setPage(Math.min(totalPages, effectivePage + 1))}
                aria-label="Next page"
              >
                Next →
              </button>
            </div>
          </div>
        </>
      )}

      {/* Slide-out Task Detail Drawer (US-32) */}
      <TaskDetailDrawer
        taskId={selectedTaskId}
        onClose={() => setSelectedTaskId(null)}
        onUpdateProgress={(task) => {
          setSelectedTaskId(null);
          setProgressTask(task);
        }}
      />

      {/* Progress Update Modal (US-10) */}
      {progressTask && (
        <ProgressUpdateModal
          key={progressTask.task_id}
          task={progressTask}
          onClose={() => setProgressTask(null)}
          onSuccess={handleProgressSuccess}
        />
      )}
    </section>
  );
}
