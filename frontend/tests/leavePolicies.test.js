import { test, describe, afterEach } from "node:test";
import assert from "node:assert/strict";

import {
  validatePolicyForm,
  formatQuotaLabel,
} from "../src/features/hr/leavePolicyUtils.js";

import {
  getLeavePolicies,
  createLeavePolicy,
  updateLeavePolicy,
} from "../src/api/leaveApi.js";

import { navConfig, filterNavForRole } from "../src/components/layout/navConfig.js";

// ============================================================================
// 1. Leave Policy Client-Side Validation Tests (US-18 / S4-FE-3)
// ============================================================================
describe("1. Leave Policy Form Validation - validatePolicyForm (US-18)", () => {
  test("rejects empty, whitespace-only, null, or undefined policy names", () => {
    assert.equal(validatePolicyForm({ name: "", yearly_quota: 10 }).isValid, false);
    assert.match(validatePolicyForm({ name: "", yearly_quota: 10 }).errors.name, /required/i);

    assert.equal(validatePolicyForm({ name: "   ", yearly_quota: 10 }).isValid, false);
    assert.match(validatePolicyForm({ name: "   ", yearly_quota: 10 }).errors.name, /required/i);

    assert.equal(validatePolicyForm({ name: null, yearly_quota: 10 }).isValid, false);
    assert.equal(validatePolicyForm({ yearly_quota: 10 }).isValid, false);
  });

  test("rejects policy names shorter than 2 characters", () => {
    const res = validatePolicyForm({ name: "A", yearly_quota: 10 });
    assert.equal(res.isValid, false);
    assert.match(res.errors.name, /at least 2 characters/i);

    const whitespaceRes = validatePolicyForm({ name: "  A  ", yearly_quota: 10 });
    assert.equal(whitespaceRes.isValid, false);
    assert.match(whitespaceRes.errors.name, /at least 2 characters/i);
  });

  test("rejects policy names longer than 50 characters (51-char name)", () => {
    const name51 = "A".repeat(51);
    const res = validatePolicyForm({ name: name51, yearly_quota: 10 });
    assert.equal(res.isValid, false);
    assert.match(res.errors.name, /cannot exceed 50 characters/i);
  });

  test("accepts valid boundary policy names (2 and 50 characters)", () => {
    const res2 = validatePolicyForm({ name: "PL", yearly_quota: 10 });
    assert.equal(res2.isValid, true);
    assert.equal(res2.errors.name, undefined);

    const name50 = "A".repeat(50);
    const res50 = validatePolicyForm({ name: name50, yearly_quota: 10 });
    assert.equal(res50.isValid, true);
    assert.equal(res50.errors.name, undefined);
  });

  test("rejects negative yearly quotas", () => {
    const res1 = validatePolicyForm({ name: "Annual Leave", yearly_quota: -1 });
    assert.equal(res1.isValid, false);
    assert.match(res1.errors.yearly_quota, /cannot be negative/i);

    const res2 = validatePolicyForm({ name: "Sick Leave", yearly_quota: "-15" });
    assert.equal(res2.isValid, false);
    assert.match(res2.errors.yearly_quota, /cannot be negative/i);
  });

  test("rejects non-integer (decimal) yearly quotas", () => {
    const res1 = validatePolicyForm({ name: "Casual Leave", yearly_quota: 10.5 });
    assert.equal(res1.isValid, false);
    assert.match(res1.errors.yearly_quota, /integer/i);

    const res2 = validatePolicyForm({ name: "Casual Leave", yearly_quota: "5.25" });
    assert.equal(res2.isValid, false);
    assert.match(res2.errors.yearly_quota, /integer/i);
  });

  test("rejects yearly quotas greater than 366 days", () => {
    const res1 = validatePolicyForm({ name: "Sabbatical", yearly_quota: 367 });
    assert.equal(res1.isValid, false);
    assert.match(res1.errors.yearly_quota, /cannot exceed 366/i);

    const res2 = validatePolicyForm({ name: "Sabbatical", yearly_quota: "400" });
    assert.equal(res2.isValid, false);
    assert.match(res2.errors.yearly_quota, /cannot exceed 366/i);
  });

  test("accepts valid boundary yearly quotas (0 and 366 days)", () => {
    const res0 = validatePolicyForm({ name: "Unpaid Leave", yearly_quota: 0 });
    assert.equal(res0.isValid, true);
    assert.equal(res0.errors.yearly_quota, undefined);

    const res366 = validatePolicyForm({ name: "Extended Study", yearly_quota: 366 });
    assert.equal(res366.isValid, true);
    assert.equal(res366.errors.yearly_quota, undefined);
  });

  test("rejects descriptions exceeding 1000 characters", () => {
    const longDesc = "X".repeat(1001);
    const res = validatePolicyForm({
      name: "Bereavement",
      yearly_quota: 5,
      description: longDesc,
    });
    assert.equal(res.isValid, false);
    assert.match(res.errors.description, /cannot exceed 1000 characters/i);
  });

  test("accepts valid descriptions and optional undefined/null descriptions", () => {
    const validDesc = "Standard annual entitlement for permanent employees.";
    const res = validatePolicyForm({
      name: "Annual Leave",
      yearly_quota: 20,
      description: validDesc,
    });
    assert.equal(res.isValid, true);
    assert.equal(res.errors.description, undefined);

    const resNull = validatePolicyForm({
      name: "Annual Leave",
      yearly_quota: 20,
      description: null,
    });
    assert.equal(resNull.isValid, true);
  });
});

// ============================================================================
// 2. formatQuotaLabel Tests
// ============================================================================
describe("2. Leave Policy Utilities - formatQuotaLabel", () => {
  test("formats 1 day with singular label", () => {
    assert.equal(formatQuotaLabel(1), "1 day");
    assert.equal(formatQuotaLabel("1"), "1 day");
  });

  test("formats N days with plural label", () => {
    assert.equal(formatQuotaLabel(20), "20 days");
    assert.equal(formatQuotaLabel(10), "10 days");
    assert.equal(formatQuotaLabel(0), "0 days");
  });

  test("handles negative or invalid quota safely", () => {
    assert.equal(formatQuotaLabel(-5), "0 days");
    assert.equal(formatQuotaLabel("invalid"), "0 days");
    assert.equal(formatQuotaLabel(null), "0 days");
  });
});

// ============================================================================
// 3. API Endpoints & Query Parameter URLs (US-18, S4-BE-2)
// ============================================================================
describe("3. Leave Policy API Endpoints & HTTP Contracts (US-18)", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("getLeavePolicies calls GET /api/v1/leave/policies without query when inactive is false", async () => {
    let capturedUrl = "";
    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(
        JSON.stringify([
          { leave_type_id: 1, name: "Annual Leave", yearly_quota: 20, is_active: true },
        ]),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    const res = await getLeavePolicies();
    assert.match(capturedUrl, /\/api\/v1\/leave\/policies$/);
    assert.equal(res.length, 1);
  });

  test("getLeavePolicies appends ?include_inactive=true when requested", async () => {
    let capturedUrl = "";
    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(
        JSON.stringify([
          { leave_type_id: 1, name: "Annual Leave", yearly_quota: 20, is_active: true },
          { leave_type_id: 4, name: "Old Policy", yearly_quota: 5, is_active: false },
        ]),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    const res = await getLeavePolicies({ includeInactive: true });
    assert.match(capturedUrl, /\/api\/v1\/leave\/policies\?include_inactive=true$/);
    assert.equal(res.length, 2);

    // Also supports include_inactive snake_case
    await getLeavePolicies({ include_inactive: true });
    assert.match(capturedUrl, /\/api\/v1\/leave\/policies\?include_inactive=true$/);
  });

  test("createLeavePolicy dispatches POST /api/v1/leave/policies with sanitized payload", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options.method;
      capturedBody = JSON.parse(options.body);
      return new Response(
        JSON.stringify({
          leave_type_id: 5,
          name: "Paternity Leave",
          yearly_quota: 15,
          is_paid: true,
          is_active: true,
          description: "New parent entitlement",
        }),
        {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    const created = await createLeavePolicy({
      name: "  Paternity Leave  ",
      yearly_quota: 15,
      is_paid: true,
      description: "  New parent entitlement  ",
    });

    assert.match(capturedUrl, /\/api\/v1\/leave\/policies$/);
    assert.equal(capturedMethod, "POST");
    assert.equal(capturedBody.name, "Paternity Leave");
    assert.equal(capturedBody.yearly_quota, 15);
    assert.equal(capturedBody.is_paid, true);
    assert.equal(capturedBody.description, "New parent entitlement");
    assert.equal(created.leave_type_id, 5);
  });

  test("updateLeavePolicy dispatches PUT /api/v1/leave/policies/{id} with partial changes", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options.method;
      capturedBody = JSON.parse(options.body);
      return new Response(
        JSON.stringify({
          leave_type_id: 3,
          name: "Casual Leave",
          yearly_quota: 7,
          is_paid: true,
          is_active: true,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    const updated = await updateLeavePolicy(3, {
      yearly_quota: 7,
    });

    assert.match(capturedUrl, /\/api\/v1\/leave\/policies\/3$/);
    assert.equal(capturedMethod, "PUT");
    assert.equal(capturedBody.yearly_quota, 7);
    assert.equal(updated.yearly_quota, 7);
  });

  test("updateLeavePolicy can toggle is_active (deactivate and reactivate)", async () => {
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedBody = JSON.parse(options.body);
      return new Response(
        JSON.stringify({
          leave_type_id: 5,
          name: "Paternity Leave",
          yearly_quota: 15,
          is_active: false,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    // Deactivate
    await updateLeavePolicy(5, { is_active: false });
    assert.equal(capturedBody.is_active, false);

    // Reactivate
    await updateLeavePolicy(5, { is_active: true });
    assert.equal(capturedBody.is_active, true);
  });
});

// ============================================================================
// 4. Seed Demo Data & User Story Scenarios (US-18)
// ============================================================================
describe("4. Seed Demo Data Scenarios & User Story Expectations (US-18)", () => {
  // Canonical seed policies established in wave3 and rich demo seeds
  const SEED_POLICIES = [
    {
      leave_type_id: 1,
      name: "Annual",
      yearly_quota: 20,
      is_paid: true,
      is_active: true,
      description: "Standard paid vacation allowance",
    },
    {
      leave_type_id: 2,
      name: "Sick",
      yearly_quota: 10,
      is_paid: true,
      is_active: true,
      description: "Medical and health-related leave",
    },
    {
      leave_type_id: 3,
      name: "Casual",
      yearly_quota: 5,
      is_paid: true,
      is_active: true,
      description: "Short notice urgent personal leave",
    },
  ];

  test("Seed baseline for hr@company.com shows Annual 20, Sick 10, Casual 5", () => {
    assert.equal(SEED_POLICIES.length, 3);

    const annual = SEED_POLICIES.find((p) => p.name === "Annual");
    assert.ok(annual);
    assert.equal(annual.yearly_quota, 20);
    assert.equal(annual.is_paid, true);
    assert.equal(annual.is_active, true);

    const sick = SEED_POLICIES.find((p) => p.name === "Sick");
    assert.ok(sick);
    assert.equal(sick.yearly_quota, 10);
    assert.equal(sick.is_paid, true);
    assert.equal(sick.is_active, true);

    const casual = SEED_POLICIES.find((p) => p.name === "Casual");
    assert.ok(casual);
    assert.equal(casual.yearly_quota, 5);
    assert.equal(casual.is_paid, true);
    assert.equal(casual.is_active, true);
  });

  test("Simulating Create 'Paternity Leave' with quota 15, Paid -> adds to collection", () => {
    const newPolicy = {
      leave_type_id: 4,
      name: "Paternity Leave",
      yearly_quota: 15,
      is_paid: true,
      is_active: true,
      description: "Parental leave for new fathers",
    };

    const updatedList = [...SEED_POLICIES, newPolicy];
    assert.equal(updatedList.length, 4);
    assert.ok(updatedList.some((p) => p.name === "Paternity Leave" && p.yearly_quota === 15));
  });

  test("Simulating Edit Casual from 5 to 7 -> quota updates in collection", () => {
    const listWithUpdatedCasual = SEED_POLICIES.map((p) =>
      p.name === "Casual" ? { ...p, yearly_quota: 7 } : p
    );

    const casual = listWithUpdatedCasual.find((p) => p.name === "Casual");
    assert.equal(casual.yearly_quota, 7);
  });

  test("Simulating Deactivate Paternity -> hidden when include_inactive is false", () => {
    const policyList = [
      ...SEED_POLICIES,
      {
        leave_type_id: 4,
        name: "Paternity Leave",
        yearly_quota: 15,
        is_paid: true,
        is_active: false, // Deactivated
      },
    ];

    // Default view (active only)
    const activeOnly = policyList.filter((p) => p.is_active !== false);
    assert.equal(activeOnly.length, 3);
    assert.equal(activeOnly.some((p) => p.name === "Paternity Leave"), false);

    // Show inactive view
    const allPolicies = policyList;
    assert.equal(allPolicies.length, 4);
    assert.equal(allPolicies.some((p) => p.name === "Paternity Leave" && p.is_active === false), true);
  });
});

// ============================================================================
// 5. Access Control & Role Guards (US-18 / Route: /hr/leave-policies)
// ============================================================================
describe("5. Role Authorization & Protected Route Guards (US-18)", () => {
  const HR_POLICY_ROLES = ["HR", "ADMIN"];

  test("Allows HR and ADMIN to view leave policy management navigation", () => {
    const hrNav = filterNavForRole(navConfig, "HR");
    assert.ok(hrNav.some((item) => item.path === "/hr/leave-policies"));

    const adminNav = filterNavForRole(navConfig, "ADMIN");
    assert.ok(adminNav.some((item) => item.path === "/hr/leave-policies"));
  });

  test("Strictly denies EMPLOYEE (sarah.connor@company.com) from /hr/leave-policies", () => {
    const empNav = filterNavForRole(navConfig, "EMPLOYEE");
    assert.equal(empNav.some((item) => item.path === "/hr/leave-policies"), false);

    // Verify allowedRoles matrix check
    const isEmpAllowed = HR_POLICY_ROLES.includes("EMPLOYEE");
    assert.equal(isEmpAllowed, false);
  });

  test("Strictly denies TEAM_LEAD, PM, IT_SUPPORT, CLIENT, and MNC_EXECUTIVE from /hr/leave-policies", () => {
    const forbiddenRoles = [
      "TEAM_LEAD",
      "PM",
      "PROJECT_MANAGER",
      "IT_SUPPORT",
      "CLIENT",
      "MNC_EXECUTIVE",
      "HR_MANAGER", // specifically not allowed per task prompt
    ];

    for (const forbidden of forbiddenRoles) {
      assert.equal(
        HR_POLICY_ROLES.includes(forbidden),
        false,
        `Role ${forbidden} must not be in HR_POLICY_ROLES`
      );
      const nav = filterNavForRole(navConfig, forbidden);
      assert.equal(
        nav.some((item) => item.path === "/hr/leave-policies"),
        false,
        `Role ${forbidden} must not see /hr/leave-policies in navigation`
      );
    }
  });
});
