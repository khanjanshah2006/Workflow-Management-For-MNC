import { test, describe } from "node:test";
import assert from "node:assert/strict";

import {
  NOTIFICATION_TYPES,
  NOTIFICATION_CATEGORY_LIST,
  UNKNOWN_NOTIFICATION_TYPE,
  getNotificationConfig,
  getNotificationRoute,
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
    const notif = { id: "proj-101", type: "PROJECT_ASSIGNED" };

    assert.equal(
      NOTIFICATION_TYPES.PROJECT_ASSIGNED.route(notif, ROLES.PM),
      "/projects/proj-101"
    );
    assert.equal(
      NOTIFICATION_TYPES.PROJECT_ASSIGNED.route(notif, ROLES.ADMIN),
      "/projects/proj-101"
    );
    assert.equal(
      NOTIFICATION_TYPES.PROJECT_ASSIGNED.route(notif, ROLES.SYSTEM_ADMIN),
      "/projects/proj-101"
    );
  });

  test("PROJECT_ASSIGNED routes to /tasks for other roles (e.g. EMPLOYEE, TEAM_LEAD)", () => {
    const notif = { id: "proj-101", type: "PROJECT_ASSIGNED" };

    assert.equal(
      NOTIFICATION_TYPES.PROJECT_ASSIGNED.route(notif, ROLES.EMPLOYEE),
      "/tasks"
    );
    assert.equal(
      NOTIFICATION_TYPES.PROJECT_ASSIGNED.route(notif, ROLES.TEAM_LEAD),
      "/tasks"
    );
    assert.equal(
      NOTIFICATION_TYPES.PROJECT_ASSIGNED.route(notif, ROLES.CLIENT),
      "/tasks"
    );
  });

  test("DELIVERABLE_SHARED routes to /client/projects/{id} for CLIENT", () => {
    const notif = { id: "proj-500", type: "DELIVERABLE_SHARED" };

    assert.equal(
      NOTIFICATION_TYPES.DELIVERABLE_SHARED.route(notif, ROLES.CLIENT),
      "/client/projects/proj-500"
    );
  });

  test("DELIVERABLE_SHARED routes to /projects/{id} for non-CLIENT roles", () => {
    const notif = { id: "proj-500", type: "DELIVERABLE_SHARED" };

    assert.equal(
      NOTIFICATION_TYPES.DELIVERABLE_SHARED.route(notif, ROLES.PM),
      "/projects/proj-500"
    );
    assert.equal(
      NOTIFICATION_TYPES.DELIVERABLE_SHARED.route(notif, ROLES.ADMIN),
      "/projects/proj-500"
    );
    assert.equal(
      NOTIFICATION_TYPES.DELIVERABLE_SHARED.route(notif, ROLES.EMPLOYEE),
      "/projects/proj-500"
    );
  });

  test("DELIVERABLE_FEEDBACK routes to /client/projects/{id} for CLIENT and /projects/{id} otherwise", () => {
    const notif = { id: "proj-500", type: "DELIVERABLE_FEEDBACK" };

    assert.equal(
      NOTIFICATION_TYPES.DELIVERABLE_FEEDBACK.route(notif, ROLES.CLIENT),
      "/client/projects/proj-500"
    );
    assert.equal(
      NOTIFICATION_TYPES.DELIVERABLE_FEEDBACK.route(notif, ROLES.PM),
      "/projects/proj-500"
    );
  });
});

describe("3. Link Overrides Route Helper", () => {
  test("backend link overrides standard route calculation", () => {
    const notifWithLink = {
      id: "task-99",
      type: "TASK_ASSIGNED",
      link: "/custom/deep/path?ref=123",
    };

    const resolved = getNotificationRoute(notifWithLink, ROLES.EMPLOYEE);
    assert.equal(resolved, "/custom/deep/path?ref=123");
  });

  test("fallback to route() when link is null, undefined, or empty", () => {
    const notifNullLink = {
      id: "task-99",
      type: "TASK_ASSIGNED",
      link: null,
    };
    assert.equal(getNotificationRoute(notifNullLink, ROLES.EMPLOYEE), "/tasks?task=task-99");

    const notifEmptyLink = {
      id: "task-99",
      type: "TASK_ASSIGNED",
      link: "   ",
    };
    assert.equal(getNotificationRoute(notifEmptyLink, ROLES.EMPLOYEE), "/tasks?task=task-99");
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
  test("Tasks drawer target: /tasks?task={id}", () => {
    const notif = { id: "42", type: "TASK_ASSIGNED" };
    assert.equal(getNotificationRoute(notif, ROLES.EMPLOYEE), "/tasks?task=42");

    const commentNotif = { task_id: "55", type: "TASK_COMMENT" };
    assert.equal(getNotificationRoute(commentNotif, ROLES.EMPLOYEE), "/tasks?task=55");
  });

  test("Task submission targets /team-lead/tasks?tab=review", () => {
    assert.equal(
      getNotificationRoute({ type: "TASK_SUBMITTED" }, ROLES.TEAM_LEAD),
      "/team-lead/tasks?tab=review"
    );
    assert.equal(
      getNotificationRoute({ type: "TASK_RESUBMITTED" }, ROLES.TEAM_LEAD),
      "/team-lead/tasks?tab=review"
    );
  });

  test("Leave routes: /team-lead/leave for requests, /leave for approvals/rejections", () => {
    assert.equal(
      getNotificationRoute({ type: "LEAVE_REQUESTED" }, ROLES.TEAM_LEAD),
      "/team-lead/leave"
    );
    assert.equal(
      getNotificationRoute({ type: "LEAVE_APPROVED" }, ROLES.EMPLOYEE),
      "/leave"
    );
    assert.equal(
      getNotificationRoute({ type: "LEAVE_REJECTED" }, ROLES.EMPLOYEE),
      "/leave"
    );
    assert.equal(
      getNotificationRoute({ type: "STAFF_LEAVE_APPROVED" }, ROLES.EMPLOYEE),
      "/leave"
    );
  });

  test("Team and skill routes", () => {
    assert.equal(
      getNotificationRoute({ type: "TEAM_MEMBER_ADDED" }, ROLES.EMPLOYEE),
      "/team/roster"
    );
    assert.equal(
      getNotificationRoute({ type: "TEAM_LEAD_ASSIGNED" }, ROLES.EMPLOYEE),
      "/team/roster"
    );
    assert.equal(
      getNotificationRoute({ type: "SKILL_REQUEST_CREATED" }, ROLES.HR),
      "/skill-requests"
    );
    assert.equal(
      getNotificationRoute({ type: "SKILL_REQUEST_DECIDED" }, ROLES.EMPLOYEE),
      "/profile"
    );
  });

  test("Support routes: /it-support?ticket={id} for IT queue, /support/tickets?ticket={id} for reporter", () => {
    assert.equal(
      getNotificationRoute({ id: "TICK-101", type: "TICKET_CREATED" }, ROLES.IT_SUPPORT),
      "/it-support?ticket=TICK-101"
    );
    assert.equal(
      getNotificationRoute({ ticket_id: "TICK-102", type: "TICKET_ASSIGNED" }, ROLES.IT_SUPPORT),
      "/it-support?ticket=TICK-102"
    );
    assert.equal(
      getNotificationRoute({ id: "TICK-103", type: "TICKET_ESCALATED" }, ROLES.ADMIN),
      "/it-support?ticket=TICK-103"
    );
    assert.equal(
      getNotificationRoute({ id: "TICK-104", type: "TICKET_RESOLVED" }, ROLES.EMPLOYEE),
      "/support/tickets?ticket=TICK-104"
    );
    assert.equal(
      getNotificationRoute({ id: "TICK-105", type: "TICKET_REOPENED" }, ROLES.IT_SUPPORT),
      "/support/tickets?ticket=TICK-105"
    );
  });

  test("Security routes: /admin/security, /account/security, /dashboard", () => {
    assert.equal(
      getNotificationRoute({ type: "SECURITY_ALERT" }, ROLES.ADMIN),
      "/admin/security"
    );
    assert.equal(
      getNotificationRoute({ type: "ACCOUNT_UNLOCKED" }, ROLES.EMPLOYEE),
      "/account/security"
    );
    assert.equal(
      getNotificationRoute({ type: "ELEVATED_ACCESS_GRANTED" }, ROLES.EMPLOYEE),
      "/dashboard"
    );
    assert.equal(
      getNotificationRoute({ type: "ELEVATED_ACCESS_REVOKED" }, ROLES.EMPLOYEE),
      "/dashboard"
    );
  });
});
