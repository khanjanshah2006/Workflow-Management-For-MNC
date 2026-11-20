import React, { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../context/AuthContext.jsx";
import { getExecutiveDashboard } from "../../api/executiveApi.js";
import ExecutiveKPIGrid from "./ExecutiveKPIGrid.jsx";
import ProjectStatusBar from "./ProjectStatusBar.jsx";
import DepartmentDrilldownTable from "./DepartmentDrilldownTable.jsx";
import ReportGeneratorCard from "./ReportGeneratorCard.jsx";
import PastReportsHistoryTable from "./PastReportsHistoryTable.jsx";
import "./executive.css";

const ALLOWED_ROLES = ["MNC_EXECUTIVE", "ADMIN", "SYSTEM_ADMIN"];

/**
 * ExecutiveConsolePage
 * S7-FE-1 Executive Command Center:
 * - Enterprise Overview Tab: KPI grid, status breakdown, department drilldown.
 * - Management Reports Tab: report generation form, archived report history with authenticated download.
 * - Preserves active tab through URL hash (#overview, #reports).
 */
export default function ExecutiveConsolePage() {
  const { role, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Internal role guard check
  const currentRole = (role || user?.role || user?.user_type || "").toUpperCase();
  const isAuthorized = ALLOWED_ROLES.includes(currentRole);

  // Tab state derived from URL hash (#overview, #reports)
  const activeTab = location.hash === "#reports" ? "reports" : "overview";
  const [reportsRefreshTrigger, setReportsRefreshTrigger] = useState(0);

  const handleTabChange = (tabKey) => {
    navigate(`#${tabKey}`, { replace: true });
  };

  // Dashboard Overview Query
  const {
    data: overview,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["executive", "dashboard"],
    queryFn: getExecutiveDashboard,
    staleTime: 2 * 60 * 1000,
    enabled: isAuthorized,
  });

  if (!isAuthorized) {
    return (
      <section className="page exec-page">
        <div className="exec-error-state">
          <div className="exec-error-icon">⛔</div>
          <h2>Access Restricted</h2>
          <p>
            The Executive Command Center is restricted to Executive Leadership, System Administrators,
            and Administrators.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="page exec-page" aria-label="Executive Command Center">
      {/* Page Header */}
      <div className="exec-header-row">
        <div>
          <div className="page-eyebrow">EXECUTIVE COMMAND CENTER</div>
          <h1 className="exec-title">Executive Console</h1>
          <p className="page-description">
            Enterprise delivery health, portfolio risk oversight, and compliance reporting.
          </p>
        </div>
        <div className="exec-header-actions">
          {activeTab === "overview" && (
            <button
              type="button"
              className="exec-refresh-btn"
              onClick={() => refetch()}
              disabled={isFetching}
              title="Refresh dashboard data"
            >
              <span className={`exec-refresh-icon ${isFetching ? "exec-spinning" : ""}`}>↻</span>
              {isFetching ? "Refreshing..." : "Refresh"}
            </button>
          )}
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="exec-tabs" role="tablist" aria-label="Executive Views">
        <button
          type="button"
          role="tab"
          id="tab-overview"
          aria-selected={activeTab === "overview"}
          aria-controls="panel-overview"
          className={`exec-tab-btn ${activeTab === "overview" ? "exec-tab-active" : ""}`}
          onClick={() => handleTabChange("overview")}
        >
          <span className="exec-tab-icon" aria-hidden="true">📊</span>
          Enterprise Overview
        </button>

        <button
          type="button"
          role="tab"
          id="tab-reports"
          aria-selected={activeTab === "reports"}
          aria-controls="panel-reports"
          className={`exec-tab-btn ${activeTab === "reports" ? "exec-tab-active" : ""}`}
          onClick={() => handleTabChange("reports")}
        >
          <span className="exec-tab-icon" aria-hidden="true">📑</span>
          Management Reports
        </button>
      </div>

      {/* Tab Panels */}
      <div className="exec-tab-panels">
        {/* TAB 1: Enterprise Overview */}
        {activeTab === "overview" && (
          <div
            id="panel-overview"
            role="tabpanel"
            aria-labelledby="tab-overview"
            className="exec-tab-panel"
          >
            {isLoading && (
              <div className="exec-loading-container">
                <div className="exec-spinner" aria-hidden="true" />
                <p>Loading executive overview metrics...</p>
              </div>
            )}

            {error && (
              <div className="exec-error-banner" role="alert">
                <div className="exec-error-icon">⚠️</div>
                <div>
                  <strong>Failed to load executive dashboard:</strong>{" "}
                  {error.message || "Unable to retrieve metrics from server."}
                </div>
                <button
                  type="button"
                  className="exec-retry-btn"
                  onClick={() => refetch()}
                >
                  Retry
                </button>
              </div>
            )}

            {!isLoading && !error && overview && (
              <div className="exec-overview-content">
                {/* 1. High-level KPI Grid */}
                <ExecutiveKPIGrid overview={overview} />

                {/* 2. Project Lifecycle Stacked Status Bar */}
                <ProjectStatusBar
                  projectsByStatus={overview.projects_by_status}
                  totalProjects={overview.total_projects}
                />

                {/* 3. Department Rollup & Drilldown Table */}
                <DepartmentDrilldownTable
                  departments={overview.department_summaries}
                />
              </div>
            )}
          </div>
        )}

        {/* TAB 2: Management Reports */}
        {activeTab === "reports" && (
          <div
            id="panel-reports"
            role="tabpanel"
            aria-labelledby="tab-reports"
            className="exec-tab-panel"
          >
            {/* 1. Report Generator Form */}
            <ReportGeneratorCard
              onReportGenerated={() => {
                setReportsRefreshTrigger((prev) => prev + 1);
              }}
            />

            {/* 2. Past Reports History Table */}
            <PastReportsHistoryTable
              refreshTrigger={reportsRefreshTrigger}
            />
          </div>
        )}
      </div>
    </section>
  );
}
