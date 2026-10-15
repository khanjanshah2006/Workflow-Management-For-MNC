import { useState, useRef, useEffect } from "react";

export default function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false);
  const bellRef = useRef(null);

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
        aria-label="Notifications"
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        title="Notifications"
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
        <span className="notification-badge-dot" aria-hidden="true" />
      </button>

      {isOpen && (
        <div
          className="notification-panel"
          role="dialog"
          aria-label="Notifications popover"
        >
          <div className="notification-panel-header">
            <span className="notification-panel-title">Notifications</span>
            <span className="notification-panel-badge">Placeholder</span>
          </div>

          <div className="notification-panel-body">
            <div className="notification-item">
              <div className="notification-item-icon" aria-hidden="true">
                ℹ
              </div>
              <div className="notification-item-content">
                <strong>WorkSphere Foundation</strong>
                <p>
                  Shared layout shell, route scaffolding, and navigation are active.
                </p>
              </div>
            </div>

            <div className="notification-item">
              <div className="notification-item-icon" aria-hidden="true">
                🔔
              </div>
              <div className="notification-item-content">
                <strong>Live Notification Service</strong>
                <p>
                  Real-time alerts will connect to backend notification services in a future epic.
                </p>
              </div>
            </div>
          </div>

          <div className="notification-panel-footer">
            <span>Foundation preview · No live connection</span>
          </div>
        </div>
      )}
    </div>
  );
}
