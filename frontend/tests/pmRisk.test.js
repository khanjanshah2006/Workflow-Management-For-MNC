import { test, describe, afterEach } from "node:test";
import assert from "node:assert/strict";

import {
  overdueChipLabel,
  riskTone,
  sortOverdue,
  statusBarSegments,
  STATUS_BAR_CONFIG,
} from "../src/features/project_manager/pmRiskUtils.js";

import {
  getProjectDashboard,
  getProjectRisks,
  getProjectTeamWorkload,
} from "../src/api/projectsApi.js";

import { getOverdueTasks } from "../src/api/tasksApi.js";

describe("1. PM Risk Dashboard - overdueChipLabel (US-15)", () => {
  test("formats 1 day overdue correctly with singular label", () => {
    assert.equal(overdueChipLabel(1), "1 day overdue");
    assert.equal(overdueChipLabel("1"), "1 day overdue");
  });

  test("formats N days overdue correctly with plural label", () => {
    assert.equal(overdueChipLabel(2), "2 days overdue");
    assert.equal(overdueChipLabel(5), "5 days overdue");
    assert.equal(overdueChipLabel("14"), "14 days overdue");
    assert.equal(overdueChipLabel(0), "0 days overdue");
  });

  test("handles negative, null, or invalid input gracefully", () => {
    assert.equal(overdueChipLabel(-3), "0 days overdue");
    assert.equal(overdueChipLabel(null), "0 days overdue");
    assert.equal(overdueChipLabel(undefined), "0 days overdue");
    assert.equal(overdueChipLabel("invalid"), "0 days overdue");
  });
});

describe("2. PM Risk Dashboard - riskTone Mapping (US-38)", () => {
  test("maps LOW score to low tone", () => {
    assert.equal(riskTone("LOW"), "low");
    assert.equal(riskTone("low"), "low");
  });

  test("maps MEDIUM score to medium tone", () => {
    assert.equal(riskTone("MEDIUM"), "medium");
    assert.equal(riskTone("medium"), "medium");
  });

  test("maps HIGH and CRITICAL score to high tone", () => {
    assert.equal(riskTone("HIGH"), "high");
    assert.equal(riskTone("high"), "high");
    assert.equal(riskTone("CRITICAL"), "high");
  });

  test("handles null or unrecognized values with safe fallback", () => {
    assert.equal(riskTone(null), "low");
    assert.equal(riskTone(""), "low");
    assert.equal(riskTone("UNKNOWN"), "low");
  });
});

describe("3. PM Risk Dashboard - sortOverdue Stability (US-15)", () => {
  test("preserves stable tie-breaker relative order for identical keys", () => {
    const tasks = [
      { task_id: 1, title: "Task Alpha", days_overdue: 5, priority: "HIGH" },
      { task_id: 2, title: "Task Beta", days_overdue: 5, priority: "HIGH" },
      { task_id: 3, title: "Task Gamma", days_overdue: 5, priority: "MEDIUM" },
      { task_id: 4, title: "Task Delta", days_overdue: 5, priority: "HIGH" },
    ];

    // Sort by days_overdue (all equal): order should remain 1, 2, 3, 4
    const sorted = sortOverdue(tasks, "days_overdue", "asc");
    assert.deepEqual(
      sorted.map((t) => t.task_id),
      [1, 2, 3, 4]
    );

    // Descending also preserves stability for identical values
    const sortedDesc = sortOverdue(tasks, "days_overdue", "desc");
    assert.deepEqual(
      sortedDesc.map((t) => t.task_id),
      [1, 2, 3, 4]
    );
  });

  test("sorts by numeric days_overdue ascending and descending", () => {
    const tasks = [
      { task_id: 10, title: "Ten", days_overdue: 2 },
      { task_id: 20, title: "Twenty", days_overdue: 8 },
      { task_id: 30, title: "Thirty", days_overdue: 5 },
    ];

    const asc = sortOverdue(tasks, "days_overdue", "asc");
    assert.deepEqual(
      asc.map((t) => t.task_id),
      [10, 30, 20]
    );

    const desc = sortOverdue(tasks, "days_overdue", "desc");
    assert.deepEqual(
      desc.map((t) => t.task_id),
      [20, 30, 10]
    );
  });

  test("sorts by priority with CRITICAL highest in desc order", () => {
    const tasks = [
      { task_id: 1, priority: "LOW" },
      { task_id: 2, priority: "CRITICAL" },
      { task_id: 3, priority: "HIGH" },
      { task_id: 4, priority: "MEDIUM" },
    ];

    const sortedDesc = sortOverdue(tasks, "priority", "desc");
    assert.deepEqual(
      sortedDesc.map((t) => t.priority),
      ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    );
  });

  test("does not mutate original array", () => {
    const original = [{ task_id: 2, days: 5 }, { task_id: 1, days: 2 }];
    const copy = [...original];
    sortOverdue(original, "days", "asc");
    assert.deepEqual(original, copy);
  });
});

describe("4. PM Risk Dashboard - statusBarSegments Sums to 100% (US-23)", () => {
  test("ensures segment percentages add up to exactly 100% across all six statuses", () => {
    // Seed project shape: total = 8
    const tasksByStatus = {
      DONE: 3,
      TODO: 1,
      IN_PROGRESS: 1,
      BLOCKED: 1,
      REJECTED: 1,
      IN_REVIEW: 1,
    };
    const segments = statusBarSegments(tasksByStatus, 8);

    assert.equal(segments.length, 6);
    const sum = segments.reduce((acc, s) => acc + s.pct, 0);
    assert.equal(Math.round(sum * 10) / 10, 100);
  });

  test("handles uneven divisions like 1/3 and absorbs rounding delta to 100%", () => {
    const tasksByStatus = {
      DONE: 1,
      IN_PROGRESS: 1,
      TODO: 1,
      BLOCKED: 0,
      REJECTED: 0,
      IN_REVIEW: 0,
    };
    const segments = statusBarSegments(tasksByStatus, 3);
    const sum = segments.reduce((acc, s) => acc + s.pct, 0);
    assert.equal(Math.round(sum * 10) / 10, 100);
  });

  test("handles empty or zero-task projects safely", () => {
    const segments = statusBarSegments({}, 0);
    assert.equal(segments.length, 6);
    segments.forEach((s) => assert.equal(s.pct, 0));
  });

  test("includes all six canonical statuses", () => {
    assert.deepEqual(
      STATUS_BAR_CONFIG.map((s) => s.status),
      ["DONE", "IN_REVIEW", "IN_PROGRESS", "TODO", "BLOCKED", "REJECTED"]
    );
  });
});

describe("5. PM Risk Dashboard - API Endpoints & Query Parameter URLs (US-15, US-23, US-38, US-39)", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("getProjectDashboard calls GET /api/v1/projects/{id}/dashboard", async () => {
    let capturedUrl = "";
    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(JSON.stringify({ project_id: 42, total_tasks: 10 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const data = await getProjectDashboard(42);
    assert.match(capturedUrl, /\/api\/v1\/projects\/42\/dashboard$/);
    assert.equal(data.project_id, 42);
  });

  test("getProjectRisks includes assignee_id and include_done queries", async () => {
    let capturedUrl = "";
    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(JSON.stringify({ project_id: 42, risk_score: "HIGH" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    await getProjectRisks(42, { assignee_id: 15, include_done: true });
    assert.match(capturedUrl, /\/api\/v1\/projects\/42\/risks\?assignee_id=15&include_done=true$/);
  });

  test("getProjectTeamWorkload calls GET /api/v1/projects/{id}/team-workload", async () => {
    let capturedUrl = "";
    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(JSON.stringify([{ emp_id: 1, full_name: "Sarah Connor" }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const workload = await getProjectTeamWorkload(42);
    assert.match(capturedUrl, /\/api\/v1\/projects\/42\/team-workload$/);
    assert.equal(workload.length, 1);
  });

  test("getOverdueTasks formats query parameters including project_id", async () => {
    let capturedUrl = "";
    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(
        JSON.stringify({
          total_overdue: 3,
          page: 1,
          limit: 20,
          items: [{ task_id: 101, days_overdue: 5 }],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    const res = await getOverdueTasks({
      project_id: 7,
      priority: "CRITICAL",
      page: 1,
      limit: 20,
    });

    assert.match(capturedUrl, /\/api\/v1\/tasks\/overdue\?project_id=7&priority=CRITICAL&page=1&limit=20$/);
    assert.equal(res.total_overdue, 3);
  });
});
