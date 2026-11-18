import { test, describe } from "node:test";
import assert from "node:assert/strict";

import { teamApi } from "../src/api/teamApi.js";

describe("teamApi.normalizeMember", () => {
  test("uses employee_id from GET /api/v1/teams/{id}/members (TeamMemberOut)", () => {
    const member = teamApi.normalizeMember({
      employee_id: 7,
      emp_code: "EMP-007",
      full_name: "Sarah Connor",
      email: "sarah.connor@company.com",
      designation: "Software Engineer",
    });

    assert.equal(member.emp_id, 7);
    assert.equal(member.id, 7);
    assert.equal(member.name, "Sarah Connor");
    assert.equal(member.role, "Software Engineer");
  });

  test("gives distinct ids to distinct members so list keys and option values are unique", () => {
    const members = [{ employee_id: 1 }, { employee_id: 2 }].map((m) => teamApi.normalizeMember(m));
    assert.deepEqual(members.map((m) => m.emp_id), [1, 2]);
    assert.notEqual(members[0].id, members[1].id);
  });

  test("still accepts the legacy emp_id shape", () => {
    const member = teamApi.normalizeMember({ emp_id: 3, team_member_id: 30 });
    assert.equal(member.emp_id, 3);
    assert.equal(member.id, 30);
  });
});
