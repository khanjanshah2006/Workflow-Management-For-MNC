---
name: api-endpoint-pattern
description: Use whenever writing or editing a FastAPI route/endpoint in wms-backend. Defines the required layering (router → service → repository) and the three things every state-changing endpoint must include (RBAC check, audit log, error handling) so the 11 of us don't each invent a different pattern.
---

# Workflow Management System for MNCs API Endpoint Pattern

Every endpoint follows this shape. Do not put business logic or raw SQLAlchemy queries directly in a router function.

```python
# routers/<epic>.py
@router.post("/tasks/{task_id}/submit", response_model=TaskOut)
def submit_task(
    task_id: int,
    payload: TaskSubmitIn,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(current_user, allowed=["Employee", "Team Lead"])  # core/rbac.py
    result = task_service.submit_task(db, task_id, payload, actor=current_user)
    return result
```

```python
# services/task_service.py
def submit_task(db, task_id, payload, actor):
    task = task_repo.get_or_404(db, task_id)
    if task.assigned_to_id != actor.employee_id:
        raise ForbiddenError("Not your task")  # core/exceptions.py
    task.status = "pending_review"
    db.commit()
    write_audit_log(db, actor, action_type="task.submitted", entity_affected="TASK", entity_id=task_id)  # core/audit.py
    notification_service.notify(db, recipient_id=task.assigned_by_id, type="task_submitted", related_entity_id=task_id)
    return task
```

## The three non-negotiables for any state-changing endpoint (POST/PUT/PATCH/DELETE)

1. **RBAC check first, before any DB read** — `require_role()` from `core/rbac.py`. Every endpoint's allowed roles should map directly to the FR it implements (check the requirement's stated actor).
2. **Audit log on every write** — call `write_audit_log()` from `core/audit.py`. This satisfies NFR-AU01–04 and is easy to forget when eleven people are each writing their own endpoints — treat it as mandatory, not optional.
3. **Raise, don't return, on failure** — use the custom exceptions in `core/exceptions.py` (`NotFoundError`, `ForbiddenError`, `ValidationError`) rather than returning `{"error": "..."}` — FastAPI's exception handlers turn these into consistent HTTP responses (NFR-U03: error messages must clearly describe the problem).

## Read-only (GET) endpoints

Still go through `services/`, but skip the audit log unless the read itself is sensitive (e.g. `AUDIT_LOG` search, `EMPLOYEE` PII) — don't log every dashboard view.

## Response schemas

Always define a `schemas/<name>.py` Pydantic model for the response — never return a raw SQLAlchemy model or a bare dict from a router.
