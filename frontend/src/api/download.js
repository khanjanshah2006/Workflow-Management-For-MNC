/**
 * Authenticated File Download Helper
 *
 * Facilitates secure file downloads from protected backend endpoints requiring Bearer tokens.
 * A standard <a href> tag cannot attach authorization headers; this helper requests the file via fetch,
 * reads the response as a Blob, extracts Content-Disposition filenames, and triggers browser downloads.
 */

import { getStoredToken, ApiError, apiClient } from "./client.js";

/**
 * Sanitizes a raw filename string to prevent path traversal and remove illegal characters.
 * @param {string} rawName
 * @returns {string|null}
 */
export function sanitizeFilename(rawName) {
  if (!rawName || typeof rawName !== "string") {
    return null;
  }

  // Strip leading path separators / directory traversal (Unix and Windows)
  let clean = rawName.trim().replace(/^.*[/\\]/, "");

  // Remove ASCII control characters (0x00-0x1F, 0x7F DEL) and invalid filesystem characters
  // eslint-disable-next-line no-control-regex
  clean = clean.replace(/[\x00-\x1f\x7f/\\?%*:|"<>]/g, "");

  // Strip leading dots to prevent hidden files or traversal remnants
  clean = clean.replace(/^\.+/, "").trim();

  return clean.length > 0 ? clean : null;
}

/**
 * Parses Content-Disposition header to extract the recommended filename.
 *
 * Supports:
 * - Quoted filenames: filename="report.pdf"
 * - Unquoted filenames: filename=report.pdf
 * - UTF-8 extended filenames: filename*=UTF-8''report%20Q4.csv (RFC 5987 / RFC 6266)
 * - Priority: Prefers valid UTF-8 extended filename when present
 * - Graceful fallback on malformed URI encodings
 *
 * @param {string|null|undefined} header Content-Disposition header string
 * @returns {string|null} Sanitized filename or null if unparseable
 */
export function parseContentDisposition(header) {
  if (!header || typeof header !== "string") {
    return null;
  }

  let extendedName = null;
  let standardName = null;

  // 1. Check for RFC 5987 / 6266 extended UTF-8 filename (filename*=UTF-8''...)
  const extMatch = header.match(/filename\*=(?:[^';\s]+)'([^';\s]*)'([^;\s]+)/i);
  if (extMatch && extMatch[2]) {
    try {
      const decoded = decodeURIComponent(extMatch[2].trim());
      extendedName = sanitizeFilename(decoded);
    } catch {
      // Malformed encoding in extended parameter; fall back to standard filename
      extendedName = null;
    }
  }

  // 2. Check for quoted standard filename: filename="..."
  const quotedMatch = header.match(/filename="([^"]+)"/i);
  if (quotedMatch && quotedMatch[1]) {
    standardName = sanitizeFilename(quotedMatch[1]);
  } else {
    // 3. Check for unquoted standard filename: filename=...
    const unquotedMatch = header.match(/(?:^|[;\s])filename=([^;\s]+)/i);
    if (unquotedMatch && unquotedMatch[1]) {
      const trimmed = unquotedMatch[1].replace(/^["']|["']$/g, "").trim();
      standardName = sanitizeFilename(trimmed);
    }
  }

  // Prefer valid UTF-8 extended filename when present
  if (extendedName) {
    return extendedName;
  }

  if (standardName) {
    return standardName;
  }

  return null;
}

/**
 * Initiates an authenticated GET request to download a file from a protected endpoint.
 *
 * @param {string} endpoint API endpoint path (e.g. "/api/v1/projects/1/report") or full URL
 * @param {string} fallbackName Fallback filename if Content-Disposition is absent
 * @returns {Promise<{ blob: Blob, filename: string }>} Resolves with the blob and resolved filename
 */
export async function downloadAuthenticatedFile(endpoint, fallbackName = "download") {
  const token = getStoredToken();
  const baseUrl = apiClient.BASE_URL || "http://localhost:8000";
  const url = endpoint.startsWith("http") ? endpoint : `${baseUrl}${endpoint}`;

  const headers = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(url, {
      method: "GET",
      credentials: "include",
      headers,
    });
  } catch (networkError) {
    throw new ApiError(
      `Network connection failed: Unable to reach backend at ${baseUrl}. Ensure the backend server is running.`,
      0,
      { originalError: networkError.message }
    );
  }

  if (!response.ok) {
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

    let message =
      (data && (data.detail || data.message || data.error)) ||
      `Download failed with status ${response.status} (${response.statusText})`;

    if (Array.isArray(message)) {
      message = message
        .map((err) => {
          const loc = Array.isArray(err?.loc)
            ? err.loc.filter((p) => p !== "body").join(".")
            : "";
          return loc ? `${loc}: ${err.msg}` : err?.msg || JSON.stringify(err);
        })
        .join("; ");
    } else if (typeof message !== "string") {
      message = JSON.stringify(message);
    }

    throw new ApiError(message, response.status, data);
  }

  const blob = await response.blob();
  const dispositionHeader = response.headers.get("content-disposition");
  const extractedName = parseContentDisposition(dispositionHeader);
  const finalFilename =
    extractedName || sanitizeFilename(fallbackName) || "download";

  // Trigger browser download anchor if DOM APIs exist
  if (typeof window !== "undefined" && typeof document !== "undefined") {
    const objectUrl = window.URL.createObjectURL(blob);
    try {
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = finalFilename;
      anchor.style.display = "none";
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
    } finally {
      window.URL.revokeObjectURL(objectUrl);
    }
  }

  return { blob, filename: finalFilename };
}

export default downloadAuthenticatedFile;
