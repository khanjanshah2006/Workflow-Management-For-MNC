import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { notificationsApi } from "../../api/notificationsApi";

export default function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false);
  const bellRef = useRef(null);

  // 1. Fetch unread count from backend (US-19)
  const { data: countData } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: notificationsApi.getUnreadCount,
    refetchInterval: 30000,
    retry: 1,
  });

  const unreadCount = countData?.unread_count ?? 0;

  // 2. Fetch notifications when dropdown is opened (US-19)
  const {
    data: notifications = [],
    isLoading: listLoading,
  } = useQuery({
    queryKey: ["notifications", "my"],
    queryFn: () => notificationsApi.getMyNotifications({ limit: 20 }),
    enabled: isOpen,
    retry: 1,
  });

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
            <span className="notification-panel-title">Notifications</span>
            {unreadCount > 0 ? (
              <span className="notification-panel-badge">{unreadCount} new</span>
            ) : (
              <span className="notification-panel-badge">Caught up</span>
            )}
          </div>

          <div className="notification-panel-body">
            {listLoading ? (
              <div className="notification-loading-state">
                <span>Loading notifications...</span>
              </div>
            ) : notifications.length === 0 ? (
              <div className="notification-empty-state">
                <p>No notifications available.</p>
              </div>
            ) : (
              notifications.map((item) => (
                <div key={item.notification_id} className="notification-item">
                  <div className="notification-item-icon" aria-hidden="true">
                    🔔
                  </div>
                  <div className="notification-item-content">
                    <strong>{item.title}</strong>
                    <p>{item.message}</p>
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
