import React, { useState, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getPendingLeaveRequests, getLeaveConflicts } from "../../api/leaveApi";
import LeaveConflictDrawer from "./LeaveConflictDrawer";
import ApproveLeaveModal from "./ApproveLeaveModal";
import RejectLeaveModal from "./RejectLeaveModal";
import "./leaveTriage.css";

/**
 * TeamLeaveTriagePage Component (US-14, US-16, US-17 / Issue #106)
 *
 * Main Team Lead Leave Management & Review Triage Dashboard:
 * - Queue of pending and historical leave requests for review
 * - Status filters: Pending (default) / All
 * - Conflicting-task count chip per row
 * - Review action opening LeaveConflictDrawer
 * - Notification deep links through `?request={id}` URL query parameter
 * - Integrated approval, task reallocation, and rejection modals
 */
export default function TeamLeaveTriagePage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Status filter state: "PENDING" | "ALL"
  const [statusFilter, setStatusFilter] = useState("PENDING");
  const [page, setPage] = useState(1);
  const limit = 20;

  // Selected request state for drawer and modals
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Modal states
  const [isApproveModalOpen, setIsApproveModalOpen] = useState(false);
  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);
  const [activeConflictReport, setActiveConflictReport] = useState(null);

  // Toast notification state
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4500);
    return () => clearTimeout(timer);
  }, [toast]);

  // Fetch queue of leave requests
  const {
    data: queueData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["leave", "pending-queue", { status: statusFilter, page, limit }],
    queryFn: () => getPendingLeaveRequests({ status: statusFilter, page, limit }),
  });

  const items = useMemo(() => {
    if (Array.isArray(queueData?.items)) return queueData.items;
    if (Array.isArray(queueData)) return queueData;
    return [];
  }, [queueData]);

  const total = queueData?.total ?? items.length;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  // Deep-link notification handling via ?request={id}
  const requestIdParam = searchParams.get("request");

  useEffect(() => {
    if (!requestIdParam) return;

    const targetId = Number(requestIdParam);
    if (!targetId) return;

    // First check if the item is already loaded in the items list
    const found = items.find((item) => item.leave_id === targetId);
    if (found) {
      queueMicrotask(() => {
        setSelectedRequest(found);
        setIsDrawerOpen(true);
      });
    } else {
      // If not in current page/filter, query conflict details directly to open drawer
      getLeaveConflicts(targetId)
        .then((report) => {
          if (report) {
            setSelectedRequest({
              leave_id: report.leave_id,
              employee_id: report.employee_id,
              employee_name: report.employee_name,
              leave_type_name: report.leave_type_name,
              start_date: report.start_date,
              end_date: report.end_date,
              total_days: report.total_days,
              reason: report.reason || "Review requested via notification deep-link.",
              status: report.status || "PENDING",
            });
            setIsDrawerOpen(true);
          }
        })
        .catch((err) => {
          console.warn("Failed to load request from notification link:", err?.message);
        });
    }
  }, [requestIdParam, items]);

  const handleOpenReview = (request) => {
    setSelectedRequest(request);
    setIsDrawerOpen(true);
    // Update URL query param to reflect active drawer without full reload
    setSearchParams({ request: String(request.leave_id) }, { replace: true });
  };

  const handleCloseDrawer = () => {
    setIsDrawerOpen(false);
    // Remove ?request from URL params
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("request");
    setSearchParams(nextParams, { replace: true });
  };

  const handleApproveClick = (request, conflictReport) => {
    setSelectedRequest(request);
    setActiveConflictReport(conflictReport);
    setIsApproveModalOpen(true);
  };

  const handleRejectClick = (request) => {
    setSelectedRequest(request);
    setIsRejectModalOpen(true);
  };

  const handleActionSuccess = ({ toastMessage }) => {
    setToast({
      message: toastMessage,
      type: "success",
    });
    refetch();
    handleCloseDrawer();
  };

  return (
    <div className="leave-triage-container" data-testid="team-leave-triage-page">
      {/* Toast Notification Banner */}
      {toast && (
        <div className="leave-toast-container" role="status" aria-live="polite">
          <div className={`leave-toast leave-toast-${toast.type}`}>
            <span>✓ {toast.message}</span>
            <button
              type="button"
              className="leave-toast-close"
              onClick={() => setToast(null)}
              aria-label="Dismiss toast"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Page Header */}
      <header className="leave-triage-header">
        <div>
          <span className="leave-triage-eyebrow">TEAM LEAD / LEAVE TRIAGE</span>
          <h1 className="leave-triage-title">Leave Review & Conflict Triage</h1>
          <p className="leave-triage-subtitle">
            Review incoming employee leave requests, analyze conflicting tasks and milestones, and manage task reallocations.
          </p>
        </div>
      </header>

      {/* Main Queue Card */}
      <div className="leave-table-card">
        {/* Filter Toolbar */}
        <div className="leave-filter-bar">
          <div className="leave-filter-group">
            <label htmlFor="triage-status-filter" className="leave-filter-label">
              Filter Queue:
            </label>
            <select
              id="triage-status-filter"
              className="leave-filter-select"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              data-testid="triage-status-filter"
            >
              <option value="PENDING">Pending Review</option>
              <option value="ALL">All Requests</option>
            </select>
          </div>

          <div style={{ fontSize: "13px", color: "#64748b", fontWeight: "600" }}>
            Total in queue: {total}
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="leave-empty-state" aria-busy="true">
            <div className="empty-state-icon">⏳</div>
            <p className="empty-state-title">Loading leave review queue...</p>
          </div>
        )}

        {/* Error State */}
        {isError && (
          <div className="leave-empty-state">
            <div className="empty-state-icon">⚠️</div>
            <p className="empty-state-title">Unable to load leave queue</p>
            <p className="empty-state-desc">{error?.message || "Server error occurred"}</p>
            <button
              type="button"
              className="leave-btn leave-btn-sm leave-btn-secondary"
              onClick={() => refetch()}
            >
              Try Again
            </button>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !isError && items.length === 0 && (
          <div className="leave-empty-state" data-testid="triage-empty-state">
            <div className="empty-state-icon">🎉</div>
            <p className="empty-state-title">No leave requests pending review</p>
            <p className="empty-state-desc">
              {statusFilter === "PENDING"
                ? "All team leave requests have been reviewed and resolved."
                : "No leave requests match the selected filter."}
            </p>
          </div>
        )}

        {/* Queue Table */}
        {!isLoading && !isError && items.length > 0 && (
          <>
            <div className="leave-table-responsive">
              <table className="leave-table" aria-label="Team leave review queue">
                <thead>
                  <tr>
                    <th>Applicant</th>
                    <th>Leave Type</th>
                    <th>Leave Dates</th>
                    <th>Days</th>
                    <th>Task Conflicts</th>
                    <th>Status</th>
                    <th>Applied At</th>
                    <th style={{ textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((req) => {
                    const conflictCount = req.conflicting_task_count ?? 0;
                    const hasConflicts = conflictCount > 0;
                    const statusStr = (req.status || "PENDING").toUpperCase();

                    return (
                      <tr key={req.leave_id} data-testid={`triage-row-${req.leave_id}`}>
                        <td>
                          <div style={{ display: "flex", flexDirection: "column" }}>
                            <strong style={{ color: "#0f172a" }}>
                              {req.employee_name || `Employee #${req.employee_id || req.emp_id}`}
                            </strong>
                            <span style={{ fontSize: "11px", color: "#64748b" }}>
                              Emp ID #{req.employee_id || req.emp_id}
                            </span>
                          </div>
                        </td>

                        <td>
                          <span>{req.leave_type_name || "Leave"}</span>
                        </td>

                        <td>
                          <span style={{ whiteSpace: "nowrap" }}>
                            {req.start_date} → {req.end_date}
                          </span>
                        </td>

                        <td>
                          <span style={{ fontWeight: "700" }}>
                            {req.total_days} {req.total_days === 1 ? "day" : "days"}
                          </span>
                        </td>

                        {/* Conflicting-task Count Chip */}
                        <td>
                          <span
                            className={`conflict-chip ${
                              hasConflicts ? "conflict-chip-has-conflicts" : "conflict-chip-zero"
                            }`}
                            data-testid={`conflict-chip-${req.leave_id}`}
                          >
                            {hasConflicts ? (
                              <>
                                <span>⚠️</span> {conflictCount} {conflictCount === 1 ? "conflict" : "conflicts"}
                              </>
                            ) : (
                              <>
                                <span>✓</span> 0 conflicts
                              </>
                            )}
                          </span>
                        </td>

                        <td>
                          <span
                            style={{
                              display: "inline-block",
                              padding: "2px 8px",
                              borderRadius: "9999px",
                              fontSize: "11px",
                              fontWeight: "700",
                              textTransform: "uppercase",
                              background: statusStr === "PENDING" ? "#fffbeb" : statusStr === "APPROVED" ? "#ecfdf5" : "#fef2f2",
                              color: statusStr === "PENDING" ? "#92400e" : statusStr === "APPROVED" ? "#065f46" : "#991b1b",
                              border: `1px solid ${statusStr === "PENDING" ? "#fde68a" : statusStr === "APPROVED" ? "#a7f3d0" : "#fecaca"}`,
                            }}
                          >
                            {statusStr}
                          </span>
                        </td>

                        <td>
                          <span style={{ fontSize: "12px", color: "#64748b" }}>
                            {req.applied_at ? String(req.applied_at).split("T")[0] : "—"}
                          </span>
                        </td>

                        <td style={{ textAlign: "right" }}>
                          <button
                            type="button"
                            className="leave-btn leave-btn-sm leave-btn-primary"
                            onClick={() => handleOpenReview(req)}
                            data-testid={`review-btn-${req.leave_id}`}
                          >
                            Review
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="leave-pagination">
              <span className="pagination-info">
                Showing {(page - 1) * limit + 1}–{Math.min(page * limit, total)} of {total} requests
              </span>

              <div className="pagination-controls">
                <button
                  type="button"
                  className="leave-btn leave-btn-sm leave-btn-secondary"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  aria-label="Previous page"
                >
                  ← Previous
                </button>
                <span style={{ fontSize: "13px", fontWeight: "600", color: "#334155" }}>
                  Page {page} of {totalPages}
                </span>
                <button
                  type="button"
                  className="leave-btn leave-btn-sm leave-btn-secondary"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  aria-label="Next page"
                >
                  Next →
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Side Conflict Drawer */}
      <LeaveConflictDrawer
        leaveRequest={selectedRequest}
        isOpen={isDrawerOpen}
        onClose={handleCloseDrawer}
        onApproveClick={handleApproveClick}
        onRejectClick={handleRejectClick}
      />

      {/* Approve & Reallocate Modal */}
      {isApproveModalOpen && (
        <ApproveLeaveModal
          isOpen={isApproveModalOpen}
          leaveRequest={selectedRequest}
          conflictReport={activeConflictReport}
          onClose={() => setIsApproveModalOpen(false)}
          onSuccess={handleActionSuccess}
        />
      )}

      {/* Reject Modal */}
      {isRejectModalOpen && (
        <RejectLeaveModal
          isOpen={isRejectModalOpen}
          leaveRequest={selectedRequest}
          onClose={() => setIsRejectModalOpen(false)}
          onSuccess={handleActionSuccess}
        />
      )}
    </div>
  );
}
