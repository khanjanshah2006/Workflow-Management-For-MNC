---
name: fastapi-endpoint
description: Use when scaffolding a brand-new FastAPI endpoint from scratch inside an existing feature slice (not when editing an existing one — see api-endpoint-pattern for editing rules). Generates the router/service/schema boilerplate pre-wired with RBAC and audit logging so nobody starts from a blank file.
---

# Scaffold a New FastAPI Endpoint

Prerequisite: the feature slice already exists (`app/features/<epic>/`). If it doesn't, use `project-structure` to find the right slice first — don't create a new top-level folder for one endpoint.

## 1. Add the schema (`features/<epic>/schemas.py`)

```python
class <Thing>In(BaseModel):
    <field>: <type>

class <Thing>Out(BaseModel):
    <thing>_id: int
    <field>: <type>
    class Config:
        from_attributes = True
```

## 2. Add the service function (`features/<epic>/service.py`)

```python
def <action>_<thing>(db: Session, <ids and payload>, actor: Employee) -> <Thing>:
    require_role(actor, allowed=[...])            # core/rbac.py — see rbac-enforcement skill
    <business logic, validation>
    db.commit()
    write_audit_log(db, actor, action_type="<thing>.<action>", entity_affected="<TABLE>", entity_id=<id>)
    return <result>
```

## 3. Add the route (`features/<epic>/router.py`)

```python
@router.post("/<resource>", response_model=<Thing>Out)
def <action>_<thing>(
    payload: <Thing>In,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return <epic>_service.<action>_<thing>(db, payload, actor=current_user)
```

## 4. Checklist before calling it done

- [ ] Schema, service function, and route all added — never put logic directly in the router
- [ ] `require_role()` call present and matches the actual allowed roles for this FR (check `rbac-enforcement`)
- [ ] `write_audit_log()` call present if this is a state-changing endpoint
- [ ] Response uses the `Out` schema, not a raw model
- [ ] Add the corresponding request to the shared Postman collection (`postman-collection` skill) before opening the PR — an endpoint without a Postman entry is easy for the rest of the group to miss
