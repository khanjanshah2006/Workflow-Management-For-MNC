import React, { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getMyLeaveRequests, cancelLeaveRequest } from "../../api/leaveApi";
import { getLeaveStatusBadgeClass } from "./leaveUtils";

/**
 * MyLeaveRequestsTable Component (US-16 / S4)
 *
 * Displays employee's leave request history:
 * - Status filter: ALL, PENDING, APPROVED, REJECTED, CANCELLED
 * - Year filter: Current year and past calendar years
 * - Server / client pagination
 * - Displays review remarks
 * - Status badges: APPROVED (green), PENDING (amber), REJECTED (red), CANCELLED (grey)
 * - Allows cancellation of PENDING requests only
 * - Accessible confirmation modal dialog before cancellation (avoids relying solely on confirm())
 */
export default function MyLeaveRequestsTable({
  onCancelSuccess,
  onRequestNewLeave,
}) {
  const queryClient = useQueryClient();

  const [currentYear] = useState(() => new Date().getFullYear());

  // Filter states
  const [selectedStatus, setSelectedStatus] = useState("ALL");
  const [selectedYear, setSelectedYear] = useState(String(currentYear));
  const [page, setPage] = useState(1);
  const limit = 10;

  // Confirmation UI state for cancellation
  const [requestToCancel, setRequestToCancel] = useState(null);
  const [cancelError, setCancelError] = useState(null);

  // Available year options (e.g. current year down to past 4 years)
  const yearOptions = useMemo(() => {
    const years = [];
    for (let y = currentYear + 1; y >= currentYear - 4; y--) {
      years.push(String(y));
    }
    return years;
  }, [currentYear]);

  // Query leave requests
  const {
    data: requestsData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: [
      "leave",
      "requests",
      { status: selectedStatus, year: selectedYear, page, limit },
    ],
    queryFn: () =>
      getMyLeaveRequests({
        status: selectedStatus,
        year: selectedYear === "ALL" ? undefined : Number(selectedYear),
        page,
        limit,
      }),
  });

  const items = useMemo(() => {
    if (Array.isArray(requestsData?.items)) return requestsData.items;
    if (Array.isArray(requestsData)) return requestsData;
    return [];
  }, [requestsData]);

  const total = requestsData?.total ?? items.length;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  // Cancellation mutation
  const cancelMutation = useMutation({
    mutationFn: (leaveId) => cancelLeaveRequest(leaveId),
    onSuccess: () => {
      // Invalidate both requests and balances queries
      queryClient.invalidateQueries({ queryKey: ["leave"] });
      setRequestToCancel(null);
      setCancelError(null);
      if (onCancelSuccess) {
        onCancelSuccess();
      }
    },
    onError: (err) => {
      setCancelError(err?.message || "Failed to cancel leave request. Please try again.");
    },
  });

  const handleOpenCancelModal = (request) => {
    setCancelError(null);
    setRequestToCancel(request);
  };

  const handleCloseCancelModal = () => {
    if (!cancelMutation.isPending) {
      setRequestToCancel(null);
      setCancelError(null);
    }
  };

  const handleConfirmCancel = () => {
    if (!requestToCancel) return;
    cancelMutation.mutate(requestToCancel.leave_id);
  };

  const handleStatusFilterChange = (e) => {
    setSelectedStatus(e.target.value);
    setPage(1);
  };

  const handleYearFilterChange = (e) => {
    setSelectedYear(e.target.value);
    setPage(1);
  };

  return (
    <div className="leave-table-card" data-testid="my-leave-requests-table">
      {/* Filter Toolbar */}
      <div className="leave-filter-bar">
        <div className="leave-filter-group">
          <label htmlFor="leave-status-filter" className="leave-filter-label">
            Status:
          </label>
          <select
            id="leave-status-filter"
            className="leave-filter-select"
            value={selectedStatus}
            onChange={handleStatusFilterChange}
            data-testid="leave-status-filter"
          >
            <option value="ALL">All Statuses</option>
            <option value="PENDING">Pending</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
            <option value="CANCELLED">Cancelled</option>
          </select>

          <label htmlFor="leave-year-filter" className="leave-filter-label">
            Year:
          </label>
          <select
            id="leave-year-filter"
            className="leave-filter-select"
            value={selectedYear}
            onChange={handleYearFilterChange}
            data-testid="leave-year-filter"
          >
            <option value="ALL">All Years</option>
            {yearOptions.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>

        {onRequestNewLeave && (
          <button
            type="button"
            className="leave-btn leave-btn-sm leave-btn-primary"
            onClick={onRequestNewLeave}
          >
            + Apply for Leave
          </button>
        )}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="leave-empty-state" aria-busy="true">
          <div className="empty-state-icon">⏳</div>
          <p className="empty-state-title">Loading leave requests...</p>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="leave-empty-state">
          <div className="empty-state-icon">⚠️</div>
          <p className="empty-state-title">Unable to load leave requests</p>
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

      {/* Empty items state */}
      {!isLoading && !isError && items.length === 0 && (
        <div className="leave-empty-state" data-testid="leave-empty-state">
          <div className="empty-state-icon">📄</div>
          <p className="empty-state-title">No leave requests found</p>
          <p className="empty-state-desc">
            {selectedStatus !== "ALL" || selectedYear !== "ALL"
              ? "No requests match the selected filter criteria."
              : "You haven't submitted any leave requests yet."}
          </p>
        </div>
      )}

      {/* Table Content */}
      {!isLoading && !isError && items.length > 0 && (
        <>
          <div className="leave-table-responsive">
            <table className="leave-table" aria-label="Leave request history">
              <thead>
                <tr>
                  <th>Leave Type</th>
                  <th>Dates</th>
                  <th>Days</th>
                  <th>Reason</th>
                  <th>Status</th>
                  <th>Review Remarks</th>
                  <th style={{ textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((req) => {
                  const isPending = req.status === "PENDING";
                  const badgeClass = getLeaveStatusBadgeClass(req.status);

                  return (
                    <tr key={req.leave_id} data-testid={`leave-row-${req.leave_id}`}>
                      <td>
                        <strong>{req.leave_type_name || `Type #${req.leave_type_id}`}</strong>
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
                      <td>
                        <div
                          className="remarks-text"
                          title={req.reason}
                          style={{ maxWidth: "220px" }}
                        >
                          {req.reason}
                        </div>
                      </td>
                      <td>
                        <span
                          className={`leave-badge ${badgeClass}`}
                          data-testid={`badge-${req.status.toLowerCase()}`}
                        >
                          {req.status}
                        </span>
                      </td>
                      <td>
                        {req.review_remarks ? (
                          <div
                            className="remarks-text"
                            title={req.review_remarks}
                            data-testid="review-remarks"
                          >
                            {req.review_remarks}
                          </div>
                        ) : (
                          <span className="remarks-empty">
                            {req.status === "PENDING" ? "Awaiting review" : "—"}
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {isPending ? (
                          <button
                            type="button"
                            className="leave-btn leave-btn-sm leave-btn-danger"
                            onClick={() => handleOpenCancelModal(req)}
                            data-testid={`cancel-btn-${req.leave_id}`}
                            title="Cancel this pending leave request"
                          >
                            Cancel
                          </button>
                        ) : (
                          <span style={{ color: "#94a3b8", fontSize: "13px" }}>—</span>
                        )}
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

      {/* Accessible Confirmation Modal for Cancellation */}
      {requestToCancel && (
        <div
          className="modal-backdrop"
          onClick={handleCloseCancelModal}
          role="dialog"
          aria-modal="true"
          aria-labelledby="cancel-modal-title"
          data-testid="cancel-confirm-modal"
        >
          <div
            className="leave-modal-dialog"
            style={{ maxWidth: "480px" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="leave-modal-header">
              <h2 id="cancel-modal-title" className="leave-modal-title">
                Cancel Leave Request
              </h2>
              <button
                type="button"
                className="leave-modal-close-btn"
                onClick={handleCloseCancelModal}
                disabled={cancelMutation.isPending}
                aria-label="Close cancel confirmation modal"
              >
                ×
              </button>
            </div>

            <div className="leave-modal-body">
              {cancelError && (
                <div className="leave-alert-error" role="alert" style={{ marginBottom: "12px" }}>
                  <span>⚠️ {cancelError}</span>
                </div>
              )}

              <p style={{ margin: "0 0 12px 0", fontSize: "14px", color: "#334155", lineHeight: "1.5" }}>
                Are you sure you want to cancel your leave request for{" "}
                <strong>{requestToCancel.leave_type_name || "Leave"}</strong>?
              </p>

              <div
                style={{
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                  padding: "12px 16px",
                  fontSize: "13px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                }}
              >
                <div>
                  <span style={{ color: "#64748b" }}>Date Range:</span>{" "}
                  <strong>
                    {requestToCancel.start_date} to {requestToCancel.end_date}
                  </strong>
                </div>
                <div>
                  <span style={{ color: "#64748b" }}>Duration:</span>{" "}
                  <strong>
                    {requestToCancel.total_days} {requestToCancel.total_days === 1 ? "day" : "days"}
                  </strong>
                </div>
              </div>

              <p style={{ margin: "12px 0 0 0", fontSize: "12px", color: "#dc2626" }}>
                * This action will cancel the pending request and restore the days to your available balance.
              </p>
            </div>

            <div className="leave-modal-footer">
              <button
                type="button"
                className="leave-btn leave-btn-secondary"
                onClick={handleCloseCancelModal}
                disabled={cancelMutation.isPending}
              >
                Keep Request
              </button>
              <button
                type="button"
                className="leave-btn leave-btn-danger"
                onClick={handleConfirmCancel}
                disabled={cancelMutation.isPending}
                data-testid="confirm-cancel-button"
              >
                {cancelMutation.isPending ? "Cancelling..." : "Confirm Cancellation"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
