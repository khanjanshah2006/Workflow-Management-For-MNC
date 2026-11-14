from typing import Any, Callable, Optional, Sequence, Union
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import UserType
from app.models.user_account import UserAccount


def _check_user_role(
    user: UserAccount,
    allowed_roles: Sequence[str],
    db: Optional[Session] = None,
) -> UserAccount:
    """Validate that the user's role (or active elevated role) is within the allowed roles."""
    user_type_val = (
        user.user_type.value
        if hasattr(user.user_type, "value")
        else str(user.user_type)
    )

    # Normalize allowed roles for comparison (case-insensitive & stripping underscores/spaces if needed)
    allowed_normalized = {
        str(r).strip().upper().replace(" ", "_") for r in allowed_roles
    }
    user_normalized = user_type_val.strip().upper().replace(" ", "_")

    # 1. Baseline role match
    if user_normalized in allowed_normalized:
        return user

    # 2. Check for active time-bound elevated access grant (US-45)
    account_id = getattr(user, "account_id", None)
    if account_id:
        from datetime import datetime, timezone
        from app.models.elevated_access_grant import ElevatedAccessGrant

        now = datetime.now(timezone.utc)

        def _has_matching_active_grant(session: Session) -> bool:
            active_grant = (
                session.query(ElevatedAccessGrant)
                .filter(
                    ElevatedAccessGrant.user_id == account_id,
                    ElevatedAccessGrant.revoked_at.is_(None),
                    ElevatedAccessGrant.expires_at > now,
                )
                .first()
            )
            if active_grant:
                elevated_role_normalized = (
                    active_grant.granted_role.strip().upper().replace(" ", "_")
                )
                return elevated_role_normalized in allowed_normalized
            return False

        if db is not None:
            try:
                if _has_matching_active_grant(db):
                    return user
            except Exception:
                pass
        else:
            from app.db.session import SessionLocal

            try:
                with SessionLocal() as session:
                    if _has_matching_active_grant(session):
                        return user
            except Exception:
                pass

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Access forbidden: requires one of {list(allowed_roles)}",
    )


def require_role(
    allowed_roles_or_user: Union[Sequence[str], UserAccount],
    allowed: Union[Sequence[str], None] = None,
    db: Optional[Session] = None,
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
        return _check_user_role(allowed_roles_or_user, roles, db=db)

    # Dependency factory pattern: Depends(require_role(["ADMIN"]))
    target_roles = list(allowed_roles_or_user)

    def role_dependency(
        current_user: UserAccount = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> UserAccount:
        return _check_user_role(current_user, target_roles, db=db)

    return role_dependency


# Plural alias matching issue specification
require_roles = require_role


