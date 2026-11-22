import React from "react";

/**
 * LeaveBalanceCards Component (US-16 AC3 / S4)
 *
 * Displays employee leave balances for each active leave type:
 * - Available days / quota
 * - Used days
 * - Pending days
 * - Progress bar visually representing consumption
 * - Unpaid tag for unpaid leave policies
 * - "No balance" display when available_days <= 0
 */
export default function LeaveBalanceCards({
  balances = [],
  isLoading = false,
  isError = false,
  error = null,
  onRetry = null,
}) {
  const balanceItems = Array.isArray(balances)
    ? balances
    : Array.isArray(balances?.balances)
    ? balances.balances
    : [];

  if (isLoading) {
    return (
      <section className="leave-balance-section" aria-busy="true" aria-label="Loading leave balances">
        <div className="leave-section-title">
          <span>Leave Balances</span>
        </div>
        <div className="leave-cards-grid">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="leave-card-skeleton" data-testid="leave-balance-skeleton">
              <div className="skeleton-line" style={{ height: "18px", width: "50%" }} />
              <div className="skeleton-line" style={{ height: "32px", width: "40%" }} />
              <div className="skeleton-line" style={{ height: "8px", width: "100%" }} />
              <div className="skeleton-line" style={{ height: "14px", width: "70%" }} />
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (isError) {
    return (
      <section className="leave-balance-section" aria-label="Leave balances error">
        <div className="leave-section-title">
          <span>Leave Balances</span>
        </div>
        <div className="leave-alert-error" role="alert">
          <span>⚠️ Failed to load leave balances: {error?.message || "Server error"}</span>
          {onRetry && (
            <button
              type="button"
              className="leave-btn leave-btn-sm leave-btn-secondary"
              onClick={onRetry}
              style={{ marginLeft: "auto" }}
            >
              Retry
            </button>
          )}
        </div>
      </section>
    );
  }

  if (balanceItems.length === 0) {
    return (
      <section className="leave-balance-section" aria-label="Leave balances">
        <div className="leave-section-title">
          <span>Leave Balances</span>
        </div>
        <div className="leave-empty-state" style={{ background: "#fff", borderRadius: "12px", border: "1px solid #e2e8f0" }}>
          <div className="empty-state-icon">📋</div>
          <p className="empty-state-title">No leave balances available</p>
          <p className="empty-state-desc">Your active leave quotas will appear here once allocated by HR.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="leave-balance-section" aria-label="Leave balances">
      <div className="leave-section-title">
        <span>Leave Balances</span>
      </div>

      <div className="leave-cards-grid">
        {balanceItems.map((balance) => {
          const quota = balance.yearly_quota ?? 0;
          const used = balance.used_days ?? 0;
          const pending = balance.pending_days ?? 0;
          const available = balance.available_days ?? 0;
          const isPaid = balance.is_paid !== false;
          const hasNoBalance = available <= 0;

          // Calculate percentage fill
          const usedPct = quota > 0 ? Math.min(100, Math.max(0, (used / quota) * 100)) : 0;
          const pendingPct = quota > 0 ? Math.min(100 - usedPct, Math.max(0, (pending / quota) * 100)) : 0;

          return (
            <article
              key={balance.leave_type_id}
              className="leave-balance-card"
              data-testid={`leave-card-${balance.leave_type_id}`}
            >
              {/* Card Header */}
              <div className="leave-card-header">
                <h3 className="leave-type-name">{balance.leave_type_name}</h3>
                <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                  {!isPaid && (
                    <span className="leave-tag leave-tag-unpaid" data-testid="tag-unpaid">
                      Unpaid
                    </span>
                  )}
                  {hasNoBalance && (
                    <span className="leave-tag leave-tag-empty" data-testid="tag-no-balance">
                      No balance
                    </span>
                  )}
                </div>
              </div>

              {/* Main Stat: Available days / Quota */}
              <div className="leave-card-stats">
                {hasNoBalance ? (
                  <div className="balance-main-stat">
                    <span className="stat-no-balance">No balance</span>
                    <span className="stat-unit">/ {quota} days quota</span>
                  </div>
                ) : (
                  <div className="balance-main-stat">
                    <span className="stat-number">{available}</span>
                    <span className="stat-unit">/ {quota} days available</span>
                  </div>
                )}
              </div>

              {/* Progress Bar */}
              <div className="leave-progress-container">
                <div
                  className="leave-progress-bar"
                  role="progressbar"
                  aria-valuenow={used + pending}
                  aria-valuemin={0}
                  aria-valuemax={quota}
                  aria-label={`${balance.leave_type_name} used ${used} days and pending ${pending} days of ${quota} days`}
                >
                  <div
                    className="leave-progress-fill-used"
                    style={{ width: `${usedPct}%` }}
                    title={`Used: ${used} days`}
                  />
                  <div
                    className="leave-progress-fill-pending"
                    style={{ width: `${pendingPct}%` }}
                    title={`Pending: ${pending} days`}
                  />
                </div>
              </div>

              {/* Breakdown */}
              <div className="leave-card-breakdown">
                <div className="breakdown-item" title="Approved leave days taken">
                  <span className="breakdown-dot dot-used" />
                  <span>Used: <strong>{used}</strong></span>
                </div>
                <div className="breakdown-item" title="Pending leave requests under review">
                  <span className="breakdown-dot dot-pending" />
                  <span>Pending: <strong>{pending}</strong></span>
                </div>
                <div className="breakdown-item" title="Available remaining quota">
                  <span className="breakdown-dot dot-available" />
                  <span>Remaining: <strong>{available}</strong></span>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
