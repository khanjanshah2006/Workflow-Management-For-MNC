---
name: erd-schema
description: Use whenever generating, editing, or reasoning about SQLAlchemy models, Alembic migrations, Pydantic schemas, or any SQL query. Contains the finalized 27-entity data model — always check here before inventing a table, column, or relationship that isn't already defined.
---

# Workflow Management System for MNCs Entity-Relationship Model (Finalized)

This is the single source of truth for the database schema. Do not invent new entities, rename existing ones, or change a relationship's cardinality without updating this file first and telling the team — every generated model, migration, and query must match this exactly.

## Core rule: one EMPLOYEE entity, not one per role

Employee, Team Lead, Project Manager, HR Manager, IT Support, and System Administrator are **the same table** (`EMPLOYEE`), distinguished only by `role_id → ROLE`. Never generate a separate `TeamLead` or `Admin` model. `CLIENT` is the one genuinely separate person-entity (external, own auth, own table).

## Entity clusters

**Identity & Org:** `OFFICE`, `DEPARTMENT`, `TEAM`, `ROLE`, `EMPLOYEE`, `CLIENT`
**Project & Task:** `PROJECT`, `PROJECT_ASSIGNMENT` (bridge, resolves Employee↔Project M:N), `MILESTONE`, `TASK`, `TASK_REVIEW`, `TASK_COMMENT`, `TASK_ATTACHMENT`
**Leave / Client / Notifications / Skills:** `LEAVE_POLICY`, `LEAVE_REQUEST`, `DELIVERABLE`, `DELIVERABLE_FEEDBACK`, `NOTIFICATION`, `SKILL`, `EMPLOYEE_SKILL` (bridge, resolves Employee↔Skill M:N)
**IT Support & Admin:** `SUPPORT_TICKET`, `TICKET_ACTIVITY`, `AUDIT_LOG`, `ELEVATED_ACCESS_GRANT`, `SYSTEM_PARAMETER`, `SYSTEM_BACKUP_LOG`, `TIMESHEET_ENTRY` (scope-contingent — confirm with the team before building this one)

## Key relationships to always respect

- `EMPLOYEE.reporting_manager_id → EMPLOYEE.employee_id` — self-referencing, nullable
- `EMPLOYEE.team_id → TEAM.team_id` — every employee belongs to exactly one team; **never add a direct `department_id` on EMPLOYEE**, it's derived via `TEAM.department_id` (this was deliberately normalized out — re-adding it is a regression)
- `TASK`: exactly one `assigned_to_id` (FK → EMPLOYEE) at a time — this is a hard domain rule (DR-03), never model Task↔Employee as many-to-many
- `PROJECT.project_manager_id` is required (every project has exactly one PM); `PROJECT.client_id` is nullable (internal projects may have no client)
- `LEAVE_REQUEST.leave_policy_id` is required — always resolve which policy applied at submission time, don't look it up dynamically by region at read time

## Before generating any migration

Check: does this table/column already exist in the clusters above? Does every new FK reference a real PK in an existing table? Is a new many-to-many relationship being introduced — if so, it needs a bridge entity, not a direct FK on either side.
