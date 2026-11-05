import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notificationsApi } from "../../api/notificationsApi";

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

function getNotificationIcon(type) {
  switch ((type || "").toUpperCase()) {
    case "PROJECT_ASSIGNED":
    case "PROJECT_ASSIGNMENT":
      return "💼";
    case "TASK_ASSIGNED":
    case "TASK":
      return "✓";
    case "DEADLINE_REMINDER":
    case "DEADLINE":
      return "⏰";
    case "LEAVE_APPROVAL":
    case "LEAVE_REJECTION":
      return "📋";
    case "ALERT":
      return "⚠️";
    default:
      return "🔔";
  }
}

export default function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false);
  const bellRef = useRef(null);
  const queryClient = useQueryClient();

  // 1. Fetch unread count (polls every 30 seconds for background updates)
  const { data: countData } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: notificationsApi.getUnreadCount,
    refetchInterval: 30000,
    retry: 1,
  });

  const unreadCount = countData?.unread_count ?? 0;

  // 2. Fetch recent notifications when dropdown is open
  const {
    data: notifications = [],
    isLoading: listLoading,
    isError,
    error,
    refetch: refetchNotifications,
  } = useQuery({
    queryKey: ["notifications", "my"],
    queryFn: () => notificationsApi.getMyNotifications({ limit: 20 }),
    enabled: isOpen,
    retry: 1,
  });

  // 3. Mark single notification as read mutation (US-19)
  const markReadMutation = useMutation({
    mutationFn: (id) => notificationsApi.markAsRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications", "unread-count"] });
      queryClient.invalidateQueries({ queryKey: ["notifications", "my"] });
    },
  });

  // 4. Mark all as read mutation (US-19)
  const markAllReadMutation = useMutation({
    mutationFn: notificationsApi.markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications", "unread-count"] });
      queryClient.invalidateQueries({ queryKey: ["notifications", "my"] });
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
    // Only call mark-as-read if unread to prevent redundant API calls / double decrementing
    if (!item.is_read) {
      markReadMutation.mutate(item.notification_id);
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
            ) : notifications.length === 0 ? (
              <div className="notification-empty-state">
                <div className="empty-symbol">🔕</div>
                <strong>All caught up!</strong>
                <p>You have no notifications at this time.</p>
              </div>
            ) : (
              notifications.map((item) => (
                <div
                  key={item.notification_id}
                  className={`notification-item ${!item.is_read ? "notification-unread" : "notification-read"}`}
                  onClick={() => handleNotificationClick(item)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      handleNotificationClick(item);
                    }
                  }}
                  title={item.is_read ? "Read notification" : "Click to mark as read"}
                >
                  <div className="notification-item-icon" aria-hidden="true">
                    {getNotificationIcon(item.type)}
                  </div>
                  <div className="notification-item-content">
                    <div className="notification-item-top">
                      <strong>{item.title}</strong>
                      {!item.is_read && <span className="unread-dot" aria-label="Unread" />}
                    </div>
                    <p>{item.message}</p>
                    <span className="notification-timestamp">
                      {formatTimestamp(item.created_at)}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="notification-panel-footer">
            <span>WorkSphere Live Notification Service · US-19</span>
          </div>
        </div>
      )}
    </div>
  );
}
