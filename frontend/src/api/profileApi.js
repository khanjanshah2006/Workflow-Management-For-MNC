import { apiClient } from "./client.js";

/**
 * WorkSphere Employee Profile API Client (US-03 / Issue #39)
 * Provides methods to retrieve and update the authenticated employee's profile.
 */

/**
 * Fetch the authenticated employee's organizational profile.
 * Endpoint: GET /api/v1/profile/me
 * @returns {Promise<Object>} ProfileResponse
 */
export async function getMyProfile() {
  return await apiClient.get("/api/v1/profile/me");
}

/**
 * Update the authenticated employee's self-service contact details.
 * Endpoint: PUT /api/v1/profile/me
 * @param {{ phone?: string, emergency_contact?: string, bio?: string }} payload
 * @returns {Promise<Object>} Updated ProfileResponse
 */
export async function updateMyProfile(payload) {
  return await apiClient.put("/api/v1/profile/me", payload);
}

export const profileApi = {
  getMyProfile,
  updateMyProfile,
};

export default profileApi;
