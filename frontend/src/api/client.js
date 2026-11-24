/**
 * WorkSphere Core API Client
 * Handles baseURL, JWT token injection, headers, silent refresh, and standardized error extraction.
 */

const BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  "http://localhost:8000";

export class ApiError extends Error {
  /**
   * @param {string} message
   * @param {number} [status]
   * @param {any} [data] Parsed response body
   * @param {Headers|null} [headers] Response headers (e.g. to read Retry-After)
   */
  constructor(message, status = 0, data = null, headers = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
    this.headers = headers;
  }
}

let activeTokenGetter = null;
let tokenRefreshHandler = null;
let sessionClearHandler = null;
let inMemoryToken = "";

/**
 * Registers an optional external token provider (e.g. in-memory session adapter).
 * @param {(() => string|null)|null} getter
 */
export function setTokenGetter(getter) {
  activeTokenGetter = typeof getter === "function" ? getter : null;
}

/**
 * Registers a handler invoked when silent refresh acquires a new access token.
 * @param {((newToken: string) => void)|null} handler
 */
export function setTokenRefreshHandler(handler) {
  tokenRefreshHandler = typeof handler === "function" ? handler : null;
}

/**
 * Registers a handler invoked when a session is invalidated / cleared.
 * @param {(() => void)|null} handler
 */
export function setSessionClearHandler(handler) {
  sessionClearHandler = typeof handler === "function" ? handler : null;
}

export function getStoredToken() {
  if (activeTokenGetter) {
    try {
      const active = activeTokenGetter();
      if (active) return active;
    } catch {
      // Fallback to storage/memory
    }
  }
  if (typeof localStorage === "undefined") return inMemoryToken;
  try {
    return localStorage.getItem("wms_access_token") || inMemoryToken;
  } catch {
    return inMemoryToken;
  }
}

export function setStoredToken(token) {
  inMemoryToken = token || "";
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

export function clearSession() {
  setStoredToken("");
  if (sessionClearHandler) {
    try {
      sessionClearHandler();
    } catch {
      // Ignore errors in clear handlers
    }
  }
}

let refreshPromise = null;

async function executeTokenRefresh() {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const refreshUrl = `${BASE_URL}/api/v1/auth/refresh`;
      const res = await fetch(refreshUrl, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });

      if (!res.ok) {
        let errData = null;
        try {
          errData = await res.json();
        } catch {
          // ignore
        }
        throw new ApiError(
          errData?.detail || "Session refresh failed",
          res.status,
          errData
        );
      }

      const data = await res.json();
      const newAccessToken = data?.access_token;
      if (!newAccessToken) {
        throw new ApiError("No access token returned from refresh", 401);
      }

      setStoredToken(newAccessToken);
      if (tokenRefreshHandler) {
        try {
          tokenRefreshHandler(newAccessToken);
        } catch {
          // ignore
        }
      }
      return newAccessToken;
    } catch (refreshErr) {
      clearSession();
      if (typeof window !== "undefined" && window.location) {
        window.location.href = "/login?expired=1";
      }
      throw refreshErr;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

async function request(endpoint, options = {}) {
  const url = endpoint.startsWith("http") ? endpoint : `${BASE_URL}${endpoint}`;

  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;

  const headers = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...options.headers,
  };

  // When body is FormData, ensure Content-Type is never manually set so fetch provides multipart boundary
  if (isFormData) {
    delete headers["Content-Type"];
  }

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

  // Handle 401 with silent refresh. Sign-in endpoints (including /auth/mfa/login) and
  // requests made with a caller-supplied token (skipRefresh) report their 401 as-is.
  const isAuthEndpoint =
    url.includes("/api/v1/auth/refresh") ||
    url.includes("/api/v1/auth/login") ||
    url.includes("/api/v1/auth/mfa/login");

  if (
    response.status === 401 &&
    !options._isRetry &&
    !options.skipRefresh &&
    !isAuthEndpoint &&
    getStoredToken()
  ) {
    try {
      const newToken = await executeTokenRefresh();
      const retryHeaders = {
        ...headers,
        Authorization: `Bearer ${newToken}`,
      };
      return await request(endpoint, {
        ...options,
        _isRetry: true,
        headers: retryHeaders,
      });
    } catch {
      // Refresh failed; clearSession and redirection already dispatched in executeTokenRefresh
    }
  }

  if (response.status === 204) {
    return null;
  }

  let data = null;
  const contentType = response.headers?.get ? response.headers.get("content-type") : null;
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

    throw new ApiError(message, response.status, data, response.headers || null);
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
  post: (endpoint, body, options = {}) => {
    const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
    return request(endpoint, {
      ...options,
      method: "POST",
      body: body !== undefined ? (isFormData ? body : JSON.stringify(body)) : undefined,
    });
  },
  put: (endpoint, body, options = {}) => {
    const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
    return request(endpoint, {
      ...options,
      method: "PUT",
      body: body !== undefined ? (isFormData ? body : JSON.stringify(body)) : undefined,
    });
  },
  patch: (endpoint, body, options = {}) => {
    const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
    return request(endpoint, {
      ...options,
      method: "PATCH",
      body: body !== undefined ? (isFormData ? body : JSON.stringify(body)) : undefined,
    });
  },
  postForm: (endpoint, formData, options = {}) =>
    request(endpoint, {
      ...options,
      method: "POST",
      body: formData,
    }),
  delete: (endpoint, options = {}) => request(endpoint, { ...options, method: "DELETE" }),
  request,
  BASE_URL,
};

export default apiClient;
