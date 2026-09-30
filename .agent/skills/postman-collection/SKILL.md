---
name: postman-collection
description: Use when adding a new endpoint to the shared Postman collection, or when asked to generate/update it. Keeps request naming and folder structure matching the 10 Epics so the collection stays usable for all 11 group members instead of drifting from the actual API.
---

# WMS Postman Collection Conventions

One shared collection, committed to the repo (`docs/postman/wms.postman_collection.json`), not eleven personal ones. Folder structure mirrors the backend feature slices exactly — same names, same order.

## Folder structure

```
Workflow Management System for MNCs API/
├── 01 Auth              (features/auth)
├── 02 Employees & Org    (features/employees, features/org)
├── 03 Projects           (features/projects)
├── 04 Tasks              (features/tasks)
├── 05 Leave              (features/leave)
├── 06 Notifications      (features/notifications)
├── 07 Client Portal      (features/client_portal)
├── 08 Reporting          (features/reporting)
├── 09 Support            (features/support)
└── 10 Admin              (features/admin)
```

## Request naming

`<HTTP method> <resource, plain English>` — e.g. `POST Submit Leave Request`, `GET Review Queue (Team Lead)`. Not the raw route path; the route is visible in the request itself.

## Environment variables (not hardcoded in requests)

- `{{base_url}}` — points at local/staging/prod, switched via Postman environment, never hardcoded per-request
- `{{access_token}}` — set automatically by the collection's `Login` request's test script (`pm.environment.set("access_token", ...)`,  so nobody manually pastes a token
- `{{client_access_token}}` — separate variable for Client-role requests, since Client and Employee auth are genuinely different (see `rbac-enforcement`)

## When adding a new endpoint

1. Add it to the folder matching its Epic (table above) — never a loose top-level request
2. Auth header: `Authorization: Bearer {{access_token}}` (or `{{client_access_token}}` for `07 Client Portal`)
3. Add at least one example response, and a failing-auth example (401/403) if the endpoint is role-restricted — this doubles as a quick manual check that RBAC is actually enforced
4. This is part of the same PR as the endpoint itself (see `fastapi-endpoint`'s checklist) — a collection update as an afterthought is how it drifts
