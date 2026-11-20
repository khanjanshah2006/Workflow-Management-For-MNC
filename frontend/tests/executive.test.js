import { test, describe, afterEach } from "node:test";
import assert from "node:assert/strict";

import {
  validateReportForm,
  formatVelocity,
  statusSegments,
  formatBytes,
  STATUS_COLORS,
  STATUS_LABELS,
} from "../src/features/executive/executiveUtils.js";

import {
  getExecutiveDashboard,
  getDepartmentDrilldown,
  generateReport,
  listReports,
  getReport,
  downloadReport,
  executiveApi,
} from "../src/api/executiveApi.js";

import { setStoredToken } from "../src/api/client.js";
import { setSession, clearSession } from "../src/auth/session.js";
import { navConfig, filterNavForRole } from "../src/components/layout/navConfig.js";

// ============================================================================
// 1. Report Form Validation (validateReportForm)
// ============================================================================
describe("1. Executive Report Form Validation (validateReportForm)", () => {
  const TODAY = "2026-11-20";

  test("valid date range of exactly 366 days is accepted", () => {
    const form = {
      report_title: "Annual Delivery Audit",
      period_start: "2025-11-19",
      period_end: "2026-11-20", // 366 days
      format: "PDF",
      include_department_breakdown: true,
    };
    const result = validateReportForm(form, TODAY);
    assert.equal(result.isValid, true);
    assert.deepEqual(result.errors, {});
  });

  test("invalid date range exceeding 366 days is rejected", () => {
    const form = {
      report_title: "Overextended Period Audit",
      period_start: "2025-11-18",
      period_end: "2026-11-20", // 367 days
      format: "PDF",
    };
    const result = validateReportForm(form, TODAY);
    assert.equal(result.isValid, false);
    assert.match(result.errors.period_end, /cannot exceed 366 days/i);
  });

  test("future start date is rejected", () => {
    const form = {
      report_title: "Future Performance Projections",
      period_start: "2026-11-21", // 1 day after TODAY
      period_end: "2026-11-25",
      format: "PDF",
    };
    const result = validateReportForm(form, TODAY);
    assert.equal(result.isValid, false);
    assert.match(result.errors.period_start, /cannot be in the future/i);
  });

  test("end date before start date is rejected", () => {
    const form = {
      report_title: "Reverse Chronology Error",
      period_start: "2026-10-15",
      period_end: "2026-10-10",
      format: "PDF",
    };
    const result = validateReportForm(form, TODAY);
    assert.equal(result.isValid, false);
    assert.match(result.errors.period_end, /cannot precede start date/i);
  });

  test("title shorter than 3 characters is rejected", () => {
    const cases = ["", "  ", "a", "ab"];
    for (const title of cases) {
      const form = {
        report_title: title,
        period_start: "2026-09-01",
        period_end: "2026-11-01",
        format: "CSV",
      };
      const result = validateReportForm(form, TODAY);
      assert.equal(result.isValid, false);
      assert.ok(result.errors.report_title);
    }
  });

  test("title longer than 255 characters is rejected", () => {
    const longTitle = "A".repeat(256);
    const form = {
      report_title: longTitle,
      period_start: "2026-09-01",
      period_end: "2026-11-01",
      format: "PDF",
    };
    const result = validateReportForm(form, TODAY);
    assert.equal(result.isValid, false);
    assert.match(result.errors.report_title, /cannot exceed 255 characters/i);
  });

  test("invalid or missing values are safely handled", () => {
    // null form
    const nullResult = validateReportForm(null, TODAY);
    assert.equal(nullResult.isValid, false);
    assert.ok(nullResult.errors.report_title);
    assert.ok(nullResult.errors.period_start);
    assert.ok(nullResult.errors.period_end);

    // empty object
    const emptyResult = validateReportForm({}, TODAY);
    assert.equal(emptyResult.isValid, false);

    // invalid date formats
    const invalidDateResult = validateReportForm(
      {
        report_title: "Valid Title",
        period_start: "not-a-date",
        period_end: "invalid",
        format: "PDF",
      },
      TODAY
    );
    assert.equal(invalidDateResult.isValid, false);
    assert.match(invalidDateResult.errors.period_start, /invalid/i);
    assert.match(invalidDateResult.errors.period_end, /invalid/i);

    // invalid format
    const invalidFormatResult = validateReportForm(
      {
        report_title: "Valid Title",
        period_start: "2026-09-01",
        period_end: "2026-10-01",
        format: "EXE",
      },
      TODAY
    );
    assert.equal(invalidFormatResult.isValid, false);
    assert.match(invalidFormatResult.errors.format, /PDF or CSV/i);
  });
});

// ============================================================================
// 2. Velocity Formatter (formatVelocity)
// ============================================================================
describe("2. Milestone Velocity Formatter (formatVelocity)", () => {
  test("formats 0 to 0.0%", () => {
    assert.equal(formatVelocity(0), "0.0%");
    assert.equal(formatVelocity("0"), "0.0%");
  });

  test("formats 76.5 to 76.5%", () => {
    assert.equal(formatVelocity(76.5), "76.5%");
    assert.equal(formatVelocity("76.5"), "76.5%");
  });

  test("formats 100 to 100.0%", () => {
    assert.equal(formatVelocity(100), "100.0%");
    assert.equal(formatVelocity(100.0), "100.0%");
  });

  test("handles missing, null, undefined, or NaN values gracefully", () => {
    assert.equal(formatVelocity(null), "0.0%");
    assert.equal(formatVelocity(undefined), "0.0%");
    assert.equal(formatVelocity(NaN), "0.0%");
    assert.equal(formatVelocity("invalid-num"), "0.0%");
  });
});

// ============================================================================
// 3. Status Bar Segments Calculation (statusSegments)
// ============================================================================
describe("3. Project Status Distribution Segments (statusSegments)", () => {
  test("calculates correct percentages for standard breakdown", () => {
    const counts = {
      PLANNED: 10,
      ACTIVE: 20,
      ON_HOLD: 10,
      COMPLETED: 50,
      CANCELLED: 10,
    };
    const segments = statusSegments(counts);
    assert.equal(segments.length, 5);

    const planned = segments.find((s) => s.status === "PLANNED");
    const active = segments.find((s) => s.status === "ACTIVE");
    const completed = segments.find((s) => s.status === "COMPLETED");

    assert.equal(planned.percentage, 10.0);
    assert.equal(active.percentage, 20.0);
    assert.equal(completed.percentage, 50.0);
  });

  test("guarantees total percentage equals exactly 100.0 when there are projects", () => {
    // 1 / 3 = 33.3333% each -> raw round would be 33.3 * 3 = 99.9%
    const counts = {
      PLANNED: 1,
      ACTIVE: 1,
      ON_HOLD: 1,
      COMPLETED: 0,
      CANCELLED: 0,
    };
    const segments = statusSegments(counts);
    const sum = segments.reduce((acc, s) => acc + s.percentage, 0);
    assert.equal(Math.round(sum * 10) / 10, 100.0);
  });

  test("safely handles zero-project case without NaN or division by zero", () => {
    const zeroCounts = {
      PLANNED: 0,
      ACTIVE: 0,
      ON_HOLD: 0,
      COMPLETED: 0,
      CANCELLED: 0,
    };
    const segments = statusSegments(zeroCounts);
    assert.equal(segments.length, 5);
    for (const seg of segments) {
      assert.equal(seg.count, 0);
      assert.equal(seg.percentage, 0);
      assert.equal(typeof seg.color, "string");
      assert.equal(typeof seg.label, "string");
    }
  });

  test("safely handles missing status keys and empty objects", () => {
    // Missing some keys
    const partial = { ACTIVE: 4 };
    const segments = statusSegments(partial);
    const active = segments.find((s) => s.status === "ACTIVE");
    const planned = segments.find((s) => s.status === "PLANNED");

    assert.equal(active.count, 4);
    assert.equal(active.percentage, 100.0);
    assert.equal(planned.count, 0);
    assert.equal(planned.percentage, 0.0);

    // Empty or non-object input
    const empty = statusSegments({});
    assert.equal(empty.length, 5);
    assert.equal(empty[0].percentage, 0);

    const nullInput = statusSegments(null);
    assert.equal(nullInput.length, 5);
  });

  test("exports valid STATUS_COLORS and STATUS_LABELS mappings", () => {
    assert.equal(STATUS_COLORS.ACTIVE, "#2563eb");
    assert.equal(STATUS_LABELS.ACTIVE, "Active");
    assert.equal(STATUS_COLORS.COMPLETED, "#10b981");
    assert.equal(STATUS_LABELS.COMPLETED, "Completed");
  });
});

// ============================================================================
// 4. File Size Formatter (formatBytes)
// ============================================================================
describe("4. File Size Formatter (formatBytes)", () => {
  test("formats byte sizes accurately", () => {
    assert.equal(formatBytes(0), "0 B");
    assert.equal(formatBytes(512), "512 B");
    assert.equal(formatBytes(1024), "1.0 KB");
    assert.equal(formatBytes(1536), "1.5 KB");
    assert.equal(formatBytes(1048576), "1.0 MB");
    assert.equal(formatBytes(124580), "121.7 KB");
    assert.equal(formatBytes(null), "0 B");
  });
});

// ============================================================================
// 5. Executive API Integration Tests
// ============================================================================
describe("5. Executive API Client Integration", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    clearSession();
    setStoredToken("");
  });

  test("getExecutiveDashboard dispatches GET to /api/v1/executive/dashboard", async () => {
    let capturedUrl = "";
    let capturedMethod = "";

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options?.method || "GET";
      return new Response(
        JSON.stringify({
          total_projects: 10,
          active_projects: 4,
          delayed_projects: 1,
          completed_projects: 3,
          overall_milestone_velocity_pct: 75.0,
          projects_by_status: { PLANNED: 2, ACTIVE: 4, ON_HOLD: 1, COMPLETED: 3, CANCELLED: 0 },
          task_kpis: { open_tasks: 20, overdue_tasks: 2, completed_last_30_days: 10 },
          total_employees: 50,
          department_summaries: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const data = await getExecutiveDashboard();
    assert.match(capturedUrl, /\/api\/v1\/executive\/dashboard$/);
    assert.equal(capturedMethod, "GET");
    assert.equal(data.total_projects, 10);
    assert.equal(data.active_projects, 4);
  });

  test("getDepartmentDrilldown dispatches GET to /api/v1/executive/dashboard/departments/{id}", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(
        JSON.stringify({
          dept_id: 3,
          dept_name: "Engineering",
          projects: [],
          teams: [],
          resource_allocation: {
            total_employees: 15,
            allocated_employees: 12,
            unallocated_employees: 3,
            headcount_by_designation: { "Lead Developer": 3 },
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const data = await getDepartmentDrilldown(3);
    assert.match(capturedUrl, /\/api\/v1\/executive\/dashboard\/departments\/3$/);
    assert.equal(data.dept_name, "Engineering");

    // Rejects null deptId
    await assert.rejects(() => getDepartmentDrilldown(null), /deptId is required/i);
  });

  test("generateReport dispatches POST with normalized payload", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options?.method;
      capturedBody = JSON.parse(options?.body || "{}");
      return new Response(
        JSON.stringify({
          report_id: 101,
          report_title: capturedBody.report_title,
          format: capturedBody.format,
          period_start: capturedBody.period_start,
          period_end: capturedBody.period_end,
          include_department_breakdown: capturedBody.include_department_breakdown,
          file_size_bytes: 45000,
          generated_at: "2026-11-20T21:00:00Z",
          download_url: "/api/v1/executive/reports/101/download",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      );
    };

    const payload = {
      report_title: "Q4 Performance Brief",
      period_start: "2026-10-01",
      period_end: "2026-11-20",
      format: "PDF",
      include_department_breakdown: true,
    };

    const report = await generateReport(payload);
    assert.match(capturedUrl, /\/api\/v1\/executive\/reports\/generate$/);
    assert.equal(capturedMethod, "POST");
    assert.equal(capturedBody.report_title, "Q4 Performance Brief");
    assert.equal(capturedBody.format, "PDF");
    assert.equal(capturedBody.include_department_breakdown, true);
    assert.equal(report.report_id, 101);
  });

  test("listReports dispatches GET with page and limit query parameters", async () => {
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
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const res = await listReports(2, 10);
    assert.match(capturedUrl, /\/api\/v1\/executive\/reports\?page=2&limit=10$/);
    assert.equal(res.page, 2);
    assert.equal(res.limit, 10);
  });

  test("getReport dispatches GET to /api/v1/executive/reports/{id}", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(
        JSON.stringify({
          report_id: 42,
          report_title: "Audit Brief",
          format: "PDF",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const report = await getReport(42);
    assert.match(capturedUrl, /\/api\/v1\/executive\/reports\/42$/);
    assert.equal(report.report_id, 42);
  });

  test("downloadReport calls authenticated file download on /api/v1/executive/reports/{id}/download", async () => {
    let capturedUrl = "";
    let capturedHeaders = {};

    setSession({ access_token: "test-exec-jwt-token" });
    setStoredToken("test-exec-jwt-token");

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedHeaders = options?.headers || {};
      return new Response(new Blob(["%PDF-1.4 report content"], { type: "application/pdf" }), {
        status: 200,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": 'attachment; filename="exec_report_88.pdf"',
        },
      });
    };

    const result = await downloadReport(88, "fallback_report.pdf");
    assert.match(capturedUrl, /\/api\/v1\/executive\/reports\/88\/download$/);
    assert.equal(capturedHeaders["Authorization"], "Bearer test-exec-jwt-token");
    assert.equal(result.filename, "exec_report_88.pdf");
  });

  test("executiveApi exports match individual named function exports", () => {
    assert.equal(executiveApi.getExecutiveDashboard, getExecutiveDashboard);
    assert.equal(executiveApi.getDepartmentDrilldown, getDepartmentDrilldown);
    assert.equal(executiveApi.generateReport, generateReport);
    assert.equal(executiveApi.listReports, listReports);
    assert.equal(executiveApi.getReport, getReport);
    assert.equal(executiveApi.downloadReport, downloadReport);
  });
});

// ============================================================================
// 6. Executive Navigation & Route Access Control
// ============================================================================
describe("6. Executive Navigation & Route Access Control", () => {
  test("MNC_EXECUTIVE can see /executive/console in navConfig", () => {
    const nav = filterNavForRole(navConfig, "MNC_EXECUTIVE");
    assert.equal(nav.some((item) => item.path === "/executive/console"), true);
  });

  test("ADMIN can see /executive/console in navConfig", () => {
    const nav = filterNavForRole(navConfig, "ADMIN");
    assert.equal(nav.some((item) => item.path === "/executive/console"), true);
  });

  test("SYSTEM_ADMIN can see /executive/console in navConfig", () => {
    const nav = filterNavForRole(navConfig, "SYSTEM_ADMIN");
    assert.equal(nav.some((item) => item.path === "/executive/console"), true);
  });

  test("EMPLOYEE cannot see /executive/console in navConfig", () => {
    const nav = filterNavForRole(navConfig, "EMPLOYEE");
    assert.equal(nav.some((item) => item.path === "/executive/console"), false);
  });

  test("CLIENT cannot see /executive/console in navConfig", () => {
    const nav = filterNavForRole(navConfig, "CLIENT");
    assert.equal(nav.some((item) => item.path === "/executive/console"), false);
  });

  test("TEAM_LEAD, PM, HR, IT_SUPPORT cannot see /executive/console in navConfig", () => {
    for (const r of ["TEAM_LEAD", "PM", "PROJECT_MANAGER", "HR", "IT_SUPPORT"]) {
      const nav = filterNavForRole(navConfig, r);
      assert.equal(
        nav.some((item) => item.path === "/executive/console"),
        false,
        `Role ${r} should not have executive console navigation`
      );
    }
  });
});
