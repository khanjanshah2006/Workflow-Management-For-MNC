from fastapi import Depends, HTTPException, status
from app.core.deps import get_current_user
from app.models.user_account import UserAccount


def require_roles(allowed_roles: list[str]):
    normalized_allowed = {
        role.upper().replace(" ", "_")
        for role in allowed_roles
    }
    if "HR_MANAGER" in normalized_allowed:
        normalized_allowed.add("HR")
    if "HR" in normalized_allowed:
        normalized_allowed.add("HR_MANAGER")

    async def role_checker(
        current_user: UserAccount = Depends(get_current_user),
    ) -> UserAccount:
        raw_role = (
            current_user.user_type.value
            if hasattr(current_user.user_type, "value")
            else str(current_user.user_type)
        )
        user_role = raw_role.upper().replace(" ", "_")
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: role '{raw_role}' is not authorized for this action",
            )
        return current_user

    return role_checker
