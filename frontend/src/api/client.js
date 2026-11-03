/**
 * Standardized HTTP API Client for WorkSphere.
 * Manages baseURL, Authorization headers, and API error formatting.
 */

const BASE_URL = import.meta.env.VITE_API_URL || "";

class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export function getStoredToken() {
  return localStorage.getItem("wms_access_token") || "";
}

export function setStoredToken(token) {
  if (token) {
    localStorage.setItem("wms_access_token", token);
  } else {
    localStorage.removeItem("wms_access_token");
  }
}

async function request(endpoint, options = {}) {
  const url = endpoint.startsWith("http") ? endpoint : `${BASE_URL}${endpoint}`;

  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const token = getStoredToken();
  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const config = {
    ...options,
    headers,
  };

  let response;
  try {
    response = await fetch(url, config);
  } catch (networkError) {
    throw new ApiError(
      `Network connection failed: Unable to connect to backend at ${BASE_URL || window.location.origin}. Verify server is running.`,
      0,
      { originalError: networkError.message }
    );
  }

  if (response.status === 204) {
    return null;
  }

  let data = null;
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    try {
      data = await response.text();
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const message =
      (data && (data.detail || data.message || data.error)) ||
      `Request failed with status ${response.status} (${response.statusText})`;
    throw new ApiError(message, response.status, data);
  }

  return data;
}

export const apiClient = {
  get: (endpoint, options = {}) => request(endpoint, { ...options, method: "GET" }),
  post: (endpoint, body, options = {}) =>
    request(endpoint, {
      ...options,
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  put: (endpoint, body, options = {}) =>
    request(endpoint, {
      ...options,
      method: "PUT",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  delete: (endpoint, options = {}) => request(endpoint, { ...options, method: "DELETE" }),
  BASE_URL,
};
