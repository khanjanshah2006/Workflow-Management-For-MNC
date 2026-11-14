/**
 * WorkSphere Core API Client
 * Handles baseURL, JWT token injection, headers, and standardized error extraction.
 */

const BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) ||
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  "http://localhost:8000";

export class ApiError extends Error {
  constructor(message, status = 0, data = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

let activeTokenGetter = null;

/**
 * Registers an optional external token provider (e.g. in-memory session adapter).
 * @param {(() => string|null)|null} getter
 */
export function setTokenGetter(getter) {
  activeTokenGetter = typeof getter === "function" ? getter : null;
}

export function getStoredToken() {
  if (activeTokenGetter) {
    try {
      const active = activeTokenGetter();
      if (active) return active;
    } catch {
      // Fallback to localStorage
    }
  }
  if (typeof localStorage === "undefined") return "";
  try {
    return localStorage.getItem("wms_access_token") || "";
  } catch {
    return "";
  }
}

export function setStoredToken(token) {
  if (typeof localStorage === "undefined") return;
  try {
    if (token) {
      localStorage.setItem("wms_access_token", token);
    } else {
      localStorage.removeItem("wms_access_token");
    }
  } catch {
    // Ignore storage quota / restricted environments
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
    credentials: "include",
    ...options,
    headers,
  };

  let response;
  try {
    response = await fetch(url, config);
  } catch (networkError) {
    throw new ApiError(
      `Network connection failed: Unable to reach backend at ${BASE_URL}. Ensure the backend server is running.`,
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
    let message =
      (data && (data.detail || data.message || data.error)) ||
      `Request failed with status ${response.status} (${response.statusText})`;

    if (Array.isArray(message)) {
      message = message
        .map((err) => {
          const loc = Array.isArray(err.loc)
            ? err.loc.filter((part) => part !== "body").join(".")
            : "";
          return loc ? `${loc}: ${err.msg}` : err.msg || JSON.stringify(err);
        })
        .join("; ");
    } else if (typeof message !== "string") {
      message = JSON.stringify(message);
    }

    throw new ApiError(message, response.status, data);
  }

  if (options.includeHeaders) {
    return {
      data,
      headers: response.headers,
      status: response.status,
    };
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
  request,
  BASE_URL,
};
