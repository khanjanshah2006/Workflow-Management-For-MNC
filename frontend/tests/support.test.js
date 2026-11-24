import { test, describe } from "node:test";
import assert from "node:assert/strict";

import {
  ACTIONS,
  allowedActions,
  validateResolutionNote,
  validateInternalNote,
  buildAssignPayload,
  buildNotePayload,
  buildStatusPayload,
  filtersToQueryString,
  filtersFromQueryString,
} from "../src/features/support/ticketStatusUtils.js";

import { supportApi } from "../src/api/supportApi.js";

// ============================================================================
// 1. Action Identifiers & Constants
// ============================================================================
describe("1. Action Identifiers & Constants", () => {
  test("ACTIONS defines all required state machine actions", () => {
    assert.equal(ACTIONS.ASSIGN_ME, "assign_me");
    assert.equal(ACTIONS.ASSIGN_OTHER, "assign_other");
    assert.equal(ACTIONS.ADD_NOTE, "add_note");
    assert.equal(ACTIONS.RESOLVE, "resolve");
    assert.equal(ACTIONS.ESCALATE, "escalate");
    assert.equal(ACTIONS.TAKE_OVER, "take_over");
    assert.equal(ACTIONS.CLOSE, "close");
    assert.equal(ACTIONS.REOPEN, "reopen");
    assert.equal(Object.isFrozen(ACTIONS), true);
  });
});

// ============================================================================
// 2. Ticket Status & Role State Machine (allowedActions)
// ============================================================================
describe("2. Ticket State Transition Matrix (allowedActions)", () => {
  // OPEN status
  test("open ticket: IT_SUPPORT gets assign_me, assign_other, escalate", () => {
    const actions = allowedActions({ status: "open" }, "IT_SUPPORT");
    assert.deepEqual(actions, [ACTIONS.ASSIGN_ME, ACTIONS.ASSIGN_OTHER, ACTIONS.ESCALATE]);
  });

  test("open ticket: SYSTEM_ADMIN gets assign_me, assign_other, escalate", () => {
    const actions = allowedActions({ status: "open" }, "SYSTEM_ADMIN");
    assert.deepEqual(actions, [ACTIONS.ASSIGN_ME, ACTIONS.ASSIGN_OTHER, ACTIONS.ESCALATE]);
  });

  test("open ticket: Reporter/Employee gets empty actions (read-only)", () => {
    const actions = allowedActions({ status: "open" }, "EMPLOYEE", true);
    assert.deepEqual(actions, []);
  });

  // IN_PROGRESS status
  test("in_progress ticket: IT_SUPPORT gets add_note, resolve, escalate", () => {
    const actions = allowedActions({ status: "in_progress" }, "IT_SUPPORT");
    assert.deepEqual(actions, [ACTIONS.ADD_NOTE, ACTIONS.RESOLVE, ACTIONS.ESCALATE]);
  });

  test("in_progress ticket: SYSTEM_ADMIN gets add_note, resolve, escalate", () => {
    const actions = allowedActions({ status: "in_progress" }, "SYSTEM_ADMIN");
    assert.deepEqual(actions, [ACTIONS.ADD_NOTE, ACTIONS.RESOLVE, ACTIONS.ESCALATE]);
  });

  test("in_progress ticket: Reporter gets empty actions", () => {
    const actions = allowedActions({ status: "in_progress" }, "EMPLOYEE", true);
    assert.deepEqual(actions, []);
  });

  // ESCALATED status (#146 & S8-FE-3: strictly SYSTEM_ADMIN only)
  test("escalated ticket: SYSTEM_ADMIN gets take_over and resolve", () => {
    const actions = allowedActions({ status: "escalated" }, "SYSTEM_ADMIN");
    assert.deepEqual(actions, [ACTIONS.TAKE_OVER, ACTIONS.RESOLVE]);
  });

  test("escalated ticket: IT_SUPPORT is strictly read-only (empty actions, awaiting SysAdmin)", () => {
    const actions = allowedActions({ status: "escalated" }, "IT_SUPPORT");
    assert.deepEqual(actions, []);
  });

  test("escalated ticket: Plain ADMIN is strictly read-only per #146 (only SYSTEM_ADMIN can move)", () => {
    const actions = allowedActions({ status: "escalated" }, "ADMIN");
    assert.deepEqual(actions, []);
  });

  test("escalated ticket: Reporter gets empty actions", () => {
    const actions = allowedActions({ status: "escalated" }, "EMPLOYEE", true);
    assert.deepEqual(actions, []);
  });

  // RESOLVED status
  test("resolved ticket: IT staff gets close action", () => {
    const actions = allowedActions({ status: "resolved" }, "IT_SUPPORT", false);
    assert.deepEqual(actions, [ACTIONS.CLOSE]);
  });

  test("resolved ticket: Reporter gets reopen action", () => {
    const actions = allowedActions({ status: "resolved" }, "EMPLOYEE", true);
    assert.deepEqual(actions, [ACTIONS.REOPEN]);
  });

  test("resolved ticket: IT staff who is also the reporter gets both close and reopen", () => {
    const actions = allowedActions({ status: "resolved" }, "IT_SUPPORT", true);
    assert.equal(actions.includes(ACTIONS.CLOSE), true);
    assert.equal(actions.includes(ACTIONS.REOPEN), true);
  });

  // CLOSED status
  test("closed ticket: returns empty actions across all roles", () => {
    assert.deepEqual(allowedActions({ status: "closed" }, "IT_SUPPORT"), []);
    assert.deepEqual(allowedActions({ status: "closed" }, "SYSTEM_ADMIN"), []);
    assert.deepEqual(allowedActions({ status: "closed" }, "EMPLOYEE", true), []);
  });

  // Edge cases
  test("handles null or undefined ticket safely", () => {
    assert.deepEqual(allowedActions(null, "IT_SUPPORT"), []);
    assert.deepEqual(allowedActions(undefined, "IT_SUPPORT"), []);
  });
});

// ============================================================================
// 3. Validation Helpers
// ============================================================================
describe("3. Validation Helpers", () => {
  test("validateResolutionNote rejects empty or whitespace-only strings", () => {
    assert.equal(validateResolutionNote("").isValid, false);
    assert.equal(validateResolutionNote("   ").isValid, false);
    assert.equal(validateResolutionNote(null).isValid, false);
    assert.equal(validateResolutionNote(undefined).isValid, false);
    assert.match(validateResolutionNote("").error, /required/i);
  });

  test("validateResolutionNote accepts non-empty resolution notes", () => {
    const res = validateResolutionNote("Replaced faulty network cable and verified connectivity.");
    assert.equal(res.isValid, true);
    assert.equal(res.error, null);
  });

  test("validateInternalNote rejects empty or whitespace-only strings", () => {
    assert.equal(validateInternalNote("").isValid, false);
    assert.equal(validateInternalNote("   ").isValid, false);
    assert.match(validateInternalNote("").error, /cannot be empty/i);
  });

  test("validateInternalNote rejects notes longer than 2000 characters", () => {
    const tooLong = "a".repeat(2001);
    const res = validateInternalNote(tooLong);
    assert.equal(res.isValid, false);
    assert.match(res.error, /exceed 2000/i);
  });

  test("validateInternalNote accepts valid 1-2000 character notes", () => {
    const res = validateInternalNote("Investigated issue with Active Directory account lockout.");
    assert.equal(res.isValid, true);
    assert.equal(res.error, null);
  });
});

// ============================================================================
// 4. API Payload Builders (Contract Compatibility)
// ============================================================================
describe("4. API Payload Builders (Backend Contract Conformance)", () => {
  test("buildAssignPayload sends { assignee_account_id }", () => {
    const payload = buildAssignPayload("usr_123e4567-e89b-12d3-a456-426614174000");
    assert.deepEqual(payload, {
      assignee_account_id: "usr_123e4567-e89b-12d3-a456-426614174000",
    });
  });

  test("buildNotePayload sends { note }", () => {
    const payload = buildNotePayload("Ran diagnostics and tested latency.");
    assert.deepEqual(payload, {
      note: "Ran diagnostics and tested latency.",
    });
  });

  test("buildStatusPayload normalizes status to lowercase", () => {
    const payload = buildStatusPayload("IN_PROGRESS");
    assert.deepEqual(payload, {
      status: "in_progress",
    });
  });

  test("buildStatusPayload includes trimmed resolution_note when provided", () => {
    const payload = buildStatusPayload("RESOLVED", "Patched server kernel.");
    assert.deepEqual(payload, {
      status: "resolved",
      resolution_note: "Patched server kernel.",
    });
  });

  test("buildStatusPayload omits resolution_note when empty or null", () => {
    const payload = buildStatusPayload("in_progress", null);
    assert.deepEqual(payload, {
      status: "in_progress",
    });
    assert.equal("resolution_note" in payload, false);
  });
});

// ============================================================================
// 5. URL Filter Serialization & Deserialization
// ============================================================================
describe("5. URL Filter Serialization & Deserialization", () => {
  test("filtersToQueryString serializes active filters", () => {
    const filters = {
      status: "open",
      category: "software",
      priority: "CRITICAL",
      assigned_to: "me",
      page: 2,
      limit: 10,
    };
    const qs = filtersToQueryString(filters);
    assert.match(qs, /status=open/);
    assert.match(qs, /category=software/);
    assert.match(qs, /priority=CRITICAL/);
    assert.match(qs, /assigned_to=me/);
    assert.match(qs, /page=2/);
    assert.match(qs, /limit=10/);
  });

  test("filtersToQueryString omits ALL defaults and page 1", () => {
    const filters = {
      status: "ALL",
      category: "ALL",
      priority: "ALL",
      assigned_to: "ALL",
      page: 1,
      limit: 20,
    };
    const qs = filtersToQueryString(filters);
    assert.equal(qs, "");
  });

  test("filtersFromQueryString parses query string accurately", () => {
    const qs = "status=in_progress&category=hardware&priority=HIGH&assigned_to=unassigned&page=3&limit=25";
    const parsed = filtersFromQueryString(qs);
    assert.equal(parsed.status, "in_progress");
    assert.equal(parsed.category, "hardware");
    assert.equal(parsed.priority, "HIGH");
    assert.equal(parsed.assigned_to, "unassigned");
    assert.equal(parsed.page, 3);
    assert.equal(parsed.limit, 25);
  });

  test("filtersFromQueryString provides clean defaults for empty or missing params", () => {
    const parsed = filtersFromQueryString("");
    assert.equal(parsed.status, "ALL");
    assert.equal(parsed.category, "ALL");
    assert.equal(parsed.priority, "ALL");
    assert.equal(parsed.assigned_to, "ALL");
    assert.equal(parsed.page, 1);
    assert.equal(parsed.limit, 20);
  });
});

// ============================================================================
// 6. supportApi Method Exports
// ============================================================================
describe("6. supportApi Method Exports", () => {
  test("supportApi exports all required endpoints", () => {
    assert.equal(typeof supportApi.getTickets, "function");
    assert.equal(typeof supportApi.getTicket, "function");
    assert.equal(typeof supportApi.getQueueMetrics, "function");
    assert.equal(typeof supportApi.getMyTickets, "function");
    assert.equal(typeof supportApi.createTicket, "function");
    assert.equal(typeof supportApi.assignTicket, "function");
    assert.equal(typeof supportApi.addInternalNote, "function");
    assert.equal(typeof supportApi.updateTicketStatus, "function");
    assert.equal(typeof supportApi.escalateTicket, "function");
    assert.equal(typeof supportApi.reopenTicket, "function");
  });
});
