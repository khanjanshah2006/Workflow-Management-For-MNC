---
name: code-review-checklist
description: Use when asked to review a pull request, diff, or piece of code in the Workflow Management System for MNCs repo. Runs the agreed team checklist so review quality doesn't depend on which of the 11 of us happens to be reviewing.
---

# Workflow Management System for MNCs Code Review Checklist

Check a diff against all of these; call out any that fail explicitly rather than only commenting on style.

## Structure
- [ ] New files are in the correct folder per `project-structure` (router matches Epic, model matches ERD cluster, feature folder matches backend router)
- [ ] No new top-level entity/table that isn't in the finalized ERD (`erd-schema`) — if one seems genuinely needed, flag it for team discussion rather than merging it silently

## Backend-specific
- [ ] RBAC check present on every protected endpoint, and matches the actual allowed-roles table in `rbac-enforcement` (not just "some check exists")
- [ ] Audit log call present on state-changing endpoints
- [ ] No business logic inside a router function — it belongs in `services/`
- [ ] Response uses a Pydantic schema, not a raw model or dict
- [ ] New Alembic migration's FKs all reference real PKs; no direct `EMPLOYEE.department_id`-style redundant column reintroduced

## Frontend-specific
- [ ] Component is in the right `features/<epic>/` folder
- [ ] API calls go through `api/<domain>Api.js`, not inline `fetch`
- [ ] Loading and error states are handled, not just the happy path
- [ ] Role-sensitive rendering double-checks `useAuth().user.role`, not just relying on the route guard

## Traceability
- [ ] Commit message references a US-ID
- [ ] The diff actually satisfies that story's acceptance criteria — read them, don't assume from the title

## What NOT to block on
Formatting/linting (should be automated, not a human review concern) and naming bikeshedding — focus review time on RBAC, audit logging, and structural correctness, since those are the things that are expensive to fix later and easy to miss when eleven people are moving in parallel.
