---
name: project-structure
description: Use whenever creating, moving, or asking where to put a new file in the Workflow Management System for MNCs codebase (FastAPI backend or React frontend). Ensures new code lands in the agreed domain-based folder structure instead of wherever seems convenient.
---

# Workflow Management System for MNCs Project Structure

Workflow Management System for MNCs is organized by **domain**, not by technical layer. Every folder name traces back to an Epic in the project backlog (10 Epics, US-01 through US-50) and an entity cluster in the ER diagram (27 entities). Before creating a new file, find which Epic/entity it belongs to and place it accordingly — never default to a generic `utils/` or `helpers/` file for something that clearly belongs to a domain.

## Backend (`wms-backend/app/`)

| New backend code for... | Goes in |
|---|---|
| A new DB table / entity | `models/<cluster>.py` (org, client, project, task, leave, support, deliverable, notification, skill, admin, timesheet) |
| Request/response shape for an entity | `schemas/<matching-name>.py` |
| A new HTTP endpoint | `routers/<epic-name>.py` — one router file per Epic, never a new router file per feature |
| Business logic (validation, orchestration, multi-step workflows) | `services/<domain>_service.py` — routers stay thin, call into services |
| A raw DB query used by more than one service | `repositories/` |
| Auth, RBAC checks, audit logging, exceptions | `core/` — never duplicate these inline in a router |
| Anything touching Supabase Storage | `integrations/supabase_client.py` |

Router-to-Epic mapping (do not create a new router — add to the existing one):
`auth.py`(1) · `employees.py`+`org.py`(2) · `projects.py`(3) · `tasks.py`(4) · `leave.py`(5) · `notifications.py`(6) · `client_portal.py`(7) · `reporting.py`(8) · `support.py`(9) · `admin.py`(10)

## Frontend (`wms-frontend/src/`)

| New frontend code for... | Goes in |
|---|---|
| A page or panel for a specific Epic | `features/<epic-folder>/` |
| A component reused across more than one Epic | `components/ui/` or `components/layout/` |
| An API call | `api/<domain>Api.js` — one file per backend router, matching names |
| Auth state, route guarding | `auth/` |
| Global app state | `store/slices/` |

`features/` folder names map 1:1 to backend router names: `employee/`, `tasks/`, `projects/`, `leave/`, `client-portal/`, `reporting/`, `support/`, `admin/`.

## Rule of thumb

If you can't say which Epic (1–10) a new file serves, stop and ask before creating it — a file with no clear Epic usually means the work should be added to an existing file instead of starting a new one.
