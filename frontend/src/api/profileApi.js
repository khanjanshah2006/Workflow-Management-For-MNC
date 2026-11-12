import { apiClient } from "./client";
import mockProfile from "../features/profile/mockData.json";

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
  try {
    return await apiClient.get("/api/v1/profile/me");
  } catch (err) {
    // Graceful fallback to mock data if backend server is unreachable in development (status 0 / network failure)
    if (err?.status === 0 && import.meta.env?.DEV) {
      console.warn("Backend /api/v1/profile/me unreachable; serving mock profile in DEV mode:", err.message);
      return mockProfile;
    }
    throw err;
  }
}

/**
 * Update the authenticated employee's self-service contact details.
 * Endpoint: PUT /api/v1/profile/me
 * @param {{ phone?: string, emergency_contact?: string, bio?: string }} payload
 * @returns {Promise<Object>} Updated ProfileResponse
 */
export async function updateMyProfile(payload) {
  try {
    return await apiClient.put("/api/v1/profile/me", payload);
  } catch (err) {
    // Graceful fallback in development when backend is unreachable
    if (err?.status === 0 && import.meta.env?.DEV) {
      console.warn("Backend PUT /api/v1/profile/me unreachable; returning updated mock in DEV mode:", payload);
      return {
        ...mockProfile,
        ...payload,
      };
    }
    throw err;
  }
}

export const profileApi = {
  getMyProfile,
  updateMyProfile,
};

export default profileApi;
