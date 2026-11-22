# Pull Request: [S1-BE-2] HR Department Teams & Team Lead Designation API (#141)

Closes #141

## Story
- **Issue:** [#141](https://github.com/khanjanshah2006/Workflow-Management-For-MNC/issues/141)
- **Scenario:** S1 (Employee Onboarding & Team Placement)
- **User Stories:** US-04, US-05, US-37, US-19
- **Branch:** `feature/s1-be-2-hr-department-teams`
- **Target PR:** `develop`

## What this implements
Closes the gap where teams only came from PM project staffing (`POST /projects/{id}/teams`) and nothing promoted a lead to `TEAM_LEAD`. Enables HR and Admin to place employees into department teams with a designated team lead, with automated role transitions, audit logging, and real-time notifications:

1. `POST /api/v1/departments/{dept_id}/teams`:
   - Creates a department team with a designated lead and initial members.
   - Lead is automatically added as a team member.
   - If lead's user account is `EMPLOYEE`, it is automatically promoted to `TEAM_LEAD` and audited with entity `USER_ACCOUNT`.
   - Sends real-time notifications: `TEAM_LEAD_ASSIGNED` to lead, `TEAM_MEMBER_ADDED` to newly added members and to lead.
   - Validates uniqueness of team name per department (case-insensitive, returns 409).
   - Validates existence (404) and active status (400) for department, lead, and all members.

2. `GET /api/v1/departments/{dept_id}/teams`:
   - Lists teams in a department with `lead_name` and `member_count`.
   - Defaults to ACTIVE teams only; `?include_disbanded=true` includes disbanded teams.

3. `PUT /api/v1/teams/{team_id}`:
   - Partial update of `name`, `description`, `lead_emp_id`, and `status`.
   - Changing lead automatically adds new lead to members, promotes new lead (if `EMPLOYEE`), demotes previous lead to `EMPLOYEE` if they no longer lead any active team, and sends notifications.
   - Setting `status=DISBANDED` runs the lead demotion check on the team lead.

4. `POST /api/v1/teams/{team_id}/members`:
   - Idempotently adds employees to team members.
   - Notifies newly added employees (`TEAM_MEMBER_ADDED`) and notifies the lead.

5. `DELETE /api/v1/teams/{team_id}/members/{emp_id}`:
   - Removes employee from team members.
   - Removing the lead returns 409 Conflict ("Cannot remove lead. Change lead first").

## RBAC Matrix

| Role | `POST /departments/{id}/teams` | `GET /departments/{id}/teams` | `PUT /teams/{id}` | `POST /teams/{id}/members` | `DELETE /teams/{id}/members/{emp_id}` |
|---|---|---|---|---|---|
| **HR Manager** (`HR`) | ✅ 201 Created | ✅ 200 OK | ✅ 200 OK | ✅ 200 OK | ✅ 204 No Content |
| **System Admin** (`ADMIN`) | ✅ 201 Created | ✅ 200 OK | ✅ 200 OK | ✅ 200 OK | ✅ 204 No Content |
| **Project Manager** (`PM`) | ❌ 403 Forbidden | ✅ 200 OK | ❌ 403 Forbidden | ❌ 403 Forbidden | ❌ 403 Forbidden |
| **Team Lead** (`TEAM_LEAD`) | ❌ 403 Forbidden | ✅ 200 OK | ❌ 403 Forbidden | ❌ 403 Forbidden | ❌ 403 Forbidden |
| **Employee** (`EMPLOYEE`) | ❌ 403 Forbidden | ✅ 200 OK | ❌ 403 Forbidden | ❌ 403 Forbidden | ❌ 403 Forbidden |
| **Client** (`CLIENT`) | ❌ 403 Forbidden | ❌ 403 Forbidden | ❌ 403 Forbidden | ❌ 403 Forbidden | ❌ 403 Forbidden |
| **Unauthenticated** | ❌ 401 Unauthorized | ❌ 401 Unauthorized | ❌ 401 Unauthorized | ❌ 401 Unauthorized | ❌ 401 Unauthorized |

## Test Suite (`backend/tests/test_department_teams.py`)
28 automated test cases covering all required flows, acceptance criteria, and defensive security:
- `test_hr_creates_team_and_lead_promoted`
- `test_duplicate_team_name_in_department_409`
- `test_lead_change_demotes_previous_lead_when_no_other_team`
- `test_remove_lead_member_conflict`
- `test_members_and_lead_notified`
- `test_project_teams_unaffected`
- RBAC tests: HR/Admin allowed, Employee/PM/Client 403, 401 unauthenticated
- Validation: missing department/employees (404), inactive employees (400)
- Preserving non-EMPLOYEE roles during lead assignment
- Listing teams: active default, `include_disbanded=true`, 404 for missing department
- Partial updates: name/description update, duplicate name conflict (409)
- Disbanding team demotes lead if no other active teams, preserves if leading other active teams
- Idempotent member additions
- Removing regular member (204)
- SQL injection prevention on all path parameters (422 strict validation)

## Checklist
- [x] RBAC check present (`require_role((roles.HR, roles.ADMIN))` for writes)
- [x] Audit log present for role changes (`USER_ACCOUNT` entity) and department team mutations
- [x] Matches domain file structure (`app/features/departments/{router,service,schemas,repository}.py`)
- [x] Acceptance criteria from the backlog are all met:
  - [x] Full S1 demo works through the API
  - [x] Lead role changes automatically (`EMPLOYEE` <-> `TEAM_LEAD`) and is audited
  - [x] Existing project-team endpoints and tests are unchanged
  - [x] 28 comprehensive test cases passing
  - [x] Postman collection updated with all required requests
