"""Leave policies / leave types (S4-BE-2).

Endpoints
---------
GET    /api/v1/leave/policies          – list all active policies (all roles)
GET    /api/v1/leave/policies/all      – list including inactive (HR / SYSTEM_ADMIN)
POST   /api/v1/leave/policies          – create a new policy (HR only)
PATCH  /api/v1/leave/policies/{id}     – update quota / description (HR only)
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.rbac import require_role
from app.db.session import get_db
from app.features.leave.schemas import (
    LeavePolicyCreate,
    LeavePolicyResponse,
    LeavePolicyUpdate,
)
from app.features.leave.service import (
    LeavePolicyService,
    LeavePolicyNotFoundError,
    DuplicateLeavePolicyNameError,
)
from app.models.user_account import UserAccount

router = APIRouter()

# ── RBAC guards ──────────────────────────────────────────────────────
hr_or_admin_guard = require_role(["HR", "SYSTEM_ADMIN"])
any_internal_guard = require_role(["EMPLOYEE", "TEAM_LEAD", "PM", "HR", "SYSTEM_ADMIN", "IT_SUPPORT"])


# ── Helpers ──────────────────────────────────────────────────────────

def _get_client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── List active leave policies (any authenticated user) ──────────────

@router.get(
    "/policies",
    response_model=List[LeavePolicyResponse],
    status_code=status.HTTP_200_OK,
    summary="List active leave policies (US-18, S4-BE-2)",
    description=(
        "Returns all **active** leave type definitions (name, yearly quota, paid/unpaid). "
        "Accessible by all internal roles so employees know their available leave types."
    ),
)
def list_policies(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(any_internal_guard),
) -> List[LeavePolicyResponse]:
    return LeavePolicyService.list_policies(db, include_inactive=False)


# ── List ALL policies including inactive (HR / SYSTEM_ADMIN) ─────────

@router.get(
    "/policies/all",
    response_model=List[LeavePolicyResponse],
    status_code=status.HTTP_200_OK,
    summary="List all leave policies including inactive (US-18, S4-BE-2) [HR/Admin]",
    description="Returns active **and** deactivated leave type definitions. HR and System Admin only.",
)
def list_all_policies(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(hr_or_admin_guard),
) -> List[LeavePolicyResponse]:
    return LeavePolicyService.list_policies(db, include_inactive=True)


# ── Create a new leave policy (HR only) ──────────────────────────────

@router.post(
    "/policies",
    response_model=LeavePolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a leave policy / leave type (US-18, S4-BE-2) [HR]",
    description=(
        "HR creates a new named leave type with its annual entitlement (yearly quota) "
        "and paid/unpaid classification. Name must be unique."
    ),
)
def create_policy(
    payload: LeavePolicyCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(hr_or_admin_guard),
) -> LeavePolicyResponse:
    try:
        return LeavePolicyService.create_policy(
            db=db,
            payload=payload,
            actor=current_user,
            ip_address=_get_client_ip(request),
        )
    except DuplicateLeavePolicyNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


# ── Update quota / description / paid flag (HR only) ─────────────────

@router.patch(
    "/policies/{leave_type_id}",
    response_model=LeavePolicyResponse,
    status_code=status.HTTP_200_OK,
    summary="Update leave policy quota / description / status (US-18, S4-BE-2) [HR]",
    description=(
        "HR updates the yearly quota, paid classification, description, or active status "
        "of an existing leave policy. All fields are optional (patch semantics)."
    ),
)
def update_policy(
    leave_type_id: int,
    payload: LeavePolicyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(hr_or_admin_guard),
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
