import { test, describe, afterEach } from "node:test";
import assert from "node:assert/strict";

import {
  validateSignoff,
  milestoneProgress,
  isMilestoneOverdue,
  deliverableStatusTone,
  milestoneStatusTone,
  formatDate,
} from "../src/features/client_portal/clientPortalUtils.js";

import {
  getClientProjects,
  getClientMilestones,
  getClientDeliverables,
  submitDeliverableFeedback,
  exportClientReportPdf,
  clientPortalApi,
} from "../src/api/clientPortalApi.js";

import { setSession, clearSession } from "../src/auth/session.js";
import { setStoredToken } from "../src/api/client.js";

// ============================================================================
// 1. Deliverable Signoff Validation (validateSignoff) - US-22
// ============================================================================
describe("1. Deliverable Signoff Validation (validateSignoff)", () => {
  test("fails when rating is missing, null, or empty", () => {
    const res1 = validateSignoff({ decision: "ACCEPTED" });
    assert.equal(res1.isValid, false);
    assert.match(res1.errors.rating, /rating between 1 and 5 is required/i);

    const res2 = validateSignoff({ decision: "ACCEPTED", rating: null });
    assert.equal(res2.isValid, false);
    assert.match(res2.errors.rating, /rating between 1 and 5 is required/i);

    const res3 = validateSignoff({ decision: "ACCEPTED", rating: "" });
    assert.equal(res3.isValid, false);
  });

  test("fails when rating is outside 1-5 or non-integer", () => {
    assert.equal(validateSignoff({ decision: "ACCEPTED", rating: 0 }).isValid, false);
    assert.equal(validateSignoff({ decision: "ACCEPTED", rating: 6 }).isValid, false);
    assert.equal(validateSignoff({ decision: "ACCEPTED", rating: 3.5 }).isValid, false);
    assert.equal(validateSignoff({ decision: "ACCEPTED", rating: "abc" }).isValid, false);
  });

  test("fails when decision is missing or invalid", () => {
    const res1 = validateSignoff({ rating: 5 });
    assert.equal(res1.isValid, false);
    assert.match(res1.errors.decision, /ACCEPTED or CHANGES_REQUESTED/i);

    const res2 = validateSignoff({ rating: 5, decision: "MAYBE" });
    assert.equal(res2.isValid, false);
    assert.match(res2.errors.decision, /ACCEPTED or CHANGES_REQUESTED/i);
  });

  test("fails when decision is CHANGES_REQUESTED and comments are missing or whitespace", () => {
    const res1 = validateSignoff({ decision: "CHANGES_REQUESTED", rating: 3 });
    assert.equal(res1.isValid, false);
    assert.match(res1.errors.comments, /mandatory when requesting changes/i);

    const res2 = validateSignoff({
      decision: "CHANGES_REQUESTED",
      rating: 3,
      comments: "   ",
    });
    assert.equal(res2.isValid, false);
    assert.match(res2.errors.comments, /mandatory when requesting changes/i);
  });

  test("fails when comments exceed 4000 characters", () => {
    const longComment = "a".repeat(4001);
    const res = validateSignoff({
      decision: "CHANGES_REQUESTED",
      rating: 2,
      comments: longComment,
    });
    assert.equal(res.isValid, false);
    assert.match(res.errors.comments, /cannot exceed 4000 characters/i);
  });

  test("passes when decision is ACCEPTED with or without comments", () => {
    const res1 = validateSignoff({ decision: "ACCEPTED", rating: 5 });
    assert.equal(res1.isValid, true);
    assert.deepEqual(res1.errors, {});

    const res2 = validateSignoff({
      decision: "ACCEPTED",
      rating: 4,
      comments: "Looks great, approved!",
    });
    assert.equal(res2.isValid, true);
  });

  test("passes when decision is CHANGES_REQUESTED with valid comments", () => {
    const res = validateSignoff({
      decision: "CHANGES_REQUESTED",
      rating: 2,
      comments: "Please update section 3 metrics as discussed.",
    });
    assert.equal(res.isValid, true);
    assert.deepEqual(res.errors, {});
  });
});

// ============================================================================
// 2. Milestone Progress Calculation (milestoneProgress) - US-20, US-21
// ============================================================================
describe("2. Milestone Progress Calculation (milestoneProgress)", () => {
  test("handles empty or non-array input safely", () => {
    assert.deepEqual(milestoneProgress([]), {
      total: 0,
      completed: 0,
      pending: 0,
      percentage: 0,
    });
    assert.deepEqual(milestoneProgress(null), {
      total: 0,
      completed: 0,
      pending: 0,
      percentage: 0,
    });
    assert.deepEqual(milestoneProgress(undefined), {
      total: 0,
      completed: 0,
      pending: 0,
      percentage: 0,
    });
  });

  test("calculates accurate completed, pending, and percentage metrics", () => {
    const milestones = [
      { id: 1, status: "completed" },
      { id: 2, status: "pending" },
      { id: 3, status: "completed" },
      { id: 4, status: "in_progress" },
    ];
    const result = milestoneProgress(milestones);
    assert.equal(result.total, 4);
    assert.equal(result.completed, 2);
    assert.equal(result.pending, 2);
    assert.equal(result.percentage, 50);
  });

  test("handles 100% and 0% edge cases", () => {
    const allCompleted = [
      { id: 1, status: "completed" },
      { id: 2, status: "Completed" },
    ];
    assert.equal(milestoneProgress(allCompleted).percentage, 100);

    const noneCompleted = [
      { id: 1, status: "pending" },
      { id: 2, status: "in_progress" },
    ];
    assert.equal(milestoneProgress(noneCompleted).percentage, 0);
  });
});

// ============================================================================
// 3. Milestone Overdue Detection (isMilestoneOverdue) - US-21
// ============================================================================
describe("3. Milestone Overdue Detection (isMilestoneOverdue)", () => {
  const referenceDate = new Date("2026-11-20T12:00:00Z");

  test("returns true when target_date is in past and status is pending", () => {
    const milestone = { target_date: "2026-11-10", status: "pending" };
    assert.equal(isMilestoneOverdue(milestone, referenceDate), true);
  });

  test("returns false when target_date is in past but status is completed", () => {
    const milestone = { target_date: "2026-11-10", status: "completed" };
    assert.equal(isMilestoneOverdue(milestone, referenceDate), false);
  });

  test("returns false when target_date is in future and status is pending", () => {
    const milestone = { target_date: "2026-11-30", status: "pending" };
    assert.equal(isMilestoneOverdue(milestone, referenceDate), false);
  });

  test("returns false when milestone or target_date is invalid or missing", () => {
    assert.equal(isMilestoneOverdue(null, referenceDate), false);
    assert.equal(isMilestoneOverdue({}, referenceDate), false);
    assert.equal(isMilestoneOverdue({ target_date: "invalid-date" }, referenceDate), false);
  });
});

// ============================================================================
// 4. Status Tone & Format Helpers
// ============================================================================
describe("4. Status Tone & Format Helpers", () => {
  test("deliverableStatusTone maps correctly", () => {
    assert.equal(deliverableStatusTone("ACCEPTED"), "green");
    assert.equal(deliverableStatusTone("CHANGES_REQUESTED"), "red");
    assert.equal(deliverableStatusTone("PENDING_REVIEW"), "amber");
    assert.equal(deliverableStatusTone("PENDING"), "amber");
    assert.equal(deliverableStatusTone("UNKNOWN"), "grey");
    assert.equal(deliverableStatusTone(null), "grey");
  });

  test("milestoneStatusTone maps correctly", () => {
    assert.equal(milestoneStatusTone("completed"), "green");
    assert.equal(milestoneStatusTone("in_progress"), "blue");
    assert.equal(milestoneStatusTone("pending"), "amber");
    assert.equal(milestoneStatusTone("unknown"), "grey");
    assert.equal(milestoneStatusTone(null), "grey");
  });

  test("formatDate formats dates safely", () => {
    assert.equal(formatDate(null), "—");
    assert.equal(formatDate("invalid-date"), "—");
    assert.match(formatDate("2026-11-20"), /Nov 20, 2026/);
  });
});

// ============================================================================
// 5. Client Portal API Client Integration
// ============================================================================
describe("5. Client Portal API Client Integration", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    clearSession();
    setStoredToken("");
  });

  test("getClientProjects dispatches GET to /api/v1/client/projects", async () => {
    let capturedUrl = "";
    let capturedMethod = "";

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options?.method || "GET";
      return new Response(
        JSON.stringify([
          {
            project_id: 1,
            project_code: "PRJ-001",
            name: "Cloud Transformation",
            status: "ACTIVE",
            start_date: "2026-01-01",
            completion_pct: 60.0,
            milestones_summary: { total: 5, completed: 3, pending: 2 },
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const projects = await getClientProjects();
    assert.match(capturedUrl, /\/api\/v1\/client\/projects$/);
    assert.equal(capturedMethod, "GET");
    assert.equal(projects.length, 1);
    assert.equal(projects[0].project_code, "PRJ-001");
  });

  test("getClientMilestones dispatches GET to /api/v1/client/projects/{id}/milestones", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(
        JSON.stringify([
          { id: 10, project_id: 1, title: "Architecture Signoff", status: "completed" },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const milestones = await getClientMilestones(1);
    assert.match(capturedUrl, /\/api\/v1\/client\/projects\/1\/milestones$/);
    assert.equal(milestones.length, 1);
    assert.equal(milestones[0].title, "Architecture Signoff");
  });

  test("getClientDeliverables dispatches GET to /api/v1/client/projects/{id}/deliverables", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(
        JSON.stringify([
          { deliverable_id: 100, project_id: 1, title: "Sprint 1 Report", status: "PENDING_REVIEW" },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const deliverables = await getClientDeliverables(1);
    assert.match(capturedUrl, /\/api\/v1\/client\/projects\/1\/deliverables$/);
    assert.equal(deliverables.length, 1);
    assert.equal(deliverables[0].title, "Sprint 1 Report");
  });

  test("submitDeliverableFeedback dispatches POST to /api/v1/client/deliverables/{id}/feedback", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options?.method;
      capturedBody = JSON.parse(options?.body || "{}");
      return new Response(
        JSON.stringify({
          deliverable_id: 100,
          status: capturedBody.decision,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const payload = {
      decision: "ACCEPTED",
      rating: 5,
      comments: "  Excellent delivery!  ",
    };

    const result = await submitDeliverableFeedback(100, payload);
    assert.match(capturedUrl, /\/api\/v1\/client\/deliverables\/100\/feedback$/);
    assert.equal(capturedMethod, "POST");
    assert.equal(capturedBody.decision, "ACCEPTED");
    assert.equal(capturedBody.rating, 5);
    assert.equal(capturedBody.comments, "Excellent delivery!");
    assert.equal(result.status, "ACCEPTED");
  });

  test("exportClientReportPdf dispatches authenticated file download", async () => {
    let capturedUrl = "";
    let capturedHeaders = {};

    setSession({ access_token: "test-client-jwt" });
    setStoredToken("test-client-jwt");

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedHeaders = options?.headers || {};
      return new Response(new Blob(["%PDF-1.4 report content"], { type: "application/pdf" }), {
        status: 200,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": 'attachment; filename="Project_Report_1.pdf"',
        },
      });
    };

    const result = await exportClientReportPdf(1);
    assert.match(capturedUrl, /\/api\/v1\/client\/projects\/1\/report\/export$/);
    assert.equal(capturedHeaders.Authorization, "Bearer test-client-jwt");
    assert.equal(result.filename, "Project_Report_1.pdf");
  });

  test("clientPortalApi exports match individual named function exports", () => {
    assert.equal(clientPortalApi.getClientProjects, getClientProjects);
    assert.equal(clientPortalApi.getClientMilestones, getClientMilestones);
    assert.equal(clientPortalApi.getClientDeliverables, getClientDeliverables);
    assert.equal(clientPortalApi.submitDeliverableFeedback, submitDeliverableFeedback);
    assert.equal(clientPortalApi.exportClientReportPdf, exportClientReportPdf);
  });
});

// ============================================================================
// 6. Client Portal Navigation & Role Separation (US-20)
// ============================================================================
describe("6. Client Portal Navigation & Role Separation (US-20)", () => {
  test("CLIENT role default home redirects to /client/projects", async () => {
    const { getHomeRouteForRole, INTERNAL_ROLES } = await import("../src/auth/session.js");
    assert.equal(getHomeRouteForRole("CLIENT"), "/client/projects");
    assert.equal(INTERNAL_ROLES.includes("CLIENT"), false);
  });

  test("CLIENT has zero internal navigation items in default navConfig", async () => {
    const { navConfig, filterNavForRole } = await import("../src/components/layout/navConfig.js");
    const clientNav = filterNavForRole(navConfig, "CLIENT");
    assert.equal(clientNav.length, 0);
  });

  test("Milestones are sorted chronologically by target_date", () => {
    const milestones = [
      { id: 1, title: "M3", target_date: "2026-12-01" },
      { id: 2, title: "M1", target_date: "2026-10-15" },
      { id: 3, title: "M2", target_date: "2026-11-05" },
    ];
    const sorted = [...milestones].sort(
      (a, b) => new Date(a.target_date).getTime() - new Date(b.target_date).getTime()
    );
    assert.equal(sorted[0].title, "M1");
    assert.equal(sorted[1].title, "M2");
    assert.equal(sorted[2].title, "M3");
  });
});
