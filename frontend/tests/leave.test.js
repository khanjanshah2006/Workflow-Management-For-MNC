import { test, describe, afterEach } from "node:test";
import assert from "node:assert/strict";

import {
  countBusinessDays,
  validateLeaveForm,
  leaveStatusTone,
  getLeaveStatusBadgeClass,
} from "../src/features/leave/leaveUtils.js";
import {
  getMyLeaveBalances,
  getLeavePolicies,
  submitLeaveRequest,
  getMyLeaveRequests,
  cancelLeaveRequest,
} from "../src/api/leaveApi.js";
import { setStoredToken } from "../src/api/client.js";

// ============================================================================
// 1. Business Days Calculation (countBusinessDays)
// ============================================================================
describe("1. countBusinessDays", () => {
  test("calculates single working day correctly", () => {
    // 2026-11-23 is Monday
    assert.equal(countBusinessDays("2026-11-23", "2026-11-23"), 1);
    // 2026-11-25 is Wednesday
    assert.equal(countBusinessDays("2026-11-25", "2026-11-25"), 1);
    // Accepts Date objects
    assert.equal(
      countBusinessDays(new Date(2026, 10, 23), new Date(2026, 10, 23)),
      1
    );
  });

  test("returns 0 for weekend days only", () => {
    // 2026-11-28 is Saturday, 2026-11-29 is Sunday
    assert.equal(countBusinessDays("2026-11-28", "2026-11-28"), 0); // Saturday
    assert.equal(countBusinessDays("2026-11-29", "2026-11-29"), 0); // Sunday
    assert.equal(countBusinessDays("2026-11-28", "2026-11-29"), 0); // Full weekend
  });

  test("calculates Friday to Monday spanning a weekend correctly", () => {
    // 2026-11-27 (Friday) to 2026-11-30 (Monday) -> Fri + Mon = 2 days (Sat, Sun excluded)
    assert.equal(countBusinessDays("2026-11-27", "2026-11-30"), 2);
  });

  test("calculates multi-week date ranges excluding all Saturdays and Sundays", () => {
    // Monday 2026-11-23 to Friday 2026-12-04 -> exactly 10 working days (2 full weeks)
    assert.equal(countBusinessDays("2026-11-23", "2026-12-04"), 10);
  });

  test("returns 0 when end date is earlier than start date or dates are invalid", () => {
    assert.equal(countBusinessDays("2026-11-30", "2026-11-27"), 0);
    assert.equal(countBusinessDays(null, "2026-11-27"), 0);
    assert.equal(countBusinessDays("2026-11-27", null), 0);
    assert.equal(countBusinessDays("", ""), 0);
  });
});

// ============================================================================
// 2. Form Validation (validateLeaveForm)
// ============================================================================
describe("2. validateLeaveForm", () => {
  const TODAY = "2026-11-23";
  const MOCK_BALANCES = [
    {
      leave_type_id: 1,
      leave_type_name: "Annual Leave",
      yearly_quota: 20,
      used_days: 5,
      pending_days: 2,
      available_days: 13,
      is_paid: true,
    },
    {
      leave_type_id: 2,
      leave_type_name: "Casual Leave",
      yearly_quota: 5,
      used_days: 3,
      pending_days: 0,
      available_days: 2,
      is_paid: true,
    },
    {
      leave_type_id: 3,
      leave_type_name: "Exhausted Leave",
      yearly_quota: 10,
      used_days: 10,
      pending_days: 0,
      available_days: 0,
      is_paid: true,
    },
  ];

  test("fails validation when start date is in the past", () => {
    const form = {
      leave_type_id: 1,
      start_date: "2026-11-20", // Past date relative to TODAY (2026-11-23)
      end_date: "2026-11-25",
      reason: "Applying for leave that already started.",
    };

    const result = validateLeaveForm(form, MOCK_BALANCES, TODAY);
    assert.equal(result.isValid, false);
    assert.ok(result.errors.start_date, "Should flag start_date as invalid");
    assert.match(
      result.errors.start_date,
      /today or later/i,
      "Error should specify start date must be today or later"
    );
  });

  test("fails validation when end date is before start date (reversed range)", () => {
    const form = {
      leave_type_id: 1,
      start_date: "2026-11-26",
      end_date: "2026-11-24", // End before start
      reason: "Inverted start and end date inputs.",
    };

    const result = validateLeaveForm(form, MOCK_BALANCES, TODAY);
    assert.equal(result.isValid, false);
    assert.ok(result.errors.end_date, "Should flag end_date as invalid");
    assert.match(
      result.errors.end_date,
      /on or after/i,
      "Error should specify end date must be on or after start date"
    );
  });

  test("fails validation when date range crosses calendar year boundary", () => {
    const form = {
      leave_type_id: 1,
      start_date: "2026-12-30",
      end_date: "2027-01-04", // Spanning 2026 into 2027
      reason: "Year-end vacation spanning into next year.",
    };

    const result = validateLeaveForm(form, MOCK_BALANCES, TODAY);
    assert.equal(result.isValid, false);
    assert.ok(result.errors.end_date, "Should reject cross-year leave span");
    assert.match(
      result.errors.end_date,
      /calendar year/i,
      "Should explain that leave cannot span calendar years"
    );
  });

  test("fails validation when requested days exceed available leave balance", () => {
    // Leave type 2 (Casual Leave) has only 2 available days
    // Requesting 3 working days (Tuesday to Thursday: 3 days)
    const form = {
      leave_type_id: 2,
      start_date: "2026-11-24",
      end_date: "2026-11-26",
      reason: "Requesting more days than casual quota remaining.",
    };

    const result = validateLeaveForm(form, MOCK_BALANCES, TODAY);
    assert.equal(result.isValid, false);
    assert.equal(result.workingDays, 3);
    assert.ok(result.errors.balance, "Should have balance error");
    assert.equal(
      result.errors.balance,
      "Insufficient leave balance (Available: 2 days)"
    );
  });

  test("fails validation when reason length is less than 10 characters", () => {
    const form = {
      leave_type_id: 1,
      start_date: "2026-11-24",
      end_date: "2026-11-25",
      reason: "Sick", // Only 4 chars
    };

    const result = validateLeaveForm(form, MOCK_BALANCES, TODAY);
    assert.equal(result.isValid, false);
    assert.ok(result.errors.reason, "Should flag short reason");
  });

  test("fails validation when reason length exceeds 2000 characters", () => {
    const form = {
      leave_type_id: 1,
      start_date: "2026-11-24",
      end_date: "2026-11-25",
      reason: "A".repeat(2001),
    };

    const result = validateLeaveForm(form, MOCK_BALANCES, TODAY);
    assert.equal(result.isValid, false);
    assert.ok(result.errors.reason, "Should flag excessively long reason");
  });

  test("fails validation when date range contains only weekends", () => {
    const form = {
      leave_type_id: 1,
      start_date: "2026-11-28", // Saturday
      end_date: "2026-11-29", // Sunday
      reason: "Applying for leave on non-working weekend days.",
    };

    const result = validateLeaveForm(form, MOCK_BALANCES, TODAY);
    assert.equal(result.isValid, false);
    assert.equal(result.workingDays, 0);
    assert.ok(result.errors.dates, "Should flag weekend-only range");
  });

  test("passes validation with valid fields within available balance", () => {
    // Annual Leave: 13 available days. Requesting 3 days: Tue to Thu
    const form = {
      leave_type_id: 1,
      start_date: "2026-11-24",
      end_date: "2026-11-26",
      reason: "Attending technical conference sessions and workshops.",
    };

    const result = validateLeaveForm(form, MOCK_BALANCES, TODAY);
    assert.equal(result.isValid, true);
    assert.equal(result.workingDays, 3);
    assert.equal(Object.keys(result.errors).length, 0);
  });
});

// ============================================================================
// 3. Status Tone Mapping (leaveStatusTone)
// ============================================================================
describe("3. leaveStatusTone", () => {
  test("maps APPROVED status to green", () => {
    assert.equal(leaveStatusTone("APPROVED"), "green");
    assert.equal(leaveStatusTone("approved"), "green");
    assert.equal(getLeaveStatusBadgeClass("APPROVED"), "leave-badge-green");
  });

  test("maps PENDING status to amber", () => {
    assert.equal(leaveStatusTone("PENDING"), "amber");
    assert.equal(leaveStatusTone("pending"), "amber");
    assert.equal(getLeaveStatusBadgeClass("PENDING"), "leave-badge-amber");
  });

  test("maps REJECTED status to red", () => {
    assert.equal(leaveStatusTone("REJECTED"), "red");
    assert.equal(leaveStatusTone("rejected"), "red");
    assert.equal(getLeaveStatusBadgeClass("REJECTED"), "leave-badge-red");
  });

  test("maps CANCELLED status to grey", () => {
    assert.equal(leaveStatusTone("CANCELLED"), "grey");
    assert.equal(leaveStatusTone("cancelled"), "grey");
    assert.equal(leaveStatusTone("CANCELED"), "grey");
    assert.equal(getLeaveStatusBadgeClass("CANCELLED"), "leave-badge-grey");
  });

  test("falls back safely to grey for unrecognized or empty status", () => {
    assert.equal(leaveStatusTone("UNKNOWN"), "grey");
    assert.equal(leaveStatusTone(null), "grey");
    assert.equal(leaveStatusTone(""), "grey");
  });
});

// ============================================================================
// 4. API Service Integration (leaveApi)
// ============================================================================
describe("4. leaveApi integration", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    setStoredToken("");
  });

  test("getMyLeaveBalances dispatches GET /api/v1/leave/balance/me", async () => {
    let capturedUrl = null;
    let capturedMethod = null;

    globalThis.fetch = async (url, options = {}) => {
      capturedUrl = String(url);
      capturedMethod = options.method || "GET";
      return {
        ok: true,
        status: 200,
        headers: {
          get: (name) => (name.toLowerCase() === "content-type" ? "application/json" : null),
        },
        json: async () => ({
          employee_id: 12,
          year: 2026,
          balances: [
            {
              leave_type_id: 1,
              leave_type_name: "Annual Leave",
              yearly_quota: 20,
              used_days: 5,
              pending_days: 2,
              available_days: 13,
              is_paid: true,
            },
          ],
        }),
      };
    };

    const data = await getMyLeaveBalances();
    assert.equal(capturedMethod, "GET");
    assert.ok(capturedUrl.includes("/api/v1/leave/balance/me"));
    assert.equal(data.employee_id, 12);
    assert.equal(data.balances.length, 1);
  });

  test("getMyLeaveBalances passes year query parameter when specified", async () => {
    let capturedUrl = null;

    globalThis.fetch = async (url) => {
      capturedUrl = String(url);
      return {
        ok: true,
        status: 200,
        headers: {
          get: () => "application/json",
        },
        json: async () => ({ employee_id: 12, year: 2025, balances: [] }),
      };
    };

    await getMyLeaveBalances({ year: 2025 });
    assert.ok(capturedUrl.includes("/api/v1/leave/balance/me?year=2025"));
  });

  test("getLeavePolicies dispatches GET /api/v1/leave/policies", async () => {
    let capturedUrl = null;
    let capturedMethod = null;

    globalThis.fetch = async (url, options = {}) => {
      capturedUrl = String(url);
      capturedMethod = options.method || "GET";
      return {
        ok: true,
        status: 200,
        headers: {
          get: () => "application/json",
        },
        json: async () => [
          {
            leave_type_id: 1,
            name: "Annual Leave",
            yearly_quota: 20,
            is_paid: true,
            description: "Annual quota",
            is_active: true,
          },
        ],
      };
    };

    const policies = await getLeavePolicies();
    assert.equal(capturedMethod, "GET");
    assert.ok(capturedUrl.includes("/api/v1/leave/policies"));
    assert.equal(policies.length, 1);
    assert.equal(policies[0].name, "Annual Leave");
  });

  test("submitLeaveRequest dispatches POST /api/v1/leave/requests with normalized payload", async () => {
    let capturedUrl = null;
    let capturedMethod = null;
    let capturedBody = null;
    let capturedHeaders = null;

    globalThis.fetch = async (url, options = {}) => {
      capturedUrl = String(url);
      capturedMethod = options.method;
      capturedBody = JSON.parse(options.body);
      capturedHeaders = options.headers;
      return {
        ok: true,
        status: 201,
        headers: {
          get: () => "application/json",
        },
        json: async () => ({
          leave_id: 42,
          emp_id: 12,
          leave_type_id: 1,
          start_date: "2026-11-27",
          end_date: "2026-11-30",
          total_days: 2,
          reason: "Attending a family gathering out of town.",
          status: "PENDING",
          applied_at: "2026-11-20T10:00:00Z",
        }),
      };
    };

    const payload = {
      leave_type_id: "1",
      start_date: "2026-11-27",
      end_date: "2026-11-30",
      reason: "  Attending a family gathering out of town.  ",
    };

    const response = await submitLeaveRequest(payload);
    assert.equal(capturedMethod, "POST");
    assert.ok(capturedUrl.includes("/api/v1/leave/requests"));
    assert.equal(capturedHeaders["Content-Type"], "application/json");
    assert.equal(capturedBody.leave_type_id, 1);
    assert.equal(capturedBody.start_date, "2026-11-27");
    assert.equal(capturedBody.end_date, "2026-11-30");
    assert.equal(capturedBody.reason, "Attending a family gathering out of town.");
    assert.equal(response.leave_id, 42);
    assert.equal(response.status, "PENDING");
  });

  test("getMyLeaveRequests dispatches GET /api/v1/leave/requests/my with filters", async () => {
    let capturedUrl = null;
    let capturedMethod = null;

    globalThis.fetch = async (url, options = {}) => {
      capturedUrl = String(url);
      capturedMethod = options.method || "GET";
      return {
        ok: true,
        status: 200,
        headers: {
          get: () => "application/json",
        },
        json: async () => ({
          items: [
            {
              leave_id: 101,
              emp_id: 12,
              leave_type_id: 1,
              start_date: "2026-12-15",
              end_date: "2026-12-18",
              total_days: 4,
              status: "PENDING",
            },
          ],
          total: 1,
          page: 2,
          limit: 10,
        }),
      };
    };

    const result = await getMyLeaveRequests({
      status: "PENDING",
      year: 2026,
      page: 2,
      limit: 10,
    });

    assert.equal(capturedMethod, "GET");
    assert.ok(capturedUrl.includes("/api/v1/leave/requests/my"));
    assert.ok(capturedUrl.includes("status=PENDING"));
    assert.ok(capturedUrl.includes("year=2026"));
    assert.ok(capturedUrl.includes("page=2"));
    assert.ok(capturedUrl.includes("limit=10"));
    assert.equal(result.items.length, 1);
    assert.equal(result.total, 1);
  });

  test("cancelLeaveRequest dispatches PUT /api/v1/leave/requests/{id}/cancel", async () => {
    let capturedUrl = null;
    let capturedMethod = null;

    globalThis.fetch = async (url, options = {}) => {
      capturedUrl = String(url);
      capturedMethod = options.method;
      return {
        ok: true,
        status: 200,
        headers: {
          get: () => "application/json",
        },
        json: async () => ({
          leave_id: 101,
          emp_id: 12,
          leave_type_id: 1,
          status: "CANCELLED",
        }),
      };
    };

    const cancelled = await cancelLeaveRequest(101);
    assert.equal(capturedMethod, "PUT");
    assert.ok(capturedUrl.includes("/api/v1/leave/requests/101/cancel"));
    assert.equal(cancelled.status, "CANCELLED");
  });

  test("cancelLeaveRequest rejects missing or null leaveId before fetch", async () => {
    await assert.rejects(async () => {
      await cancelLeaveRequest(null);
    }, /Leave ID is required/i);
  });
});
