import { test, describe, afterEach } from "node:test";
import assert from "node:assert/strict";

import {
  validateTeamForm,
  buildCreatePayload,
  diffMembers,
} from "../src/features/hr/teams/teamFormUtils.js";

import {
  getDepartments,
  getDepartmentTeams,
  createDepartmentTeam,
  updateTeam,
  addTeamMembers,
  removeTeamMember,
  searchEmployees,
  teamApi,
} from "../src/api/teamApi.js";

import {
  navConfig,
  filterNavForRole,
} from "../src/components/layout/navConfig.js";

import { setSession, clearSession } from "../src/auth/session.js";

// ============================================================================
// 1. Team Form Validation (validateTeamForm)
// ============================================================================
describe("1. Team Form Validation (validateTeamForm)", () => {
  test("fails when team name is missing, empty, or whitespace-only", () => {
    const res1 = validateTeamForm({ name: "", description: "desc", leadEmpId: 10 });
    assert.equal(res1.valid, false);
    assert.equal(res1.errors.name, "Team name is required");

    const res2 = validateTeamForm({ name: "   ", description: "", leadEmpId: 10 });
    assert.equal(res2.valid, false);
    assert.equal(res2.errors.name, "Team name is required");

    const res3 = validateTeamForm({ name: null, description: "", leadEmpId: 10 });
    assert.equal(res3.valid, false);
    assert.equal(res3.errors.name, "Team name is required");
  });

  test("fails when team name is shorter than 2 characters", () => {
    const res = validateTeamForm({ name: "A", description: "", leadEmpId: 10 });
    assert.equal(res.valid, false);
    assert.equal(res.errors.name, "Team name must be at least 2 characters");
  });

  test("fails when team name exceeds 100 characters", () => {
    const longName = "A".repeat(101);
    const res = validateTeamForm({ name: longName, description: "", leadEmpId: 10 });
    assert.equal(res.valid, false);
    assert.equal(res.errors.name, "Team name must not exceed 100 characters");
  });

  test("fails when description exceeds 500 characters", () => {
    const longDesc = "D".repeat(501);
    const res = validateTeamForm({ name: "DevOps", description: longDesc, leadEmpId: 10 });
    assert.equal(res.valid, false);
    assert.equal(res.errors.description, "Description must not exceed 500 characters");
  });

  test("fails when team lead is missing or null", () => {
    const res1 = validateTeamForm({ name: "DevOps", description: "Infra team", leadEmpId: null });
    assert.equal(res1.valid, false);
    assert.equal(res1.errors.leadEmpId, "A team lead must be selected");

    const res2 = validateTeamForm({ name: "DevOps", description: "", leadEmpId: undefined });
    assert.equal(res2.valid, false);
    assert.equal(res2.errors.leadEmpId, "A team lead must be selected");
  });

  test("passes with valid inputs (including boundary lengths)", () => {
    const validRes = validateTeamForm({
      name: "Engineering Wave 3",
      description: "Platform core infrastructure and API services",
      leadEmpId: 42,
    });
    assert.equal(validRes.valid, true);
    assert.deepEqual(validRes.errors, {});

    // Boundary: 2 chars name, 0 chars desc, lead 0 (numeric ID)
    const boundaryRes = validateTeamForm({
      name: "IT",
      description: "",
      leadEmpId: 0,
    });
    assert.equal(boundaryRes.valid, true);

    // Boundary: exactly 100 chars name, 500 chars desc
    const maxBoundaryRes = validateTeamForm({
      name: "B".repeat(100),
      description: "C".repeat(500),
      leadEmpId: 1,
    });
    assert.equal(maxBoundaryRes.valid, true);
  });
});

// ============================================================================
// 2. Create Payload Construction (buildCreatePayload)
// ============================================================================
describe("2. Create Payload Construction (buildCreatePayload)", () => {
  test("trims name and sets null for empty description", () => {
    const payload = buildCreatePayload({
      name: "  Security Operations  ",
      description: "   ",
      leadEmpId: 5,
      memberEmpIds: [],
    });
    assert.equal(payload.name, "Security Operations");
    assert.equal(payload.description, null);
    assert.equal(payload.lead_emp_id, 5);
    assert.deepEqual(payload.member_emp_ids, [5]);
  });

  test("automatically includes leadEmpId in member_emp_ids", () => {
    const payload = buildCreatePayload({
      name: "Core Frontend",
      description: "React client app",
      leadEmpId: 12,
      memberEmpIds: [15, 18, 20],
    });
    assert.equal(payload.member_emp_ids.includes(12), true);
    assert.equal(payload.member_emp_ids.length, 4);
  });

  test("deduplicates member IDs and handles null or undefined values", () => {
    const payload = buildCreatePayload({
      name: "QA Team",
      description: "Testing automation",
      leadEmpId: 10,
      memberEmpIds: [10, 10, 11, 11, null, undefined],
    });
    assert.deepEqual(payload.member_emp_ids.sort((a, b) => a - b), [10, 11]);
  });
});

// ============================================================================
// 3. Member Diffing Helper (diffMembers)
// ============================================================================
describe("3. Member Diffing Helper (diffMembers)", () => {
  test("calculates added and removed members correctly", () => {
    const before = [1, 2, 3];
    const after = [2, 3, 4, 5];
    const { toAdd, toRemove } = diffMembers(before, after, 2);

    assert.deepEqual(toAdd.sort((a, b) => a - b), [4, 5]);
    assert.deepEqual(toRemove, [1]);
  });

  test("safeguard: never includes currentLeadId in toRemove", () => {
    const before = [10, 20, 30];
    const after = [30]; // lead 10 was omitted in after list
    const { toAdd, toRemove } = diffMembers(before, after, 10);

    assert.equal(toRemove.includes(10), false);
    assert.deepEqual(toRemove, [20]);
    assert.deepEqual(toAdd, []);
  });

  test("handles empty arrays or missing arguments gracefully", () => {
    const res1 = diffMembers([], []);
    assert.deepEqual(res1.toAdd, []);
    assert.deepEqual(res1.toRemove, []);

    const res2 = diffMembers(null, [1, 2]);
    assert.deepEqual(res2.toAdd, [1, 2]);
    assert.deepEqual(res2.toRemove, []);
  });
});

// ============================================================================
// 4. Department Teams API Integration (teamApi)
// ============================================================================
describe("4. Department Teams API Integration", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    clearSession();
  });

  test("getDepartments dispatches GET /api/v1/departments?limit=100", async () => {
    let capturedUrl = "";
    let capturedMethod = "";

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options.method;
      return new Response(JSON.stringify([{ dept_id: 1, name: "Engineering", team_count: 3 }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const res = await getDepartments();
    assert.equal(capturedUrl, "/api/v1/departments?limit=100");
    assert.equal(capturedMethod, "GET");
    assert.equal(res.length, 1);
    assert.equal(res[0].name, "Engineering");
  });

  test("getDepartmentTeams dispatches GET with include_disbanded option", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(JSON.stringify([{ team_id: 10, name: "Alpha", status: "ACTIVE" }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    // Default: without includeDisbanded
    await getDepartmentTeams(4);
    assert.equal(capturedUrl, "/api/v1/departments/4/teams");

    // With includeDisbanded = true
    await getDepartmentTeams(4, { includeDisbanded: true });
    assert.equal(capturedUrl, "/api/v1/departments/4/teams?include_disbanded=true");
  });

  test("createDepartmentTeam dispatches POST /api/v1/departments/{id}/teams", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options.method;
      capturedBody = JSON.parse(options.body);
      return new Response(
        JSON.stringify({ team_id: 99, name: capturedBody.name, status: "ACTIVE" }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      );
    };

    const payload = {
      name: "Platform",
      description: "Platform infra",
      lead_emp_id: 10,
      member_emp_ids: [10, 11],
    };

    const res = await createDepartmentTeam(2, payload);
    assert.equal(capturedUrl, "/api/v1/departments/2/teams");
    assert.equal(capturedMethod, "POST");
    assert.deepEqual(capturedBody, payload);
    assert.equal(res.team_id, 99);
  });

  test("updateTeam dispatches PUT /api/v1/teams/{teamId}", async () => {
    let capturedUrl = "";
    let capturedMethod = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options.method;
      capturedBody = JSON.parse(options.body);
      return new Response(JSON.stringify({ team_id: 15, ...capturedBody }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    // Update fields
    await updateTeam(15, { name: "Renamed Team", lead_emp_id: 25 });
    assert.equal(capturedUrl, "/api/v1/teams/15");
    assert.equal(capturedMethod, "PUT");
    assert.equal(capturedBody.name, "Renamed Team");
    assert.equal(capturedBody.lead_emp_id, 25);

    // Disband status update
    await updateTeam(15, { status: "DISBANDED" });
    assert.equal(capturedBody.status, "DISBANDED");
  });

  test("addTeamMembers dispatches POST /api/v1/teams/{teamId}/members with emp_ids", async () => {
    let capturedUrl = "";
    let capturedBody = null;

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedBody = JSON.parse(options.body);
      return new Response(JSON.stringify({ message: "Members added" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    await addTeamMembers(12, [3, 4, 5]);
    assert.equal(capturedUrl, "/api/v1/teams/12/members");
    assert.deepEqual(capturedBody, { emp_ids: [3, 4, 5] });
  });

  test("removeTeamMember dispatches DELETE /api/v1/teams/{teamId}/members/{empId}", async () => {
    let capturedUrl = "";
    let capturedMethod = "";

    globalThis.fetch = async (url, options) => {
      capturedUrl = url;
      capturedMethod = options.method;
      return new Response(null, { status: 204 });
    };

    await removeTeamMember(12, 7);
    assert.equal(capturedUrl, "/api/v1/teams/12/members/7");
    assert.equal(capturedMethod, "DELETE");
  });

  test("searchEmployees dispatches GET /api/v1/employees with query parameters", async () => {
    let capturedUrl = "";

    globalThis.fetch = async (url) => {
      capturedUrl = url;
      return new Response(JSON.stringify([{ emp_id: 8, full_name: "Alice Smith" }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    await searchEmployees({ deptId: 3, search: "Alice" });
    assert.equal(
      capturedUrl,
      "/api/v1/employees?status=ACTIVE&limit=50&dept_id=3&search=Alice"
    );

    // Without search query
    await searchEmployees({ deptId: 3 });
    assert.equal(capturedUrl, "/api/v1/employees?status=ACTIVE&limit=50&dept_id=3");
  });
});

// ============================================================================
// 5. Navigation Configuration & Role Filtering (/hr/teams)
// ============================================================================
describe("5. Navigation Configuration & Role Filtering (/hr/teams)", () => {
  test("navConfig contains /hr/teams with correct metadata and roles", () => {
    const teamsNav = navConfig.find((item) => item.path === "/hr/teams");
    assert.notEqual(teamsNav, undefined);
    assert.equal(teamsNav.label, "Department Teams");
    assert.equal(teamsNav.icon, "🏢");
    assert.deepEqual(teamsNav.roles, ["HR", "ADMIN"]);
  });

  test("HR role sees /hr/teams in navigation", () => {
    const hrNav = filterNavForRole(navConfig, "HR");
    const hrPaths = hrNav.map((i) => i.path);
    assert.equal(hrPaths.includes("/hr/teams"), true);
  });

  test("ADMIN role sees /hr/teams in navigation", () => {
    const adminNav = filterNavForRole(navConfig, "ADMIN");
    const adminPaths = adminNav.map((i) => i.path);
    assert.equal(adminPaths.includes("/hr/teams"), true);
  });

  test("Non-authorized roles cannot see /hr/teams in navigation", () => {
    const forbiddenRoles = [
      "EMPLOYEE",
      "TEAM_LEAD",
      "PM",
      "PROJECT_MANAGER",
      "MNC_EXECUTIVE",
      "IT_SUPPORT",
      "CLIENT",
    ];

    for (const role of forbiddenRoles) {
      const visible = filterNavForRole(navConfig, role);
      const paths = visible.map((i) => i.path);
      assert.equal(
        paths.includes("/hr/teams"),
        false,
        `Role ${role} should not see /hr/teams`
      );
    }
  });
});
