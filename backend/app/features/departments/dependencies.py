"""
Authentication and Role-Based Access Control (RBAC) dependencies
for the Department API feature slice.

Integration Dependency:
    Central authentication (JWT verification against Supabase and UserAccount lookup)
    is part of Epic 1 (features/auth or core/auth.py).
    This module defines the identity contract required by department endpoints.
    In test environments, `get_current_user` must be explicitly overridden via
    FastAPI's `app.dependency_overrides[get_current_user]`.
"""

from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

security = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    """
    Authenticated user identity contract for request context and RBAC checks.
    Populated by the central authentication provider once Epic 1 (Auth) is integrated.
    """

    account_id: UUID
    email: str
    role: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    """
    Resolve the authenticated user from the active session/token.

    Raises:
        HTTPException 401: If Bearer token is missing.
        HTTPException 401: If unverified/unintegrated credentials are provided without
                           an active central authentication provider.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Central authentication provider (Epic 1) is not yet integrated into the repository.
    # Reject unverified tokens in runtime; test suites explicitly override this dependency.
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication provider not configured: pending Epic 1 integration",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_roles(allowed_roles: list[str]):
    """
    FastAPI dependency factory enforcing allowed roles.
    Raises HTTP 403 if the authenticated user's role is not in allowed_roles.
    """
    normalized_allowed = {
        role.upper().replace(" ", "_")
        for role in allowed_roles
    }

    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        user_role = current_user.role.upper().replace(" ", "_")
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: role '{current_user.role}' is not authorized for this action",
            )
        return current_user

    return role_checker
