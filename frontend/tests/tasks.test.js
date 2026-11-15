import { test, describe, afterEach } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
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
} from "../src/api/tasksApi.js";

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

  test("CONTRACT CHECK: does NOT search blocker_reason (GET /api/v1/tasks/my-tasks contract)", () => {
    // Even if an object carries a blocker_reason property, search MUST NOT match on it
    const taskWithBlocker = {
      ...SAMPLE_SUMMARY_TASKS[2],
      blocker_reason: "Specialized IT SecOps network egress allowance pending approval",
    };

    // "SecOps" and "egress" only exist in blocker_reason, NOT in title, task_id (103), or project_id (2)
    assert.equal(matchesTaskSearch(taskWithBlocker, "SecOps"), false);
    assert.equal(matchesTaskSearch(taskWithBlocker, "egress"), false);

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
