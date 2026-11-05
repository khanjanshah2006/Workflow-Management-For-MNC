# Pull Request: US-37 — Team Members Roster and Team Tasks Query Endpoints

## Story
US-37 — View Team Members & Tasks ([Issue #35](https://github.com/khanjanshah2006/Workflow-Management-For-MNC/issues/35))
- **Scenario:** S1 — Employee Onboarding & Team Placement
- **Milestone:** Wave 1 (Day 1)
- **Branch:** `feature/us-37-team-members-api`

## What this implements
Implements the remaining S1 endpoint gap so Team Leads can query active employees assigned to their team and view team tasks:
1. `GET /api/v1/teams/{id}/members`: Queries active employees assigned to team `{id}` via `team_member` join with `status = ACTIVE`. Returns `employee_id`, `emp_code`, `full_name`, `email`, `designation`.
2. `GET /api/v1/teams/{id}/tasks`: Stub returning `[]` until S3 tasks land.

## Technical Scope & Architecture
- **Pydantic Schemas (`backend/app/features/departments/schemas.py`):**
  - `TeamMemberOut`: `employee_id`, `emp_code`, `full_name`, `email`, `designation`.
- **Repository (`backend/app/features/departments/repository.py`):**
  - `get_team_by_id(db, team_id)`: Fetches team by primary key.
  - `get_active_members_for_team(db, team_id)`: Parameterized ORM join query over `team_member` and `employee` with `CommonStatus.ACTIVE`.
- **Service Layer (`backend/app/features/departments/service.py`):**
  - `TeamNotFoundError`: 404 Not Found exception when team ID does not exist.
  - `TeamAccessForbiddenError`: 403 Forbidden exception on RBAC scope violation.
  - `_assert_team_access(db, team, current_user)`: Enforces that HR and SysAdmin can query any team; PMs can query teams; Team Leads can only query their own assigned team (`team.lead_emp_id == employee.emp_id`); non-lead employees and external clients receive 403.
  - `get_team_members(db, team_id, current_user)`: Resolves team, verifies scope, returns active members.
  - `get_team_tasks(db, team_id, current_user)`: Resolves team, verifies scope, returns `[]`.
- **Router (`backend/app/features/departments/router.py`):**
  - `team_router = APIRouter(prefix="/api/v1/teams", tags=["Teams"])`
  - Routes `GET /{id}/members` and `GET /{id}/tasks`.
- **Main App (`backend/app/main.py`):**
  - Registered `team_router`.

## RBAC Matrix

| Role | `GET /api/v1/teams/{id}/members` | `GET /api/v1/teams/{id}/tasks` |
|---|---|---|
| **HR Manager** (`HR`) | Allowed (Any team) | Allowed (Any team) |
| **System Administrator** (`ADMIN`) | Allowed (Any team) | Allowed (Any team) |
| **Project Manager** (`PM`) | Allowed (Any team) | Allowed (Any team) |
| **Team Lead** (`EMPLOYEE`, is `lead_emp_id`) | Allowed (Own assigned team only) | Allowed (Own assigned team only) |
| **Team Lead** (querying other team) | 403 Forbidden | 403 Forbidden |
| **Employee** (Non-Lead) | 403 Forbidden | 403 Forbidden |
| **Client** | 403 Forbidden | 403 Forbidden |
| **Unauthenticated** | 401 Unauthorized | 401 Unauthorized |

## Test Suite (`backend/tests/test_team_members.py`)
28 automated pytest test cases covering:
1. `test_get_team_members_team_lead_own_team_success`: Team Lead querying own team (200 OK)
2. `test_get_team_members_schema_fields`: Exact field names and types validation
3. `test_get_team_members_hr_manager_success`: HR Manager querying any team (200 OK)
4. `test_get_team_members_sysadmin_success`: SysAdmin querying any team (200 OK)
5. `test_get_team_members_pm_success`: PM querying team (200 OK)
6. `test_get_team_members_empty_team_returns_empty_array`: Team with zero members returning `[]`
7. `test_get_team_members_filters_out_inactive_employees`: INACTIVE employees excluded from roster
8. `test_get_team_members_team_lead_forbidden_on_other_team`: Team Lead querying other team (403)
9. `test_get_team_members_non_lead_employee_forbidden`: Regular employee querying roster (403)
10. `test_get_team_members_client_role_forbidden`: Client querying roster (403)
11. `test_get_team_members_employee_without_profile_forbidden`: Account without profile (403)
12. `test_get_team_members_unauthenticated_401`: Missing token (401)
13. `test_get_team_members_invalid_token_401`: Invalid token (401)
14. `test_get_team_members_expired_token_401`: Expired token (401)
15. `test_get_team_tasks_team_lead_success`: Team Lead querying tasks stub (200 OK `[]`)
16. `test_get_team_tasks_hr_success`: HR querying tasks stub (200 OK `[]`)
17. `test_get_team_tasks_admin_success`: SysAdmin querying tasks stub (200 OK `[]`)
18. `test_get_team_tasks_pm_success`: PM querying tasks stub (200 OK `[]`)
19. `test_get_team_tasks_team_lead_other_team_forbidden`: Team Lead querying other team tasks (403)
20. `test_get_team_tasks_non_lead_employee_forbidden`: Regular employee querying tasks (403)
21. `test_get_team_tasks_client_forbidden`: Client querying tasks (403)
22. `test_get_team_tasks_nonexistent_team_404`: Non-existent team tasks (404)
23. `test_get_team_members_nonexistent_team_404`: Non-existent team members (404)
24. `test_sqli_in_team_id_path_or_injection`: SQL injection `' OR '1'='1` in path param (422)
25. `test_sqli_in_team_id_path_stacked_query`: SQL injection `1; DROP TABLE team; --` in path (422)
26. `test_sqli_in_team_id_path_union_select`: SQL injection `1 UNION SELECT 1,2,3` in path (422)
27. `test_sqli_in_team_id_path_hex_encoding`: SQL injection `0x1` hex in path (422)
28. `test_negative_and_zero_team_id_edge_cases`: Boundary testing with `-1` and `0` (404)

## Checklist
- [x] RBAC check present (`_assert_team_access` enforced in service layer)
- [x] Read-only GET endpoints (no audit log required per api-endpoint-pattern guidelines)
- [x] Matches file structure (`features/departments/` per Org epic / project structure)
- [x] Acceptance criteria from the backlog are all met:
  - [x] Team Lead can query their own assigned team (403 Forbidden if querying other teams)
  - [x] HR and SysAdmin can query any team's roster
  - [x] Returns empty array cleanly if team has no members assigned
  - [x] Tasks stub returns `[]`
- [x] Postman collection updated with team endpoints and documentation examples
- [x] All 28 tests passing
