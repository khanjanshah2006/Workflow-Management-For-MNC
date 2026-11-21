# Workflow Management System for MNC

## Project Overview

The Workflow Management System for MNC is a centralized platform designed to manage employees, projects, tasks, workload, leave, and organizational workflows.

## Project Idea

When a new project is received, the Project Manager can create the project, define tasks, set deadlines, and assign suitable employees.

Team Leads can monitor their team's workload, assign or reassign tasks, and review completed work. Employees can view their assigned tasks, update their progress, submit completed work, and request leave.

The system also supports HR Managers, Clients, MNC Executives, IT Support, and System Administrators according to their roles.

## Main Objectives

- Manage projects and tasks in one centralized system
- Distribute work among employees efficiently
- Monitor employee workload and task progress
- Manage employee leave requests
- Track project deadlines and delays
- Improve communication between different roles
- Provide reports and dashboards for management
- Maintain secure role-based access

## Stakeholders

- Employee
- Team Lead
- Project Manager
- HR Manager
- Client / Customer
- MNC Executive
- IT Support
- System Administrator

## Expected Outcome

The system provides a structured way to manage organizational workflows and helps improve task coordination, workload visibility, project tracking, and communication within an MNC.

## Wave 3 Demo Data

Run the idempotent demo seed from `backend/` after `alembic upgrade head`:

```bash
python scripts/seed_wave3_demo.py
```

It creates a Team Lead (`john.teamlead@company.com`), three employees (`sarah.connor@`, `john.matrix@`, `kyle.reese@company.com`), `pm@company.com`, `hr@company.com`, `executive@company.com` and `client@acme.com`, plus the "Alpha ERP Modernization" project, team, leave types, leave requests and tasks. All accounts use the password in the `SEED_PASSWORD` environment variable (default `Password@123`). Dates are relative to today, so re-running it refreshes the demo instead of duplicating it.

## Rich Demo Data

A larger, idempotent demo that fills every dashboard. It runs the Wave 3 seed first, so run only this one from `backend/`:

```bash
export DATABASE_URL=sqlite:///wms_dev.db   # set it deliberately: an exported URL is used as-is
export REPORTS_DIR=uploads/reports         # optional; executive report files (this is the default)
python scripts/seed_rich_demo.py
```

If `DATABASE_URL` is unset the script uses `sqlite:///wms_dev.db` (it ignores the URL in `backend/.env`, which may point at the shared database) and creates the tables itself. Check your shell before running: an exported `DATABASE_URL` is seeded as-is. On PostgreSQL run `alembic upgrade head` first. Re-running it refreshes the data (dates move with the day you seed) instead of duplicating it. All accounts use `SEED_PASSWORD` (default `Password@123`).

| Login | Role | What to look at |
|---|---|---|
| `admin@company.com` | Admin | User accounts, audit log, system parameters |
| `sysadmin@company.com` | System Admin | Anomaly alerts (failed-login burst, backup failure), backup status, escalated tickets |
| `it.support@company.com` | IT Support | Ticket queue; active 48h System Admin grant |
| `it.helpdesk@company.com` | IT Support | Assigned tickets; expired Admin grant |
| `executive@company.com` | MNC Executive | Department breakdown, 3 generated reports |
| `hr@company.com` | HR | Leave review queue, leave policies (Sabbatical inactive) |
| `pm@company.com` | PM, Delivery | Alpha, Phoenix (at-risk milestone), Nova (planned), Lyra (cancelled) |
| `daniel.okafor@company.com` | PM, Engineering | Helios (on hold, overdue milestone), Zephyr (at-risk milestone) |
| `mei.lin@company.com` | PM, Data & Analytics | Atlas (overdue milestone), Vega (completed) |
| `sofia.alvarez@company.com` | PM, Quality Engineering | Orion, client change request |
| `john.teamlead@company.com` | Team Lead, Alpha | Review queue, Sarah's pending leave |
| `ana.lopez@company.com` | Team Lead, Phoenix | Tom's pending leave; reallocate Ravi's tasks for his approved leave |
| `marcus.chen@company.com` | Team Lead, Atlas | Elena's pending leave and its conflicts |
| `grace.kim@`, `omar.haddad@`, `leo.novak@company.com` | Team Leads, Orion / Helios / Zephyr | One pending leave each, blocked and rejected tasks |
| `ravi.kumar@company.com` | Employee | On 5 projects; approved leave the week after next with 3 tasks inside it |
| `elena.petrova@company.com` | Employee | Pending leave next week overlapping 2 tasks and a milestone |
| `sarah.connor@company.com` | Employee | Wave 3 tasks, unread notifications |
| `rachel.green@company.com` | Employee, Human Resources | No team; pending casual leave |
| `tom.becker@`, `aisha.khan@`, `lucas.silva@`, `hannah.wright@`, `yuki.tanaka@`, `carlos.mendes@`, `fatima.zahra@`, `noah.fischer@`, `priya.nair@`, `ben.carter@`, `zoe.martin@`, `samir.patel@`, `olivia.brown@`, `ethan.ross@`, `john.matrix@`, `kyle.reese@`, `employee@company.com` | Employees | Tasks, leave history, support tickets |
| `client@acme.com` | Client, Acme Corp | Alpha ERP |
| `client.globex@company.com` | Client, Globex | Phoenix and Vega deliverables with feedback |
| `client.initech@company.com` | Client, Initech | Atlas, Nova |
| `client.umbrella@company.com` | Client, Umbrella Health | Helios, Zephyr |
| `client.stark@company.com` | Client, Stark Logistics | Orion, Lyra |

Notes:

- `admin@company.com` is reset to the seed password with MFA off, even if `seed_test_users.py` created it earlier with `Admin@123`.
- The failed-login anomaly only shows for 15 minutes after a seed run (the detector's window). Re-run the seed to bring it back.
- Leave, task and milestone dates are relative to the day you seed.
- Task submission and deliverable file URLs are placeholders; the files do not exist.

Data summary (Wave 3 rows included): 42 accounts across all 9 roles, 6 departments, 31 employees, 4 PMs, 5 clients, 9 projects in every status, 28 milestones, 8 teams, 43 project assignments, 118 tasks in every status with 62 submissions and 30 comments, 7 leave types, 18 leave requests in every status, 18 support tickets with 57 activities, 10 deliverables with 6 client feedback entries, 52 notifications, 6 backup logs, 3 elevated access grants, 3 executive reports and about 325 audit log rows.
