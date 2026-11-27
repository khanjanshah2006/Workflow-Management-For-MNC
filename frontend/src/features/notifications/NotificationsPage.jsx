import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notificationsApi } from "../../api/notificationsApi";
import { useAuth } from "../../context/AuthContext";
import {
  NOTIFICATION_CATEGORIES,
  NOTIFICATION_CATEGORY_LIST,
  getNotificationConfig,
  getNotificationRoute,
  parseServerDate,
} from "./notificationTypes";
import "./notifications.css";

// Backend caps page_size at 100. A category filter needs every notification,
// so it fetches pages of this size (up to CATEGORY_MAX_PAGES) and filters locally.
const CATEGORY_FETCH_SIZE = 100;
const CATEGORY_MAX_PAGES = 10;

async function fetchAllNotifications(unreadOnly) {
  const items = [];
  for (let p = 1; p <= CATEGORY_MAX_PAGES; p += 1) {
    const data = await notificationsApi.getMyNotifications({
      page: p,
      page_size: CATEGORY_FETCH_SIZE,
      unread_only: unreadOnly,
    });
    const batch = Array.isArray(data) ? data : data?.items || [];
    items.push(...batch);
    const total = Array.isArray(data) ? batch.length : data?.total ?? batch.length;
    if (batch.length < CATEGORY_FETCH_SIZE || items.length >= total) break;
  }
  return items;
}

function formatTimestamp(isoString) {
  if (!isoString) return "";
  try {
    const date = parseServerDate(isoString);
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
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
    });
  } catch {
    return isoString;
  }
}

export default function NotificationsPage() {
  const { role } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(NOTIFICATION_CATEGORIES.ALL);

  // 1. Fetch unread count badge
  const { data: countData } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: notificationsApi.getUnreadCount,
    retry: 1,
  });

  const unreadCount = countData?.count ?? countData?.unread_count ?? 0;

  const isCategoryFiltered = selectedCategory !== NOTIFICATION_CATEGORIES.ALL;

  // 2. Fetch notifications: one server page for "All", every page for a category
  const {
    data: notifData,
    isLoading,
    isError,
    error,
    refetch,
    isPlaceholderData,
  } = useQuery({
    queryKey: isCategoryFiltered
      ? ["notifications", "my", "all-pages", { unreadOnly }]
      : ["notifications", "my", { page, pageSize, unreadOnly }],
    queryFn: () =>
      isCategoryFiltered
        ? fetchAllNotifications(unreadOnly)
        : notificationsApi.getMyNotifications({
            page,
            page_size: pageSize,
            unread_only: unreadOnly,
          }),
    retry: 1,
  });

  // 3. Mark single notification as read
  const markReadMutation = useMutation({
    mutationFn: (id) => notificationsApi.markAsRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  // 4. Mark all notifications as read
  const markAllReadMutation = useMutation({
    mutationFn: notificationsApi.markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const rawItems = Array.isArray(notifData)
    ? notifData
    : notifData?.items || [];
  // Category filtering runs over every fetched notification, then paginates locally
  const categoryItems = isCategoryFiltered
    ? rawItems.filter(
        (item) => getNotificationConfig(item.type).category === selectedCategory
      )
    : rawItems;

  const totalItems = isCategoryFiltered
    ? categoryItems.length
    : notifData?.total ?? rawItems.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));

  const displayedItems = isCategoryFiltered
    ? categoryItems.slice((page - 1) * pageSize, page * pageSize)
    : rawItems;

  const handleRowClick = (item) => {
    const notifId = item.id || item.notification_id;
    if (!item.is_read && notifId) {
      markReadMutation.mutate(notifId);
    }
    const targetRoute = getNotificationRoute(item, role);
    if (targetRoute) {
      navigate(targetRoute);
    }
  };

  const handleSingleMarkRead = (e, item) => {
    e.stopPropagation();
    const notifId = item.id || item.notification_id;
    if (notifId) {
      markReadMutation.mutate(notifId);
    }
  };

  return (
    <div className="notifications-page">
      {/* Page Header */}
      <div className="notifications-page-header">
        <div className="notifications-header-left">
          <h1 className="notifications-page-title">
            Notifications
            {unreadCount > 0 && (
              <span className="notifications-unread-badge-pill">
                {unreadCount} unread
              </span>
            )}
          </h1>
          <p className="notifications-page-subtitle">
            Stay updated on task handoffs, approvals, schedule changes, and security events.
          </p>
        </div>

        <div className="notifications-header-actions">
          <button
            type="button"
            className="notifications-mark-all-btn"
            onClick={() => markAllReadMutation.mutate()}
            disabled={unreadCount === 0 || markAllReadMutation.isPending}
            title={unreadCount === 0 ? "No unread notifications" : "Mark all as read"}
          >
            {markAllReadMutation.isPending ? "Marking..." : "✓ Mark all as read"}
          </button>
        </div>
      </div>

      {/* Filter and Category Toolbar */}
      <div className="notifications-toolbar">
        <div className="notifications-category-tabs" role="tablist" aria-label="Notification Categories">
          {NOTIFICATION_CATEGORY_LIST.map((category) => {
            const isActive = selectedCategory === category;
            return (
              <button
                key={category}
                type="button"
                role="tab"
                aria-selected={isActive}
                className={`notifications-tab-btn ${isActive ? "active" : ""}`}
                onClick={() => {
                  setSelectedCategory(category);
                  setPage(1);
                }}
              >
                {category}
              </button>
            );
          })}
        </div>

        <label className="notifications-filter-toggle">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => {
              setUnreadOnly(e.target.checked);
              setPage(1);
            }}
          />
          <span>Unread only</span>
        </label>
      </div>

      {/* Main Content Area */}
      {isLoading ? (
        <div className="notifications-state-box">
          <div className="spinner-small" style={{ margin: "0 auto 12px" }} />
          <h3 className="notifications-state-title">Loading notifications...</h3>
          <p className="notifications-state-text">Fetching your notification stream.</p>
        </div>
      ) : isError ? (
        <div className="notifications-state-box">
          <div className="notifications-state-icon">⚠️</div>
          <h3 className="notifications-state-title">Failed to load notifications</h3>
          <p className="notifications-state-text">
            {error?.message || "An unexpected error occurred while loading your notifications."}
          </p>
          <button
            type="button"
            className="notifications-retry-btn"
            onClick={() => refetch()}
          >
            Retry
          </button>
        </div>
      ) : displayedItems.length === 0 ? (
        <div className="notifications-state-box">
          <div className="notifications-state-icon">🔕</div>
          <h3 className="notifications-state-title">No notifications found</h3>
          <p className="notifications-state-text">
            {unreadOnly
              ? "You don't have any unread notifications."
              : selectedCategory !== NOTIFICATION_CATEGORIES.ALL
              ? `No notifications found in the "${selectedCategory}" category.`
              : "You have no notifications yet."}
          </p>
          {(unreadOnly || selectedCategory !== NOTIFICATION_CATEGORIES.ALL) && (
            <button
              type="button"
              className="notifications-btn-subtle"
              onClick={() => {
                setUnreadOnly(false);
                setSelectedCategory(NOTIFICATION_CATEGORIES.ALL);
                setPage(1);
              }}
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="notifications-feed" role="feed" aria-label="Notifications list">
            {displayedItems.map((item) => {
              const config = getNotificationConfig(item.type);
              const targetRoute = getNotificationRoute(item, role);
              const isClickable = Boolean(targetRoute);
              const notifId = item.id || item.notification_id;

              return (
                <article
                  key={notifId}
                  className={`notifications-card ${!item.is_read ? "unread" : "read"} ${
                    isClickable ? "clickable" : ""
                  }`}
                  onClick={() => handleRowClick(item)}
                  role={isClickable ? "button" : "article"}
                  tabIndex={isClickable ? 0 : undefined}
                  onKeyDown={(e) => {
                    if (isClickable && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      handleRowClick(item);
                    }
                  }}
                  title={
                    isClickable
                      ? item.is_read
                        ? "Click to open target"
                        : "Click to mark read and open"
                      : undefined
                  }
                >
                  <div className="notifications-card-icon" aria-hidden="true">
                    {config.icon}
                  </div>

                  <div className="notifications-card-main">
                    <div className="notifications-card-meta">
                      <span className="notifications-card-badge">{config.label}</span>
                      <span className="notifications-card-time">
                        {formatTimestamp(item.created_at)}
                      </span>
                    </div>

                    <h2 className="notifications-card-title">{item.title}</h2>
                    <p className="notifications-card-message">{item.message}</p>
                  </div>

                  <div className="notifications-card-controls">
                    {!item.is_read && (
                      <button
                        type="button"
                        className="notifications-btn-subtle"
                        onClick={(e) => handleSingleMarkRead(e, item)}
                        title="Mark as read"
                        disabled={markReadMutation.isPending}
                      >
                        Mark read
                      </button>
                    )}

                    {targetRoute && (
                      <span className="notifications-btn-open" aria-hidden="true">
                        Open →
                      </span>
                    )}
                  </div>
                </article>
              );
            })}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="notifications-pagination-bar">
              <span className="notifications-pagination-info">
                Page {page} of {totalPages} ({totalItems} total)
              </span>

              <div className="notifications-pagination-buttons">
                <button
                  type="button"
                  className="notifications-page-btn"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                >
                  ← Previous
                </button>
                <button
                  type="button"
                  className="notifications-page-btn"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages || isPlaceholderData}
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
