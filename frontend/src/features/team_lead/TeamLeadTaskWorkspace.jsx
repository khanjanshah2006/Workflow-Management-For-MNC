import { useState, useMemo, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getProjectTasks, getReviewQueue, getProgressFillClass } from "../../api/tasksApi";
import { getProjects } from "../../api/projectsApi";
import { teamApi } from "../../api/teamApi";
import { useAuth } from "../../context/AuthContext";
import CreateTaskModal from "./CreateTaskModal";
import ReassignTaskModal from "./ReassignTaskModal";
import TaskReviewQueue from "./TaskReviewQueue";
import ReviewDecisionModal from "./ReviewDecisionModal";
import "./teamLead.css";

const STATUS_COLUMNS = [
  { key: "TODO", label: "To Do", badgeClass: "badge-status-todo" },
  { key: "IN_PROGRESS", label: "In Progress", badgeClass: "badge-status-inprogress" },
  { key: "BLOCKED", label: "Blocked", badgeClass: "badge-status-blocked" },
  { key: "IN_REVIEW", label: "In Review", badgeClass: "badge-status-inreview" },
  { key: "DONE", label: "Completed", badgeClass: "badge-status-done" },
  { key: "REJECTED", label: "Rejected / Revising", badgeClass: "badge-status-rejected" },
];

/**
 * TeamLeadTaskWorkspace Component (US-09, US-12, US-14)
 *
 * Mission Control view for Team Leads and Project Managers:
 * - Tabbed navigation: "Team Task Board" & "Review Queue"
 * - Kanban board and Table view of team tasks
 * - Task Creation with live team roster assignment
 * - Workload Reassignment with mandatory business reasons
 * - Review Queue triage with deliverable approvals and mandatory rejection feedback
 */
export default function TeamLeadTaskWorkspace() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  // Navigation and view states
  const [activeTab, setActiveTab] = useState("BOARD"); // "BOARD" | "REVIEW_QUEUE"
  const [viewMode, setViewMode] = useState("KANBAN"); // "KANBAN" | "TABLE"

  // Filter states
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("ALL");
  const [selectedPriority, setSelectedPriority] = useState("ALL");
  const [selectedAssignee, setSelectedAssignee] = useState("ALL");

  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [reassigningTask, setReassigningTask] = useState(null);
  const [reviewingTask, setReviewingTask] = useState(null);

  // Toast notification state
  const [toastMessage, setToastMessage] = useState(null);

  useEffect(() => {
    if (!toastMessage) return;
    const timer = setTimeout(() => setToastMessage(null), 4000);
    return () => clearTimeout(timer);
  }, [toastMessage]);

  // Fetch available projects
  const { data: projects = [], isLoading: isLoadingProjects } = useQuery({
    queryKey: ["projects"],
    queryFn: () => getProjects(),
  });

  const [selectedProjectId, setSelectedProjectId] = useState("");
  const activeProjectId = selectedProjectId || (projects.length > 0 ? String(projects[0].project_id) : "1");

  const teamId = user?.team_id ? String(user.team_id) : "1";

  // Fetch tasks for the project and team
  const {
    data: projectTasksData,
    isLoading: isLoadingTasks,
    isError: isTasksError,
    error: tasksError,
  } = useQuery({
    queryKey: ["projects", activeProjectId, "tasks", teamId],
    queryFn: () => getProjectTasks(activeProjectId, { team_id: Number(teamId), limit: 100 }),
    enabled: Boolean(activeProjectId),
  });

  const tasks = useMemo(
    () => (Array.isArray(projectTasksData?.items) ? projectTasksData.items : []),
    [projectTasksData]
  );

  // Fetch review queue for pending review badge count
  const { data: reviewQueueItems = [] } = useQuery({
    queryKey: ["tasks", "review-queue"],
    queryFn: () => getReviewQueue(),
  });

  // Fetch team members for filter dropdown and card display
  const { data: rawTeamMembers = [] } = useQuery({
    queryKey: ["teams", teamId, "members"],
    queryFn: () => teamApi.getTeamMembers(teamId, activeProjectId || null),
    enabled: Boolean(teamId),
  });

  const teamMembers = (rawTeamMembers || []).map((m) => teamApi.normalizeMember(m));

  // Compute KPI statistics
  const metrics = useMemo(() => {
    const total = tasks.length;
    const inReview = tasks.filter((t) => (t.status || "").toUpperCase() === "IN_REVIEW").length;
    const inProgress = tasks.filter((t) => (t.status || "").toUpperCase() === "IN_PROGRESS").length;
    const blocked = tasks.filter((t) => (t.status || "").toUpperCase() === "BLOCKED").length;
    const done = tasks.filter((t) => (t.status || "").toUpperCase() === "DONE").length;
    return { total, inReview, inProgress, blocked, done };
  }, [tasks]);

  // Filter tasks based on search and dropdown filters
  const filteredTasks = useMemo(() => {
    return tasks.filter((task) => {
      // Status filter
      if (selectedStatus !== "ALL" && (task.status || "").toUpperCase() !== selectedStatus) {
        return false;
      }
      // Priority filter
      if (selectedPriority !== "ALL" && (task.priority || "").toUpperCase() !== selectedPriority) {
        return false;
      }
      // Assignee filter
      if (selectedAssignee !== "ALL") {
        if (selectedAssignee === "UNASSIGNED" && task.assigned_to) return false;
        if (selectedAssignee !== "UNASSIGNED" && String(task.assigned_to) !== selectedAssignee) return false;
      }
      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const titleMatch = Boolean(task.title && task.title.toLowerCase().includes(q));
        const idMatch = String(task.task_id).includes(q);
        if (!titleMatch && !idMatch) return false;
      }
      return true;
    });
  }, [tasks, selectedStatus, selectedPriority, selectedAssignee, searchQuery]);

  // Group filtered tasks by status column for Kanban
  const kanbanColumns = useMemo(() => {
    const columns = {};
    STATUS_COLUMNS.forEach((col) => {
      columns[col.key] = [];
    });

    filteredTasks.forEach((task) => {
      const statusKey = (task.status || "TODO").toUpperCase();
      if (columns[statusKey]) {
        columns[statusKey].push(task);
      } else {
        // Fallback to TODO for unknown non-standard status
        columns["TODO"].push(task);
      }
    });

    return columns;
  }, [filteredTasks]);

  // Action success callbacks
  const handleTaskCreated = () => {
    queryClient.invalidateQueries({ queryKey: ["projects", activeProjectId, "tasks"] });
    setToastMessage("Task created and assigned successfully!");
  };

  const handleTaskReassigned = () => {
    queryClient.invalidateQueries({ queryKey: ["projects", activeProjectId, "tasks"] });
    setToastMessage("Task successfully reassigned to new team member!");
  };

  const handleReviewDecision = (result) => {
    queryClient.invalidateQueries({ queryKey: ["projects", activeProjectId, "tasks"] });
    queryClient.invalidateQueries({ queryKey: ["tasks", "review-queue"] });
    const isApproval = result?.status === "DONE" || (result?.message || "").includes("approved");
    setToastMessage(isApproval ? "Task deliverable approved and marked as DONE!" : "Task deliverable rejected with feedback.");
  };

  return (
    <div className="team-lead-workspace">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="workspace-toast-banner" role="status" aria-live="polite">
          <span>✓</span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Workspace Header */}
      <header className="workspace-header">
        <div className="workspace-header-left">
          <div className="workspace-badge">Team Lead Mission Control</div>
          <h1 className="workspace-title">Team Task Workspace & Review Triage</h1>
          <p className="workspace-subtitle">
            Create tasks, reallocate workloads across team members, and inspect submitted deliverables.
          </p>
        </div>

        <div className="workspace-header-actions">
          {/* Project selector */}
          <select
            className="form-control form-control-sm"
            value={activeProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            disabled={isLoadingProjects || projects.length === 0}
            title="Switch project workspace"
          >
            {projects.map((p) => (
              <option key={p.project_id} value={p.project_id}>
                {p.name} ({p.project_code || `#${p.project_id}`})
              </option>
            ))}
          </select>

          <button
            className="btn btn-primary"
            onClick={() => setIsCreateModalOpen(true)}
          >
            + Create Task
          </button>
        </div>
      </header>

      {/* KPI Summary Cards */}
      <section className="workspace-kpi-grid" aria-label="Team task summary metrics">
        <div className="kpi-stat-card">
          <span className="kpi-stat-label">Total Team Tasks</span>
          <span className="kpi-stat-value">{metrics.total}</span>
        </div>
        <div className="kpi-stat-card kpi-review">
          <span className="kpi-stat-label">Awaiting Review</span>
          <span className="kpi-stat-value">{reviewQueueItems.length}</span>
        </div>
        <div className="kpi-stat-card">
          <span className="kpi-stat-label">In Progress</span>
          <span className="kpi-stat-value">{metrics.inProgress}</span>
        </div>
        <div className="kpi-stat-card kpi-blocked">
          <span className="kpi-stat-label">Blocked</span>
          <span className="kpi-stat-value">{metrics.blocked}</span>
        </div>
        <div className="kpi-stat-card kpi-done">
          <span className="kpi-stat-label">Completed</span>
          <span className="kpi-stat-value">{metrics.done}</span>
        </div>
      </section>

      {/* Tab Navigation */}
      <div className="workspace-tabs-bar">
        <div className="tabs-nav-list" role="tablist">
          <button
            className={`tab-nav-btn ${activeTab === "BOARD" ? "tab-nav-active" : ""}`}
            onClick={() => setActiveTab("BOARD")}
            role="tab"
            aria-selected={activeTab === "BOARD"}
          >
            <span>Team Task Board</span>
            <span className="tab-count-badge">{tasks.length}</span>
          </button>

          <button
            className={`tab-nav-btn ${activeTab === "REVIEW_QUEUE" ? "tab-nav-active" : ""}`}
            onClick={() => setActiveTab("REVIEW_QUEUE")}
            role="tab"
            aria-selected={activeTab === "REVIEW_QUEUE"}
          >
            <span>Review Queue</span>
            <span className={`tab-count-badge ${reviewQueueItems.length > 0 ? "badge-highlight" : ""}`}>
              {reviewQueueItems.length}
            </span>
          </button>
        </div>

        {activeTab === "BOARD" && (
          <div className="view-toggle-group">
            <button
              className={`btn-view-toggle ${viewMode === "KANBAN" ? "active" : ""}`}
              onClick={() => setViewMode("KANBAN")}
              title="Kanban Board view"
            >
              ▦ Kanban
            </button>
            <button
              className={`btn-view-toggle ${viewMode === "TABLE" ? "active" : ""}`}
              onClick={() => setViewMode("TABLE")}
              title="Table view"
            >
              ☰ Table
            </button>
          </div>
        )}
      </div>

      {/* Tab 1: Team Task Board View */}
      {activeTab === "BOARD" && (
        <div className="board-view-container">
          {/* Board Filter Toolbar */}
          <div className="board-toolbar">
            <div className="toolbar-search-wrapper">
              <span className="search-icon">🔍</span>
              <input
                type="text"
                className="form-control queue-search-input"
                placeholder="Search tasks by title or #id..."
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

            <div className="toolbar-filter-group">
              {/* Status Filter */}
              <select
                className="form-control form-control-sm"
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
              >
                <option value="ALL">All Statuses</option>
                <option value="TODO">To Do</option>
                <option value="IN_PROGRESS">In Progress</option>
                <option value="BLOCKED">Blocked</option>
                <option value="IN_REVIEW">In Review</option>
                <option value="DONE">Completed</option>
                <option value="REJECTED">Rejected</option>
              </select>

              {/* Priority Filter */}
              <select
                className="form-control form-control-sm"
                value={selectedPriority}
                onChange={(e) => setSelectedPriority(e.target.value)}
              >
                <option value="ALL">All Priorities</option>
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
                <option value="CRITICAL">Critical</option>
              </select>

              {/* Assignee Filter */}
              <select
                className="form-control form-control-sm"
                value={selectedAssignee}
                onChange={(e) => setSelectedAssignee(e.target.value)}
              >
                <option value="ALL">All Team Members</option>
                <option value="UNASSIGNED">Unassigned</option>
                {teamMembers.map((m) => (
                  <option key={m.emp_id || m.id} value={String(m.emp_id || m.id)}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Loading state */}
          {isLoadingTasks && (
            <div className="queue-loading-state">
              <div className="spinner-border" role="status" />
              <p>Loading team tasks...</p>
            </div>
          )}

          {/* Error Banner */}
          {isTasksError && (
            <div className="alert-banner alert-banner-danger" role="alert">
              <span className="alert-icon">⚠️</span>
              <span>{tasksError?.message || "Failed to load project tasks."}</span>
            </div>
          )}

          {/* Kanban Board Grid */}
          {viewMode === "KANBAN" && (
            <div className="kanban-board-grid">
              {STATUS_COLUMNS.map((column) => {
                const columnTasks = kanbanColumns[column.key] || [];

                return (
                  <div key={column.key} className="kanban-column">
                    <div className="kanban-column-header">
                      <div className="column-title-wrap">
                        <span>{column.label}</span>
                        <span className="column-count">{columnTasks.length}</span>
                      </div>
                    </div>

                    <div className="kanban-column-cards">
                      {columnTasks.length === 0 ? (
                        <div className="column-empty-placeholder">No tasks</div>
                      ) : (
                        columnTasks.map((task) => {
                          const priorityLower = (task.priority || "MEDIUM").toLowerCase();
                          const progressFillClass = getProgressFillClass(task.status);
                          const progressVal = task.progress_pct || 0;

                          return (
                            <div key={task.task_id} className="team-task-card">
                              <div className="card-top-meta">
                                <span className="task-id-tag">#{task.task_id}</span>
                                <span className={`badge-pill badge-priority-${priorityLower}`}>
                                  {task.priority || "MEDIUM"}
                                </span>
                              </div>

                              <h4 className="card-title">{task.title}</h4>

                              <div className="card-assignee-row">
                                <span className="assignee-chip">
                                  <span className="avatar-mini">
                                    {(task.assignee?.full_name || "U").charAt(0).toUpperCase()}
                                  </span>
                                  <span>
                                    {task.assignee?.full_name ||
                                      (task.assigned_to ? `Emp #${task.assigned_to}` : "Unassigned")}
                                  </span>
                                </span>
                                <span className="progress-pct-text">{progressVal}%</span>
                              </div>

                              <div className="card-progress-bar">
                                <div
                                  className={`card-progress-fill ${progressFillClass}`}
                                  style={{ width: `${progressVal}%` }}
                                />
                              </div>

                              {task.status === "BLOCKED" && task.blocker_reason && (
                                <div className="card-blocker-banner">
                                  <strong>Blocker:</strong> {task.blocker_reason}
                                </div>
                              )}

                              <div className="card-actions-row">
                                <button
                                  className="btn-card-action"
                                  onClick={() => setReassigningTask(task)}
                                  title="Reassign task to another team member"
                                >
                                  Reassign...
                                </button>

                                {task.status === "IN_REVIEW" && (
                                  <button
                                    className="btn-card-action btn-action-review"
                                    onClick={() => setReviewingTask(task)}
                                    title="Evaluate submitted deliverable"
                                  >
                                    Evaluate →
                                  </button>
                                )}
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Table View */}
          {viewMode === "TABLE" && (
            <div className="board-table-card">
              <table className="table table-hover">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Title</th>
                    <th>Assignee</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Progress</th>
                    <th>Due Date</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTasks.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="text-center py-4 text-muted">
                        No tasks match the active filters.
                      </td>
                    </tr>
                  ) : (
                    filteredTasks.map((task) => (
                      <tr key={task.task_id}>
                        <td className="font-mono text-xs">#{task.task_id}</td>
                        <td className="font-semibold">{task.title}</td>
                        <td>
                          {task.assignee?.full_name ||
                            (task.assigned_to ? `Employee #${task.assigned_to}` : "Unassigned")}
                        </td>
                        <td>
                          <span className={`badge-pill badge-priority-${(task.priority || "MEDIUM").toLowerCase()}`}>
                            {task.priority}
                          </span>
                        </td>
                        <td>
                          <span className="badge-pill badge-status-default">
                            {task.status}
                          </span>
                        </td>
                        <td>{task.progress_pct || 0}%</td>
                        <td>{task.due_date || "—"}</td>
                        <td>
                          <div style={{ display: "flex", gap: "6px" }}>
                            <button
                              className="btn btn-secondary btn-xs"
                              onClick={() => setReassigningTask(task)}
                            >
                              Reassign
                            </button>
                            {task.status === "IN_REVIEW" && (
                              <button
                                className="btn btn-warning btn-xs"
                                onClick={() => setReviewingTask(task)}
                              >
                                Evaluate
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Review Queue View */}
      {activeTab === "REVIEW_QUEUE" && (
        <TaskReviewQueue
          onReviewTask={(item) => setReviewingTask(item)}
        />
      )}

      {/* Modal: Create Task */}
      <CreateTaskModal
        isOpen={isCreateModalOpen}
        defaultProjectId={activeProjectId}
        defaultTeamId={teamId}
        onClose={() => setIsCreateModalOpen(false)}
        onSuccess={handleTaskCreated}
      />

      {/* Modal: Reassign Task */}
      <ReassignTaskModal
        isOpen={Boolean(reassigningTask)}
        task={reassigningTask}
        onClose={() => setReassigningTask(null)}
        onSuccess={handleTaskReassigned}
      />

      {/* Modal: Review Decision */}
      <ReviewDecisionModal
        isOpen={Boolean(reviewingTask)}
        task={reviewingTask}
        onClose={() => setReviewingTask(null)}
        onSuccess={handleReviewDecision}
      />
    </div>
  );
}
