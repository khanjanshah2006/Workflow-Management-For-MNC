import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";

import {
  validateRejectionRemarks,
  buildReallocationPayload,
  coverageLabel,
} from "../src/features/team_lead/leaveTriageUtils.js";

import {
  getPendingLeaveRequests,
  getLeaveConflicts,
  approveLeave,
  rejectLeave,
  reallocateLeaveTasks,
} from "../src/api/leaveApi.js";

import mockTriageData from "../src/features/team_lead/mockLeaveTriageData.json" with { type: "json" };

describe("1. Rejection Remarks Validation (validateRejectionRemarks)", () => {
  test("rejects null, undefined, or empty string", () => {
    const resNull = validateRejectionRemarks(null);
    assert.equal(resNull.isValid, false);
    assert.ok(resNull.error.includes("mandatory"));

    const resUndef = validateRejectionRemarks(undefined);
    assert.equal(resUndef.isValid, false);
    assert.ok(resUndef.error.includes("mandatory"));

    const resEmpty = validateRejectionRemarks("");
    assert.equal(resEmpty.isValid, false);
    assert.ok(resEmpty.error.includes("mandatory"));
  });

  test("rejects whitespace-only strings", () => {
    const res = validateRejectionRemarks("          ");
    assert.equal(res.isValid, false);
    assert.ok(res.error.includes("mandatory"));
  });

  test("rejects remarks with fewer than 10 non-whitespace characters", () => {
    const res = validateRejectionRemarks("   Short  ");
    assert.equal(res.isValid, false);
    assert.ok(res.error.includes("at least 10"));
  });

  test("accepts valid remarks with 10 or more characters", () => {
    const res = validateRejectionRemarks("Critical release requires full attendance.");
    assert.equal(res.isValid, true);
    assert.equal(res.error, null);
    assert.equal(res.length, "Critical release requires full attendance.".length);
  });

  test("accepts remarks with leading/trailing whitespace if trimmed length >= 10", () => {
    const res = validateRejectionRemarks("   Sprint deadline critical   ");
    assert.equal(res.isValid, true);
    assert.equal(res.error, null);
    assert.equal(res.length, "Sprint deadline critical".length);
  });

  test("rejects remarks exceeding 2000 characters", () => {
    const longRemarks = "a".repeat(2001);
    const res = validateRejectionRemarks(longRemarks);
    assert.equal(res.isValid, false);
    assert.ok(res.error.includes("cannot exceed 2000 characters"));
  });
});

describe("2. Task Reallocation Payload Builder (buildReallocationPayload)", () => {
  test("skips LEAVE_AS_IS selections and empty objects", () => {
    const selections = {
      42: { action: "LEAVE_AS_IS" },
      43: { action: "" },
    };
    const payload = buildReallocationPayload(selections);
    assert.deepEqual(payload, { actions: [] });
  });

  test("handles empty or null selections safely", () => {
    assert.deepEqual(buildReallocationPayload(null), { actions: [] });
    assert.deepEqual(buildReallocationPayload(undefined), { actions: [] });
    assert.deepEqual(buildReallocationPayload({}), { actions: [] });
  });

  test("correctly structures REASSIGN actions", () => {
    const selections = {
      42: {
        action: "REASSIGN",
        new_assignee_id: "12",
        reason: "John Matrix has capacity to cover this task",
      },
    };
    const payload = buildReallocationPayload(selections);
    assert.equal(payload.actions.length, 1);
    assert.deepEqual(payload.actions[0], {
      task_id: 42,
      action_type: "REASSIGN",
      new_assignee_id: 12,
      reason: "John Matrix has capacity to cover this task",
    });
  });

  test("correctly structures EXTEND_DEADLINE actions", () => {
    const selections = {
      43: {
        action: "EXTEND_DEADLINE",
        new_due_date: "2026-11-28",
        reason: "Milestone deferred until employee returns",
      },
    };
    const payload = buildReallocationPayload(selections);
    assert.equal(payload.actions.length, 1);
    assert.deepEqual(payload.actions[0], {
      task_id: 43,
      action_type: "EXTEND_DEADLINE",
      new_due_date: "2026-11-28",
      reason: "Milestone deferred until employee returns",
    });
  });

  test("combines multiple mixed actions while skipping LEAVE_AS_IS", () => {
    const selections = {
      42: {
        action: "REASSIGN",
        new_assignee_id: 12,
        reason: "Covered by John",
      },
      43: {
        action: "LEAVE_AS_IS",
      },
      44: {
        action: "EXTEND_DEADLINE",
        new_due_date: "2026-12-01",
        reason: "Extended",
      },
    };
    const payload = buildReallocationPayload(selections);
    assert.equal(payload.actions.length, 2);
    assert.equal(payload.actions[0].task_id, 42);
    assert.equal(payload.actions[0].action_type, "REASSIGN");
    assert.equal(payload.actions[1].task_id, 44);
    assert.equal(payload.actions[1].action_type, "EXTEND_DEADLINE");
  });
});

describe("3. Coverage Label Formatter (coverageLabel)", () => {
  test("formats available teammate with active task count", () => {
    const label = coverageLabel({
      has_leave_overlap: false,
      active_tasks_count: 2,
    });
    assert.equal(label, "Available · 2 active tasks");
  });

  test("formats teammate on leave via has_leave_overlap", () => {
    const label = coverageLabel({
      has_leave_overlap: true,
      active_tasks_count: 0,
    });
    assert.equal(label, "On leave");
  });

  test("formats teammate at capacity due to active tasks >= threshold", () => {
    const label = coverageLabel({
      has_leave_overlap: false,
      active_tasks_count: 5,
      availability_threshold: 5,
    });
    assert.equal(label, "At capacity (5 tasks)");
  });

  test("formats teammate unavailable for reassignment flag", () => {
    const label = coverageLabel({
      has_leave_overlap: false,
      is_available_for_reassignment: false,
      active_tasks_count: 3,
    });
    assert.equal(label, "At capacity (3 tasks)");
  });

  test("handles missing or null member gracefully", () => {
    assert.equal(coverageLabel(null), "Unavailable");
    assert.equal(coverageLabel(undefined), "Unavailable");
  });
});

describe("4. Mock Triage Fixture Conformance", () => {
  test("mockLeaveTriageData.json contains required root properties", () => {
    assert.ok(mockTriageData.pendingRequests !== null);
    assert.ok(Array.isArray(mockTriageData.pendingRequests.items));
    assert.ok(mockTriageData.conflictReports !== null);
  });

  test("pendingRequests entries have leave_id, employee_name, conflicting_task_count", () => {
    for (const req of mockTriageData.pendingRequests.items) {
      assert.ok(typeof req.leave_id === "number");
      assert.ok(typeof req.employee_name === "string");
      assert.ok(typeof req.conflicting_task_count === "number");
      assert.ok(typeof req.start_date === "string");
      assert.ok(typeof req.end_date === "string");
    }
  });

  test("conflictReports contain conflicting_tasks, milestone_conflicts, team_coverage", () => {
    const report = mockTriageData.conflictReports["1"];
    assert.ok(report);
    assert.ok(typeof report.leave_id === "number");
    assert.ok(Array.isArray(report.conflicting_tasks));
    assert.ok(Array.isArray(report.milestone_conflicts));
    assert.ok(Array.isArray(report.team_coverage));
  });

  test("conflicting tasks contain task_id, title, due_date", () => {
    const report = mockTriageData.conflictReports["1"];
    for (const task of report.conflicting_tasks) {
      assert.ok(typeof task.task_id === "number");
      assert.ok(typeof task.title === "string");
      assert.ok(typeof task.due_date === "string");
    }
  });
});

describe("5. Team Lead Leave API Functions (Mocked Fetch)", () => {
  const originalFetch = globalThis.fetch;
  let fetchCalls = [];

  beforeEach(() => {
    fetchCalls = [];
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("getPendingLeaveRequests dispatches GET to /api/v1/leave/requests/pending with params", async () => {
    globalThis.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          items: [{ leave_id: 1, employee_name: "Sarah Connor" }],
          total: 1,
          page: 1,
          limit: 20,
        }),
      };
    };

    const res = await getPendingLeaveRequests({ status: "PENDING", page: 1, limit: 20 });
    assert.equal(fetchCalls.length, 1);
    const call = fetchCalls[0];
    assert.ok(call.url.includes("/api/v1/leave/requests/pending"));
    assert.ok(call.url.includes("status=PENDING"));
    assert.ok(call.url.includes("page=1"));
    assert.ok(call.url.includes("limit=20"));
    assert.equal(call.options.method, "GET");
    assert.equal(res.items.length, 1);
    assert.equal(res.items[0].leave_id, 1);
  });

  test("getLeaveConflicts dispatches GET to /api/v1/leave/requests/{id}/conflicts", async () => {
    globalThis.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          leave_id: 1,
          conflicting_tasks: [{ task_id: 42, title: "DB Migration" }],
          milestone_conflicts: [],
          team_coverage: [],
        }),
      };
    };

    const res = await getLeaveConflicts(1);
    assert.equal(fetchCalls.length, 1);
    const call = fetchCalls[0];
    assert.ok(call.url.includes("/api/v1/leave/requests/1/conflicts"));
    assert.equal(call.options.method, "GET");
    assert.equal(res.leave_id, 1);
    assert.equal(res.conflicting_tasks.length, 1);
  });

  test("approveLeave dispatches PUT to /api/v1/leave/requests/{id}/approve", async () => {
    globalThis.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          leave_id: 1,
          status: "APPROVED",
          review_remarks: "Approved for medical reasons.",
        }),
      };
    };

    const res = await approveLeave(1, { review_remarks: "Approved for medical reasons." });
    assert.equal(fetchCalls.length, 1);
    const call = fetchCalls[0];
    assert.ok(call.url.includes("/api/v1/leave/requests/1/approve"));
    assert.equal(call.options.method, "PUT");
    assert.equal(JSON.parse(call.options.body).review_remarks, "Approved for medical reasons.");
    assert.equal(res.status, "APPROVED");
  });

  test("rejectLeave dispatches PUT to /api/v1/leave/requests/{id}/reject", async () => {
    globalThis.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          leave_id: 1,
          status: "REJECTED",
          review_remarks: "Team coverage insufficient during production release.",
        }),
      };
    };

    const res = await rejectLeave(1, {
      review_remarks: "Team coverage insufficient during production release.",
    });
    assert.equal(fetchCalls.length, 1);
    const call = fetchCalls[0];
    assert.ok(call.url.includes("/api/v1/leave/requests/1/reject"));
    assert.equal(call.options.method, "PUT");
    assert.equal(
      JSON.parse(call.options.body).review_remarks,
      "Team coverage insufficient during production release."
    );
    assert.equal(res.status, "REJECTED");
  });

  test("reallocateLeaveTasks dispatches POST to /api/v1/leave/requests/{id}/reallocate-tasks", async () => {
    globalThis.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          success: true,
          reallocated_count: 1,
        }),
      };
    };

    const actionsPayload = {
      actions: [
        {
          task_id: 42,
          action_type: "REASSIGN",
          new_assignee_id: 12,
          reason: "John takes over DB migration",
        },
      ],
    };

    const res = await reallocateLeaveTasks(1, actionsPayload);
    assert.equal(fetchCalls.length, 1);
    const call = fetchCalls[0];
    assert.ok(call.url.includes("/api/v1/leave/requests/1/reallocate-tasks"));
    assert.equal(call.options.method, "POST");
    assert.deepEqual(JSON.parse(call.options.body), actionsPayload);
    assert.equal(res.reallocated_count, 1);
  });

  test("reallocateLeaveTasks throws structured API error on 400 failure", async () => {
    globalThis.fetch = async () => {
      return {
        ok: false,
        status: 400,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          detail: "Selected teammate is over capacity",
          task_id: 42,
        }),
      };
    };

    const validPayload = {
      actions: [
        {
          task_id: 42,
          action_type: "REASSIGN",
          new_assignee_id: 12,
          reason: "John Matrix cover",
        },
      ],
    };

    await assert.rejects(
      async () => {
        await reallocateLeaveTasks(1, validPayload);
      },
      (err) => {
        assert.equal(err.status, 400);
        assert.equal(err.data.task_id, 42);
        assert.ok(err.message.includes("Selected teammate is over capacity"));
        return true;
      }
    );
  });
});
