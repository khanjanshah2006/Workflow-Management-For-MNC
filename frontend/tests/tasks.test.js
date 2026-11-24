import { test, describe, afterEach } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  validateCommentContent,
  getTaskComments,
  createTaskComment,
  validateTaskDates,
  validateRejectionFeedback,
  validateReassignReason,
  createTask,
  assignTask,
  reassignTask,
  getReviewQueue,
  reviewTask,
  getProjectTasks,
  getProgressFillClass,
  matchesTaskSearch,
  filterTasks,
  computeTaskMetrics,
  calculatePagination,
  getPaginatedItems,
  getMyTasks,
  fetchAllMyTasks,
  updateTaskProgress,
  groupTasksForKanban,
  submitTask,
  resubmitTask,
  getTaskSubmissions,
  validateDeliverableFile,
  isValidUrl,
  ALLOWED_FILE_EXTENSIONS,
  MAX_FILE_SIZE_BYTES,
  MAX_UPLOAD_BYTES,
  openDeliverable,
} from "../src/api/tasksApi.js";
import { apiClient } from "../src/api/client.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Sample fixtures conforming to TaskSummaryResponse
const SAMPLE_SUMMARY_TASKS = [
  {
    task_id: 101,
    project_id: 1,
    team_id: 2,
    milestone_id: 4,
    assigned_to: 12,
    created_by: 5,
    title: "Design Enterprise RBAC Permission Matrix",
    priority: "HIGH",
    status: "TODO",
    progress_pct: 0,
    start_date: "2026-11-10",
    due_date: "2026-11-20",
    created_at: "2026-11-10T09:00:00Z",
    updated_at: "2026-11-10T09:00:00Z",
  },
  {
    task_id: 102,
    project_id: 1,
    team_id: 2,
    milestone_id: 4,
    assigned_to: 12,
    created_by: 5,
    title: "Implement Employee My Tasks Dashboard & Kanban View",
    priority: "CRITICAL",
    status: "IN_PROGRESS",
    progress_pct: 65,
    start_date: "2026-11-12",
    due_date: "2026-11-18",
    created_at: "2026-11-12T10:15:00Z",
    updated_at: "2026-11-14T14:30:00Z",
  },
  {
    task_id: 103,
    project_id: 2,
    team_id: 3,
    milestone_id: 7,
    assigned_to: 12,
    created_by: 8,
    title: "Integrate Supabase Webhook for Real-time Notifications",
    priority: "HIGH",
    status: "BLOCKED",
    progress_pct: 40,
    start_date: "2026-11-08",
    due_date: "2026-11-15",
    created_at: "2026-11-08T11:00:00Z",
    updated_at: "2026-11-13T16:45:00Z",
  },
  {
    task_id: 104,
    project_id: 1,
    team_id: 2,
    milestone_id: 3,
    assigned_to: 12,
    created_by: 5,
    title: "Build Slide-out Detail Drawer for Task Inspection",
    priority: "MEDIUM",
    status: "IN_REVIEW",
    progress_pct: 99,
    start_date: "2026-11-05",
    due_date: "2026-11-12",
    created_at: "2026-11-05T08:30:00Z",
    updated_at: "2026-11-12T18:00:00Z",
  },
  {
    task_id: 105,
    project_id: 3,
    team_id: 1,
    milestone_id: 2,
    assigned_to: 12,
    created_by: 4,
    title: "Setup Automated End-to-End Test Suite for Authentication",
    priority: "LOW",
    status: "DONE",
    progress_pct: 100,
    start_date: "2026-10-25",
    due_date: "2026-11-02",
    created_at: "2026-10-25T09:00:00Z",
    updated_at: "2026-11-02T15:20:00Z",
  },
];

describe("1. Progress Bar Fill Class Mapping", () => {
  test("maps standard uppercase task statuses correctly", () => {
    assert.equal(getProgressFillClass("TODO"), "progress-fill-todo");
    assert.equal(getProgressFillClass("IN_PROGRESS"), "progress-fill-inprogress");
    assert.equal(getProgressFillClass("BLOCKED"), "progress-fill-blocked");
    assert.equal(getProgressFillClass("IN_REVIEW"), "progress-fill-inreview");
    assert.equal(getProgressFillClass("DONE"), "progress-fill-done");
  });

  test("handles lowercase and mixed-case status values", () => {
    assert.equal(getProgressFillClass("todo"), "progress-fill-todo");
    assert.equal(getProgressFillClass("In_Progress"), "progress-fill-inprogress");
    assert.equal(getProgressFillClass("blocked"), "progress-fill-blocked");
    assert.equal(getProgressFillClass("done"), "progress-fill-done");
  });

  test("falls back safely to in-progress for unrecognized or missing status", () => {
    assert.equal(getProgressFillClass(""), "progress-fill-inprogress");
    assert.equal(getProgressFillClass(null), "progress-fill-inprogress");
    assert.equal(getProgressFillClass(undefined), "progress-fill-inprogress");
    assert.equal(getProgressFillClass("UNKNOWN_STATUS"), "progress-fill-inprogress");
  });

  test("maps REJECTED status to progress-fill-rejected", () => {
    assert.equal(getProgressFillClass("REJECTED"), "progress-fill-rejected");
    assert.equal(getProgressFillClass("rejected"), "progress-fill-rejected");
  });
});

describe("2. Supported-Field Search & Filtering Contract", () => {
  test("matches task title case-insensitively", () => {
    const task = SAMPLE_SUMMARY_TASKS[0]; // Title: "Design Enterprise RBAC Permission Matrix"
    assert.equal(matchesTaskSearch(task, "rbac"), true);
    assert.equal(matchesTaskSearch(task, "ENTERPRISE"), true);
    assert.equal(matchesTaskSearch(task, "permission matrix"), true);
    assert.equal(matchesTaskSearch(task, "nonexistent"), false);
  });

  test("matches task_id by numeric string", () => {
    const task = SAMPLE_SUMMARY_TASKS[1]; // task_id: 102
    assert.equal(matchesTaskSearch(task, "102"), true);
    assert.equal(matchesTaskSearch(task, "10"), true);
    assert.equal(matchesTaskSearch(task, "999"), false);
  });

  test("matches project_id by numeric string", () => {
    const task = SAMPLE_SUMMARY_TASKS[2]; // project_id: 2
    assert.equal(matchesTaskSearch(task, "2"), true);
  });

  test("matches blocker_reason in client-side search (Issue #162)", () => {
    const taskWithBlocker = {
      ...SAMPLE_SUMMARY_TASKS[2],
      blocker_reason: "Specialized IT SecOps network egress allowance pending approval",
    };

    // "SecOps" and "egress" exist in blocker_reason and must now match
    assert.equal(matchesTaskSearch(taskWithBlocker, "SecOps"), true);
    assert.equal(matchesTaskSearch(taskWithBlocker, "egress"), true);

    // Title words must still match
    assert.equal(matchesTaskSearch(taskWithBlocker, "Webhook"), true);
    assert.equal(matchesTaskSearch(taskWithBlocker, "103"), true);
  });

  test("filterTasks filters correctly by status and search query together", () => {
    // Status filter only
    const blockedOnly = filterTasks(SAMPLE_SUMMARY_TASKS, { statusFilter: "BLOCKED" });
    assert.equal(blockedOnly.length, 1);
    assert.equal(blockedOnly[0].task_id, 103);

    // Status filter + search query
    const inProgressDashboard = filterTasks(SAMPLE_SUMMARY_TASKS, {
      statusFilter: "IN_PROGRESS",
      searchQuery: "Dashboard",
    });
    assert.equal(inProgressDashboard.length, 1);
    assert.equal(inProgressDashboard[0].task_id, 102);

    // Search query with no matching status returns empty
    const noMatch = filterTasks(SAMPLE_SUMMARY_TASKS, {
      statusFilter: "DONE",
      searchQuery: "Dashboard",
    });
    assert.equal(noMatch.length, 0);

    // Empty/ALL returns everything
    const all = filterTasks(SAMPLE_SUMMARY_TASKS, { statusFilter: "ALL", searchQuery: "" });
    assert.equal(all.length, 5);
  });

  test("filters REJECTED status tasks correctly", () => {
    const tasksWithRejected = [
      ...SAMPLE_SUMMARY_TASKS,
      { task_id: 106, project_id: 1, title: "Refactor API", status: "REJECTED" },
    ];
    const filtered = filterTasks(tasksWithRejected, { statusFilter: "REJECTED" });
    assert.equal(filtered.length, 1);
    assert.equal(filtered[0].task_id, 106);
  });
});

describe("3. Full-Dataset Summary Metrics", () => {
  test("accurately counts each status from the full task array", () => {
    const metrics = computeTaskMetrics(SAMPLE_SUMMARY_TASKS, 5);
    assert.equal(metrics.TOTAL, 5);
    assert.equal(metrics.TODO, 1);
    assert.equal(metrics.IN_PROGRESS, 1);
    assert.equal(metrics.BLOCKED, 1);
    assert.equal(metrics.IN_REVIEW, 1);
    assert.equal(metrics.DONE, 1);
    assert.equal(metrics.REJECTED, 0);
  });

  test("accurately counts REJECTED status in summary metrics", () => {
    const tasksWithRejected = [
      ...SAMPLE_SUMMARY_TASKS,
      { task_id: 106, status: "REJECTED" },
      { task_id: 107, status: "rejected" },
    ];
    const metrics = computeTaskMetrics(tasksWithRejected, 7);
    assert.equal(metrics.TOTAL, 7);
    assert.equal(metrics.TODO, 1);
    assert.equal(metrics.REJECTED, 2);
  });

  test("uses total count when total exceeds items length (server pagination)", () => {
    const metrics = computeTaskMetrics(SAMPLE_SUMMARY_TASKS, 42);
    assert.equal(metrics.TOTAL, 42);
  });

  test("handles empty and malformed task lists gracefully", () => {
    const emptyMetrics = computeTaskMetrics([], 0);
    assert.equal(emptyMetrics.TOTAL, 0);
    assert.equal(emptyMetrics.TODO, 0);
    assert.equal(emptyMetrics.IN_PROGRESS, 0);

    const nullMetrics = computeTaskMetrics(null);
    assert.equal(nullMetrics.TOTAL, 0);
  });
});

describe("4. Pagination Calculations & Slicing", () => {
  test("calculates page count, start and end indexes correctly", () => {
    const p1 = calculatePagination(45, 1, 20);
    assert.equal(p1.totalPages, 3);
    assert.equal(p1.page, 1);
    assert.equal(p1.startIndex, 0);
    assert.equal(p1.endIndex, 20);

    const p2 = calculatePagination(45, 2, 20);
    assert.equal(p2.page, 2);
    assert.equal(p2.startIndex, 20);
    assert.equal(p2.endIndex, 40);

    const p3 = calculatePagination(45, 3, 20);
    assert.equal(p3.page, 3);
    assert.equal(p3.startIndex, 40);
    assert.equal(p3.endIndex, 45);
  });

  test("handles exact multiples of page size", () => {
    const p = calculatePagination(40, 2, 20);
    assert.equal(p.totalPages, 2);
    assert.equal(p.endIndex, 40);
  });

  test("clamps page out of bounds safely", () => {
    const clampedHigh = calculatePagination(10, 99, 20);
    assert.equal(clampedHigh.totalPages, 1);
    assert.equal(clampedHigh.page, 1);

    const clampedLow = calculatePagination(10, -5, 20);
    assert.equal(clampedLow.page, 1);
  });

  test("slices items correctly with getPaginatedItems", () => {
    const items = [1, 2, 3, 4, 5];
    assert.deepEqual(getPaginatedItems(items, 1, 2), [1, 2]);
    assert.deepEqual(getPaginatedItems(items, 2, 2), [3, 4]);
    assert.deepEqual(getPaginatedItems(items, 3, 2), [5]);
    assert.deepEqual(getPaginatedItems([], 1, 20), []);
  });

  test("regression: page 3 shrinks to page 1 when dataset count drops after update/refetch", () => {
    // User starts on page 3 of 50 tasks (pageSize: 20)
    const initialPagination = calculatePagination(50, 3, 20);
    assert.equal(initialPagination.totalPages, 3);
    assert.equal(initialPagination.page, 3);
    assert.equal(initialPagination.startIndex, 40);
    assert.equal(initialPagination.endIndex, 50);

    // Dataset shrinks to 12 items (e.g. after progress update moves completed tasks or search filter is applied)
    const clampedPagination = calculatePagination(12, 3, 20);
    assert.equal(clampedPagination.totalPages, 1);
    assert.equal(clampedPagination.page, 1, "Page 3 must be clamped to page 1");
    assert.equal(clampedPagination.startIndex, 0);
    assert.equal(clampedPagination.endIndex, 12);

    // Verify getPaginatedItems retrieves page 1 items rather than an empty slice
    const tasks12 = Array.from({ length: 12 }, (_, i) => ({ task_id: 100 + i }));
    const items = getPaginatedItems(tasks12, 3, 20);
    assert.equal(items.length, 12, "Clamped page must return 12 items");
    assert.equal(items[0].task_id, 100);
    assert.equal(items[11].task_id, 111);

    // Edge case: complete shrink to 0 items
    const emptyPagination = calculatePagination(0, 3, 20);
    assert.equal(emptyPagination.totalPages, 1);
    assert.equal(emptyPagination.page, 1);
    assert.equal(emptyPagination.startIndex, 0);
    assert.equal(emptyPagination.endIndex, 0);
    assert.deepEqual(getPaginatedItems([], 3, 20), []);
  });
});

describe("5. Pagination Fetching Integration (getMyTasks & fetchAllMyTasks)", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("getMyTasks formats query parameters correctly", async () => {
    let capturedUrl = "";
    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(
        JSON.stringify({
          items: [],
          total: 0,
          page: 2,
          limit: 10,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    await getMyTasks({ status: "TODO", priority: "HIGH", page: 2, limit: 10 });
    const u = new URL(capturedUrl, "http://localhost:8000");
    assert.equal(u.searchParams.get("status"), "TODO");
    assert.equal(u.searchParams.get("priority"), "HIGH");
    assert.equal(u.searchParams.get("page"), "2");
    assert.equal(u.searchParams.get("limit"), "10");

    // "ALL" filters should not be appended as query params
    await getMyTasks({ status: "ALL", priority: "ALL" });
    const uAll = new URL(capturedUrl, "http://localhost:8000");
    assert.equal(uAll.searchParams.get("status"), null);
    assert.equal(uAll.searchParams.get("priority"), null);
  });

  test("resolves single page without additional requests when total <= limit", async () => {
    let callCount = 0;
    globalThis.fetch = async (url) => {
      callCount++;
      assert.match(url, /\/api\/v1\/tasks\/my-tasks/);
      return new Response(
        JSON.stringify({
          items: SAMPLE_SUMMARY_TASKS,
          total: 5,
          page: 1,
          limit: 20,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    const result = await fetchAllMyTasks({ batchSize: 20 });
    assert.equal(callCount, 1);
    assert.equal(result.total, 5);
    assert.equal(result.items.length, 5);
  });

  test("fetches and merges multiple pages concurrently when total > batchSize", async () => {
    const requestedPages = [];

    globalThis.fetch = async (url) => {
      const u = new URL(url, "http://localhost:8000");
      const page = Number(u.searchParams.get("page") || 1);
      requestedPages.push(page);

      if (page === 1) {
        return new Response(
          JSON.stringify({
            items: [SAMPLE_SUMMARY_TASKS[0], SAMPLE_SUMMARY_TASKS[1]],
            total: 5,
            page: 1,
            limit: 2,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }
        );
      }
      if (page === 2) {
        return new Response(
          JSON.stringify({
            items: [SAMPLE_SUMMARY_TASKS[2], SAMPLE_SUMMARY_TASKS[3]],
            total: 5,
            page: 2,
            limit: 2,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }
        );
      }
      if (page === 3) {
        return new Response(
          JSON.stringify({
            items: [SAMPLE_SUMMARY_TASKS[4]],
            total: 5,
            page: 3,
            limit: 2,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }
        );
      }
    };

    const result = await fetchAllMyTasks({ batchSize: 2 });
    assert.equal(result.total, 5);
    assert.equal(result.items.length, 5);
    assert.deepEqual(result.items.map((t) => t.task_id), [101, 102, 103, 104, 105]);
    assert.equal(requestedPages.includes(1), true);
    assert.equal(requestedPages.includes(2), true);
    assert.equal(requestedPages.includes(3), true);
  });
});

describe("6. Mock Fixtures Shape Verification", () => {
  const mockTasksPath = path.resolve(__dirname, "../src/features/tasks/mockTasksData.json");
  const mockDetailPath = path.resolve(__dirname, "../src/features/tasks/mockTaskDetail.json");

  test("mockTasksData.json strictly matches PaginatedTasksResponse schema", () => {
    assert.equal(fs.existsSync(mockTasksPath), true, "mockTasksData.json must exist");
    const content = JSON.parse(fs.readFileSync(mockTasksPath, "utf-8"));

    // Root keys check: items, total, page, limit ONLY
    const rootKeys = Object.keys(content);
    assert.deepEqual(rootKeys.sort(), ["items", "limit", "page", "total"].sort());

    // sampleDetail must NOT be present
    assert.equal(content.sampleDetail, undefined, "sampleDetail must be removed from mockTasksData.json");

    assert.equal(Array.isArray(content.items), true);
    assert.equal(typeof content.total, "number");
    assert.equal(typeof content.page, "number");
    assert.equal(typeof content.limit, "number");

    // Every item in items must strictly conform to TaskSummaryResponse
    content.items.forEach((item, idx) => {
      assert.equal(typeof item.task_id, "number", `Item ${idx} missing task_id`);
      assert.equal(typeof item.project_id, "number", `Item ${idx} missing project_id`);
      assert.equal(typeof item.team_id, "number", `Item ${idx} missing team_id`);
      assert.equal(typeof item.title, "string", `Item ${idx} missing title`);
      assert.equal(typeof item.priority, "string", `Item ${idx} missing priority`);
      assert.equal(typeof item.status, "string", `Item ${idx} missing status`);
      assert.equal(typeof item.progress_pct, "number", `Item ${idx} missing progress_pct`);

      // blocker_reason must NOT be present on TaskSummaryResponse items
      assert.equal(
        item.blocker_reason,
        undefined,
        `Item ${idx} (${item.title}) must not contain blocker_reason`
      );

      // completed_at must NOT be present on TaskSummaryResponse items
      assert.equal(
        item.completed_at,
        undefined,
        `Item ${idx} (${item.title}) must not contain completed_at`
      );
    });
  });

  test("mockTaskDetail.json conforms to TaskDetailResponse schema", () => {
    assert.equal(fs.existsSync(mockDetailPath), true, "mockTaskDetail.json must exist");
    const detail = JSON.parse(fs.readFileSync(mockDetailPath, "utf-8"));

    assert.equal(typeof detail.task_id, "number");
    assert.equal(typeof detail.project_id, "number");
    assert.equal(typeof detail.title, "string");
    assert.equal(typeof detail.description, "string");
    assert.equal(typeof detail.status, "string");
    assert.equal(typeof detail.blocker_reason, "string");
    assert.equal(typeof detail.rejection_count, "number");
    assert.equal(typeof detail.project, "object");
    assert.equal(typeof detail.assignee, "object");
    assert.equal(typeof detail.creator, "object");
  });
});

describe("7. Task Progress & Blocker Updates (updateTaskProgress)", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("rejects taskId when missing or null", async () => {
    await assert.rejects(
      () => updateTaskProgress(null, { status: "IN_PROGRESS", progress_pct: 50 }),
      /Task ID is required/
    );
    await assert.rejects(
      () => updateTaskProgress("", { status: "IN_PROGRESS", progress_pct: 50 }),
      /Task ID is required/
    );
  });

  test("rejects progress 100 and invalid progress values", async () => {
    // 100% requires review submission, not progress update (US-10)
    await assert.rejects(
      () => updateTaskProgress(101, { status: "IN_PROGRESS", progress_pct: 100 }),
      /integer between 0 and 99/
    );
    await assert.rejects(
      () => updateTaskProgress(101, { status: "IN_PROGRESS", progress_pct: 105 }),
      /integer between 0 and 99/
    );
    await assert.rejects(
      () => updateTaskProgress(101, { status: "IN_PROGRESS", progress_pct: -1 }),
      /integer between 0 and 99/
    );
    await assert.rejects(
      () => updateTaskProgress(101, { status: "IN_PROGRESS", progress_pct: 45.5 }),
      /integer between 0 and 99/
    );
    await assert.rejects(
      () => updateTaskProgress(101, { status: "IN_PROGRESS", progress_pct: "abc" }),
      /integer between 0 and 99/
    );
  });

  test("rejects invalid statuses (only IN_PROGRESS and BLOCKED permitted)", async () => {
    await assert.rejects(
      () => updateTaskProgress(101, { status: "TODO", progress_pct: 50 }),
      /Allowed update statuses are IN_PROGRESS and BLOCKED/
    );
    await assert.rejects(
      () => updateTaskProgress(101, { status: "DONE", progress_pct: 50 }),
      /Allowed update statuses are IN_PROGRESS and BLOCKED/
    );
    await assert.rejects(
      () => updateTaskProgress(101, { status: "IN_REVIEW", progress_pct: 50 }),
      /Allowed update statuses are IN_PROGRESS and BLOCKED/
    );
    await assert.rejects(
      () => updateTaskProgress(101, { status: "CANCELLED", progress_pct: 50 }),
      /Allowed update statuses are IN_PROGRESS and BLOCKED/
    );
  });

  test("rejects BLOCKED with fewer than 5 non-whitespace characters", async () => {
    await assert.rejects(
      () => updateTaskProgress(101, { status: "BLOCKED", progress_pct: 40 }),
      /at least 5 characters/
    );
    await assert.rejects(
      () => updateTaskProgress(101, { status: "BLOCKED", progress_pct: 40, blocker_reason: "" }),
      /at least 5 characters/
    );
    await assert.rejects(
      () => updateTaskProgress(101, { status: "BLOCKED", progress_pct: 40, blocker_reason: "   " }),
      /at least 5 characters/
    );
    await assert.rejects(
      () => updateTaskProgress(101, { status: "BLOCKED", progress_pct: 40, blocker_reason: "wait" }),
      /at least 5 characters/
    );
    await assert.rejects(
      () => updateTaskProgress(101, { status: "BLOCKED", progress_pct: 40, blocker_reason: "  ab  " }),
      /at least 5 characters/
    );
  });

  test("verifies BLOCKED sends trimmed blocker reason to backend", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options?.method;
      capturedBody = JSON.parse(options?.body || "{}");

      return new Response(
        JSON.stringify({
          task_id: 103,
          status: "BLOCKED",
          progress_pct: 45,
          blocker_reason: capturedBody.blocker_reason,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    const res = await updateTaskProgress(103, {
      status: "BLOCKED",
      progress_pct: 45,
      blocker_reason: "   Waiting for IT SecOps egress allowance   ",
    });

    assert.equal(capturedMethod, "PUT");
    assert.match(capturedUrl, /\/api\/v1\/tasks\/103\/progress$/);
    assert.deepEqual(capturedBody, {
      status: "BLOCKED",
      progress_pct: 45,
      blocker_reason: "Waiting for IT SecOps egress allowance",
    });
    assert.equal(res.status, "BLOCKED");
    assert.equal(res.blocker_reason, "Waiting for IT SecOps egress allowance");
  });

  test("verify IN_PROGRESS sends blocker_reason: null to unblock task", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options?.method;
      capturedBody = JSON.parse(options?.body || "{}");

      return new Response(
        JSON.stringify({
          task_id: 102,
          status: "IN_PROGRESS",
          progress_pct: 65,
          blocker_reason: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    // Even if an old blocker_reason string is passed, status IN_PROGRESS must force blocker_reason to null
    const res = await updateTaskProgress(102, {
      status: "IN_PROGRESS",
      progress_pct: 65,
      blocker_reason: "old blocker",
    });

    assert.equal(capturedMethod, "PUT");
    assert.match(capturedUrl, /\/api\/v1\/tasks\/102\/progress$/);
    assert.deepEqual(capturedBody, {
      status: "IN_PROGRESS",
      progress_pct: 65,
      blocker_reason: null,
    });
    assert.equal(res.status, "IN_PROGRESS");
    assert.equal(res.blocker_reason, null);
  });
});

describe("8. Kanban Grouping Contract & REJECTED Isolation", () => {
  test("regression: REJECTED tasks are explicitly isolated and NEVER mapped to TODO", () => {
    const mixedTasks = [
      { task_id: 101, title: "Initial To Do", status: "TODO" },
      { task_id: 102, title: "Rejected Feature A", status: "REJECTED" },
      { task_id: 103, title: "Rejected Bugfix B", status: "rejected" },
      { task_id: 104, title: "Mixed Case Rejected", status: "Rejected" },
      { task_id: 105, title: "Active Dev", status: "IN_PROGRESS" },
    ];

    const grouped = groupTasksForKanban(mixedTasks);

    // Verify TODO contains ONLY the actual TODO task
    assert.equal(grouped.TODO.length, 1);
    assert.equal(grouped.TODO[0].task_id, 101);

    // Verify REJECTED bucket contains all 3 rejected tasks
    assert.equal(grouped.REJECTED.length, 3);
    assert.deepEqual(
      grouped.REJECTED.map((t) => t.task_id),
      [102, 103, 104]
    );

    // Invariant check: TODO must never contain any task with status REJECTED
    const anyRejectedInTodo = grouped.TODO.some(
      (t) => String(t.status).toUpperCase() === "REJECTED"
    );
    assert.equal(
      anyRejectedInTodo,
      false,
      "CRITICAL INVARIANT: TODO column must NOT contain any REJECTED tasks"
    );
  });

  test("preserves all five required Kanban columns intact", () => {
    const sampleTasks = [
      { task_id: 1, status: "TODO" },
      { task_id: 2, status: "IN_PROGRESS" },
      { task_id: 3, status: "BLOCKED" },
      { task_id: 4, status: "IN_REVIEW" },
      { task_id: 5, status: "DONE" },
      { task_id: 6, status: "REJECTED" },
    ];

    const grouped = groupTasksForKanban(sampleTasks);
    assert.equal(grouped.TODO.length, 1);
    assert.equal(grouped.IN_PROGRESS.length, 1);
    assert.equal(grouped.BLOCKED.length, 1);
    assert.equal(grouped.IN_REVIEW.length, 1);
    assert.equal(grouped.DONE.length, 1);
    assert.equal(grouped.REJECTED.length, 1);
  });

  test("handles unexpected non-rejected statuses and empty lists gracefully", () => {
    const strangeTasks = [
      { task_id: 1, status: "UNKNOWN_CUSTOM" },
      { task_id: 2, status: "" },
      { task_id: 3, status: null },
    ];
    const grouped = groupTasksForKanban(strangeTasks);
    assert.equal(grouped.TODO.length, 3);
    assert.equal(grouped.REJECTED.length, 0);

    const emptyGrouped = groupTasksForKanban([]);
    assert.deepEqual(emptyGrouped.TODO, []);
    assert.deepEqual(emptyGrouped.REJECTED, []);

    const nullGrouped = groupTasksForKanban(null);
    assert.deepEqual(nullGrouped.TODO, []);
    assert.deepEqual(nullGrouped.REJECTED, []);
  });
});


describe("9. Task Submission & Deliverable Validation (submitTask & US-11)", () => {
  const originalFetch = globalThis.fetch;
  const originalLocalStorage = globalThis.localStorage;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    globalThis.localStorage = originalLocalStorage;
  });

  test("exports expected ALLOWED_FILE_EXTENSIONS and MAX_FILE_SIZE_BYTES constants", () => {
    assert.deepEqual(ALLOWED_FILE_EXTENSIONS, [
      ".pdf",
      ".zip",
      ".tar.gz",
      ".png",
      ".jpg",
      ".jpeg",
      ".docx",
    ]);
    assert.equal(MAX_FILE_SIZE_BYTES, 25 * 1024 * 1024);
  });

  test("rejects taskId when missing, null or empty", async () => {
    await assert.rejects(
      () => submitTask(null, { remarks: "Done" }),
      /Task ID is required/
    );
    await assert.rejects(
      () => submitTask("", { remarks: "Done" }),
      /Task ID is required/
    );
  });

  test("rejects empty or whitespace-only remarks", async () => {
    await assert.rejects(
      () => submitTask(102, { remarks: "" }),
      /Remarks are required/
    );
    await assert.rejects(
      () => submitTask(102, { remarks: "     " }),
      /Remarks are required/
    );
    await assert.rejects(
      () => submitTask(102, {}),
      /Remarks are required/
    );
  });

  test("validates deliverable file extensions strictly", () => {
    // Allowed extensions
    const allowed = [
      "document.pdf",
      "archive.zip",
      "bundle.tar.gz",
      "BUNDLE.TAR.GZ",
      "screenshot.png",
      "photo.jpg",
      "image.jpeg",
      "report.docx",
    ];
    for (const name of allowed) {
      const res = validateDeliverableFile({ name, size: 1024 });
      assert.equal(res.valid, true, `Expected ${name} to be valid`);
      assert.equal(res.error, undefined);
    }

    // Disallowed extensions
    const disallowed = [
      "malware.exe",
      "script.sh",
      "index.js",
      "styles.css",
      "video.mp4",
      "audio.mp3",
      "data.csv",
    ];
    for (const name of disallowed) {
      const res = validateDeliverableFile({ name, size: 1024 });
      assert.equal(res.valid, false, `Expected ${name} to be rejected`);
      assert.match(res.error, /File type not allowed/);
    }
  });

  test("validates file size at and above the 5MB boundary (Issue #162)", () => {
    const exactly5MB = 5 * 1024 * 1024;
    const over5MB = 5 * 1024 * 1024 + 1;
    const under5MB = 5 * 1024 * 1024 - 1;

    // At or under 5MB passes
    assert.equal(
      validateDeliverableFile({ name: "deliverable.zip", size: exactly5MB }).valid,
      true
    );
    assert.equal(
      validateDeliverableFile({ name: "deliverable.zip", size: under5MB }).valid,
      true
    );

    // Above 5MB fails
    const overCheck = validateDeliverableFile({ name: "deliverable.zip", size: over5MB });
    assert.equal(overCheck.valid, false);
    assert.match(overCheck.error, /File size exceeds the 5MB limit/);
  });

  test("dispatches correct multipart fields, auth bearer header, and credentials without manual Content-Type", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    let capturedHeaders = null;
    let capturedCredentials = null;
    let capturedBody = null;

    // Simulate stored user authentication token
    globalThis.localStorage = {
      getItem: (key) => (key === "wms_access_token" ? "jwt-bearer-test-token-789" : null),
      setItem: () => {},
      removeItem: () => {},
    };

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options?.method;
      capturedHeaders = options?.headers;
      capturedCredentials = options?.credentials;
      capturedBody = options?.body;

      return new Response(
        JSON.stringify({
          submission_id: 501,
          task_id: 102,
          submitted_by: 12,
          remarks: "Initial test deliverable",
          file_name: "evidence.pdf",
          file_url: "/uploads/task_submissions/evidence.pdf",
          file_size_bytes: 4096,
          submitted_at: "2026-11-15T20:00:00Z",
        }),
        {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    // Real standard File instance
    const fakeFile = new File(["sample deliverable content"], "evidence.pdf", {
      type: "application/pdf",
    });

    const res = await submitTask(102, {
      remarks: "   Initial test deliverable   ",
      file: fakeFile,
    });

    assert.equal(capturedMethod, "POST");
    assert.match(capturedUrl, /\/api\/v1\/tasks\/102\/submit$/);
    assert.equal(capturedCredentials, "include", "Credentials must be 'include'");

    // Authorization header must carry bearer token from auth storage
    assert.equal(
      capturedHeaders["Authorization"],
      "Bearer jwt-bearer-test-token-789",
      "Bearer token must be injected into request headers"
    );

    // Content-Type must NOT be manually set so the browser/fetch provides its multipart boundary
    assert.equal(
      capturedHeaders["Content-Type"],
      undefined,
      "Content-Type header must be omitted for multipart/form-data"
    );

    // Body must be a genuine FormData instance, never a JSON string
    assert.equal(capturedBody instanceof FormData, true);
    assert.equal(capturedBody.get("remarks"), "Initial test deliverable");
    assert.equal(capturedBody.get("file").name, "evidence.pdf");

    assert.equal(res.submission_id, 501);
    assert.equal(res.task_id, 102);
  });

  test("handles API errors (400, 403, 500) gracefully", async () => {
    globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({
          detail: "Cannot submit task with status 'TODO'. Task status must be 'IN_PROGRESS'.",
        }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    await assert.rejects(
      () => submitTask(101, { remarks: "Test remarks" }),
      /Task status must be 'IN_PROGRESS'/
    );
  });
});

describe("10. Task Resubmission & URL-based Deliverable Contract (resubmitTask & US-13)", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("rejects missing taskId or empty revised remarks", async () => {
    await assert.rejects(
      () => resubmitTask(null, { revised_remarks: "Fixes" }),
      /Task ID is required/
    );
    await assert.rejects(
      () => resubmitTask(103, { revised_remarks: "" }),
      /Revised remarks are required/
    );
    await assert.rejects(
      () => resubmitTask(103, { revised_remarks: "   " }),
      /Revised remarks are required/
    );
  });

  test("dispatches correct JSON payload with revised_remarks and new_file_url", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    let capturedHeaders = null;
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options?.method;
      capturedHeaders = options?.headers;
      capturedBody = JSON.parse(options?.body || "{}");

      return new Response(
        JSON.stringify({
          task_id: 103,
          title: "Fixed Task",
          status: "IN_REVIEW",
          team_id: 3,
          assigned_to: 12,
          submission_id: 502,
          revised_remarks: capturedBody.revised_remarks,
          new_file_url: capturedBody.new_file_url,
          message: "Task resubmitted successfully",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    const res = await resubmitTask(103, {
      revised_remarks: "   Addressed security ingress allowlist feedback   ",
      new_file_url: "  https://github.com/khanjanshah2006/Workflow-Management-For-MNC/pull/99  ",
    });

    assert.equal(capturedMethod, "PUT");
    assert.match(capturedUrl, /\/api\/v1\/tasks\/103\/resubmit$/);
    assert.equal(capturedHeaders["Content-Type"], "application/json");

    // Strictly conforms to backend JSON contract:
    assert.deepEqual(capturedBody, {
      revised_remarks: "Addressed security ingress allowlist feedback",
      new_file_url: "https://github.com/khanjanshah2006/Workflow-Management-For-MNC/pull/99",
    });

    assert.equal(res.status, "IN_REVIEW");
    assert.equal(res.submission_id, 502);
  });

  test("sends null for new_file_url when deliverable URL is omitted", async () => {
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedBody = JSON.parse(options?.body || "{}");
      return new Response(
        JSON.stringify({
          task_id: 103,
          status: "IN_REVIEW",
          message: "Task resubmitted successfully",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    await resubmitTask(103, {
      revised_remarks: "Fixed typo in configuration",
    });

    assert.equal(capturedBody.new_file_url, null);
  });

  test("handles backend error when task is not in REJECTED status", async () => {
    globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({
          detail: "Task must currently have status == 'REJECTED' to resubmit. Current status: 'IN_PROGRESS'.",
        }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    await assert.rejects(
      () => resubmitTask(102, { revised_remarks: "Attempted early resubmit" }),
      /Task must currently have status == 'REJECTED'/
    );
  });

  test("regression: resubmitTask conforms to backend TaskResubmitResponse shape and excludes nested domain objects", async () => {
    // Exact schema returned by backend /api/v1/tasks/{id}/resubmit (TaskResubmitResponse)
    const mockBackendResponse = {
      task_id: 104,
      title: "Implement OAuth2 PKCE Flow",
      status: "IN_REVIEW",
      team_id: 2,
      assigned_to: 12,
      submission_id: 503,
      revised_remarks: "Added code_challenge and code_verifier validation per TL review notes",
      new_file_url: "https://github.com/khanjanshah2006/Workflow-Management-For-MNC/pull/105",
      message: "Task resubmitted successfully",
    };

    globalThis.fetch = async () => {
      return new Response(JSON.stringify(mockBackendResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await resubmitTask(104, {
      revised_remarks: "Added code_challenge and code_verifier validation per TL review notes",
      new_file_url: "https://github.com/khanjanshah2006/Workflow-Management-For-MNC/pull/105",
    });

    // 1. Confirm returned status is IN_REVIEW
    assert.equal(res.status, "IN_REVIEW");
    assert.equal(res.task_id, 104);
    assert.equal(res.submission_id, 503);
    assert.equal(res.message, "Task resubmitted successfully");
    assert.equal(res.revised_remarks, "Added code_challenge and code_verifier validation per TL review notes");
    assert.equal(res.new_file_url, "https://github.com/khanjanshah2006/Workflow-Management-For-MNC/pull/105");

    // 2. CONTRACT INTEGRITY: TaskResubmitResponse MUST NOT include nested domain objects
    // Callers must not assume full project, milestone, assignee, or creator objects exist in the response
    assert.equal(res.project, undefined, "TaskResubmitResponse must not contain project object");
    assert.equal(res.milestone, undefined, "TaskResubmitResponse must not contain milestone object");
    assert.equal(res.assignee, undefined, "TaskResubmitResponse must not contain assignee object");
    assert.equal(res.creator, undefined, "TaskResubmitResponse must not contain creator object");
  });

  test("isValidUrl validates optional deliverable URLs strictly (empty allowed, http/https required)", () => {
    // Optional field: empty, whitespace or null are valid
    assert.equal(isValidUrl(""), true);
    assert.equal(isValidUrl("   "), true);
    assert.equal(isValidUrl(null), true);
    assert.equal(isValidUrl(undefined), true);

    // Valid http and https absolute URLs
    assert.equal(isValidUrl("https://github.com/khanjanshah2006/Workflow-Management-For-MNC/pull/99"), true);
    assert.equal(isValidUrl("http://localhost:8000/docs"), true);
    assert.equal(isValidUrl("https://drive.google.com/file/d/12345/view"), true);

    // Invalid non-http schemes and malformed strings
    assert.equal(isValidUrl("not-a-valid-url"), false);
    assert.equal(isValidUrl("ftp://files.example.com/archive.zip"), false);
    assert.equal(isValidUrl("javascript:alert(1)"), false);
    assert.equal(isValidUrl("data:text/plain;base64,SGVsbG8="), false);
    assert.equal(isValidUrl("//missing-protocol.com"), false);
  });

  test("resubmitTask rejects malformed deliverable URL before dispatching", async () => {
    await assert.rejects(
      () =>
        resubmitTask(104, {
          revised_remarks: "Fixed bug",
          new_file_url: "not-a-valid-url",
        }),
      /Invalid deliverable URL/
    );
  });

  test("getTaskSubmissions dispatches GET /api/v1/tasks/{id}/submissions correctly", async () => {
    let capturedUrl = "";
    let capturedMethod = "";

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options?.method;
      return new Response(
        JSON.stringify([
          {
            submission_id: 1,
            task_id: 104,
            remarks: "First submission",
            submitted_at: "2026-11-15T12:00:00Z",
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    await assert.rejects(() => getTaskSubmissions(null), /Task ID is required/);

    const submissions = await getTaskSubmissions(104);
    assert.equal(capturedMethod, "GET");
    assert.match(capturedUrl, /\/api\/v1\/tasks\/104\/submissions$/);
    assert.equal(Array.isArray(submissions), true);
    assert.equal(submissions.length, 1);
    assert.equal(submissions[0].submission_id, 1);
  });
});

describe("11. Shared API Client Headers & Serialization (JSON vs FormData)", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("JSON POST requests serialize body and retain Content-Type: application/json", async () => {
    let capturedHeaders = null;
    let capturedBody = null;
    let capturedMethod = "";

    globalThis.fetch = async (url, options) => {
      capturedMethod = options?.method;
      capturedHeaders = options?.headers;
      capturedBody = options?.body;
      return new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const payload = { title: "API Client Test", count: 42, active: true };
    await apiClient.post("/api/v1/test-json", payload);

    assert.equal(capturedMethod, "POST");
    assert.equal(
      capturedHeaders["Content-Type"],
      "application/json",
      "Ordinary JSON POST must retain Content-Type: application/json"
    );
    assert.equal(typeof capturedBody, "string");
    assert.deepEqual(JSON.parse(capturedBody), payload);
  });

  test("JSON PUT requests serialize body and retain Content-Type: application/json", async () => {
    let capturedHeaders = null;
    let capturedBody = null;
    let capturedMethod = "";

    globalThis.fetch = async (url, options) => {
      capturedMethod = options?.method;
      capturedHeaders = options?.headers;
      capturedBody = options?.body;
      return new Response(JSON.stringify({ updated: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const payload = { status: "IN_PROGRESS", progress_pct: 75 };
    await apiClient.put("/api/v1/test-json/1", payload);

    assert.equal(capturedMethod, "PUT");
    assert.equal(
      capturedHeaders["Content-Type"],
      "application/json",
      "Ordinary JSON PUT must retain Content-Type: application/json"
    );
    assert.equal(typeof capturedBody, "string");
    assert.deepEqual(JSON.parse(capturedBody), payload);
  });

  test("FormData POST requests omit manual Content-Type and pass genuine FormData", async () => {
    let capturedHeaders = null;
    let capturedBody = null;
    let capturedMethod = "";

    globalThis.fetch = async (url, options) => {
      capturedMethod = options?.method;
      capturedHeaders = options?.headers;
      capturedBody = options?.body;
      return new Response(JSON.stringify({ uploaded: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const formData = new FormData();
    formData.append("title", "Multipart Document");
    formData.append(
      "file",
      new File(["content"], "doc.pdf", { type: "application/pdf" })
    );

    await apiClient.post("/api/v1/test-upload", formData);

    assert.equal(capturedMethod, "POST");
    assert.equal(
      capturedHeaders["Content-Type"],
      undefined,
      "FormData requests must omit manual Content-Type header so fetch manages multipart boundary"
    );
    assert.equal(capturedBody instanceof FormData, true);
    assert.equal(capturedBody.get("title"), "Multipart Document");
    assert.equal(capturedBody.get("file").name, "doc.pdf");
  });

  test("FormData PUT and postForm requests omit manual Content-Type and pass genuine FormData", async () => {
    let capturedHeaders = null;
    let capturedBody = null;
    let capturedMethod = "";

    globalThis.fetch = async (url, options) => {
      capturedMethod = options?.method;
      capturedHeaders = options?.headers;
      capturedBody = options?.body;
      return new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const formData = new FormData();
    formData.append("revised", "true");

    // Test apiClient.put with FormData
    await apiClient.put("/api/v1/test-put-form", formData);
    assert.equal(capturedMethod, "PUT");
    assert.equal(capturedHeaders["Content-Type"], undefined);
    assert.equal(capturedBody instanceof FormData, true);

    // Test apiClient.postForm with FormData
    await apiClient.postForm("/api/v1/test-post-form", formData);
    assert.equal(capturedMethod, "POST");
    assert.equal(capturedHeaders["Content-Type"], undefined);
    assert.equal(capturedBody instanceof FormData, true);
  });
});

describe("12. Team Lead Task Creation & Date Validation (US-09)", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("validateTaskDates enforces due_date >= start_date strictly", () => {
    // Both missing or one missing -> valid
    assert.equal(validateTaskDates(null, null).valid, true);
    assert.equal(validateTaskDates("2026-11-15", null).valid, true);
    assert.equal(validateTaskDates(null, "2026-11-20").valid, true);

    // due_date equals start_date -> valid
    assert.equal(validateTaskDates("2026-11-15", "2026-11-15").valid, true);

    // due_date after start_date -> valid
    assert.equal(validateTaskDates("2026-11-15", "2026-11-20").valid, true);

    // due_date earlier than start_date -> invalid
    const invalidCheck = validateTaskDates("2026-11-20", "2026-11-15");
    assert.equal(invalidCheck.valid, false);
    assert.match(invalidCheck.error, /cannot be earlier/i);

    // Malformed dates
    const malformed = validateTaskDates("not-a-date", "2026-11-20");
    assert.equal(malformed.valid, false);
  });

  test("createTask validates required fields before dispatching", async () => {
    await assert.rejects(
      async () => createTask(null),
      /Task payload is required/
    );

    await assert.rejects(
      async () => createTask({ project_id: 1, team_id: 2, title: "   " }),
      /Task title is required/
    );

    await assert.rejects(
      async () => createTask({ title: "Build feature", team_id: 2 }),
      /valid project ID is required/
    );

    await assert.rejects(
      async () => createTask({ title: "Build feature", project_id: 1 }),
      /valid team ID is required/
    );

    await assert.rejects(
      async () => createTask({
        title: "Build feature",
        project_id: 1,
        team_id: 2,
        start_date: "2026-11-20",
        due_date: "2026-11-10",
      }),
      /Due date cannot be earlier than start date/
    );
  });

  test("createTask dispatches POST /api/v1/tasks with normalized payload", async () => {
    let capturedUrl = "";
    let capturedBody = null;
    let capturedMethod = "";

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options.method;
      capturedBody = JSON.parse(options.body);
      return new Response(JSON.stringify({
        task_id: 88,
        title: capturedBody.title,
        status: "TODO",
        progress_pct: 0,
      }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await createTask({
      project_id: 1,
      team_id: 3,
      milestone_id: 5,
      assigned_to: 12,
      title: "  Implement Team Lead Task Board  ",
      description: "Mission control for team tasks",
      priority: "high",
      start_date: "2026-11-16",
      due_date: "2026-11-25",
    });

    assert.equal(capturedMethod, "POST");
    assert.match(capturedUrl, /\/api\/v1\/tasks$/);
    assert.equal(capturedBody.title, "Implement Team Lead Task Board");
    assert.equal(capturedBody.project_id, 1);
    assert.equal(capturedBody.team_id, 3);
    assert.equal(capturedBody.milestone_id, 5);
    assert.equal(capturedBody.assigned_to, 12);
    assert.equal(capturedBody.priority, "HIGH");
    assert.equal(capturedBody.start_date, "2026-11-16");
    assert.equal(capturedBody.due_date, "2026-11-25");
    assert.equal(res.task_id, 88);
  });
});

describe("13. Task Assignment & Reassignment (US-09 & US-14)", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("validateReassignReason requires minimum 10 non-whitespace characters", () => {
    assert.equal(validateReassignReason("").valid, false);
    assert.equal(validateReassignReason("   ").valid, false);
    assert.equal(validateReassignReason("Short").valid, false);

    const validReason = validateReassignReason("Employee on sick leave until next Monday");
    assert.equal(validReason.valid, true);
  });

  test("assignTask dispatches PUT /api/v1/tasks/{id}/assign", async () => {
    let capturedUrl = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedBody = JSON.parse(options.body);
      return new Response(JSON.stringify({ task_id: 10, assigned_to: capturedBody.assignee_id }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await assignTask(10, 15);
    assert.match(capturedUrl, /\/api\/v1\/tasks\/10\/assign/);
    assert.equal(capturedBody.assignee_id, 15);
    assert.equal(res.assigned_to, 15);
  });

  test("reassignTask validates reason and dispatches PUT /api/v1/tasks/{id}/reassign", async () => {
    await assert.rejects(
      async () => reassignTask(10, { new_assignee_id: 15, reason: "Too short" }),
      /Reason must be at least 10 characters/
    );

    let capturedUrl = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedBody = JSON.parse(options.body);
      return new Response(JSON.stringify({ task_id: 10, assigned_to: capturedBody.new_assignee_id }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await reassignTask(10, {
      new_assignee_id: 18,
      reason: "Reallocating workload due to emergency critical bug",
    });

    assert.match(capturedUrl, /\/api\/v1\/tasks\/10\/reassign/);
    assert.equal(capturedBody.new_assignee_id, 18);
    assert.equal(capturedBody.reason, "Reallocating workload due to emergency critical bug");
    assert.equal(res.assigned_to, 18);
  });
});

describe("14. Review Triage Queue & Review Decision Engine (US-12 & US-13)", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("validateRejectionFeedback requires at least 10 non-whitespace characters", () => {
    assert.equal(validateRejectionFeedback("").valid, false);
    assert.equal(validateRejectionFeedback("   ").valid, false);
    assert.equal(validateRejectionFeedback("Fix this").valid, false);

    const validFeedback = validateRejectionFeedback("Missing unit tests for edge conditions.");
    assert.equal(validFeedback.valid, true);
  });

  test("getReviewQueue formats query parameters correctly", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(JSON.stringify([
        { task_id: 1, title: "Review item", status: "IN_REVIEW" },
      ]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const items = await getReviewQueue({ priority: "high", page: 2, limit: 10 });
    assert.match(capturedUrl, /\/api\/v1\/tasks\/review-queue\?priority=HIGH&page=2&limit=10/);
    assert.equal(items.length, 1);
  });

  test("reviewTask dispatches APPROVE decision cleanly", async () => {
    let capturedUrl = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedBody = JSON.parse(options.body);
      return new Response(JSON.stringify({
        task_id: 42,
        status: "DONE",
        progress_pct: 100,
        message: "Task approved successfully",
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await reviewTask(42, { decision: "APPROVE" });
    assert.match(capturedUrl, /\/api\/v1\/tasks\/42\/review/);
    assert.equal(capturedBody.decision, "APPROVE");
    assert.equal(capturedBody.feedback, null);
    assert.equal(res.status, "DONE");
    assert.equal(res.progress_pct, 100);
  });

  test("reviewTask enforces mandatory rejection feedback before dispatching", async () => {
    await assert.rejects(
      async () => reviewTask(42, { decision: "REJECT", feedback: "Too short" }),
      /Feedback must be at least 10 characters/
    );

    let capturedUrl = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedBody = JSON.parse(options.body);
      return new Response(JSON.stringify({
        task_id: 42,
        status: "REJECTED",
        rejection_feedback: capturedBody.feedback,
        message: "Task rejected",
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await reviewTask(42, {
      decision: "REJECT",
      feedback: "Deliverable archive is missing documentation and test reports.",
    });

    assert.match(capturedUrl, /\/api\/v1\/tasks\/42\/review/);
    assert.equal(capturedBody.decision, "REJECT");
    assert.equal(capturedBody.feedback, "Deliverable archive is missing documentation and test reports.");
    assert.equal(res.status, "REJECTED");
  });

  test("getProjectTasks dispatches GET /api/v1/projects/{id}/tasks", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(JSON.stringify({ items: [], total: 0, page: 1, limit: 50 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    await getProjectTasks(10, { team_id: 4, status: "IN_PROGRESS" });
    assert.match(capturedUrl, /\/api\/v1\/projects\/10\/tasks\?team_id=4&status=IN_PROGRESS&page=1&limit=50/);
  });
});

describe("15. Task Discussion Thread & Comment API Contract (US-33)", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("validateCommentContent strictly enforces non-empty content and 2000 character boundary", () => {
    // Empty & whitespace tests
    assert.equal(validateCommentContent(null).valid, false);
    assert.equal(validateCommentContent(undefined).valid, false);
    assert.equal(validateCommentContent("").valid, false);
    assert.equal(validateCommentContent("    \n\t  ").valid, false);

    // Valid comment trimming
    const validResult = validateCommentContent("  Fixing the race condition in the auth token refresh handler.  ");
    assert.equal(validResult.valid, true);
    assert.equal(validResult.trimmed, "Fixing the race condition in the auth token refresh handler.");

    // Boundary check at exactly 2,000 characters
    const exact2000 = "a".repeat(2000);
    assert.equal(validateCommentContent(exact2000).valid, true);

    // Over boundary: 2,001 characters
    const over2000 = "a".repeat(2001);
    const overResult = validateCommentContent(over2000);
    assert.equal(overResult.valid, false);
    assert.match(overResult.error, /exceeds maximum length of 2000/);
  });

  test("getTaskComments dispatches GET /api/v1/tasks/{id}/comments correctly", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(JSON.stringify([
        {
          comment_id: 1,
          task_id: 55,
          author_name: "Alice Johnson",
          author_role: "Senior Backend Engineer",
          content: "Initial database migration deployed.",
          created_at: "2026-11-16T10:00:00Z",
        },
      ]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const comments = await getTaskComments(55);
    assert.match(capturedUrl, /\/api\/v1\/tasks\/55\/comments$/);
    assert.equal(comments.length, 1);
    assert.equal(comments[0].comment_id, 1);
    assert.equal(comments[0].author_name, "Alice Johnson");
  });

  test("createTaskComment validates and dispatches POST /api/v1/tasks/{id}/comments", async () => {
    // Rejects empty or whitespace-only
    await assert.rejects(
      async () => createTaskComment(55, "   "),
      /Comment cannot be blank/
    );

    // Rejects missing taskId
    await assert.rejects(
      async () => createTaskComment(null, "Valid content"),
      /Task ID is required/
    );

    let capturedUrl = "";
    let capturedMethod = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options.method;
      capturedBody = JSON.parse(options.body);
      return new Response(JSON.stringify({
        comment_id: 12,
        task_id: 55,
        author_name: "Ridhang Jain",
        author_role: "Team Lead",
        content: capturedBody.content,
        created_at: "2026-11-16T12:00:00Z",
      }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await createTaskComment(55, "  Please review unit tests for coverage on edge cases.  ");
    assert.equal(capturedMethod, "POST");
    assert.match(capturedUrl, /\/api\/v1\/tasks\/55\/comments$/);
    assert.equal(capturedBody.content, "Please review unit tests for coverage on edge cases.");
    assert.equal(res.comment_id, 12);
  });

  test("TaskCommentThread initial generator handles multi-word and single-word names cleanly", () => {
    function getInitials(name) {
      if (!name || typeof name !== "string") return "U";
      const parts = name.trim().split(/\s+/);
      if (parts.length >= 2) {
        return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
      }
      return parts[0].slice(0, 2).toUpperCase();
    }

    assert.equal(getInitials("Ridhang Jain"), "RJ");
    assert.equal(getInitials("Alice Marie Johnson"), "AJ");
    assert.equal(getInitials("Developer"), "DE");
    assert.equal(getInitials("X"), "X");
    assert.equal(getInitials(""), "U");
    assert.equal(getInitials(null), "U");
  });

  test("Optimistic comment structure conforms to TaskCommentResponse shape with isOptimistic flag", () => {
    const taskId = 88;
    const author = { full_name: "Ridhang Jain", role: "Team Lead" };
    const content = "Testing optimistic rollback behavior";

    const optimisticComment = {
      comment_id: `temp-${Date.now()}`,
      task_id: Number(taskId),
      author_name: author.full_name,
      author_role: author.role,
      content: content.trim(),
      created_at: new Date().toISOString(),
      isOptimistic: true,
    };

    assert.equal(optimisticComment.task_id, 88);
    assert.equal(optimisticComment.author_name, "Ridhang Jain");
    assert.equal(optimisticComment.author_role, "Team Lead");
    assert.equal(optimisticComment.isOptimistic, true);
    assert.match(optimisticComment.comment_id, /^temp-/);
  });
});

describe("16. Authenticated Deliverable Downloads & openDeliverable (Issue #162)", () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  const originalLocalStorage = globalThis.localStorage;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    if (originalWindow !== undefined) {
      globalThis.window = originalWindow;
    } else {
      delete globalThis.window;
    }
    if (originalLocalStorage !== undefined) {
      globalThis.localStorage = originalLocalStorage;
    } else {
      delete globalThis.localStorage;
    }
  });

  test("openDeliverable sends /api/... URLs to downloadAuthenticatedFile with Bearer token", async () => {
    let capturedUrl = null;
    let capturedHeaders = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedHeaders = options.headers;
      return {
        ok: true,
        status: 200,
        headers: {
          get: (name) => {
            if (name.toLowerCase() === "content-disposition") {
              return 'attachment; filename="deliverable.pdf"';
            }
            return null;
          },
        },
        blob: async () => ({ size: 1024, type: "application/pdf" }),
      };
    };

    globalThis.localStorage = {
      getItem: (k) => (k === "wms_access_token" ? "jwt-test-bearer-token" : null),
      setItem: () => {},
      removeItem: () => {},
    };

    await openDeliverable("/api/v1/tasks/42/submissions/5/file", "fallback.pdf");

    assert.ok(capturedUrl.includes("/api/v1/tasks/42/submissions/5/file"));
    assert.equal(capturedHeaders["Authorization"], "Bearer jwt-test-bearer-token");
  });

  test("openDeliverable routes external URLs to window.open with noopener,noreferrer", async () => {
    let openedUrl = null;
    let openedTarget = null;
    let openedFeatures = null;

    globalThis.window = {
      open: (url, target, features) => {
        openedUrl = url;
        openedTarget = target;
        openedFeatures = features;
        return {};
      },
    };

    const externalLink = "https://github.com/organization/repo/pull/123";
    await openDeliverable(externalLink);

    assert.equal(openedUrl, externalLink);
    assert.equal(openedTarget, "_blank");
    assert.equal(openedFeatures, "noopener,noreferrer");
  });
});
