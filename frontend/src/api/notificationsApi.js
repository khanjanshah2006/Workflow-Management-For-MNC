import { apiClient } from "./client";

export const notificationsApi = {
  /**
   * Fetch current user's chronological notifications (US-19).
   * @param {Object} [params]
   * @param {number} [params.page=1]
   * @param {number} [params.page_size=20]
   * @param {boolean} [params.unread_only=false]
   */
  getMyNotifications: async (params = {}) => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        searchParams.append(key, value);
      }
    });
    const query = searchParams.toString();
    const endpoint = `/api/v1/notifications/my${query ? `?${query}` : ""}`;
    return apiClient.get(endpoint);
  },

  /**
   * Fetch current user's unread notification count badge (US-19).
   * @returns {Promise<{ count: number }>}
   */
  getUnreadCount: async () => {
    return apiClient.get("/api/v1/notifications/unread-count");
  },

  /**
   * Mark a single notification as read (US-19).
   * @param {string} notificationId
   */
  markAsRead: async (notificationId) => {
    return apiClient.put(`/api/v1/notifications/${notificationId}/read`);
  },

  /**
   * Mark all unread notifications of user as read (US-19).
   * @returns {Promise<{ updated: number }>}
   */
  markAllAsRead: async () => {
    return apiClient.put("/api/v1/notifications/read-all");
  },
};

export default notificationsApi;
