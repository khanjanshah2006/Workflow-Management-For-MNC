import React, { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../context/AuthContext";
import { getMyLeaveBalances, getLeavePolicies } from "../../api/leaveApi";
import { getMyProfile } from "../../api/profileApi";
import LeaveBalanceCards from "./LeaveBalanceCards";
import ApplyLeaveModal from "./ApplyLeaveModal";
import MyLeaveRequestsTable from "./MyLeaveRequestsTable";
import "./leave.css";

/**
 * LeaveDashboardPage Component (US-16 / S4 Leave Management)
 *
 * Main self-service leave portal for Employees and Team Leads:
 * - Leave balance summary cards at the top
 * - Two tabs: "Apply for Leave" and "My Requests"
 * - Profile validation ensuring only users with active employee profiles can apply
 * - Automated tab-switch and balance refresh on submission
 * - Accessible cancellation UI and toast notifications
 */
export default function LeaveDashboardPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  // Active tab state: "APPLY" | "MY_REQUESTS"
  const [activeTab, setActiveTab] = useState("APPLY");

  // Optional modal state (when user clicks modal trigger instead of embedded tab)
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Toast notification state
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => {
      setToast(null);
    }, 4500);
    return () => clearTimeout(timer);
  }, [toast]);

  // Query employee profile to verify employee linkage
  const {
    data: profile,
    isLoading: isLoadingProfile,
    isError: isProfileError,
  } = useQuery({
    queryKey: ["profile", "me"],
    queryFn: () => getMyProfile(),
    retry: false,
  });

  // Query employee leave balances
  const {
    data: balancesData,
    isLoading: isLoadingBalances,
    isError: isBalancesError,
    error: balancesError,
    refetch: refetchBalances,
  } = useQuery({
    queryKey: ["leave", "balance", "me"],
    queryFn: () => getMyLeaveBalances(),
  });

  // Query leave policies
  const { data: policiesData = [] } = useQuery({
    queryKey: ["leave", "policies"],
    queryFn: () => getLeavePolicies(),
  });

  const balances = balancesData?.balances || (Array.isArray(balancesData) ? balancesData : []);

  // Determine if user has an active employee profile
  // Check if profile or user session has emp_id / employee_id
  const hasEmployeeProfile = Boolean(
    profile?.emp_id ||
    profile?.employee_id ||
    user?.emp_id ||
    user?.employee_id
  );

  const handleApplySuccess = (_createdRequest) => {
    setToast({
      message: "Leave request submitted",
      type: "success",
    });
    // Invalidate queries so balances and table refresh
    queryClient.invalidateQueries({ queryKey: ["leave"] });
    // Switch to My Requests tab
    setActiveTab("MY_REQUESTS");
    setIsModalOpen(false);
  };

  const handleCancelSuccess = () => {
    setToast({
      message: "Leave request cancelled",
      type: "success",
    });
    queryClient.invalidateQueries({ queryKey: ["leave"] });
  };

  return (
    <div className="leave-dashboard" data-testid="leave-dashboard-page">
      {/* Toast Notification */}
      {toast && (
        <div className="leave-toast-container" role="status" aria-live="polite">
          <div className={`leave-toast leave-toast-${toast.type}`}>
            <span>✓ {toast.message}</span>
            <button
              type="button"
              className="leave-toast-close"
              onClick={() => setToast(null)}
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Page Header */}
      <header className="leave-header">
        <div className="leave-header-left">
          <span className="leave-eyebrow">SELF SERVICE / LEAVE</span>
          <h1 className="leave-title">Leave Management</h1>
          <p className="leave-subtitle">
            View your yearly leave balance, apply for upcoming time off, and track your request history.
          </p>
        </div>

        <div className="leave-header-actions">
          {activeTab === "MY_REQUESTS" && (
            <button
              type="button"
              className="leave-btn leave-btn-primary"
              onClick={() => setActiveTab("APPLY")}
              data-testid="header-apply-button"
            >
              + Apply for Leave
            </button>
          )}
        </div>
      </header>

      {/* Employee Profile Warning Banner if account is not linked to an employee */}
      {!isLoadingProfile && !hasEmployeeProfile && (
        <div
          className="leave-alert-error"
          role="alert"
          style={{ background: "#fffbeb", borderColor: "#fde68a", color: "#92400e" }}
        >
          <span>
            ⚠️ No employee profile linked to this account. Only registered employees can submit leave requests.
            Please contact your HR administrator.
          </span>
        </div>
      )}

      {/* 1. Leave Balance Cards at the Top */}
      <LeaveBalanceCards
        balances={balances}
        isLoading={isLoadingBalances}
        isError={isBalancesError}
        error={balancesError}
        onRetry={refetchBalances}
      />

      {/* 2. Tabs Navigation */}
      <nav className="leave-tabs-bar" role="tablist" aria-label="Leave management views">
        <button
          type="button"
          role="tab"
          id="tab-apply"
          aria-selected={activeTab === "APPLY"}
          aria-controls="panel-apply"
          className={`leave-tab-btn ${activeTab === "APPLY" ? "leave-tab-btn-active" : ""}`}
          onClick={() => setActiveTab("APPLY")}
          data-testid="tab-apply-leave"
        >
          <span>Apply for Leave</span>
        </button>

        <button
          type="button"
          role="tab"
          id="tab-requests"
          aria-selected={activeTab === "MY_REQUESTS"}
          aria-controls="panel-requests"
          className={`leave-tab-btn ${activeTab === "MY_REQUESTS" ? "leave-tab-btn-active" : ""}`}
          onClick={() => setActiveTab("MY_REQUESTS")}
          data-testid="tab-my-requests"
        >
          <span>My Requests</span>
        </button>
      </nav>

      {/* 3. Tab Panels */}
      {activeTab === "APPLY" && (
        <section
          id="panel-apply"
          role="tabpanel"
          aria-labelledby="tab-apply"
          className="leave-tab-panel"
        >
          <ApplyLeaveModal
            isOpen={true}
            embedded={true}
            balances={balances}
            policies={policiesData}
            onSuccess={handleApplySuccess}
          />
        </section>
      )}

      {activeTab === "MY_REQUESTS" && (
        <section
          id="panel-requests"
          role="tabpanel"
          aria-labelledby="tab-requests"
          className="leave-tab-panel"
        >
          <MyLeaveRequestsTable
            onCancelSuccess={handleCancelSuccess}
            onRequestNewLeave={() => setActiveTab("APPLY")}
          />
        </section>
      )}

      {/* Optional Standalone Modal Dialog */}
      {isModalOpen && (
        <ApplyLeaveModal
          isOpen={isModalOpen}
          embedded={false}
          balances={balances}
          policies={policiesData}
          onClose={() => setIsModalOpen(false)}
          onSuccess={handleApplySuccess}
        />
      )}
    </div>
  );
}
