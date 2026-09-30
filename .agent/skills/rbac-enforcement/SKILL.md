---
name: rbac-enforcement
description: Use whenever adding access control to an endpoint or a frontend route, or when unsure which roles should be allowed to see or do something in Workflow Management System for MNCs. Contains the actual role-to-permission mapping for all 8 stakeholders so nobody has to guess or re-derive it per feature.
---

# Workflow Management System for MNCs Role-Based Access Control

Eight roles exist: **Employee, Team Lead, Project Manager, HR Manager, IT Support, System Administrator** (all rows in `EMPLOYEE`, distinguished by `role_id`), plus **Client** (separate table/auth) and **MNC Executive** (an `EMPLOYEE` role — read-only across the org).

## Scope rules per role (apply server-side, not just in the UI)

- **Employee** — own profile, own tasks, own leave requests, own tickets only. Never org-wide reads.
- **Team Lead** — everything an Employee has, plus: their own team's members and tasks, leave approval for their team, task review/reassignment within their team. Scope check: `task.project_id` must be in a project the TL's team is assigned to, or `employee.team_id == current_user.team_id` for team-member data.
- **Project Manager** — their own project(s) only (`project.project_manager_id == current_user.employee_id`), plus cross-project workload as an *aggregate-only* view (never another PM's project-internal detail).
- **HR Manager** — org-wide read/write on `EMPLOYEE`, `DEPARTMENT`, `TEAM`, `LEAVE_POLICY`, `LEAVE_REQUEST`. This is the one internal role with legitimately broad scope — don't under-scope it to match Team Lead's pattern.
- **IT Support** — `SUPPORT_TICKET` and `TICKET_ACTIVITY` only. Explicitly must NOT access `LEAVE_REQUEST`, `EMPLOYEE` salary/personal fields, or project financials even though they can see which employee raised a ticket.
- **System Administrator** — `EMPLOYEE`/`ROLE` management, `AUDIT_LOG`, `ELEVATED_ACCESS_GRANT`, `SYSTEM_PARAMETER`, `SYSTEM_BACKUP_LOG`. Does NOT get blanket access to business data (tasks, leave, tickets) — admin access is about the system, not a backdoor into everything.
- **MNC Executive** — read-only across `PROJECT`, `TASK` (aggregate), `EMPLOYEE` (aggregate/KPI level, not individual PII). Never gets write access to operational data unless a specific FR says so.
- **Client** — strictly scoped to `project.client_id == current_user.client_id`. Never sees `EMPLOYEE` records, internal `TASK_COMMENT`, or any `is_client_visible = false` deliverable. This is the tightest boundary in the system — treat any Client-facing query as needing an explicit allowlist, not a denylist.

## Implementation checklist for a new protected endpoint

1. Which role(s) should see this, per the table above?
2. Is the check row-level (e.g. "their own X") or table-level (e.g. HR sees everything)? Row-level checks need the scope condition in the query itself, not just a role check.
3. Does a Client ever reach this endpoint path? If the endpoint isn't explicitly in `routers/client_portal.py`, a Client token should be rejected outright.
