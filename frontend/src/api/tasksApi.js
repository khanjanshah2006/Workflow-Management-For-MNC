import { apiClient } from "./client.js";

/**
 * Tasks API Service (WorkSphere S3 / US-10 & US-32)
 *
 * Provides typed methods interacting with the backend tasks endpoints:
 * - GET /api/v1/tasks/my-tasks (List tasks assigned to authenticated employee)
 * - GET /api/v1/tasks/{id}     (Retrieve full task details with relations)
 * - PUT /api/v1/tasks/{id}/progress (Update task progress 0-99% and blocker reason)
 */

/**
 * Maps task status to the corresponding progress bar fill CSS class name.
 * Ensures consistent styling for TODO, IN_PROGRESS, BLOCKED, IN_REVIEW, and DONE
 * across Kanban cards, Table view, and Detail Drawer.
 *
 * @param {string} status
 * @returns {string} CSS class name
 */
export function getProgressFillClass(status) {
  const s = (status || "").toUpperCase();
  switch (s) {
    case "TODO":
      return "progress-fill-todo";
    case "IN_PROGRESS":
      return "progress-fill-inprogress";
    case "BLOCKED":
      return "progress-fill-blocked";
    case "IN_REVIEW":
      return "progress-fill-inreview";
    case "DONE":
      return "progress-fill-done";
    case "REJECTED":
      return "progress-fill-rejected";
    default:
      return "progress-fill-inprogress";
  }
}

/**
 * Checks if a task matches the search query against supported fields:
 * - Task Title (case-insensitive substring)
 * - Task ID (exact or partial numeric match)
 * - Project ID (exact or partial numeric match)
 *
 * NOTE: blocker_reason is intentionally NOT searched because GET /api/v1/tasks/my-tasks
 * returns TaskSummaryResponse which does not include blocker_reason.
 *
 * @param {Object} task
 * @param {string} query
 * @returns {boolean}
 */
export function matchesTaskSearch(task, query) {
  if (!query || !query.trim()) return true;
  if (!task) return false;
  const q = query.trim().toLowerCase();
  const titleMatch = Boolean(task.title && task.title.toLowerCase().includes(q));
  const taskIdMatch =
    task.task_id !== undefined &&
    task.task_id !== null &&
    String(task.task_id).includes(q);
  const projectIdMatch =
    task.project_id !== undefined &&
    task.project_id !== null &&
    String(task.project_id).includes(q);

  return titleMatch || taskIdMatch || projectIdMatch;
}

/**
 * Filters a list of tasks by status and search query (supported fields only).
 *
 * @param {Array<Object>} tasks
 * @param {Object} [filters]
 * @param {string} [filters.statusFilter="ALL"]
 * @param {string} [filters.searchQuery=""]
 * @returns {Array<Object>}
 */
export function filterTasks(
  tasks,
  { statusFilter = "ALL", searchQuery = "" } = {}
) {
  if (!Array.isArray(tasks)) return [];
  let list = tasks;

  if (statusFilter && statusFilter !== "ALL") {
    const s = statusFilter.toUpperCase();
    list = list.filter((task) => (task?.status || "").toUpperCase() === s);
  }

  if (searchQuery && searchQuery.trim()) {
    list = list.filter((task) => matchesTaskSearch(task, searchQuery));
  }

  return list;
}

/**
 * Computes status counts across the complete dataset.
 *
 * @param {Array<Object>} tasks
 * @param {number} [total]
 * @returns {{ TOTAL: number, TODO: number, IN_PROGRESS: number, BLOCKED: number, IN_REVIEW: number, DONE: number, REJECTED: number }}
 */
export function computeTaskMetrics(tasks, total) {
  const list = Array.isArray(tasks) ? tasks : [];
  const counts = {
    TOTAL: typeof total === "number" ? total : list.length,
    TODO: 0,
    IN_PROGRESS: 0,
    BLOCKED: 0,
    IN_REVIEW: 0,
    DONE: 0,
    REJECTED: 0,
  };

  list.forEach((task) => {
    const s = (task?.status || "").toUpperCase();
    if (counts[s] !== undefined) {
      counts[s] += 1;
    }
  });

  return counts;
}

/**
 * Groups tasks for the Kanban board into columns while isolating REJECTED tasks.
 *
 * CRITICAL INVARIANT:
 * Under NO circumstances are REJECTED tasks mapped or classified into TODO.
 * They are placed into a dedicated REJECTED collection rendered in a separate
 * "Needs Revision" section.
 *
 * @param {Array<Object>} tasks
 * @returns {{ TODO: Array<Object>, IN_PROGRESS: Array<Object>, BLOCKED: Array<Object>, IN_REVIEW: Array<Object>, DONE: Array<Object>, REJECTED: Array<Object> }}
 */
export function groupTasksForKanban(tasks) {
  const map = {
    TODO: [],
    IN_PROGRESS: [],
    BLOCKED: [],
    IN_REVIEW: [],
    DONE: [],
    REJECTED: [],
  };

  const list = Array.isArray(tasks) ? tasks : [];
  list.forEach((task) => {
    const s = (task?.status || "").toUpperCase();
    if (s === "REJECTED") {
      map.REJECTED.push(task);
    } else if (map[s]) {
      map[s].push(task);
    } else {
      // Fallback for missing/empty/other unmapped status (never REJECTED)
      map.TODO.push(task);
    }
  });

  return map;
}

/**
 * Calculates pagination details given total items, current page, and page size.
 *
 * @param {number} totalItems
 * @param {number} [currentPage=1]
 * @param {number} [pageSize=20]
 * @returns {{ totalItems: number, totalPages: number, page: number, startIndex: number, endIndex: number }}
 */
export function calculatePagination(
  totalItems,
  currentPage = 1,
  pageSize = 20
) {
  const safeTotal = Math.max(0, Number(totalItems) || 0);
  const safePageSize = Math.max(1, Number(pageSize) || 20);
  const totalPages = Math.max(1, Math.ceil(safeTotal / safePageSize));
  const safePage = Math.min(Math.max(1, Number(currentPage) || 1), totalPages);
  const startIndex = safeTotal === 0 ? 0 : (safePage - 1) * safePageSize;
  const endIndex =
    safeTotal === 0 ? 0 : Math.min(safeTotal, safePage * safePageSize);

  return {
    totalItems: safeTotal,
    totalPages,
    page: safePage,
    startIndex,
    endIndex,
  };
}

/**
 * Slices an array of items for the given page.
 *
 * @param {Array} items
 * @param {number} page
 * @param {number} pageSize
 * @returns {Array}
 */
export function getPaginatedItems(items, page = 1, pageSize = 20) {
  if (!Array.isArray(items)) return [];
  const { startIndex, endIndex } = calculatePagination(
    items.length,
    page,
    pageSize
  );
  if (items.length === 0) return [];
  return items.slice(startIndex, endIndex);
}

/**
 * Fetch paginated tasks assigned to the current employee (US-32 / US-10).
 *
 * @param {Object} [params]
 * @param {string} [params.status] Optional TaskStatus (TODO, IN_PROGRESS, BLOCKED, IN_REVIEW, DONE)
 * @param {string} [params.priority] Optional PriorityLevel (LOW, MEDIUM, HIGH, CRITICAL)
 * @param {number} [params.page=1] Page number (1-indexed)
 * @param {number} [params.limit=20] Number of tasks per page (1-100)
 * @returns {Promise<{ items: Array<Object>, total: number, page: number, limit: number }>}
 */
export async function getMyTasks({
  status,
  priority,
  page = 1,
  limit = 20,
} = {}) {
  const queryParams = new URLSearchParams();

  if (status && status !== "ALL") {
    queryParams.append("status", status);
  }
  if (priority && priority !== "ALL") {
    queryParams.append("priority", priority);
  }
  if (page) {
    queryParams.append("page", String(page));
  }
  if (limit) {
    queryParams.append("limit", String(limit));
  }

  const queryString = queryParams.toString();
  const endpoint = `/api/v1/tasks/my-tasks${queryString ? `?${queryString}` : ""}`;

  return apiClient.get(endpoint);
}

/**
 * Fetches all tasks assigned to the current employee across all pages (US-10 / US-32).
 * Used for accurate cross-status summary metrics and comprehensive title search.
 * Fetches up to 100 tasks per batch and resolves any remaining pages concurrently.
 *
 * @param {Object} [params]
 * @param {string} [params.priority] Optional PriorityLevel filter
 * @param {number} [params.batchSize=100] Page size per batch fetch
 * @returns {Promise<{ items: Array<Object>, total: number }>}
 */
export async function fetchAllMyTasks({ priority, batchSize = 100 } = {}) {
  const firstBatch = await getMyTasks({
    priority,
    page: 1,
    limit: batchSize,
  });

  const items = Array.isArray(firstBatch?.items) ? [...firstBatch.items] : [];
  const total =
    typeof firstBatch?.total === "number" ? firstBatch.total : items.length;

  // If total tasks exceed first page (limit=batchSize), fetch remaining pages concurrently
  if (total > items.length) {
    const totalPages = Math.ceil(total / batchSize);
    const pagePromises = [];
    for (let p = 2; p <= totalPages; p++) {
      pagePromises.push(getMyTasks({ priority, page: p, limit: batchSize }));
    }
    const subsequentBatches = await Promise.all(pagePromises);
    for (const batch of subsequentBatches) {
      if (Array.isArray(batch?.items)) {
        items.push(...batch.items);
      }
    }
  }

  return { items, total };
}

/**
 * Retrieve complete task details by ID (US-32).
 *
 * @param {number|string} taskId
 * @returns {Promise<Object>} TaskDetailResponse
 */
export async function getTaskDetail(taskId) {
  if (!taskId) {
    throw new Error("Task ID is required to fetch task details.");
  }
  return apiClient.get(`/api/v1/tasks/${taskId}`);
}

/**
 * Update task progress and blocker status (US-10).
 *
 * Permitted update statuses: 'IN_PROGRESS' | 'BLOCKED'
 * Progress must be an integer between 0 and 99.
 * When status is 'BLOCKED', blocker_reason must be >= 5 non-whitespace chars.
 * When status is 'IN_PROGRESS', blocker_reason is cleared (null).
 *
 * @param {number|string} taskId
 * @param {Object} payload
 * @param {'IN_PROGRESS'|'BLOCKED'} payload.status
 * @param {number} payload.progress_pct (0 to 99)
 * @param {string} [payload.blocker_reason] Required if status is BLOCKED
 * @returns {Promise<Object>} TaskProgressResponse
 */
export async function updateTaskProgress(
  taskId,
  { status, progress_pct, blocker_reason }
) {
  if (!taskId) {
    throw new Error("Task ID is required to update progress.");
  }

  const normalizedStatus = (status || "").toUpperCase();
  if (normalizedStatus !== "IN_PROGRESS" && normalizedStatus !== "BLOCKED") {
    throw new Error(
      `Invalid status "${status}". Allowed update statuses are IN_PROGRESS and BLOCKED.`
    );
  }

  const numericProgress = Number(progress_pct);
  if (
    isNaN(numericProgress) ||
    !Number.isInteger(numericProgress) ||
    numericProgress < 0 ||
    numericProgress > 99
  ) {
    throw new Error(
      "Progress percentage must be an integer between 0 and 99. 100% requires submitting for review."
    );
  }

  const body = {
    status: normalizedStatus,
    progress_pct: numericProgress,
  };

  if (normalizedStatus === "BLOCKED") {
    const trimmedReason = (blocker_reason || "").trim();
    if (trimmedReason.length < 5) {
      throw new Error(
        "A blocker explanation of at least 5 characters is required when task is BLOCKED."
      );
    }
    body.blocker_reason = trimmedReason;
  } else {
    // When returning to IN_PROGRESS, send null so backend clears the blocker
    body.blocker_reason = null;
  }

  return apiClient.put(`/api/v1/tasks/${taskId}/progress`, body);
}

/**
 * Permitted file extensions for task deliverable attachments (US-11).
 */
export const ALLOWED_FILE_EXTENSIONS = [
  ".pdf",
  ".zip",
  ".tar.gz",
  ".png",
  ".jpg",
  ".jpeg",
  ".docx",
];

/**
 * Maximum deliverable attachment file size in bytes (25MB).
 */
export const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024; // 26,214,400 bytes

/**
 * Validates a file's format and size against WorkSphere deliverable standards.
 * Allowed types: .pdf, .zip, .tar.gz, .png, .jpg, .jpeg, .docx
 * Max size: 25 MB
 *
 * @param {File|{ name: string, size: number }|null} file
 * @returns {{ valid: boolean, error?: string }}
 */
export function validateDeliverableFile(file) {
  if (!file) return { valid: true };

  const fileName = (file.name || "").toLowerCase();
  const isAllowedExt =
    fileName.endsWith(".tar.gz") ||
    ALLOWED_FILE_EXTENSIONS.some((ext) => fileName.endsWith(ext));

  if (!isAllowedExt) {
    return {
      valid: false,
      error:
        "File type not allowed. Permitted formats: PDF, ZIP, TAR.GZ, PNG, JPG, JPEG, DOCX.",
    };
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    return {
      valid: false,
      error: `File size exceeds the 25MB limit (current size: ${sizeMb} MB).`,
    };
  }

  return { valid: true };
}

/**
 * Submit task deliverable for review (US-11).
 *
 * Dispatches multipart/form-data with remarks and optional file attachment.
 * Transitions task status from IN_PROGRESS to IN_REVIEW and alerts Team Lead.
 *
 * @param {number|string} taskId
 * @param {Object} payload
 * @param {string} payload.remarks Mandatory remarks describing deliverables
 * @param {File} [payload.file] Optional attached file (max 25MB)
 * @returns {Promise<Object>} TaskSubmissionResponse
 */
export async function submitTask(taskId, { remarks, file } = {}) {
  if (!taskId) {
    throw new Error("Task ID is required for submission.");
  }

  const trimmedRemarks = (remarks || "").trim();
  if (!trimmedRemarks) {
    throw new Error("Remarks are required when submitting a task for review.");
  }

  if (file) {
    const check = validateDeliverableFile(file);
    if (!check.valid) {
      throw new Error(check.error);
    }
  }

  const formData = new FormData();
  formData.append("remarks", trimmedRemarks);
  if (file) {
    formData.append("file", file);
  }

  return apiClient.post(`/api/v1/tasks/${taskId}/submit`, formData);
}

/**
 * Validates whether an optional deliverable URL is well-formed.
 * Empty, null, or whitespace-only inputs are considered valid (optional field).
 * When provided, URL must be an absolute http:// or https:// URL.
 *
 * @param {string|null|undefined} urlStr
 * @returns {boolean}
 */
export function isValidUrl(urlStr) {
  if (!urlStr || typeof urlStr !== "string" || !urlStr.trim()) {
    return true; // Optional field: empty is valid
  }
  try {
    const parsed = new URL(urlStr.trim());
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

/**
 * Resubmit revised task after rejection (US-13).
 *
 * CRITICAL BACKEND CONTRACT:
 * The PUT /api/v1/tasks/{id}/resubmit endpoint exclusively accepts JSON:
 * { revised_remarks: string, new_file_url?: string }
 * It does NOT accept multipart file uploads. File evidence must be supplied via URL.
 *
 * @param {number|string} taskId
 * @param {Object} payload
 * @param {string} payload.revised_remarks Mandatory description of fixes applied
 * @param {string} [payload.new_file_url] Optional URL to updated deliverable or repository
 * @returns {Promise<Object>} TaskResubmitResponse
 */
export async function resubmitTask(
  taskId,
  { revised_remarks, new_file_url } = {}
) {
  if (!taskId) {
    throw new Error("Task ID is required for resubmission.");
  }

  const trimmedRemarks = (revised_remarks || "").trim();
  if (!trimmedRemarks) {
    throw new Error(
      "Revised remarks are required when resubmitting a task."
    );
  }

  const trimmedUrl = new_file_url ? String(new_file_url).trim() : null;
  if (trimmedUrl && !isValidUrl(trimmedUrl)) {
    throw new Error(
      "Invalid deliverable URL. URL must start with http:// or https://"
    );
  }

  const body = {
    revised_remarks: trimmedRemarks,
    new_file_url: trimmedUrl,
  };

  return apiClient.put(`/api/v1/tasks/${taskId}/resubmit`, body);
}

/**
 * Fetch chronological list of submissions for a task (US-11).
 *
 * @param {number|string} taskId
 * @returns {Promise<Array<Object>>} List of TaskSubmissionResponse
 */
export async function getTaskSubmissions(taskId) {
  if (!taskId) {
    throw new Error("Task ID is required to fetch submissions.");
  }
  return apiClient.get(`/api/v1/tasks/${taskId}/submissions`);
}


/**
 * Maximum character limit for task comments (US-33).
 */
export const MAX_COMMENT_LENGTH = 2000;

/**
 * Validates task comment content (US-33).
 * Must be non-empty after trimming and no more than 2,000 characters.
 *
 * @param {string|null|undefined} content
 * @returns {{ valid: boolean, error?: string, trimmed: string }}
 */
export function validateCommentContent(content) {
  if (content === null || content === undefined) {
    return { valid: false, error: "Comment content cannot be empty.", trimmed: "" };
  }
  const trimmed = String(content).trim();
  if (!trimmed) {
    return { valid: false, error: "Comment cannot be blank or whitespace-only.", trimmed: "" };
  }
  if (trimmed.length > MAX_COMMENT_LENGTH) {
    return {
      valid: false,
      error: `Comment exceeds maximum length of ${MAX_COMMENT_LENGTH} characters (current: ${trimmed.length}).`,
      trimmed,
    };
  }
  return { valid: true, trimmed };
}

/**
 * Fetch chronological list of comments for a task (US-33).
 *
 * @param {number|string} taskId
 * @returns {Promise<Array<Object>>} List of TaskCommentResponse
 */
export async function getTaskComments(taskId) {
  if (!taskId) {
    throw new Error("Task ID is required to fetch comments.");
  }
  return apiClient.get(`/api/v1/tasks/${taskId}/comments`);
}

/**
 * Add a new comment to a task (US-33).
 *
 * @param {number|string} taskId
 * @param {string} content
 * @returns {Promise<Object>} Created TaskCommentResponse
 */
export async function createTaskComment(taskId, content) {
  if (!taskId) {
    throw new Error("Task ID is required to post a comment.");
  }
  const check = validateCommentContent(content);
  if (!check.valid) {
    throw new Error(check.error);
  }
  return apiClient.post(`/api/v1/tasks/${taskId}/comments`, {
    content: check.trimmed,
  });
}

export const tasksApi = {
  getProgressFillClass,
  matchesTaskSearch,
  filterTasks,
  computeTaskMetrics,
  calculatePagination,
  getPaginatedItems,
  getMyTasks,
  fetchAllMyTasks,
  getTaskDetail,
  updateTaskProgress,
  submitTask,
  resubmitTask,
  getTaskSubmissions,
  getTaskComments,
  createTaskComment,
  validateCommentContent,
  MAX_COMMENT_LENGTH,
  validateDeliverableFile,
  isValidUrl,
  ALLOWED_FILE_EXTENSIONS,
  MAX_FILE_SIZE_BYTES,
};

export default tasksApi;
