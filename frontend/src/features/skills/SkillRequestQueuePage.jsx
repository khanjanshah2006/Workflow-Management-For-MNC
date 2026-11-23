import React, { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../context/AuthContext.jsx";
import { normalizeRole } from "../../auth/session.js";
import { getSkillRequestQueue } from "../../api/profileApi.js";
import {
  SKILL_ACTIONS,
  SKILL_STATUSES,
  PROFICIENCY_LABELS,
  formatSkillDate,
} from "./skillRequestUtils.js";
import SkillDecisionModal from "./SkillDecisionModal.jsx";
import "./skills.css";

const PAGE_SIZE = 20;

const TABS = [
  { key: SKILL_STATUSES.PENDING, label: "Pending" },
  { key: SKILL_STATUSES.APPROVED, label: "Approved" },
  { key: SKILL_STATUSES.REJECTED, label: "Rejected" },
];

/**
 * SkillRequestQueuePage Component (US-34 / Issue #161)
 *
 * Route: /skill-requests
 * Permissions: HR, TEAM_LEAD, ADMIN
 *
 * Features:
 * - Three review tabs: Pending, Approved, Rejected
 * - Server-paginated review queue (20 per page)
 * - Display columns: Employee, Department, Action, Skill (old -> new for UPDATE), Justification, Submitted date
 * - Role-scoped data: HR sees company-wide; Team Lead sees active team members
 * - Integrated decision modal for approving (optional remarks) and rejecting (mandatory remarks)
 */
export default function SkillRequestQueuePage() {
  const { user, role } = useAuth();

  // Guard against unauthorized view (belt-and-suspenders; ProtectedRoute also enforces this)
  const currentRole = normalizeRole(role || user?.user_type || user?.role || "");
  const isAuthorized =
    currentRole === "HR" || currentRole === "TEAM_LEAD" || currentRole === "ADMIN" || currentRole === "SYSTEM_ADMIN";

  // Tab and Pagination state
  const [activeTab, setActiveTab] = useState(SKILL_STATUSES.PENDING);
  const [page, setPage] = useState(1);

  // Decision Modal state
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [decisionAction, setDecisionAction] = useState("APPROVE"); // "APPROVE" | "REJECT"
  const [isDecisionModalOpen, setIsDecisionModalOpen] = useState(false);

  // Toast feedback state
  const [toast, setToast] = useState(null);

  const showToast = (message, type = "success") => {
    setToast({ message, type, id: Date.now() });
    setTimeout(() => setToast(null), 4500);
  };

  // Fetch paginated review queue from backend API
  const {
    data: queueResponse,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["skill-requests", "queue", { status: activeTab, page, limit: PAGE_SIZE }],
    queryFn: () =>
      getSkillRequestQueue({
        status: activeTab,
        page,
        limit: PAGE_SIZE,
      }),
    enabled: isAuthorized,
  });

  const items = useMemo(() => {
    if (Array.isArray(queueResponse?.items)) return queueResponse.items;
    if (Array.isArray(queueResponse)) return queueResponse;
    return [];
  }, [queueResponse]);

  const total = queueResponse?.total ?? items.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const handleTabChange = (newTab) => {
    if (newTab !== activeTab) {
      setActiveTab(newTab);
      setPage(1);
    }
  };

  const handleOpenApprove = (req) => {
    setSelectedRequest(req);
    setDecisionAction("APPROVE");
    setIsDecisionModalOpen(true);
  };

  const handleOpenReject = (req) => {
    setSelectedRequest(req);
    setDecisionAction("REJECT");
    setIsDecisionModalOpen(true);
  };

  const handleDecisionSuccess = (updatedRequest, actionType) => {
    setIsDecisionModalOpen(false);
    setSelectedRequest(null);
    refetch();
    const actionLabel = actionType === "APPROVE" ? "approved" : "rejected";
    showToast(
      `Skill proposal for ${updatedRequest?.employee_name || "employee"} successfully ${actionLabel}.`,
      "success"
    );
  };

  if (!isAuthorized) {
    return (
      <section className="page skill-queue-page">
        <div className="page-eyebrow">ACCESS CONTROL</div>
        <h1>403 — Unauthorized Access</h1>
        <p className="page-description">
          Your current assigned role does not have permission to view the skill proposal review queue.
        </p>
        <div className="placeholder-panel">
          <div className="placeholder-symbol">🔒</div>
          <h2>Restricted Queue</h2>
          <p>Access is restricted to Human Resources, Team Leads, and Administrators.</p>
        </div>
      </section>
    );
  }

  const getActionBadgeClass = (action) => {
    switch (action?.toUpperCase()) {
      case SKILL_ACTIONS.ADD:
        return "skill-action-tag-add";
      case SKILL_ACTIONS.UPDATE:
        return "skill-action-tag-update";
      case SKILL_ACTIONS.REMOVE:
        return "skill-action-tag-remove";
      default:
        return "";
    }
  };

  const renderSkillColumn = (req) => {
    const action = (req.action || "").toUpperCase();
    const skillName = req.skill_name || req.proposed_skill_name || `Skill #${req.skill_id || "—"}`;
    const proficiency = req.proficiency ? PROFICIENCY_LABELS[req.proficiency] || req.proficiency : "";
    const years = req.years_of_experience != null ? `${req.years_of_experience} yrs` : "";

    if (action === SKILL_ACTIONS.UPDATE) {
      const isNewName = req.proposed_skill_name && req.proposed_skill_name !== req.skill_name;
      return (
        <div className="skill-change-display">
          <div className="skill-change-flow">
            <span>{req.skill_name || "Current Skill"}</span>
            <span className="skill-change-arrow" aria-hidden="true">→</span>
            <span>{isNewName ? req.proposed_skill_name : proficiency || "Updated"}</span>
          </div>
          <span className="skill-change-details">
            Proposed: {proficiency}{years ? ` · ${years}` : ""}
          </span>
        </div>
      );
    }

    if (action === SKILL_ACTIONS.ADD) {
      return (
        <div className="skill-change-display">
          <span className="skill-name-text">{skillName}</span>
          <span className="skill-change-details">
            {proficiency}{years ? ` · ${years}` : ""}
          </span>
        </div>
      );
    }

    if (action === SKILL_ACTIONS.REMOVE) {
      return (
        <div className="skill-change-display">
          <span className="skill-name-text">{skillName}</span>
          <span className="skill-change-details" style={{ color: "#dc2626" }}>
            Proposed for removal
          </span>
        </div>
      );
    }

    return <span className="skill-name-text">{skillName}</span>;
  };

  const startIndex = total > 0 ? (page - 1) * PAGE_SIZE + 1 : 0;
  const endIndex = Math.min(page * PAGE_SIZE, total);

  return (
    <section className="page skill-queue-page" data-testid="skill-request-queue-page">
      <div className="skill-queue-header">
        <div className="page-eyebrow">TALENT & WORKFORCE / REVIEW QUEUE</div>
        <h1 className="skill-queue-title">Skill-Change Proposals Review Queue</h1>
        <p className="skill-queue-subtitle">
          {currentRole === "HR" || currentRole === "ADMIN" || currentRole === "SYSTEM_ADMIN"
            ? "Organization-wide skill change requests submitted by employees across all departments."
            : "Skill proposals submitted by members of teams you lead."}
        </p>
      </div>

      {/* Floating feedback toast */}
      {toast && (
        <div
          style={{
            position: "fixed",
            top: 24,
            right: 24,
            zIndex: 9999,
            background: toast.type === "error" ? "#fef2f2" : "#f0fdf4",
            border: `1px solid ${toast.type === "error" ? "#fecaca" : "#bbf7d0"}`,
            color: toast.type === "error" ? "#991b1b" : "#14532d",
            padding: "12px 18px",
            borderRadius: "8px",
            boxShadow: "0 10px 15px -3px rgba(0,0,0,0.1)",
            fontSize: "13.5px",
            fontWeight: "500",
          }}
          role="status"
        >
          {toast.message}
        </div>
      )}

      {/* Tabs: Pending, Approved, Rejected */}
      <div className="skill-queue-tabs" role="tablist" aria-label="Review Queue Status Tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.key}
            className={`skill-queue-tab ${activeTab === tab.key ? "active" : ""}`}
            onClick={() => handleTabChange(tab.key)}
            data-testid={`queue-tab-${tab.key.toLowerCase()}`}
          >
            <span>{tab.label}</span>
            {activeTab === tab.key && (
              <span className="skill-tab-count" data-testid={`tab-count-${tab.key.toLowerCase()}`}>
                {total}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Queue Card */}
      <div className="skill-queue-card">
        {/* Loading State */}
        {isLoading && (
          <div style={{ textAlign: "center", padding: "48px 0", color: "#64748b" }}>
            <div style={{ fontSize: "24px", marginBottom: "8px" }}>⏳</div>
            <p style={{ margin: 0, fontSize: "14px", fontWeight: "500" }}>Loading review queue...</p>
          </div>
        )}

        {/* Error State */}
        {isError && (
          <div style={{ padding: "32px", textAlign: "center" }}>
            <div style={{ fontSize: "24px", marginBottom: "8px" }}>⚠️</div>
            <h3 style={{ margin: "0 0 6px 0", color: "#991b1b", fontSize: "16px" }}>
              Unable to load review queue
            </h3>
            <p style={{ margin: "0 0 16px 0", color: "#64748b", fontSize: "13.5px" }}>
              {error?.message || "A network or server error occurred."}
            </p>
            <button
              type="button"
              className="skill-btn-secondary"
              onClick={() => refetch()}
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !isError && items.length === 0 && (
          <div
            style={{ padding: "48px 24px", textAlign: "center", color: "#64748b" }}
            data-testid="queue-empty-state"
          >
            <div style={{ fontSize: "32px", marginBottom: "12px" }}>
              {activeTab === SKILL_STATUSES.PENDING ? "🎉" : "📂"}
            </div>
            <h3 style={{ margin: "0 0 6px 0", color: "#0f172a", fontSize: "16px" }}>
              {activeTab === SKILL_STATUSES.PENDING
                ? "No pending skill proposals"
                : `No ${activeTab.toLowerCase()} proposals`}
            </h3>
            <p style={{ margin: 0, fontSize: "13.5px" }}>
              {activeTab === SKILL_STATUSES.PENDING
                ? "All team skill change proposals have been reviewed and decided."
                : `There are currently no proposals in ${activeTab.toLowerCase()} status.`}
            </p>
          </div>
        )}

        {/* Queue Table */}
        {!isLoading && !isError && items.length > 0 && (
          <>
            <div className="skill-queue-table-container">
              <table className="skill-queue-table" aria-label="Skill change proposals queue">
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Department</th>
                    <th>Action</th>
                    <th>Skill</th>
                    <th>Justification</th>
                    <th>Submitted Date</th>
                    {activeTab === SKILL_STATUSES.PENDING ? (
                      <th style={{ textAlign: "right" }}>Decisions</th>
                    ) : (
                      <th>Review Remarks</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {items.map((req) => {
                    const action = (req.action || "").toUpperCase();

                    return (
                      <tr key={req.request_id} data-testid={`queue-row-${req.request_id}`}>
                        {/* 1. Employee */}
                        <td>
                          <div className="skill-employee-info">
                            <span className="skill-employee-name">
                              {req.employee_name || `Employee #${req.emp_id}`}
                            </span>
                            <span className="skill-employee-meta">ID: #{req.emp_id}</span>
                          </div>
                        </td>

                        {/* 2. Department */}
                        <td>
                          <span style={{ color: "#475569" }}>
                            {req.department || req.department_name || "—"}
                          </span>
                        </td>

                        {/* 3. Action */}
                        <td>
                          <span className={`skill-action-tag ${getActionBadgeClass(action)}`}>
                            {action}
                          </span>
                        </td>

                        {/* 4. Skill (shows old -> new for UPDATE) */}
                        <td>{renderSkillColumn(req)}</td>

                        {/* 5. Justification */}
                        <td className="skill-justification-cell" title={req.justification}>
                          {req.justification}
                        </td>

                        {/* 6. Submitted date */}
                        <td style={{ whiteSpace: "nowrap", color: "#64748b" }}>
                          {formatSkillDate(req.created_at)}
                        </td>

                        {/* 7. Decision Actions (Pending tab) or Review Remarks (Approved/Rejected) */}
                        {activeTab === SKILL_STATUSES.PENDING ? (
                          <td style={{ textAlign: "right" }}>
                            <div className="skill-queue-actions" style={{ justifyContent: "flex-end" }}>
                              <button
                                type="button"
                                className="skill-btn-approve"
                                onClick={() => handleOpenApprove(req)}
                                data-testid={`approve-btn-${req.request_id}`}
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                className="skill-btn-reject"
                                onClick={() => handleOpenReject(req)}
                                data-testid={`reject-btn-${req.request_id}`}
                              >
                                Reject
                              </button>
                            </div>
                          </td>
                        ) : (
                          <td>
                            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                              <span style={{ fontStyle: "italic", color: "#334155", fontSize: "12.5px" }}>
                                {req.remarks || req.review_remarks || "—"}
                              </span>
                              {req.reviewed_at && (
                                <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                                  Decided: {formatSkillDate(req.reviewed_at)}
                                </span>
                              )}
                            </div>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="skill-pagination-container" data-testid="queue-pagination">
              <div>
                Showing <strong>{startIndex}</strong>–<strong>{endIndex}</strong> of <strong>{total}</strong> proposals
              </div>
              <div className="skill-pagination-buttons">
                <button
                  type="button"
                  className="skill-pagination-btn"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1 || isFetching}
                  data-testid="pagination-prev-btn"
                >
                  ← Previous
                </button>
                <span className="skill-pagination-page-indicator">
                  Page {page} of {totalPages}
                </span>
                <button
                  type="button"
                  className="skill-pagination-btn"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages || isFetching}
                  data-testid="pagination-next-btn"
                >
                  Next →
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Decision Modal Component */}
      <SkillDecisionModal
        key={`${selectedRequest?.request_id || "none"}-${decisionAction}`}
        isOpen={isDecisionModalOpen}
        action={decisionAction}
        request={selectedRequest}
        onClose={() => {
          setIsDecisionModalOpen(false);
          setSelectedRequest(null);
        }}
        onSuccess={handleDecisionSuccess}
        onRefresh={() => refetch()}
        onShowToast={showToast}
      />
    </section>
  );
}
