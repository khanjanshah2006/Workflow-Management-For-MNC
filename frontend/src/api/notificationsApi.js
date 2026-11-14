import { apiClient } from "./client";

export const notificationsApi = {
  /**
   * Fetch current user's chronological notifications (US-19).
   */
  getMyNotifications: async (params = {}) => {
    const query = new URLSearchParams(params).toString();
    const endpoint = `/api/v1/notifications/my${query ? `?${query}` : ""}`;
    return apiClient.get(endpoint);
  },

  /**
   * Fetch current user's unread notification count badge (US-19).
   */
  getUnreadCount: async () => {
    return apiClient.get("/api/v1/notifications/unread-count");
  },

  /**
   * Mark a single notification as read (US-19).
   */
  markAsRead: async (notificationId) => {
    return apiClient.put(`/api/v1/notifications/${notificationId}/read`);
  },

  /**
   * Mark all unread notifications of user as read (US-19).
   */
  markAllAsRead: async () => {
    return apiClient.put("/api/v1/notifications/read-all");
  },
};
