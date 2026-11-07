import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { projectsApi } from "../../api/projectsApi";
import { useAuth } from "../../hooks/useAuth";
import MilestoneTimeline from "./MilestoneTimeline";
import AddMilestoneModal from "./AddMilestoneModal";
import ProjectStaffingPanel from "./components/ProjectStaffingPanel";
import "./projectDetail.css";

/**
 * Lifecycle state transitions contract (US-36).
 */
const ALLOWED_STATUS_TRANSITIONS = {
  PLANNED: ["ACTIVE", "CANCELLED"],
  ACTIVE: ["ON_HOLD", "COMPLETED", "CANCELLED"],
  ON_HOLD: ["ACTIVE", "CANCELLED"],
  COMPLETED: ["CANCELLED"],
  CANCELLED: [],
};

function formatDate(dateStr) {
  if (!dateStr) return "—";
  try {
    const [year, month, day] = dateStr.split("-");
    if (!year || !month || !day) return dateStr;
    const date = new Date(Number(year), Number(month) - 1, Number(day));
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

/**
 * Status Confirmation Dialog (Frame 9:624).
 */
function StatusConfirmationModal({
  isOpen,
  onClose,
  project,
  targetStatus,
  onConfirm,
  isPending,
  error,
}) {
  if (!isOpen || !project || !targetStatus) return null;

  const currentStatus = (project.status || "").toUpperCase();

  return (
    <div
      className="modal-overlay"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isPending) {
          onClose();
        }
      }}
    >
      <div
        className="modal-card status-confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-status-title"
      >
        <div className="modal-header">
          <div>
            <div className="modal-eyebrow">US-36 STATUS TRANSITION</div>
            <h2 id="confirm-status-title" className="modal-title">
              Confirm Status Change
            </h2>
          </div>
          <button
            type="button"
            className="modal-close-button"
            onClick={onClose}
            disabled={isPending}
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="modal-alert-error" role="alert">
            <span className="alert-symbol">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <div className="confirm-status-body">
          <p className="confirm-transition-statement">
            Are you sure you want to transition project{" "}
            <strong>{project.name}</strong> ({project.project_code})?
          </p>

          <div className="transition-visual">
            <span className={`status-pill status-pill-${currentStatus.toLowerCase()}`}>
              {currentStatus}
            </span>
            <span className="transition-arrow">→</span>
            <span className={`status-pill status-pill-${targetStatus.toLowerCase()}`}>
              {targetStatus}
            </span>
          </div>

          {targetStatus === "CANCELLED" && (
            <div className="confirm-callout-warning" role="note">
              <strong>Warning:</strong> Cancelling a project terminates active milestones
              and staffing assignments. This action cannot be easily reversed.
            </div>
          )}

          {targetStatus === "COMPLETED" && (
            <div className="confirm-callout-info" role="note">
              <strong>Note:</strong> Marking as completed indicates that all milestones and
              deliverables are finalized.
            </div>
          )}

          {targetStatus === "ON_HOLD" && (
            <div className="confirm-callout-info" role="note">
              <strong>Note:</strong> Putting this project on hold signals that work is
              temporarily paused.
            </div>
          )}

          {targetStatus === "ACTIVE" && (
            <div className="confirm-callout-info" role="note">
              <strong>Note:</strong> Activating this project enables active sprint work
              and delivery tracking.
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button
            type="button"
            className="btn-secondary"
            onClick={onClose}
            disabled={isPending}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={isPending}
            onClick={() => onConfirm(targetStatus)}
            id="confirm-transition-btn"
          >
            {isPending ? (
              <>
                <span className="spinner-inline" />
                <span>Updating Status...</span>
              </>
            ) : (
              `Confirm Change to ${targetStatus}`
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Project Detail Page (US-08 / US-36 - Frame 9:378).
 */
export default function ProjectDetailPage() {
  const { projectId } = useParams();
  const queryClient = useQueryClient();
  const { canManageProject } = useAuth();

  const [activeTab, setActiveTab] = useState("milestones"); // 'milestones' | 'staffing'
  const [isAddMilestoneOpen, setIsAddMilestoneOpen] = useState(false);
  const [pendingStatusChange, setPendingStatusChange] = useState(null); // target status to confirm
  const [statusActionError, setStatusActionError] = useState("");
  const [statusSuccessMessage, setStatusSuccessMessage] = useState("");

  // 1. Fetch real project data
  const {
    data: project,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => projectsApi.getProject(projectId),
    enabled: Boolean(projectId),
    retry: 1,
  });

  // 2. Status Transition Mutation (US-36)
  const statusMutation = useMutation({
    mutationFn: (newStatus) => projectsApi.updateProjectStatus(projectId, newStatus),
    onSuccess: (data) => {
      // Invalidate project query to refresh UI state immediately
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setPendingStatusChange(null);
      setStatusActionError("");
      setStatusSuccessMessage(
        `Project status successfully updated to "${data?.status || pendingStatusChange}".`
      );
      setTimeout(() => setStatusSuccessMessage(""), 5000);
    },
    onError: (err) => {
      setStatusActionError(
        err?.message ||
          "Failed to update project status. Ensure status transition endpoint (PR #58) is available."
      );
    },
  });

  const handleSelectStatus = (e) => {
    const nextStatus = e.target.value;
    if (!nextStatus) return;
    setStatusActionError("");
    setPendingStatusChange(nextStatus);
    // Reset dropdown visually
    e.target.value = "";
  };

  const handleConfirmStatusChange = (status) => {
    statusMutation.mutate(status);
  };

  // Loading state
  if (isLoading) {
    return (
      <section className="page project-detail-container">
        <div className="placeholder-panel">
          <div className="spinner-medium" />
          <h2>Loading Project Details...</h2>
          <p>Connecting to enterprise project service.</p>
        </div>
      </section>
    );
  }

  // Not Found or Error state
  if (isError || !project) {
    const isNotFound = error?.status === 404;

    return (
      <section className="page project-detail-container">
        <div className="project-detail-nav">
          <Link to="/projects" className="back-to-projects-link">
            ← Back to Projects
          </Link>
        </div>

        <div className="placeholder-panel" role="alert">
          <div className="placeholder-symbol">{isNotFound ? "🔍" : "⚠️"}</div>
          <h2>{isNotFound ? "Project Record Not Found" : "Unable to Load Project"}</h2>
          <p>
            {isNotFound
              ? `No project record exists with identifier #${projectId}.`
              : error?.message || "An unexpected error occurred while fetching project data."}
          </p>
          <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
            <button type="button" className="btn-secondary" onClick={() => refetch()}>
              Retry Request
            </button>
            <Link to="/projects" className="btn-primary" style={{ textDecoration: "none" }}>
              Return to Project Directory
            </Link>
          </div>
        </div>
      </section>
    );
  }

  const currentStatus = (project.status || "PLANNED").toUpperCase();
  const allowedTransitions = ALLOWED_STATUS_TRANSITIONS[currentStatus] || [];
  const priorityClass = `priority-${(project.priority || "medium").toLowerCase()}`;

  return (
    <section className="page project-detail-container">
      {/* Navigation Breadcrumb */}
      <div className="project-detail-nav">
        <Link to="/projects" className="back-to-projects-link" id="back-to-projects-btn">
          ← Back to Projects
        </Link>
        <span className="workspace-label">PROJECT ID: #{project.project_id}</span>
      </div>

      {statusSuccessMessage && (
        <div
          className="notification-item notification-unread"
          style={{
            marginBottom: 16,
            padding: "12px 18px",
            borderRadius: 8,
            borderLeft: "4px solid #10b981",
            background: "#ecfdf5",
            color: "#065f46",
          }}
          role="status"
        >
          <strong>✓ Success: </strong> {statusSuccessMessage}
        </div>
      )}

      {/* Hero Card */}
      <div className="project-hero-card">
        <div className="project-hero-header">
          <div className="project-hero-left">
            <div className="hero-meta-tags">
              <span className="project-code-badge" id="project-detail-code">
                {project.project_code}
              </span>
              <span className={`priority-badge ${priorityClass}`}>
                {project.priority || "Medium"} Priority
              </span>
              <span className={`status-pill status-pill-${currentStatus.toLowerCase()}`}>
                {currentStatus}
              </span>
            </div>

            <h1 className="hero-project-title" id="project-detail-name">
              {project.name}
            </h1>

            {project.description && (
              <p className="hero-project-desc" id="project-detail-desc">
                {project.description}
              </p>
            )}
          </div>

          {/* Right Header Status Action Area */}
          <div className="project-hero-actions">
            {canManageProject && (
              <div className="status-transition-box">
                <span className="status-box-label">Lifecycle Status</span>
                <div className="status-control-row">
                  <span className={`status-pill status-pill-${currentStatus.toLowerCase()}`}>
                    {currentStatus}
                  </span>

                  <select
                    id="status-transition-select"
                    className="status-select-action"
                    aria-label="Change project status"
                    defaultValue=""
                    onChange={handleSelectStatus}
                    disabled={allowedTransitions.length === 0 || statusMutation.isPending}
                  >
                    <option value="" disabled>
                      {allowedTransitions.length === 0
                        ? "No transitions"
                        : "Change Status..."}
                    </option>
                    {allowedTransitions.map((nextSt) => (
                      <option key={nextSt} value={nextSt}>
                        Transition to {nextSt}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Key Metrics Grid */}
        <div className="detail-metrics-grid">
          <div className="metric-box">
            <span className="metric-box-label">START DATE</span>
            <strong className="metric-box-val">{formatDate(project.start_date)}</strong>
          </div>
          <div className="metric-box">
            <span className="metric-box-label">TARGET COMPLETION</span>
            <strong className="metric-box-val">
              {project.end_date ? formatDate(project.end_date) : "Open Ended"}
            </strong>
          </div>
          <div className="metric-box">
            <span className="metric-box-label">PROJECT MANAGER</span>
            <strong className="metric-box-val">
              {project.pm_id ? `PM #${project.pm_id}` : "Unassigned"}
            </strong>
          </div>
          <div className="metric-box">
            <span className="metric-box-label">COMMISSIONING CLIENT</span>
            <strong className="metric-box-val">Client #{project.client_id}</strong>
          </div>
        </div>
      </div>

      {/* Tabs Row */}
      <div className="detail-section-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          id="tab-milestones"
          aria-selected={activeTab === "milestones"}
          aria-controls="panel-milestones"
          className={`tab-btn ${activeTab === "milestones" ? "tab-active" : ""}`}
          onClick={() => setActiveTab("milestones")}
        >
          <span>Milestone Roadmap</span>
        </button>

        <button
          type="button"
          role="tab"
          id="tab-staffing"
          aria-selected={activeTab === "staffing"}
          aria-controls="panel-staffing"
          className={`tab-btn ${activeTab === "staffing" ? "tab-active" : ""}`}
          onClick={() => setActiveTab("staffing")}
        >
          <span>Team Staffing &amp; Roster</span>
        </button>
      </div>

      {/* Tab Panels */}
      {activeTab === "milestones" && (
        <div id="panel-milestones" role="tabpanel" aria-labelledby="tab-milestones">
          <MilestoneTimeline
            projectId={project.project_id}
            project={project}
            canManage={canManageProject}
            onAddMilestone={() => setIsAddMilestoneOpen(true)}
          />
        </div>
      )}

      {activeTab === "staffing" && (
        <div id="panel-staffing" role="tabpanel" aria-labelledby="tab-staffing">
          {/* Embedded Project Staffing Panel (PR #50) */}
          <ProjectStaffingPanel projectId={project.project_id} />
        </div>
      )}

      {/* Add Milestone Modal Dialog (US-08) */}
      <AddMilestoneModal
        isOpen={isAddMilestoneOpen}
        onClose={() => setIsAddMilestoneOpen(false)}
        project={project}
      />

      {/* Status Confirmation Modal Dialog (US-36) */}
      <StatusConfirmationModal
        isOpen={Boolean(pendingStatusChange)}
        onClose={() => {
          setPendingStatusChange(null);
          setStatusActionError("");
        }}
        project={project}
        targetStatus={pendingStatusChange}
        onConfirm={handleConfirmStatusChange}
        isPending={statusMutation.isPending}
        error={statusActionError}
      />
    </section>
  );
}
