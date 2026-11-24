import { test, describe, afterEach } from "node:test";
import assert from "node:assert/strict";

import {
  navConfig,
  filterNavForRole,
} from "../src/components/layout/navConfig.js";

import {
  INTERNAL_ROLES,
  getHomeRouteForRole,
  isExecutive,
  isClient,
  isHr,
  isInternalRole,
  setSession,
  clearSession,
} from "../src/auth/session.js";

import {
  parseContentDisposition,
  sanitizeFilename,
  downloadAuthenticatedFile,
} from "../src/api/download.js";

import { ApiError, setStoredToken } from "../src/api/client.js";

// ============================================================================
// 1. Role-Aware Navigation Tests (filterNavForRole)
// ============================================================================
describe("1. Role-Aware Navigation Filtering (filterNavForRole)", () => {
  const sampleNav = [
    { path: "/dashboard", label: "Dashboard", roles: INTERNAL_ROLES },
    { path: "/tasks", label: "Tasks", roles: ["EMPLOYEE", "TEAM_LEAD"] },
    { path: "/hr/leave-policies", label: "Leave Policies", roles: ["HR", "ADMIN"] },
    { path: "/admin/users", label: "User Admin", roles: ["ADMIN", "SYSTEM_ADMIN"] },
    { path: "/executive/console", label: "Executive Console", roles: ["MNC_EXECUTIVE", "ADMIN"] },
    { path: "/help", label: "Public Help", roles: null }, // shared entry
  ];

  test("1. An EMPLOYEE does not see HR-only navigation", () => {
    const visible = filterNavForRole(sampleNav, "EMPLOYEE");
    const paths = visible.map((item) => item.path);
    assert.equal(paths.includes("/hr/leave-policies"), false);
  });

  test("2. An EMPLOYEE does not see admin-only navigation", () => {
    const visible = filterNavForRole(sampleNav, "EMPLOYEE");
    const paths = visible.map((item) => item.path);
    assert.equal(paths.includes("/admin/users"), false);
  });

  test("3. An EMPLOYEE does not see executive-only navigation", () => {
    const visible = filterNavForRole(sampleNav, "EMPLOYEE");
    const paths = visible.map((item) => item.path);
    assert.equal(paths.includes("/executive/console"), false);
  });

  test("4. A CLIENT cannot see internal navigation entries", () => {
    const visible = filterNavForRole(sampleNav, "CLIENT");
    const paths = visible.map((item) => item.path);
    assert.equal(paths.includes("/dashboard"), false);
    assert.equal(paths.includes("/tasks"), false);
    assert.equal(paths.includes("/hr/leave-policies"), false);
    assert.equal(paths.includes("/admin/users"), false);
    assert.equal(paths.includes("/executive/console"), false);
  });

  test("5. Shared entries (roles: null) are handled correctly and visible to authenticated roles", () => {
    const empVisible = filterNavForRole(sampleNav, "EMPLOYEE");
    assert.equal(empVisible.some((item) => item.path === "/help"), true);

    const clientVisible = filterNavForRole(sampleNav, "CLIENT");
    assert.equal(clientVisible.some((item) => item.path === "/help"), true);

    const adminVisible = filterNavForRole(sampleNav, "ADMIN");
    assert.equal(adminVisible.some((item) => item.path === "/help"), true);
  });

  test("6. Strictly fail-closed: missing, null, undefined, empty, or unknown roles return an empty array", () => {
    assert.deepEqual(filterNavForRole(sampleNav, "UNKNOWN_ROLE"), []);
    assert.deepEqual(filterNavForRole(sampleNav, "HACKER"), []);
    assert.deepEqual(filterNavForRole(sampleNav, null), []);
    assert.deepEqual(filterNavForRole(sampleNav, undefined), []);
    assert.deepEqual(filterNavForRole(sampleNav, ""), []);
    assert.deepEqual(filterNavForRole(sampleNav, {}), []);
    assert.deepEqual(filterNavForRole(sampleNav, { role: "UNKNOWN" }), []);
  });

  test("7. Strictly enforces roles property semantics: only roles: null is shared, undefined or malformed non-array roles are excluded", () => {
    const edgeCaseNav = [
      { path: "/strictly-null", label: "Shared", roles: null },
      { path: "/undef-roles", label: "Undef", roles: undefined },
      { path: "/missing-roles", label: "Missing" },
      { path: "/string-roles", label: "String", roles: "EMPLOYEE" }, // malformed non-array
      { path: "/number-roles", label: "Number", roles: 42 }, // malformed non-array
      { path: "/valid-array", label: "Valid", roles: ["EMPLOYEE"] },
    ];

    const empVisible = filterNavForRole(edgeCaseNav, "EMPLOYEE");
    const empPaths = empVisible.map((i) => i.path);
    assert.equal(empPaths.includes("/strictly-null"), true);
    assert.equal(empPaths.includes("/valid-array"), true);
    assert.equal(empPaths.includes("/undef-roles"), false);
    assert.equal(empPaths.includes("/missing-roles"), false);
    assert.equal(empPaths.includes("/string-roles"), false);
    assert.equal(empPaths.includes("/number-roles"), false);

    const clientVisible = filterNavForRole(edgeCaseNav, "CLIENT");
    const clientPaths = clientVisible.map((i) => i.path);
    assert.deepEqual(clientPaths, ["/strictly-null"]);
  });

  test("8. The input configuration is not mutated", () => {
    const frozenSample = Object.freeze([
      Object.freeze({ path: "/dashboard", label: "Dashboard", roles: INTERNAL_ROLES }),
      Object.freeze({ path: "/admin", label: "Admin", roles: ["ADMIN"] }),
    ]);
    const originalLength = frozenSample.length;
    const result = filterNavForRole(frozenSample, "EMPLOYEE");

    assert.equal(frozenSample.length, originalLength);
    assert.equal(result.length, 1);
    assert.notEqual(result, frozenSample);
  });

  test("filters default application navConfig cleanly across all 9 canonical roles", () => {
    // 1. EMPLOYEE
    const empNav = filterNavForRole(navConfig, "EMPLOYEE");
    const empPaths = empNav.map((i) => i.path);
    assert.equal(empPaths.includes("/dashboard"), true);
    assert.equal(empPaths.includes("/tasks"), true);
    assert.equal(empPaths.includes("/leave"), true);
    assert.equal(empPaths.includes("/team"), true);
    assert.equal(empPaths.includes("/profile"), true);
    assert.equal(empPaths.includes("/projects"), false);
    assert.equal(empPaths.includes("/pm/risk-dashboard"), false);
    assert.equal(empPaths.includes("/team-lead/tasks"), false);
    assert.equal(empPaths.includes("/admin/users"), false);
    assert.equal(empPaths.includes("/admin/security"), false);
    assert.equal(empPaths.includes("/it-support"), false);

    // 2. TEAM_LEAD
    const tlNav = filterNavForRole(navConfig, "TEAM_LEAD");
    const tlPaths = tlNav.map((i) => i.path);
    assert.equal(tlPaths.includes("/team-lead/tasks"), true);
    assert.equal(tlPaths.includes("/team-lead/leave"), true);
    assert.equal(tlPaths.includes("/leave"), true);
    assert.equal(tlPaths.includes("/projects"), false);
    assert.equal(tlPaths.includes("/pm/risk-dashboard"), false);

    // 3. PM
    const pmNav = filterNavForRole(navConfig, "PM");
    const pmPaths = pmNav.map((i) => i.path);
    assert.equal(pmPaths.includes("/projects"), true);
    assert.equal(pmPaths.includes("/pm/risk-dashboard"), true);
    assert.equal(pmPaths.includes("/team-lead/tasks"), true);
    assert.equal(pmPaths.includes("/admin/users"), false);
    assert.equal(pmPaths.includes("/admin/security"), false);

    // 4. HR
    const hrNav = filterNavForRole(navConfig, "HR");
    const hrPaths = hrNav.map((i) => i.path);
    assert.equal(hrPaths.includes("/hr/leave-policies"), true);
    assert.equal(hrPaths.includes("/team-lead/leave"), true);
    assert.equal(hrPaths.includes("/projects"), false);
    assert.equal(hrPaths.includes("/pm/risk-dashboard"), false);

    // 5. IT_SUPPORT
    const itNav = filterNavForRole(navConfig, "IT_SUPPORT");
    const itPaths = itNav.map((i) => i.path);
    assert.equal(itPaths.includes("/it-support"), true);
    assert.equal(itPaths.includes("/projects"), false);
    assert.equal(itPaths.includes("/admin/users"), false);

    // 6. ADMIN (sees Security Ops, Users, Projects, Risk Dashboard, Executive)
    const adminNav = filterNavForRole(navConfig, "ADMIN");
    const adminPaths = adminNav.map((i) => i.path);
    assert.equal(adminPaths.includes("/admin/users"), true);
    assert.equal(adminPaths.includes("/admin/security"), true);
    assert.equal(adminPaths.includes("/projects"), true);
    assert.equal(adminPaths.includes("/pm/risk-dashboard"), true);
    assert.equal(adminPaths.includes("/executive/console"), true);

    // 7. SYSTEM_ADMIN (sees Security Ops and Users, but NEVER Projects or Risk Dashboard)
    const sysAdminNav = filterNavForRole(navConfig, "SYSTEM_ADMIN");
    const sysAdminPaths = sysAdminNav.map((i) => i.path);
    assert.equal(sysAdminPaths.includes("/admin/users"), true);
    assert.equal(sysAdminPaths.includes("/admin/security"), true);
    assert.equal(sysAdminPaths.includes("/it-support"), true);
    assert.equal(sysAdminPaths.includes("/projects"), false);
    assert.equal(sysAdminPaths.includes("/pm/risk-dashboard"), false);

    // 8. MNC_EXECUTIVE
    const execNav = filterNavForRole(navConfig, "MNC_EXECUTIVE");
    const execPaths = execNav.map((i) => i.path);
    assert.equal(execPaths.includes("/executive/console"), true);
    assert.equal(execPaths.includes("/projects"), false);
    assert.equal(execPaths.includes("/admin/users"), false);

    // 9. CLIENT (sees 0 internal navigation entries)
    const clientNav = filterNavForRole(navConfig, "CLIENT");
    assert.equal(clientNav.length, 0);
  });

  test("accepts user objects with role or user_type properties", () => {
    // User object with role
    const empByRole = filterNavForRole(sampleNav, { role: "EMPLOYEE" });
    assert.equal(empByRole.some((i) => i.path === "/dashboard"), true);
    assert.equal(empByRole.some((i) => i.path === "/tasks"), true);
    assert.equal(empByRole.some((i) => i.path === "/executive/console"), false);

    // User object with user_type
    const clientByUserType = filterNavForRole(sampleNav, { user_type: "CLIENT" });
    assert.equal(clientByUserType.some((i) => i.path === "/dashboard"), false);
    assert.equal(clientByUserType.some((i) => i.path === "/tasks"), false);
    assert.equal(clientByUserType.some((i) => i.path === "/help"), true);

    // User object with both properties
    const execUser = filterNavForRole(sampleNav, { user_type: "MNC_EXECUTIVE", role: "MNC_EXECUTIVE" });
    assert.equal(execUser.some((i) => i.path === "/executive/console"), true);

    // Empty user object or missing role property strictly returns empty array (fail-closed)
    const emptyUser = filterNavForRole(sampleNav, {});
    assert.deepEqual(emptyUser, []);

    // Case-insensitivity and formatting in user objects
    const formattedUser = filterNavForRole(sampleNav, { role: "team-lead" });
    assert.equal(formattedUser.some((i) => i.path === "/tasks"), true);
  });
});

// ============================================================================
// 2. Role-Based Home-Page Redirects (getHomeRouteForRole)
// ============================================================================
describe("2. Role-Based Home-Page Redirects (getHomeRouteForRole)", () => {
  test("maps CLIENT to /client/projects", () => {
    assert.equal(getHomeRouteForRole("CLIENT"), "/client/projects");
    assert.equal(getHomeRouteForRole("client"), "/client/projects");
    assert.equal(getHomeRouteForRole({ user_type: "CLIENT" }), "/client/projects");
  });

  test("maps MNC_EXECUTIVE to /executive/console", () => {
    assert.equal(getHomeRouteForRole("MNC_EXECUTIVE"), "/executive/console");
    assert.equal(getHomeRouteForRole("mnc_executive"), "/executive/console");
    assert.equal(getHomeRouteForRole("MNC-EXECUTIVE"), "/executive/console");
    assert.equal(getHomeRouteForRole({ user_type: "MNC_EXECUTIVE" }), "/executive/console");
  });

  test("maps EMPLOYEE to /dashboard", () => {
    assert.equal(getHomeRouteForRole("EMPLOYEE"), "/dashboard");
    assert.equal(getHomeRouteForRole({ user_type: "EMPLOYEE" }), "/dashboard");
  });

  test("maps TEAM_LEAD to /dashboard", () => {
    assert.equal(getHomeRouteForRole("TEAM_LEAD"), "/dashboard");
    assert.equal(getHomeRouteForRole("team_lead"), "/dashboard");
  });

  test("maps PM to /dashboard", () => {
    assert.equal(getHomeRouteForRole("PM"), "/dashboard");
  });

  test("maps HR to /dashboard", () => {
    assert.equal(getHomeRouteForRole("HR"), "/dashboard");
  });

  test("maps ADMIN to /dashboard", () => {
    assert.equal(getHomeRouteForRole("ADMIN"), "/dashboard");
  });

  test("maps SYSTEM_ADMIN to /dashboard", () => {
    assert.equal(getHomeRouteForRole("SYSTEM_ADMIN"), "/dashboard");
  });

  test("maps IT_SUPPORT to /dashboard", () => {
    assert.equal(getHomeRouteForRole("IT_SUPPORT"), "/dashboard");
  });

  test("fails safely for unknown, missing, or invalid roles by returning /login", () => {
    assert.equal(getHomeRouteForRole(null), "/login");
    assert.equal(getHomeRouteForRole(undefined), "/login");
    assert.equal(getHomeRouteForRole(""), "/login");
    assert.equal(getHomeRouteForRole("RANDOM_UNKNOWN_ROLE"), "/login");
    assert.equal(getHomeRouteForRole({}), "/login");
  });

  test("RootRedirect contract: maps authenticated roles or user objects accurately and never redirects undefined role to /dashboard", () => {
    // If auth hook supplies undefined/null role (e.g. initial or broken auth state), must go to safe fallback (/login)
    assert.equal(getHomeRouteForRole(undefined), "/login");
    assert.equal(getHomeRouteForRole(null), "/login");

    // Client user
    assert.equal(getHomeRouteForRole("CLIENT"), "/client/projects");
    assert.equal(getHomeRouteForRole({ role: "CLIENT" }), "/client/projects");
    assert.equal(getHomeRouteForRole({ user_type: "CLIENT" }), "/client/projects");

    // MNC Executive user
    assert.equal(getHomeRouteForRole("MNC_EXECUTIVE"), "/executive/console");
    assert.equal(getHomeRouteForRole({ role: "MNC_EXECUTIVE" }), "/executive/console");
    assert.equal(getHomeRouteForRole({ user_type: "MNC_EXECUTIVE" }), "/executive/console");

    // Internal roles must never route to /login or /client/projects
    for (const role of INTERNAL_ROLES) {
      const destination = getHomeRouteForRole(role);
      const destinationFromObj = getHomeRouteForRole({ user_type: role });
      assert.equal(destination, destinationFromObj);
      if (role === "MNC_EXECUTIVE") {
        assert.equal(destination, "/executive/console");
      } else {
        assert.equal(destination, "/dashboard");
      }
      assert.notEqual(destination, "/login");
      assert.notEqual(destination, "/client/projects");
    }
  });
});

// ============================================================================
// 3. Content-Disposition Header Filename Parser (parseContentDisposition)
// ============================================================================
describe("3. Content-Disposition Filename Parsing (parseContentDisposition)", () => {
  test("handles quoted filename", () => {
    const header = 'attachment; filename="report.pdf"';
    assert.equal(parseContentDisposition(header), "report.pdf");
  });

  test("handles unquoted filename", () => {
    const header = "attachment; filename=summary_export.csv";
    assert.equal(parseContentDisposition(header), "summary_export.csv");
  });

  test("handles UTF-8 extended filename*", () => {
    const header = "attachment; filename*=UTF-8''report%20Q4.csv";
    assert.equal(parseContentDisposition(header), "report Q4.csv");

    const lowercaseCharset = "attachment; filename*=utf-8''deliverable%2Dv1.pdf";
    assert.equal(parseContentDisposition(lowercaseCharset), "deliverable-v1.pdf");
  });

  test("prefers valid UTF-8 filename* when both parameters are present", () => {
    const header = 'attachment; filename="fallback.pdf"; filename*=UTF-8\'\'preferred%20report.pdf';
    assert.equal(parseContentDisposition(header), "preferred report.pdf");
  });

  test("handles missing, null, or non-string header gracefully", () => {
    assert.equal(parseContentDisposition(null), null);
    assert.equal(parseContentDisposition(undefined), null);
    assert.equal(parseContentDisposition(""), null);
    assert.equal(parseContentDisposition(123), null);
  });

  test("handles malformed percent-encoding gracefully and falls back to standard filename", () => {
    const malformed = 'attachment; filename="safe_fallback.pdf"; filename*=UTF-8\'\'%ZZmalformed.pdf';
    assert.equal(parseContentDisposition(malformed), "safe_fallback.pdf");

    const onlyMalformed = "attachment; filename*=UTF-8''%ZZmalformed.pdf";
    assert.equal(parseContentDisposition(onlyMalformed), null);
  });

  test("handles empty or unusable filenames safely", () => {
    assert.equal(parseContentDisposition('attachment; filename=""'), null);
    assert.equal(parseContentDisposition('attachment; filename="   "'), null);
    assert.equal(parseContentDisposition("attachment;"), null);
  });

  test("sanitizes path traversal attempts and invalid characters", () => {
    assert.equal(parseContentDisposition('attachment; filename="../../etc/passwd"'), "passwd");
    assert.equal(parseContentDisposition('attachment; filename="..\\..\\Windows\\System32\\cmd.exe"'), "cmd.exe");
    assert.equal(parseContentDisposition('attachment; filename="audit:log*2026?.csv"'), "auditlog2026.csv");
  });

  test("sanitizes ASCII control characters (0x00-0x1F, 0x7F DEL) including CR, LF, and TAB", () => {
    // Direct sanitizeFilename tests
    assert.equal(sanitizeFilename("report\r\n.pdf"), "report.pdf");
    assert.equal(sanitizeFilename("data\x00\x08\x1f.csv"), "data.csv");
    assert.equal(sanitizeFilename("test\x7fname.txt"), "testname.txt");
    assert.equal(sanitizeFilename("tab\tseparated.tsv"), "tabseparated.tsv");
    assert.equal(sanitizeFilename("..\\..\\test\r\n.pdf"), "test.pdf");

    // Content-Disposition header with CRLF / control character injection attempt
    const crlfHeader = 'attachment; filename="malicious\r\nheader.pdf"';
    assert.equal(parseContentDisposition(crlfHeader), "maliciousheader.pdf");

    const tabHeader = 'attachment; filename="sheet\tdata.xlsx"';
    assert.equal(parseContentDisposition(tabHeader), "sheetdata.xlsx");

    // Returns null if control characters or invalid chars leave an empty filename
    assert.equal(sanitizeFilename("\x00\r\n\t"), null);
    assert.equal(sanitizeFilename("   ///???:::***   "), null);
    assert.equal(sanitizeFilename(null), null);
    assert.equal(sanitizeFilename(undefined), null);
    assert.equal(sanitizeFilename(""), null);
  });
});

// ============================================================================
// 4. Session Role Helper Utilities
// ============================================================================
describe("4. Session Role Helpers", () => {
  test("INTERNAL_ROLES contains all internal roles and strictly excludes CLIENT and legacy aliases", () => {
    assert.equal(INTERNAL_ROLES.includes("CLIENT"), false);
    assert.equal(INTERNAL_ROLES.includes("PROJECT_MANAGER"), false);
    assert.equal(INTERNAL_ROLES.includes("HR_MANAGER"), false);
    assert.equal(INTERNAL_ROLES.includes("EMPLOYEE"), true);
    assert.equal(INTERNAL_ROLES.includes("TEAM_LEAD"), true);
    assert.equal(INTERNAL_ROLES.includes("PM"), true);
    assert.equal(INTERNAL_ROLES.includes("HR"), true);
    assert.equal(INTERNAL_ROLES.includes("ADMIN"), true);
    assert.equal(INTERNAL_ROLES.includes("SYSTEM_ADMIN"), true);
    assert.equal(INTERNAL_ROLES.includes("MNC_EXECUTIVE"), true);
    assert.equal(INTERNAL_ROLES.includes("IT_SUPPORT"), true);
    assert.equal(Object.isFrozen(INTERNAL_ROLES), true);
  });

  test("isExecutive identifies MNC_EXECUTIVE accurately", () => {
    assert.equal(isExecutive("MNC_EXECUTIVE"), true);
    assert.equal(isExecutive("mnc_executive"), true);
    assert.equal(isExecutive({ user_type: "MNC_EXECUTIVE" }), true);
    assert.equal(isExecutive("EMPLOYEE"), false);
    assert.equal(isExecutive(null), false);
  });

  test("isClient identifies CLIENT accurately", () => {
    assert.equal(isClient("CLIENT"), true);
    assert.equal(isClient("client"), true);
    assert.equal(isClient({ user_type: "CLIENT" }), true);
    assert.equal(isClient("ADMIN"), false);
    assert.equal(isClient(undefined), false);
  });

  test("isHr identifies HR accurately", () => {
    assert.equal(isHr("HR"), true);
    assert.equal(isHr("hr"), true);
    assert.equal(isHr({ user_type: "HR" }), true);
    assert.equal(isHr("EMPLOYEE"), false);
    assert.equal(isHr(""), false);
  });

  test("isInternalRole confirms internal membership", () => {
    assert.equal(isInternalRole("EMPLOYEE"), true);
    assert.equal(isInternalRole("HR"), true);
    assert.equal(isInternalRole("CLIENT"), false);
    assert.equal(isInternalRole("UNKNOWN"), false);
  });

  test("role helpers accept user objects as well as raw role strings", () => {
    assert.equal(isExecutive({ user_type: "MNC_EXECUTIVE" }), true);
    assert.equal(isExecutive({ role: "MNC_EXECUTIVE" }), true);
    assert.equal(isExecutive({ role: "EMPLOYEE" }), false);

    assert.equal(isClient({ user_type: "CLIENT" }), true);
    assert.equal(isClient({ role: "CLIENT" }), true);
    assert.equal(isClient({ role: "ADMIN" }), false);

    assert.equal(isHr({ user_type: "HR" }), true);
    assert.equal(isHr({ role: "HR" }), true);
    assert.equal(isHr({ role: "EMPLOYEE" }), false);

    assert.equal(isInternalRole({ user_type: "EMPLOYEE" }), true);
    assert.equal(isInternalRole({ role: "TEAM_LEAD" }), true);
    assert.equal(isInternalRole({ role: "CLIENT" }), false);
    assert.equal(isInternalRole({}), false);
  });
});

// ============================================================================
// 5. Authenticated File Download (downloadAuthenticatedFile)
// ============================================================================
describe("5. Authenticated File Download (downloadAuthenticatedFile)", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    clearSession();
    setStoredToken("");
  });

  test("attaches Bearer Authorization header and extracts Content-Disposition filename", async () => {
    setSession({ access_token: "test-bearer-token-12345" });
    let capturedHeaders = null;

    globalThis.fetch = async (url, options) => {
      capturedHeaders = options.headers;
      const fakeBlob = new Blob(["mock pdf content"], { type: "application/pdf" });
      return new Response(fakeBlob, {
        status: 200,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": 'attachment; filename="sprint1-deliverable.pdf"',
        },
      });
    };

    const result = await downloadAuthenticatedFile("/api/v1/deliverables/1/download", "default.pdf");
    assert.equal(capturedHeaders["Authorization"], "Bearer test-bearer-token-12345");
    assert.equal(result.filename, "sprint1-deliverable.pdf");
    assert.equal(result.blob instanceof Blob, true);
  });

  test("uses fallbackName when Content-Disposition is missing", async () => {
    globalThis.fetch = async () => {
      const fakeBlob = new Blob(["mock csv data"], { type: "text/csv" });
      return new Response(fakeBlob, {
        status: 200,
        headers: { "Content-Type": "text/csv" },
      });
    };

    const result = await downloadAuthenticatedFile("/api/v1/reports/export", "fallback_report.csv");
    assert.equal(result.filename, "fallback_report.csv");
  });

  test("sanitizes fallback filenames to prevent path traversal, control chars, and invalid names", async () => {
    globalThis.fetch = async () => {
      const fakeBlob = new Blob(["mock data"], { type: "application/octet-stream" });
      return new Response(fakeBlob, {
        status: 200,
        headers: { "Content-Type": "application/octet-stream" }, // No Content-Disposition
      });
    };

    // Path traversal in fallback
    const dotDotResult = await downloadAuthenticatedFile("/export", "../../report.pdf");
    assert.equal(dotDotResult.filename, "report.pdf");

    // Windows path separators in fallback
    const winPathResult = await downloadAuthenticatedFile("/export", "..\\..\\Windows\\System32\\cmd.exe");
    assert.equal(winPathResult.filename, "cmd.exe");

    // CR/LF/TAB in fallback
    const crlfResult = await downloadAuthenticatedFile("/export", "report\r\n\t.pdf");
    assert.equal(crlfResult.filename, "report.pdf");

    // Empty or entirely invalid fallback name defaults safely to "download"
    const emptyResult = await downloadAuthenticatedFile("/export", "");
    assert.equal(emptyResult.filename, "download");

    const invalidResult = await downloadAuthenticatedFile("/export", "   ///???:::***   ");
    assert.equal(invalidResult.filename, "download");

    const nullResult = await downloadAuthenticatedFile("/export", null);
    assert.equal(nullResult.filename, "download");

    // Normal valid fallback
    const normalResult = await downloadAuthenticatedFile("/export", "summary.csv");
    assert.equal(normalResult.filename, "summary.csv");
  });

  test("throws ApiError on non-success HTTP status (403, 404, 500)", async () => {
    globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({ detail: "You do not have access to download this file." }),
        {
          status: 403,
          statusText: "Forbidden",
          headers: { "Content-Type": "application/json" },
        }
      );
    };

    await assert.rejects(
      () => downloadAuthenticatedFile("/api/v1/deliverables/secret"),
      (err) => {
        assert.equal(err instanceof ApiError, true);
        assert.equal(err.status, 403);
        assert.match(err.message, /You do not have access/);
        return true;
      }
    );
  });
});
