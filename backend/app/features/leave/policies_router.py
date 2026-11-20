"""Leave policies / leave types (US-18, S4-BE-2).

GET  /api/v1/leave/policies        all authenticated roles; HR/ADMIN may pass ?include_inactive=true
POST /api/v1/leave/policies        HR, ADMIN
PUT  /api/v1/leave/policies/{id}   HR, ADMIN (partial update; is_active=false deactivates)

There is no DELETE: leave_request.leave_type_id is ON DELETE RESTRICT, so policies
are retired through is_active instead.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.db.session import get_db
from app.features.leave.schemas import (
    LeavePolicyCreate,
    LeavePolicyResponse,
    LeavePolicyUpdate,
)
from app.features.leave.service import (
    DuplicateLeavePolicyNameError,
    LeavePolicyNotFoundError,
    LeavePolicyService,
)
from app.models.enums import UserType
from app.models.user_account import UserAccount

router = APIRouter()

POLICY_ADMIN_ROLES = ["HR", "ADMIN"]
policy_admin_guard = require_role(POLICY_ADMIN_ROLES)


def _get_client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get(
    "/policies",
    response_model=List[LeavePolicyResponse],
    summary="List leave policies (US-18, S4-BE-2)",
    description=(
        "All authenticated roles see active policies, ordered by name. "
        "HR and ADMIN may pass `include_inactive=true` to also see deactivated ones; "
        "the flag is ignored for other roles."
    ),
)
def list_policies(
    include_inactive: bool = Query(False, description="HR/ADMIN only: include deactivated policies"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> List[LeavePolicyResponse]:
    can_see_inactive = current_user.user_type in (UserType.HR, UserType.ADMIN)
    return LeavePolicyService.list_policies(db, include_inactive=include_inactive and can_see_inactive)


@router.post(
    "/policies",
    response_model=LeavePolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a leave policy (US-18, S4-BE-2) [HR, ADMIN]",
)
def create_policy(
    payload: LeavePolicyCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(policy_admin_guard),
) -> LeavePolicyResponse:
    try:
        return LeavePolicyService.create_policy(
            db=db, payload=payload, actor=current_user, ip_address=_get_client_ip(request)
        )
    except DuplicateLeavePolicyNameError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.put(
    "/policies/{leave_type_id}",
    response_model=LeavePolicyResponse,
    summary="Update a leave policy (US-18, S4-BE-2) [HR, ADMIN]",
    description=(
        "Partial update of name, yearly_quota, is_paid, description and is_active. "
        "Lowering a quota below what is already used is allowed."
    ),
)
def update_policy(
    leave_type_id: int,
    payload: LeavePolicyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(policy_admin_guard),
) -> LeavePolicyResponse:
    try:
        return LeavePolicyService.update_policy(
            db=db,
            leave_type_id=leave_type_id,
            payload=payload,
            actor=current_user,
            ip_address=_get_client_ip(request),
        )
    except LeavePolicyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DuplicateLeavePolicyNameError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
