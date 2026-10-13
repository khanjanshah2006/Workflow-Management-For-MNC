from typing import Any, Callable, Sequence, Union
from fastapi import Depends, HTTPException, status

from app.core.deps import get_current_user
from app.models.enums import UserType
from app.models.user_account import UserAccount


def _check_user_role(user: UserAccount, allowed_roles: Sequence[str]) -> UserAccount:
    """Validate that the user's role is within the allowed roles."""
    user_type_val = (
        user.user_type.value
        if hasattr(user.user_type, "value")
        else str(user.user_type)
    )

    # Normalize allowed roles for comparison (case-insensitive & stripping underscores/spaces if needed)
    allowed_normalized = {str(r).strip().upper() for r in allowed_roles}
    user_normalized = user_type_val.strip().upper()

    if user_normalized not in allowed_normalized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: requires one of {list(allowed_roles)}",
        )
    return user


def require_role(
    allowed_roles_or_user: Union[Sequence[str], UserAccount],
    allowed: Union[Sequence[str], None] = None,
) -> Any:
    """
    Role-Based Access Control (RBAC) guard.

    Supports both FastAPI dependency injection and direct function calls:

    1. As a dependency factory:
       @router.get("/admin", dependencies=[Depends(require_role(["ADMIN"]))])
       or
       @router.get("/admin")
       def admin_route(user: UserAccount = Depends(require_role(["ADMIN"]))):

    2. As an inline function check:
       require_role(current_user, allowed=["ADMIN", "HR"])
    """
    # Direct function check: require_role(current_user, allowed=["ADMIN"])
    if isinstance(allowed_roles_or_user, UserAccount) or hasattr(
        allowed_roles_or_user, "user_type"
    ):
        roles = allowed if allowed is not None else []
        return _check_user_role(allowed_roles_or_user, roles)

    # Dependency factory pattern: Depends(require_role(["ADMIN"]))
    target_roles = list(allowed_roles_or_user)

    def role_dependency(
        current_user: UserAccount = Depends(get_current_user),
    ) -> UserAccount:
        return _check_user_role(current_user, target_roles)

    return role_dependency
