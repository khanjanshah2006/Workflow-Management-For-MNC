import { useState, useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notificationsApi } from "../../api/notificationsApi";
import { useAuth } from "../../context/AuthContext";
import { ROUTES } from "../../routes";
import {
  getNotificationConfig,
  getNotificationRoute,
} from "../../features/notifications/notificationTypes";

function formatTimestamp(isoString) {
  if (!isoString) return "";
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return isoString;
  }
}

export default function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false);
  const bellRef = useRef(null);
  const queryClient = useQueryClient();
  const { role } = useAuth();
  const navigate = useNavigate();

  // Tab visibility state to stop polling while backgrounded
  const [isTabVisible, setIsTabVisible] = useState(() =>
    typeof document !== "undefined" ? document.visibilityState === "visible" : true
  );

  useEffect(() => {
    function handleVisibility() {
      const visible = document.visibilityState === "visible";
      setIsTabVisible(visible);
      if (visible) {
        // Immediately refresh unread count on returning to foreground
        queryClient.invalidateQueries({ queryKey: ["notifications", "unread-count"] });
      }
    }

    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [queryClient]);

  // 1. Fetch unread count (polls every 30 seconds, only while tab is visible)
  const { data: countData } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: notificationsApi.getUnreadCount,
    refetchInterval: isTabVisible ? 30000 : false,
    refetchIntervalInBackground: false,
    retry: 1,
  });

  const unreadCount = countData?.count ?? countData?.unread_count ?? 0;

  // 2. Fetch latest notifications when dropdown is open
  const {
    data: notifData = [],
    isLoading: listLoading,
    isError,
    error,
    refetch: refetchNotifications,
  } = useQuery({
    queryKey: ["notifications", "recent-dropdown"],
    queryFn: () => notificationsApi.getMyNotifications({ page: 1, page_size: 10 }),
    enabled: isOpen,
    retry: 1,
  });

  const notificationsList = Array.isArray(notifData)
    ? notifData
    : notifData?.items || [];
  const latestTen = notificationsList.slice(0, 10);

  // 3. Mark single notification as read mutation
  const markReadMutation = useMutation({
    mutationFn: (id) => notificationsApi.markAsRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  // 4. Mark all as read mutation
  const markAllReadMutation = useMutation({
    mutationFn: notificationsApi.markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  // Handle click outside & Escape key
  useEffect(() => {
    if (!isOpen) return;

    function handlePointerDown(event) {
      if (bellRef.current && !bellRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const handleNotificationClick = (item) => {
    const notifId = item.id || item.notification_id;
    if (!item.is_read && notifId) {
      markReadMutation.mutate(notifId);
    }
    setIsOpen(false);

    const targetRoute = getNotificationRoute(item, role);
    if (targetRoute) {
      navigate(targetRoute);
    }
  };

  return (
    <div className="notification-wrapper" ref={bellRef}>
      <button
        type="button"
        className="notification-bell-button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        title={unreadCount > 0 ? `${unreadCount} unread notifications` : "Notifications"}
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>

        {unreadCount > 0 && (
          <span className="notification-badge-count" aria-hidden="true">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          className="notification-panel"
          role="dialog"
          aria-label="Notifications popover"
        >
          <div className="notification-panel-header">
            <div className="notification-panel-header-left">
              <span className="notification-panel-title">Notifications</span>
              {unreadCount > 0 && (
                <span className="notification-panel-badge">{unreadCount} new</span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                type="button"
                className="notification-action-link"
                onClick={() => markAllReadMutation.mutate()}
                disabled={markAllReadMutation.isPending}
              >
                {markAllReadMutation.isPending ? "Clearing..." : "Mark all read"}
              </button>
            )}
          </div>

          <div className="notification-panel-body">
            {listLoading ? (
              <div className="notification-loading-state">
                <div className="spinner-small" />
                <span>Loading notifications...</span>
              </div>
            ) : isError ? (
              <div className="notification-error-state">
                <span className="error-icon">⚠️</span>
                <p>{error?.message || "Failed to load notifications"}</p>
                <button
                  type="button"
                  className="retry-button-small"
                  onClick={() => refetchNotifications()}
                >
                  Retry
                </button>
              </div>
            ) : latestTen.length === 0 ? (
              <div className="notification-empty-state">
                <div className="empty-symbol">🔕</div>
                <strong>All caught up!</strong>
                <p>You have no notifications at this time.</p>
              </div>
            ) : (
              latestTen.map((item) => {
                const config = getNotificationConfig(item.type);
                const hasTarget = Boolean(getNotificationRoute(item, role));
                const notifId = item.id || item.notification_id;

                return (
                  <div
                    key={notifId}
                    className={`notification-item ${!item.is_read ? "notification-unread" : "notification-read"} ${hasTarget ? "notification-clickable" : ""}`}
                    onClick={() => handleNotificationClick(item)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleNotificationClick(item);
                      }
                    }}
                    title={
                      hasTarget
                        ? (item.is_read ? "Click to open" : "Click to mark read and open")
                        : (item.is_read ? "Read notification" : "Click to mark read")
                    }
                  >
                    <div className="notification-item-icon" aria-hidden="true">
                      {config.icon}
                    </div>
                    <div className="notification-item-content">
                      <div className="notification-item-top">
                        <span className="notification-type-badge">{config.label}</span>
                        {!item.is_read && <span className="unread-dot" aria-label="Unread" />}
                      </div>
                      <div className="notification-item-title">{item.title}</div>
                      <p>{item.message}</p>
                      <span className="notification-timestamp">
                        {formatTimestamp(item.created_at)}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="notification-panel-footer">
            <Link
              to={ROUTES.NOTIFICATIONS}
              className="notification-view-all-link"
              onClick={() => setIsOpen(false)}
            >
              View all notifications →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
