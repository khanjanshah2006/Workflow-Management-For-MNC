import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";

import {
  SKILL_ACTIONS,
  SKILL_PROFICIENCIES,
  SKILL_STATUSES,
  PROFICIENCY_LABELS,
  DEFAULT_CATALOG_SKILLS,
  validateProposal,
  validateRejectionRemarks,
  describeChange,
  formatSkillDate,
} from "../src/features/skills/skillRequestUtils.js";

import {
  proposeSkillChange,
  getMySkillRequests,
  getSkillRequestQueue,
  approveSkillRequest,
  rejectSkillRequest,
} from "../src/api/profileApi.js";

import {
  navConfig,
  filterNavForRole,
} from "../src/components/layout/navConfig.js";

/* ============================================================================
   1. Skill Proposal Form Validation (validateProposal)
   ============================================================================ */
describe("1. Skill Proposal Form Validation (validateProposal)", () => {
  // ADD mode validation
  describe("ADD Mode", () => {
    test("fails if neither catalog skill_id nor custom proposed_skill_name is provided", () => {
      const res = validateProposal("ADD", {
        proficiency: "INTERMEDIATE",
        years_of_experience: 2,
        justification: "Three years working on backend APIs in production.",
      });
      assert.equal(res.isValid, false);
      assert.ok(res.errors.skill);
    });

    test("fails if custom skill name is shorter than 2 characters", () => {
      const res = validateProposal("ADD", {
        proposed_skill_name: "A",
        proficiency: "INTERMEDIATE",
        years_of_experience: 2,
        justification: "Three years working on backend APIs in production.",
      });
      assert.equal(res.isValid, false);
      assert.ok(res.errors.proposed_skill_name.includes("at least 2"));
    });

    test("fails if custom skill name exceeds 100 characters", () => {
      const res = validateProposal("ADD", {
        proposed_skill_name: "x".repeat(101),
        proficiency: "INTERMEDIATE",
        years_of_experience: 2,
        justification: "Three years working on backend APIs in production.",
      });
      assert.equal(res.isValid, false);
      assert.ok(res.errors.proposed_skill_name.includes("cannot exceed 100"));
    });

    test("fails if proficiency is missing or invalid", () => {
      const resMissing = validateProposal("ADD", {
        skill_id: 1,
        years_of_experience: 2,
        justification: "Extensive background building distributed systems.",
      });
      assert.equal(resMissing.isValid, false);
      assert.ok(resMissing.errors.proficiency);

      const resInvalid = validateProposal("ADD", {
        skill_id: 1,
        proficiency: "SUPER_EXPERT",
        years_of_experience: 2,
        justification: "Extensive background building distributed systems.",
      });
      assert.equal(resInvalid.isValid, false);
      assert.ok(resInvalid.errors.proficiency);
    });

    test("fails if years of experience is below 0 or above 50 or non-integer", () => {
      const resBelow = validateProposal("ADD", {
        skill_id: 1,
        proficiency: "EXPERT",
        years_of_experience: -1,
        justification: "Lead developer on cloud infrastructure.",
      });
      assert.equal(resBelow.isValid, false);
      assert.ok(resBelow.errors.years_of_experience);

      const resAbove = validateProposal("ADD", {
        skill_id: 1,
        proficiency: "EXPERT",
        years_of_experience: 51,
        justification: "Lead developer on cloud infrastructure.",
      });
      assert.equal(resAbove.isValid, false);
      assert.ok(resAbove.errors.years_of_experience);

      const resDecimal = validateProposal("ADD", {
        skill_id: 1,
        proficiency: "EXPERT",
        years_of_experience: 3.5,
        justification: "Lead developer on cloud infrastructure.",
      });
      assert.equal(resDecimal.isValid, false);
      assert.ok(resDecimal.errors.years_of_experience);
    });

    test("fails if justification is shorter than 10 characters", () => {
      const res = validateProposal("ADD", {
        skill_id: 1,
        proficiency: "BEGINNER",
        years_of_experience: 0,
        justification: "Too short",
      });
      assert.equal(res.isValid, false);
      assert.ok(res.errors.justification.includes("at least 10"));
    });

    test("fails if justification exceeds 500 characters", () => {
      const res = validateProposal("ADD", {
        skill_id: 1,
        proficiency: "BEGINNER",
        years_of_experience: 0,
        justification: "w".repeat(501),
      });
      assert.equal(res.isValid, false);
      assert.ok(res.errors.justification.includes("cannot exceed 500"));
    });

    test("passes with valid catalog skill selection and all required fields", () => {
      const res = validateProposal("ADD", {
        skill_id: 4,
        proficiency: "INTERMEDIATE",
        years_of_experience: 3,
        justification: "Completed React modernization project with 100% test coverage.",
      });
      assert.equal(res.isValid, true);
      assert.deepEqual(res.errors, {});
    });

    test("passes with valid custom skill name and 0 years of experience", () => {
      const res = validateProposal("ADD", {
        proposed_skill_name: "Rust",
        proficiency: "BEGINNER",
        years_of_experience: 0,
        justification: "Completed internal fundamentals training workshop.",
      });
      assert.equal(res.isValid, true);
      assert.deepEqual(res.errors, {});
    });

    test("passes with typed proposed_skill_name without hardcoded skill_id", () => {
      const res = validateProposal("ADD", {
        proposed_skill_name: "Kubernetes",
        proficiency: "INTERMEDIATE",
        years_of_experience: 2,
        justification: "Configured Kubernetes clusters for production deployments.",
      });
      assert.equal(res.isValid, true);
      assert.deepEqual(res.errors, {});
    });

    test("DEFAULT_CATALOG_SKILLS contains skill names without hardcoded IDs", () => {
      assert.ok(Array.isArray(DEFAULT_CATALOG_SKILLS));
      assert.ok(DEFAULT_CATALOG_SKILLS.includes("Kubernetes"));
      assert.ok(DEFAULT_CATALOG_SKILLS.includes("Selenium"));
      assert.ok(DEFAULT_CATALOG_SKILLS.every((item) => typeof item === "string"));
    });
  });

  // UPDATE mode validation
  describe("UPDATE Mode", () => {
    test("fails if skill_id is missing or non-positive", () => {
      const res = validateProposal("UPDATE", {
        proficiency: "EXPERT",
        years_of_experience: 5,
        justification: "Promoted to tech lead managing cloud microservices.",
      });
      assert.equal(res.isValid, false);
      assert.ok(res.errors.skill_id);
    });

    test("fails if proficiency or years are invalid", () => {
      const res = validateProposal("UPDATE", {
        skill_id: 2,
        proficiency: "INVALID_LEVEL",
        years_of_experience: 55,
        justification: "Five years of full stack web development experience.",
      });
      assert.equal(res.isValid, false);
      assert.ok(res.errors.proficiency);
      assert.ok(res.errors.years_of_experience);
    });

    test("fails if justification is shorter than 10 characters", () => {
      const res = validateProposal("UPDATE", {
        skill_id: 2,
        proficiency: "EXPERT",
        years_of_experience: 7,
        justification: "Update me",
      });
      assert.equal(res.isValid, false);
      assert.ok(res.errors.justification);
    });

    test("passes with valid UPDATE fields", () => {
      const res = validateProposal("UPDATE", {
        skill_id: 2,
        proficiency: "EXPERT",
        years_of_experience: 6,
        justification: "Led front-end architecture and published shared UI library.",
      });
      assert.equal(res.isValid, true);
      assert.deepEqual(res.errors, {});
    });
  });

  // REMOVE mode validation
  describe("REMOVE Mode", () => {
    test("fails if skill_id is missing", () => {
      const res = validateProposal("REMOVE", {
        justification: "No longer working with legacy technology stack.",
      });
      assert.equal(res.isValid, false);
      assert.ok(res.errors.skill_id);
    });

    test("does NOT require proficiency or years_of_experience", () => {
      const res = validateProposal("REMOVE", {
        skill_id: 7,
        justification: "Deprecated stack, transitioning to modern cloud database services.",
      });
      assert.equal(res.isValid, true);
      assert.deepEqual(res.errors, {});
    });

    test("fails if justification is under 10 characters", () => {
      const res = validateProposal("REMOVE", {
        skill_id: 7,
        justification: "Remove it",
      });
      assert.equal(res.isValid, false);
      assert.ok(res.errors.justification);
    });

    test("passes with valid REMOVE fields", () => {
      const res = validateProposal("REMOVE", {
        skill_id: 7,
        justification: "Transitioning to specialized machine learning engineering full-time.",
      });
      assert.equal(res.isValid, true);
      assert.deepEqual(res.errors, {});
    });
  });
});

/* ============================================================================
   2. Review Decision Validation (validateRejectionRemarks)
   ============================================================================ */
describe("2. Review Decision Validation (validateRejectionRemarks)", () => {
  test("rejects null, undefined, and empty string", () => {
    assert.equal(validateRejectionRemarks(null).isValid, false);
    assert.equal(validateRejectionRemarks(undefined).isValid, false);
    assert.equal(validateRejectionRemarks("").isValid, false);
  });

  test("rejects whitespace-only remarks", () => {
    const res = validateRejectionRemarks("     ");
    assert.equal(res.isValid, false);
    assert.ok(res.error.includes("mandatory"));
  });

  test("rejects remarks shorter than 5 characters", () => {
    const res1 = validateRejectionRemarks("No");
    assert.equal(res1.isValid, false);
    assert.ok(res1.error.includes("at least 5"));

    const res2 = validateRejectionRemarks("Nope");
    assert.equal(res2.isValid, false);
    assert.ok(res2.error.includes("at least 5"));
  });

  test("accepts valid rejection remarks of 5 or more characters", () => {
    const res = validateRejectionRemarks("Requires additional project demonstration.");
    assert.equal(res.isValid, true);
    assert.equal(res.error, null);
  });

  test("rejects remarks exceeding 1000 characters", () => {
    const longStr = "r".repeat(1001);
    const res = validateRejectionRemarks(longStr);
    assert.equal(res.isValid, false);
    assert.ok(res.error.includes("cannot exceed 1000"));
  });
});

/* ============================================================================
   3. Presentation & Change Formatters (describeChange, formatSkillDate)
   ============================================================================ */
describe("3. Presentation & Change Formatters", () => {
  test("describeChange formats ADD proposal accurately", () => {
    const desc = describeChange({
      action: SKILL_ACTIONS.ADD,
      proposed_skill_name: "GraphQL",
      proficiency: "INTERMEDIATE",
      years_of_experience: 2,
    });
    assert.equal(desc, "Add GraphQL (Intermediate, 2 yrs)");
  });

  test("describeChange formats UPDATE proposal with proficiency change", () => {
    const desc = describeChange({
      action: SKILL_ACTIONS.UPDATE,
      skill_name: "React",
      proficiency: "EXPERT",
      years_of_experience: 5,
    });
    assert.equal(desc, "React → Expert, 5 yrs");
  });

  test("describeChange formats REMOVE proposal accurately", () => {
    const desc = describeChange({
      action: SKILL_ACTIONS.REMOVE,
      skill_name: "COBOL",
    });
    assert.equal(desc, "Remove COBOL");
  });

  test("describeChange handles empty or null request safely", () => {
    assert.equal(describeChange(null), "—");
    assert.equal(describeChange(undefined), "—");
  });

  test("formatSkillDate formats ISO dates to readable string", () => {
    const formatted = formatSkillDate("2026-11-23T10:00:00Z");
    assert.ok(formatted.includes("Nov"));
    assert.ok(formatted.includes("2026"));
  });

  test("formatSkillDate handles null or invalid date safely", () => {
    assert.equal(formatSkillDate(null), "—");
    assert.equal(formatSkillDate(""), "—");
  });

  test("exports expected constants and labels", () => {
    assert.equal(SKILL_ACTIONS.ADD, "ADD");
    assert.equal(SKILL_ACTIONS.UPDATE, "UPDATE");
    assert.equal(SKILL_ACTIONS.REMOVE, "REMOVE");

    assert.equal(SKILL_STATUSES.PENDING, "PENDING");
    assert.equal(SKILL_STATUSES.APPROVED, "APPROVED");
    assert.equal(SKILL_STATUSES.REJECTED, "REJECTED");

    assert.equal(PROFICIENCY_LABELS.BEGINNER, "Beginner");
    assert.equal(PROFICIENCY_LABELS.INTERMEDIATE, "Intermediate");
    assert.equal(PROFICIENCY_LABELS.EXPERT, "Expert");
    assert.deepEqual(SKILL_PROFICIENCIES, ["BEGINNER", "INTERMEDIATE", "EXPERT"]);
  });
});

/* ============================================================================
   4. Skill Proposal & Review API Client Integration (Mocked Fetch)
   ============================================================================ */
describe("4. Skill Proposal & Review API Client Integration", () => {
  const originalFetch = globalThis.fetch;
  let fetchCalls = [];

  beforeEach(() => {
    fetchCalls = [];
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("proposeSkillChange dispatches POST /api/v1/profile/me/skill-requests with payload", async () => {
    globalThis.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      return {
        ok: true,
        status: 201,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          request_id: 101,
          action: "ADD",
          skill_id: 4,
          proficiency: "INTERMEDIATE",
          years_of_experience: 2,
          justification: "Built internal analytics dashboard.",
          status: "PENDING",
        }),
      };
    };

    const payload = {
      action: "ADD",
      skill_id: 4,
      proficiency: "INTERMEDIATE",
      years_of_experience: 2,
      justification: "Built internal analytics dashboard.",
    };

    const res = await proposeSkillChange(payload);
    assert.equal(fetchCalls.length, 1);
    const call = fetchCalls[0];
    assert.ok(call.url.includes("/api/v1/profile/me/skill-requests"));
    assert.equal(call.options.method, "POST");
    assert.deepEqual(JSON.parse(call.options.body), payload);
    assert.equal(res.request_id, 101);
    assert.equal(res.status, "PENDING");
  });

  test("getMySkillRequests dispatches GET /api/v1/profile/me/skill-requests", async () => {
    globalThis.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => [
          { request_id: 1, action: "ADD", status: "PENDING", skill_name: "React" },
          { request_id: 2, action: "UPDATE", status: "APPROVED", skill_name: "Python" },
        ],
      };
    };

    const res = await getMySkillRequests();
    assert.equal(fetchCalls.length, 1);
    const call = fetchCalls[0];
    assert.ok(call.url.includes("/api/v1/profile/me/skill-requests"));
    assert.equal(call.options.method, "GET");
    assert.equal(res.length, 2);
    assert.equal(res[0].request_id, 1);
  });

  test("getSkillRequestQueue formats status, page, and limit query parameters", async () => {
    globalThis.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          items: [{ request_id: 5, action: "ADD", status: "PENDING" }],
          total: 1,
          page: 1,
          limit: 20,
        }),
      };
    };

    const res = await getSkillRequestQueue({ status: "PENDING", page: 1, limit: 20 });
    assert.equal(fetchCalls.length, 1);
    const call = fetchCalls[0];
    assert.ok(call.url.includes("/api/v1/skill-requests"));
    assert.ok(call.url.includes("status=PENDING"));
    assert.ok(call.url.includes("page=1"));
    assert.ok(call.url.includes("limit=20"));
    assert.equal(call.options.method, "GET");
    assert.equal(res.total, 1);
  });

  test("approveSkillRequest dispatches PUT /api/v1/skill-requests/{id}/approve with remarks", async () => {
    globalThis.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          request_id: 42,
          status: "APPROVED",
          remarks: "Verified in recent sprints",
        }),
      };
    };

    const res = await approveSkillRequest(42, "Verified in recent sprints");
    assert.equal(fetchCalls.length, 1);
    const call = fetchCalls[0];
    assert.ok(call.url.includes("/api/v1/skill-requests/42/approve"));
    assert.equal(call.options.method, "PUT");
    const body = JSON.parse(call.options.body);
    assert.equal(body.remarks, "Verified in recent sprints");
    assert.equal(res.status, "APPROVED");
  });

  test("rejectSkillRequest dispatches PUT /api/v1/skill-requests/{id}/reject with mandatory remarks", async () => {
    globalThis.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          request_id: 42,
          status: "REJECTED",
          remarks: "Needs additional client-facing proof of expertise",
        }),
      };
    };

    const res = await rejectSkillRequest(42, "Needs additional client-facing proof of expertise");
    assert.equal(fetchCalls.length, 1);
    const call = fetchCalls[0];
    assert.ok(call.url.includes("/api/v1/skill-requests/42/reject"));
    assert.equal(call.options.method, "PUT");
    const body = JSON.parse(call.options.body);
    assert.equal(body.remarks, "Needs additional client-facing proof of expertise");
    assert.equal(res.status, "REJECTED");
  });

  test("handles HTTP 409 duplicate pending proposal error gracefully", async () => {
    globalThis.fetch = async () => ({
      ok: false,
      status: 409,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({
        detail: "A pending request already exists for this skill",
      }),
    });

    await assert.rejects(
      async () => {
        await proposeSkillChange({
          action: "ADD",
          skill_id: 1,
          proficiency: "EXPERT",
          years_of_experience: 5,
          justification: "Duplicate attempt",
        });
      },
      (err) => {
        assert.equal(err.status, 409);
        assert.ok(err.data.detail.includes("pending request already exists"));
        return true;
      }
    );
  });

  test("handles HTTP 403 unauthorized review error gracefully", async () => {
    globalThis.fetch = async () => ({
      ok: false,
      status: 403,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({
        detail: "You are not authorized to decide this skill request.",
      }),
    });

    await assert.rejects(
      async () => {
        await approveSkillRequest(99, "Self approval attempt");
      },
      (err) => {
        assert.equal(err.status, 403);
        assert.ok(err.data.detail.includes("not authorized"));
        return true;
      }
    );
  });
});

/* ============================================================================
   5. Role-Based Navigation & Route Access Control (US-34)
   ============================================================================ */
describe("5. Role-Based Navigation & Route Access Control (US-34)", () => {
  test("HR can see /skill-requests in navConfig", () => {
    const hrNav = filterNavForRole(navConfig, "HR");
    assert.ok(
      hrNav.some((item) => item.path === "/skill-requests"),
      "HR must see /skill-requests in navigation"
    );
  });

  test("TEAM_LEAD can see /skill-requests in navConfig", () => {
    const tlNav = filterNavForRole(navConfig, "TEAM_LEAD");
    assert.ok(
      tlNav.some((item) => item.path === "/skill-requests"),
      "TEAM_LEAD must see /skill-requests in navigation"
    );
  });

  test("ADMIN and SYSTEM_ADMIN can see /skill-requests in navConfig", () => {
    const adminNav = filterNavForRole(navConfig, "ADMIN");
    assert.ok(
      adminNav.some((item) => item.path === "/skill-requests"),
      "ADMIN must see /skill-requests in navigation"
    );

    const sysAdminNav = filterNavForRole(navConfig, "SYSTEM_ADMIN");
    assert.ok(
      sysAdminNav.some((item) => item.path === "/skill-requests"),
      "SYSTEM_ADMIN must see /skill-requests in navigation"
    );
  });

  test("EMPLOYEE cannot see /skill-requests in navConfig", () => {
    const empNav = filterNavForRole(navConfig, "EMPLOYEE");
    assert.equal(
      empNav.some((item) => item.path === "/skill-requests"),
      false,
      "EMPLOYEE must NOT see /skill-requests in navigation"
    );
  });

  test("CLIENT cannot see /skill-requests in navConfig", () => {
    const clientNav = filterNavForRole(navConfig, "CLIENT");
    assert.equal(
      clientNav.some((item) => item.path === "/skill-requests"),
      false,
      "CLIENT must NOT see /skill-requests in navigation"
    );
  });

  test("PM and IT_SUPPORT cannot see /skill-requests in navConfig", () => {
    for (const r of ["PM", "PROJECT_MANAGER", "IT_SUPPORT"]) {
      const nav = filterNavForRole(navConfig, r);
      assert.equal(
        nav.some((item) => item.path === "/skill-requests"),
        false,
        `${r} must NOT see /skill-requests in navigation`
      );
    }
  });

  test("All internal roles (EMPLOYEE, TEAM_LEAD, HR, PM, ADMIN) can access /profile", () => {
    for (const role of ["EMPLOYEE", "TEAM_LEAD", "HR", "PM", "ADMIN"]) {
      const nav = filterNavForRole(navConfig, role);
      assert.ok(
        nav.some((item) => item.path === "/profile"),
        `${role} must have access to /profile`
      );
    }
  });
});

/* ============================================================================
   6. UI Business Logic & Pending Request Lockout
   ============================================================================ */
describe("6. UI Business Logic & Pending Request Lockout", () => {
  test("pendingSkillIds logic correctly locks out only skills with PENDING proposals", () => {
    const requests = [
      { request_id: 1, skill_id: 10, status: "PENDING" },
      { request_id: 2, skill_id: 20, status: "APPROVED" },
      { request_id: 3, skill_id: 30, status: "REJECTED" },
      { request_id: 4, skill_id: 40, status: "PENDING" },
    ];

    const pendingIds = new Set();
    requests.forEach((r) => {
      if (r?.status === "PENDING" && r.skill_id) {
        pendingIds.add(Number(r.skill_id));
      }
    });

    assert.equal(pendingIds.has(10), true);
    assert.equal(pendingIds.has(40), true);
    assert.equal(pendingIds.has(20), false);
    assert.equal(pendingIds.has(30), false);
  });

  test("pagination helper computes totalPages and item bounds correctly", () => {
    const PAGE_SIZE = 20;
    const total = 45;
    const page = 2;

    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const startIndex = (page - 1) * PAGE_SIZE + 1;
    const endIndex = Math.min(page * PAGE_SIZE, total);

    assert.equal(totalPages, 3);
    assert.equal(startIndex, 21);
    assert.equal(endIndex, 40);
  });

  test("handles empty list pagination correctly", () => {
    const PAGE_SIZE = 20;
    const total = 0;
    const page = 1;

    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const startIndex = total > 0 ? (page - 1) * PAGE_SIZE + 1 : 0;
    const endIndex = Math.min(page * PAGE_SIZE, total);

    assert.equal(totalPages, 1);
    assert.equal(startIndex, 0);
    assert.equal(endIndex, 0);
  });
});
