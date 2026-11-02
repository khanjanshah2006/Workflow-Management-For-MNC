from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.rbac import require_role
from app.db.session import get_db
from app.features.admin.schemas import (
    AdminPasswordReset,
    BackupStatusResponse,
    UserAccountCreate,
    UserAccountFilter,
    UserAccountPaginationResponse,
    UserAccountResponse,
    UserAccountStatusUpdate,
    UserRoleUpdate,
)
from app.features.admin.service import (
    AdminService,
    EmailAlreadyExistsError,
    UserNotFoundError,
)
from app.models.enums import UserType
from app.models.user_account import UserAccount

router = APIRouter(prefix="/api/v1/admin", tags=["Admin User Management"])

# Strict RBAC guard: Admin access only
admin_guard = require_role(["ADMIN"])


@router.get(
    "/users",
    response_model=UserAccountPaginationResponse,
    status_code=status.HTTP_200_OK,
    summary="List all user accounts (US-43)",
    description="Retrieve paginated list of user accounts with optional filtering by role, status, and search query.",
)
def list_users(
    search: Optional[str] = Query(None, description="Search by email"),
    user_type: Optional[UserType] = Query(None, description="Filter by user role/type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(admin_guard),
) -> UserAccountPaginationResponse:
    filters = UserAccountFilter(
        search=search,
        user_type=user_type,
        is_active=is_active,
        page=page,
        limit=limit,
    )
    return AdminService.list_accounts(db=db, filters=filters)


@router.post(
    "/users",
    response_model=UserAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a standalone user account (US-43)",
    description="Allows administrators to directly create user accounts for clients, managers, or new admins.",
)
def create_user(
    payload: UserAccountCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(admin_guard),
) -> UserAccountResponse:
    client_ip = request.client.host if request.client else None
    try:
        return AdminService.create_account(
            db=db,
            payload=payload,
            admin_user=current_user,
            ip_address=client_ip,
        )
    except EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/users/{account_id}",
    response_model=UserAccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user account details (US-43)",
    description="Retrieve user account metadata by account ID.",
)
def get_user(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(admin_guard),
) -> UserAccountResponse:
    try:
        return AdminService.get_account(db=db, account_id=account_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch(
    "/users/{account_id}/status",
    response_model=UserAccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate or deactivate a user account (US-43, US-48)",
    description="Toggles user active state. Deactivation immediately prevents any further API authentication.",
)
def update_user_status(
    account_id: UUID,
    payload: UserAccountStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(admin_guard),
) -> UserAccountResponse:
    client_ip = request.client.host if request.client else None
    try:
        return AdminService.update_status(
            db=db,
            account_id=account_id,
            is_active=payload.is_active,
            admin_user=current_user,
            ip_address=client_ip,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch(
    "/users/{account_id}/role",
    response_model=UserAccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign or revoke user role (US-44)",
    description="Updates user role/type with immediate effect. Generates an immutable audit record.",
)
def update_user_role(
    account_id: UUID,
    payload: UserRoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(admin_guard),
) -> UserAccountResponse:
    client_ip = request.client.host if request.client else None
    try:
        return AdminService.update_role(
            db=db,
            account_id=account_id,
            new_role=payload.user_type,
            admin_user=current_user,
            ip_address=client_ip,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/users/{account_id}/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Admin password reset (US-48)",
    description="Sets a user's password to new credentials. Encrypted via bcrypt and recorded in audit log.",
)
def reset_user_password(
    account_id: UUID,
    payload: AdminPasswordReset,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(admin_guard),
) -> dict:
    client_ip = request.client.host if request.client else None
    try:
        return AdminService.reset_password(
            db=db,
            account_id=account_id,
            new_password=payload.new_password,
            admin_user=current_user,
            ip_address=client_ip,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/system/backup-status",
    response_model=BackupStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Database backup and health status (US-50)",
    description="Check Supabase backup health and connection pool telemetry.",
)
def get_backup_status(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(admin_guard),
) -> BackupStatusResponse:
    return AdminService.get_backup_status(db=db)
