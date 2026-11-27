import { test, describe } from "node:test";
import assert from "node:assert/strict";

import {
  NOTIFICATION_TYPES,
  NOTIFICATION_CATEGORY_LIST,
  UNKNOWN_NOTIFICATION_TYPE,
  getLinkedEntityId,
  getNotificationConfig,
  getNotificationRoute,
  parseServerDate,
} from "../src/features/notifications/notificationTypes.js";

import { ROLES } from "../src/auth/session.js";

/**
 * Complete list of all notification types emitted by the backend:
 * - backend/app/core/notification_types.py
 * - Literal strings in backend/app/features (tasks, support, departments, client_portal, admin)
 */
const BACKEND_NOTIFICATION_TYPES = [
  // Core types
  "LEAVE_REQUESTED",
  "LEAVE_APPROVED",
  "LEAVE_REJECTED",
  "STAFF_LEAVE_APPROVED",
  "TASK_ASSIGNED",
  "TASK_REASSIGNED",
  "TASK_DEADLINE_EXTENDED",
  "TASK_OVERDUE",
  "TASK_DEADLINE_MISSED",
  "SKILL_REQUEST_CREATED",
  "SKILL_REQUEST_DECIDED",
  "SECURITY_ALERT",
  "ACCOUNT_UNLOCKED",
  "ELEVATED_ACCESS_GRANTED",
  "ELEVATED_ACCESS_REVOKED",
  "PROJECT_ASSIGNED",
  "DELIVERABLE_SHARED",
  // Feature-specific literal types
  "DELIVERABLE_FEEDBACK",
  "TASK_APPROVED",
  "TASK_BLOCKED",
  "TASK_COMMENT",
  "TASK_REJECTED",
  "TASK_RESUBMITTED",
  "TASK_SUBMITTED",
  "TEAM_LEAD_ASSIGNED",
  "TEAM_MEMBER_ADDED",
  "TICKET_ASSIGNED",
  "TICKET_CREATED",
  "TICKET_ESCALATED",
  "TICKET_REOPENED",
  "TICKET_RESOLVED",
];

// Notification ids are UUIDs; they must never leak into entity routes.
const NOTIF_UUID = "7d9f2c1e-4b6a-4f3e-9a1d-2c5b8e0f1a23";

describe("1. Notification Types Completeness", () => {
  test("every constant in the backend notification list has an entry in NOTIFICATION_TYPES", () => {
    for (const type of BACKEND_NOTIFICATION_TYPES) {
      const entry = NOTIFICATION_TYPES[type];
      assert.ok(entry, `Expected NOTIFICATION_TYPES to have an entry for "${type}"`);
      assert.ok(entry.icon, `Expected entry for "${type}" to have an icon`);
      assert.ok(entry.label, `Expected entry for "${type}" to have a label`);
      assert.ok(entry.category, `Expected entry for "${type}" to have a category`);
      assert.equal(
        typeof entry.route,
        "function",
        `Expected entry for "${type}" to have a route function`
      );
    }
  });

  test("contains exactly the required categories", () => {
    assert.deepEqual(NOTIFICATION_CATEGORY_LIST, [
      "All",
      "Tasks",
      "Leave",
      "Teams & Skills",
      "Support",
      "Security",
      "Projects & Clients",
    ]);
  });
});

describe("2. Role-Dependent Route Resolution", () => {
  test("PROJECT_ASSIGNED routes to /projects/{id} for PM, ADMIN, and SYSTEM_ADMIN", () => {
    const notif = { id: NOTIF_UUID, type: "PROJECT_ASSIGNED", link: "/projects/101" };

    assert.equal(getNotificationRoute(notif, ROLES.PM), "/projects/101");
    assert.equal(getNotificationRoute(notif, ROLES.ADMIN), "/projects/101");
    assert.equal(getNotificationRoute(notif, ROLES.SYSTEM_ADMIN), "/projects/101");
  });

  test("PROJECT_ASSIGNED routes to /tasks for other roles (e.g. EMPLOYEE, TEAM_LEAD)", () => {
    const notif = { id: NOTIF_UUID, type: "PROJECT_ASSIGNED", link: "/projects/101" };

    assert.equal(getNotificationRoute(notif, ROLES.EMPLOYEE), "/tasks");
    assert.equal(getNotificationRoute(notif, ROLES.TEAM_LEAD), "/tasks");
    assert.equal(getNotificationRoute(notif, ROLES.CLIENT), "/tasks");
  });

  test("DELIVERABLE_SHARED routes CLIENT to /client/projects/{id} using the backend deliverables link", () => {
    const notif = {
      id: NOTIF_UUID,
      type: "DELIVERABLE_SHARED",
      link: "/client/projects/500/deliverables",
    };
    assert.equal(getNotificationRoute(notif, ROLES.CLIENT), "/client/projects/500");
  });

  test("DELIVERABLE_SHARED routes non-CLIENT roles to /projects/{id}", () => {
    const notif = { id: NOTIF_UUID, type: "DELIVERABLE_SHARED", link: "/projects/500/deliverables" };

    assert.equal(getNotificationRoute(notif, ROLES.PM), "/projects/500");
    assert.equal(getNotificationRoute(notif, ROLES.ADMIN), "/projects/500");
  });

  test("DELIVERABLE_FEEDBACK routes to /client/projects/{id} for CLIENT and /projects/{id} otherwise", () => {
    const notif = { id: NOTIF_UUID, type: "DELIVERABLE_FEEDBACK", link: "/projects/500/deliverables" };

    assert.equal(getNotificationRoute(notif, ROLES.CLIENT), "/client/projects/500");
    assert.equal(getNotificationRoute(notif, ROLES.PM), "/projects/500");
  });

  test("project routes fall back to the list when the link has no project id", () => {
    const notif = { id: NOTIF_UUID, type: "DELIVERABLE_SHARED", link: null };
    assert.equal(getNotificationRoute(notif, ROLES.CLIENT), "/client/projects");
    assert.equal(getNotificationRoute(notif, ROLES.PM), "/projects");
  });
});

describe("3. Mapped Types Ignore Backend Links", () => {
  test("backend links that are not frontend routes resolve via route()", () => {
    const cases = [
      [{ type: "TASK_COMMENT", link: "/tasks/11" }, ROLES.EMPLOYEE, "/tasks?task=11"],
      [{ type: "TASK_OVERDUE", link: "/tasks/7" }, ROLES.EMPLOYEE, "/tasks?task=7"],
      [
        { type: "TASK_SUBMITTED", link: "/api/v1/tasks/9/submissions" },
        ROLES.TEAM_LEAD,
        "/team-lead/tasks?tab=review",
      ],
      [{ type: "TASK_RESUBMITTED", link: "/tasks/9" }, ROLES.TEAM_LEAD, "/team-lead/tasks?tab=review"],
      [{ type: "LEAVE_APPROVED", link: "/leave/requests/3" }, ROLES.EMPLOYEE, "/leave"],
      [{ type: "SKILL_REQUEST_CREATED", link: "/skills/requests/5" }, ROLES.TEAM_LEAD, "/skill-requests"],
      [{ type: "SKILL_REQUEST_DECIDED", link: "/profile/me/skills" }, ROLES.EMPLOYEE, "/profile"],
    ];
    for (const [notif, role, expected] of cases) {
      assert.equal(
        getNotificationRoute({ id: NOTIF_UUID, ...notif }, role),
        expected,
        `${notif.type} with link ${notif.link}`
      );
    }
  });

  test("task id is taken from API-style links too", () => {
    const notif = { id: NOTIF_UUID, type: "TASK_ASSIGNED", link: "/api/v1/tasks/42" };
    assert.equal(getNotificationRoute(notif, ROLES.EMPLOYEE), "/tasks?task=42");
  });

  test("never uses the notification UUID as an entity id", () => {
    for (const type of ["TASK_ASSIGNED", "TICKET_CREATED", "TICKET_RESOLVED", "DELIVERABLE_SHARED"]) {
      const route = getNotificationRoute({ id: NOTIF_UUID, type, link: null }, ROLES.CLIENT);
      assert.ok(!route.includes(NOTIF_UUID), `${type} leaked the notification id: ${route}`);
    }
  });

  test("mapped types fall back to the base route when link is null, undefined, or empty", () => {
    assert.equal(getNotificationRoute({ type: "TASK_ASSIGNED", link: null }, ROLES.EMPLOYEE), "/tasks");
    assert.equal(getNotificationRoute({ type: "TASK_ASSIGNED" }, ROLES.EMPLOYEE), "/tasks");
    assert.equal(getNotificationRoute({ type: "TASK_ASSIGNED", link: "   " }, ROLES.EMPLOYEE), "/tasks");
  });
});

describe("4. Unknown Types and Fallbacks", () => {
  test("unknown types return null and do not navigate", () => {
    const notifUnknown = {
      id: "unknown-1",
      type: "FUTURE_UNRECOGNIZED_NOTIFICATION",
    };

    const resolvedRoute = getNotificationRoute(notifUnknown, ROLES.PM);
    assert.equal(resolvedRoute, null);
  });

  test("unknown types use the backend link when one is provided", () => {
    const notif = { id: NOTIF_UUID, type: "FUTURE_TYPE", link: " /custom/deep/path?ref=123 " };
    assert.equal(getNotificationRoute(notif, ROLES.PM), "/custom/deep/path?ref=123");
  });

  test("getNotificationConfig returns UNKNOWN_NOTIFICATION_TYPE for unknown types", () => {
    const config = getNotificationConfig("SOMETHING_UNKNOWN");
    assert.equal(config.icon, UNKNOWN_NOTIFICATION_TYPE.icon);
    assert.equal(config.label, UNKNOWN_NOTIFICATION_TYPE.label);
    assert.equal(config.category, "Other");
    assert.equal(config.route(), null);
  });

  test("handles null, undefined, or malformed notifications safely", () => {
    assert.equal(getNotificationRoute(null, ROLES.PM), null);
    assert.equal(getNotificationRoute(undefined, ROLES.PM), null);
    assert.equal(getNotificationRoute({}, ROLES.PM), null);
  });
});

describe("5. Specific Route Targets for Notification Groups", () => {
  test("Leave routes: /team-lead/leave for requests, /leave for approvals/rejections", () => {
    assert.equal(
      getNotificationRoute({ type: "LEAVE_REQUESTED" }, ROLES.TEAM_LEAD),
      "/team-lead/leave"
    );
    assert.equal(
      getNotificationRoute(
        { type: "LEAVE_REQUESTED", link: "/team-lead/leave?request=12" },
        ROLES.TEAM_LEAD
      ),
      "/team-lead/leave?request=12"
    );
    assert.equal(getNotificationRoute({ type: "LEAVE_REJECTED" }, ROLES.EMPLOYEE), "/leave");
    assert.equal(getNotificationRoute({ type: "STAFF_LEAVE_APPROVED" }, ROLES.EMPLOYEE), "/leave");
  });

  test("Team routes", () => {
    assert.equal(getNotificationRoute({ type: "TEAM_MEMBER_ADDED" }, ROLES.EMPLOYEE), "/team/roster");
    assert.equal(getNotificationRoute({ type: "TEAM_LEAD_ASSIGNED" }, ROLES.EMPLOYEE), "/team/roster");
  });

  test("Support routes: /it-support for IT queue, /support/tickets for reporter", () => {
    for (const type of ["TICKET_CREATED", "TICKET_ASSIGNED", "TICKET_ESCALATED"]) {
      assert.equal(getNotificationRoute({ id: NOTIF_UUID, type }, ROLES.IT_SUPPORT), "/it-support");
    }
    for (const type of ["TICKET_RESOLVED", "TICKET_REOPENED"]) {
      assert.equal(getNotificationRoute({ id: NOTIF_UUID, type }, ROLES.EMPLOYEE), "/support/tickets");
    }
  });

  test("Security routes: /admin/security, /account/security, /dashboard", () => {
    assert.equal(getNotificationRoute({ type: "SECURITY_ALERT" }, ROLES.ADMIN), "/admin/security");
    assert.equal(getNotificationRoute({ type: "ACCOUNT_UNLOCKED" }, ROLES.EMPLOYEE), "/account/security");
    assert.equal(getNotificationRoute({ type: "ELEVATED_ACCESS_GRANTED" }, ROLES.EMPLOYEE), "/dashboard");
    assert.equal(getNotificationRoute({ type: "ELEVATED_ACCESS_REVOKED" }, ROLES.EMPLOYEE), "/dashboard");
  });
});

describe("6. Helpers", () => {
  test("getLinkedEntityId extracts numeric ids for the requested segment only", () => {
    assert.equal(getLinkedEntityId({ link: "/tasks/11" }, "tasks"), "11");
    assert.equal(getLinkedEntityId({ link: "/api/v1/tasks/9/submissions" }, "tasks"), "9");
    assert.equal(getLinkedEntityId({ link: "/projects/4/deliverables" }, "projects"), "4");
    assert.equal(getLinkedEntityId({ link: "/tasks/team" }, "tasks"), null);
    assert.equal(getLinkedEntityId({ link: "/projects/4" }, "tasks"), null);
    assert.equal(getLinkedEntityId({ link: null }, "tasks"), null);
    assert.equal(getLinkedEntityId(null, "tasks"), null);
  });

  test("parseServerDate treats naive timestamps as UTC", () => {
    assert.equal(
      parseServerDate("2026-11-27T10:00:00").toISOString(),
      "2026-11-27T10:00:00.000Z"
    );
    assert.equal(
      parseServerDate("2026-11-27 10:00:00.123456").toISOString(),
      "2026-11-27T10:00:00.123Z"
    );
  });

  test("parseServerDate keeps explicit zones", () => {
    assert.equal(parseServerDate("2026-11-27T10:00:00Z").toISOString(), "2026-11-27T10:00:00.000Z");
    assert.equal(
      parseServerDate("2026-11-27T15:30:00+05:30").toISOString(),
      "2026-11-27T10:00:00.000Z"
    );
    assert.equal(parseServerDate(null), null);
  });
});
