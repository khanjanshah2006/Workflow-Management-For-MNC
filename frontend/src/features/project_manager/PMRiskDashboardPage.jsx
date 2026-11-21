import React, { useState, useEffect, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getProjects, getProjectDashboard, getProjectRisks } from "../../api/projectsApi";
import { getOverdueTasks } from "../../api/tasksApi";
import { useToast } from "../../components/common/Toast";
import ReassignTaskModal from "../team_lead/ReassignTaskModal";
import ProjectKPICards from "./ProjectKPICards";
import OverdueTasksTable from "./OverdueTasksTable";
import RepeatedRejectionsCard from "./RepeatedRejectionsCard";
import BlockedTasksList from "./BlockedTasksList";
import WorkloadModal from "./WorkloadModal";
import { riskTone } from "./pmRiskUtils";
import "./pmRisk.css";

const STORAGE_KEY = "pm_risk_selected_project_id";

/**
 * PMRiskDashboardPage Component (US-15, US-23, US-38, US-39 / S5)
 *
 * Dedicated mission control for Project Managers to monitor project risks,
 * overdue tasks, repeated quality rejections, blocked items, and team workload.
 */
export default function PMRiskDashboardPage() {
  const queryClient = useQueryClient();
  const toast = useToast();

  const [selectedProjectId, setSelectedProjectId] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? parseInt(saved, 10) : null;
  });

  const [isWorkloadOpen, setIsWorkloadOpen] = useState(false);
  const [taskToReassign, setTaskToReassign] = useState(null);

  // 1. Fetch Projects scoped to user
  const {
    data: projects = [],
    isLoading: isLoadingProjects,
    isError: isProjectsError,
    error: projectsError,
  } = useQuery({
    queryKey: ["projects", "pm-scoped"],
    queryFn: () => getProjects(),
  });

  // Automatically select first available project if none selected or saved project not found
  useEffect(() => {
    if (projects.length > 0) {
      const match = projects.find((p) => p.project_id === selectedProjectId);
      if (!match) {
        const firstId = projects[0].project_id;
        setSelectedProjectId(firstId);
        localStorage.setItem(STORAGE_KEY, String(firstId));
      }
    }
  }, [projects, selectedProjectId]);

  const handleProjectChange = (e) => {
    const id = parseInt(e.target.value, 10);
    setSelectedProjectId(id);
    localStorage.setItem(STORAGE_KEY, String(id));
  };

  const currentProject = useMemo(() => {
    return projects.find((p) => p.project_id === selectedProjectId) || null;
  }, [projects, selectedProjectId]);

  // 2. Fetch Project Dashboard Aggregates (US-23)
  const {
    data: dashboard,
    isError: isDashboardError,
    error: dashboardError,
  } = useQuery({
    queryKey: ["projects", selectedProjectId, "dashboard"],
    queryFn: () => getProjectDashboard(selectedProjectId),
    enabled: Boolean(selectedProjectId),
  });

  // 3. Fetch Project Risks (US-38)
  const {
    data: risks,
    isLoading: isLoadingRisks,
  } = useQuery({
    queryKey: ["projects", selectedProjectId, "risks"],
    queryFn: () => getProjectRisks(selectedProjectId),
    enabled: Boolean(selectedProjectId),
  });

  // 4. Fetch Overdue Tasks for Project (US-15)
  const {
    data: overdueData,
    isLoading: isLoadingOverdue,
  } = useQuery({
    queryKey: ["tasks", "overdue", selectedProjectId],
    queryFn: () => getOverdueTasks({ project_id: selectedProjectId, limit: 100 }),
    enabled: Boolean(selectedProjectId),
  });

  const overdueTasks = overdueData?.items || [];
  const overdueCount = dashboard?.overdue_tasks_count ?? overdueTasks.length;
  const currentRiskScore = risks?.risk_score || "LOW";
  const tone = riskTone(currentRiskScore);

  const handleReassignSuccess = () => {
    if (toast?.success) {
      toast.success("Task successfully reassigned.");
    } else {
      alert("Task reassigned successfully.");
    }

    // Invalidate affected queries
    queryClient.invalidateQueries({ queryKey: ["tasks", "overdue", selectedProjectId] });
    queryClient.invalidateQueries({ queryKey: ["projects", selectedProjectId, "dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["projects", selectedProjectId, "risks"] });
    queryClient.invalidateQueries({ queryKey: ["projects", selectedProjectId, "team-workload"] });
  };

  return (
    <div className="pm-dashboard-page" role="main" aria-label="PM Risk & Delivery Dashboard">
      {/* Top Header & Project Selection */}
      <header className="pm-header-row">
        <div className="pm-header-left">
          <span className="page-eyebrow">PROJECT RISK & DELIVERY</span>
          <div className="pm-title-row">
            <h1 className="pm-page-title">Risk & Quality Dashboard</h1>
            {/* Risk Score Pill */}
            {selectedProjectId && (
              <span className={`pm-risk-pill pm-risk-pill-${tone}`} aria-label={`Project Risk Level: ${currentRiskScore}`}>
                ● Risk: {currentRiskScore}
              </span>
            )}
          </div>
        </div>

        <div className="pm-header-actions">
          {/* Project Selector */}
          <div className="pm-project-picker">
            <label htmlFor="pm-project-select">Project:</label>
            <select
              id="pm-project-select"
              className="pm-select"
              value={selectedProjectId || ""}
              onChange={handleProjectChange}
              disabled={isLoadingProjects || projects.length === 0}
            >
              {projects.length === 0 ? (
                <option value="">No projects available</option>
              ) : (
                projects.map((p) => (
                  <option key={p.project_id} value={p.project_id}>
                    {p.name || p.project_code || `Project #${p.project_id}`}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Workload View Button */}
          <button
            type="button"
            className="pm-btn pm-btn-secondary"
            onClick={() => setIsWorkloadOpen(true)}
            disabled={!selectedProjectId}
          >
            👥 Team Workload
          </button>
        </div>
      </header>

      {/* Overdue Alert Banner when overdue_tasks_count > 0 */}
      {overdueCount > 0 && (
        <div className="pm-overdue-banner" role="alert">
          <span className="pm-banner-icon">⚠️</span>
          <div className="pm-banner-content">
            <strong>Action Required:</strong>
            {overdueCount === 1
              ? `There is 1 overdue task in ${currentProject?.name || "this project"} requiring immediate escalation.`
              : `There are ${overdueCount} overdue tasks in ${currentProject?.name || "this project"} requiring immediate escalation.`}
          </div>
        </div>
      )}

      {/* Global Project State Errors */}
      {isProjectsError && (
        <div className="alert-banner alert-banner-danger" role="alert">
          <span>Failed to load project list: {projectsError?.message || "Unknown error"}</span>
        </div>
      )}

      {isDashboardError && (
        <div className="alert-banner alert-banner-danger" role="alert">
          <span>Failed to load dashboard metrics: {dashboardError?.message || "Unknown error"}</span>
        </div>
      )}

      {/* KPI Cards & Status Distribution */}
      <ProjectKPICards dashboard={dashboard} />

      {/* Overdue Tasks Table */}
      <OverdueTasksTable
        tasks={overdueTasks}
        isLoading={isLoadingOverdue}
        onReassignTask={(task) => setTaskToReassign(task)}
      />

      {/* Dual Row: Quality Rejections & Blocked Tasks */}
      <div className="pm-dual-grid">
        <RepeatedRejectionsCard
          tasks={risks?.repeatedly_rejected_tasks || []}
          rejectionThreshold={risks?.rejection_threshold ?? dashboard?.rejection_threshold ?? 2}
          isLoading={isLoadingRisks}
        />

        <BlockedTasksList
          tasks={risks?.blocked_tasks || []}
          isLoading={isLoadingRisks}
        />
      </div>

      {/* Workload Modal (US-39) */}
      <WorkloadModal
        isOpen={isWorkloadOpen}
        projectId={selectedProjectId}
        onClose={() => setIsWorkloadOpen(false)}
      />

      {/* Reassign Task Modal (Reuses features/team_lead/ReassignTaskModal.jsx) */}
      {taskToReassign && (
        <ReassignTaskModal
          isOpen={Boolean(taskToReassign)}
          task={{
            ...taskToReassign,
            assigned_to: taskToReassign.assignee_id,
            assignee: {
              emp_id: taskToReassign.assignee_id,
              full_name: taskToReassign.assignee_name,
            },
          }}
          onClose={() => setTaskToReassign(null)}
          onSuccess={handleReassignSuccess}
        />
      )}
    </div>
  );
}
