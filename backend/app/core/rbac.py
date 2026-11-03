from typing import Any, Iterable, List
from app.core.exceptions import ForbiddenError


def normalize_role(role_name: str) -> str:
    """Normalize role string to uppercase with underscores."""
    if not role_name:
        return ""
    return str(role_name).strip().upper().replace(" ", "_").replace("-", "_")


def get_actor_roles(actor: Any) -> List[str]:
    """
    Extract all detectable roles for an actor (UserAccount, Employee, or dict).
    Checks user_type, role, and designation.
    """
    roles = []
    if actor is None:
        return roles

    # Dict representation
    if isinstance(actor, dict):
        if "role" in actor and actor["role"]:
            roles.append(normalize_role(actor["role"]))
        if "user_type" in actor and actor["user_type"]:
            roles.append(normalize_role(str(actor["user_type"])))
        if "designation" in actor and actor["designation"]:
            roles.append(normalize_role(actor["designation"]))
        return roles

    # Object attributes (UserAccount / Employee)
    if hasattr(actor, "user_type") and actor.user_type is not None:
        val = actor.user_type.value if hasattr(actor.user_type, "value") else str(actor.user_type)
        roles.append(normalize_role(val))

    if hasattr(actor, "role") and actor.role is not None:
        val = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
        roles.append(normalize_role(val))

    if hasattr(actor, "designation") and actor.designation is not None:
        roles.append(normalize_role(actor.designation))

    # Check related employee if actor is UserAccount
    if hasattr(actor, "employee") and actor.employee is not None:
        if hasattr(actor.employee, "designation") and actor.employee.designation:
            roles.append(normalize_role(actor.employee.designation))

    return roles


def has_any_role(actor: Any, allowed: Iterable[str]) -> bool:
    """Check if actor holds any of the specified roles."""
    actor_roles = set(get_actor_roles(actor))
    normalized_allowed = {normalize_role(r) for r in allowed}
    return bool(actor_roles.intersection(normalized_allowed))


def require_role(actor: Any, allowed: Iterable[str]) -> None:
    """
    Ensure the actor holds at least one of the allowed roles.
    Raises ForbiddenError if unauthorized.
    """
    if not has_any_role(actor, allowed):
        allowed_str = ", ".join(allowed)
        raise ForbiddenError(f"Access forbidden: insufficient role permissions. Requires one of the following roles: [{allowed_str}]")


def is_it_support(actor: Any) -> bool:
    """Check whether the actor holds the IT_SUPPORT role."""
    return has_any_role(actor, ["IT_SUPPORT", "IT Support"])
