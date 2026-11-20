"""Business logic for the leave feature (US-16, US-40, S4-BE-1, S4-BE-2)."""
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import scope
from app.core.audit import write_audit_log
from app.core.notification_types import LEAVE_REQUESTED
from app.features.leave.repository import LeaveRepository
from app.features.leave.schemas import (
    EmployeeLeaveBalanceResponse,
    LeaveBalanceItem,
    LeaveBalanceOut,
    LeaveBalanceResponse,
    LeavePolicyCreate,
    LeavePolicyResponse,
    LeavePolicyUpdate,
    LeaveRequestCreate,
    LeaveRequestOut,
    PaginatedLeaveRequestsOut,
)
from app.features.notifications.service import NotificationService
from app.models.employee import Employee
from app.models.enums import AuditAction, LeaveStatus
from app.models.leave import LeaveRequest, LeaveType
from app.models.user_account import UserAccount


class LeaveService:
    """Service providing core leave operations and validations (S4-BE-1)."""

    @staticmethod
    def calculate_business_days(start_date: date, end_date: date) -> int:
        """
        Count Monday–Friday business days only within [start_date, end_date] inclusive.
        Saturday (weekday 5) and Sunday (weekday 6) are excluded.
        """
        if end_date < start_date:
            return 0
        days = 0
        cur = start_date
        one_day = timedelta(days=1)
        while cur <= end_date:
            if cur.weekday() < 5:
                days += 1
            cur += one_day
        return days

    @classmethod
    def validate_leave_application(
        cls,
        db: Session,
        emp_id: int,
        data: LeaveRequestCreate,
        today: Optional[date] = None,
    ) -> Tuple[LeaveType, int]:
        """
        Validate leave request in the strict required order:
        1. (Schema validated by Pydantic: required fields + stripped reason 10-2000 chars -> 422)
        2. Leave type exists: 404
        3. Leave type is active: 400, "Leave type is not active"
        4. end_date >= start_date: 400
        5. start_date >= today: 400, "Cannot apply for leave in the past"
        6. start_date.year == end_date.year: 400, "Leave cannot span calendar years; submit two requests"
        7. Count Monday–Friday business days only. If total_days <= 0: 400, "Selected range contains no working days"
        8. Reject overlapping PENDING or APPROVED requests of same employee: 409, "Overlapping leave request exists"
        9. Validate yearly quota using calendar year of start_date:
           used_days + pending_days + requested_days <= yearly_quota.
           If exceeded: 400, "Insufficient leave balance (Available: X days)"
        """
        # 2. Leave type exists: 404
        leave_type = LeaveRepository.get_leave_type(db, data.leave_type_id)
        if leave_type is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Leave type not found",
            )

        # 3. Leave type is active: 400
        if not leave_type.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Leave type is not active",
            )

        # 4. end_date >= start_date: 400
        if data.end_date < data.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date must be greater than or equal to start date",
            )

        # 5. start_date >= today: 400
        if today is None:
            today = date.today()
        if data.start_date < today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot apply for leave in the past",
            )

        # 6. start_date.year == end_date.year: 400
        if data.start_date.year != data.end_date.year:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Leave cannot span calendar years; submit two requests",
            )

        # 7. Count Monday–Friday business days only. If total_days <= 0: 400
        total_days = cls.calculate_business_days(data.start_date, data.end_date)
        if total_days <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected range contains no working days",
            )

        # 8. Overlapping PENDING or APPROVED requests: 409
        if LeaveRepository.has_overlapping_request(db, emp_id, data.start_date, data.end_date):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Overlapping leave request exists",
            )

        # 9. Yearly quota validation using start_date calendar year
        calendar_year = data.start_date.year
        used_days = LeaveRepository.get_leave_days_by_status(
            db=db,
            emp_id=emp_id,
            leave_type_id=data.leave_type_id,
            year=calendar_year,
            status=LeaveStatus.APPROVED,
        )
        pending_days = LeaveRepository.get_leave_days_by_status(
            db=db,
            emp_id=emp_id,
            leave_type_id=data.leave_type_id,
            year=calendar_year,
            status=LeaveStatus.PENDING,
        )
        available_days = leave_type.yearly_quota - used_days - pending_days
        if used_days + pending_days + total_days > leave_type.yearly_quota:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient leave balance (Available: {available_days} days)",
            )

        return leave_type, total_days

    @classmethod
    def submit_leave_request(
        cls,
        db: Session,
        current_user: UserAccount,
        data: LeaveRequestCreate,
        today: Optional[date] = None,
    ) -> LeaveRequestOut:
        """
        Submit a leave request (US-16):
        1. Resolve employee profile (403 if missing).
        2. Validate inputs and business constraints in strict order.
        3. Insert PENDING record.
        4. Commit transaction atomically.
        """
        employee = scope.resolve_employee(db, current_user)
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No employee profile linked to this account",
            )

        leave_type, total_days = cls.validate_leave_application(
            db=db,
            emp_id=employee.emp_id,
            data=data,
            today=today,
        )

        leave_request = LeaveRepository.create_leave_request(
            db=db,
            emp_id=employee.emp_id,
            leave_type_id=leave_type.leave_type_id,
            start_date=data.start_date,
            end_date=data.end_date,
            total_days=total_days,
            reason=data.reason,
        )

        # US-40: Automatic notifications to Team Leads and staffing PMs
        cls._send_submission_notifications(
            db=db,
            employee=employee,
            leave_request=leave_request,
            total_days=total_days,
        )

        # Audit log for creation
        write_audit_log(
            db=db,
            action=AuditAction.CREATE,
            entity_name="LEAVE_REQUEST",
            entity_ref_id=str(leave_request.leave_id),
            account_id=current_user.account_id,
            new_value={
                "leave_id": leave_request.leave_id,
                "emp_id": leave_request.emp_id,
                "leave_type_id": leave_request.leave_type_id,
                "start_date": str(leave_request.start_date),
                "end_date": str(leave_request.end_date),
                "total_days": leave_request.total_days,
                "status": leave_request.status.value if hasattr(leave_request.status, "value") else str(leave_request.status),
                "reason": leave_request.reason,
            },
            commit=False,
        )

        db.commit()
        db.refresh(leave_request)

        return LeaveRequestOut(
            leave_id=leave_request.leave_id,
            emp_id=leave_request.emp_id,
            leave_type_id=leave_request.leave_type_id,
            leave_type_name=leave_type.name,
            start_date=leave_request.start_date,
            end_date=leave_request.end_date,
            total_days=leave_request.total_days,
            reason=leave_request.reason,
            status=leave_request.status,
            applied_at=leave_request.applied_at,
            reviewed_at=leave_request.reviewed_at,
            reviewed_by_account_id=leave_request.reviewed_by_account_id,
            review_remarks=leave_request.review_remarks,
        )

    @staticmethod
    def _send_submission_notifications(
        db: Session,
        employee: Employee,
        leave_request: LeaveRequest,
        total_days: int,
    ) -> None:
        """
        US-40: Immediately notify every Team Lead of active teams and every staffing PM.
        Avoids duplicates, avoids notifying applicant themself, and does not silently skip.
        """
        tl_account_ids = scope.team_lead_account_ids_for(db, employee.emp_id)
        pm_account_ids = scope.staffing_pm_account_ids_for(db, employee.emp_id)

        # Deduplicate recipients
        recipients = set(tl_account_ids) | set(pm_account_ids)
        if employee.account_id is not None:
            recipients.discard(employee.account_id)

        # Collect affected project names
        staffing_projects = scope.staffing_projects_for(db, employee.emp_id)
        project_names = [p.name for p in staffing_projects]
        projects_str = ", ".join(project_names) if project_names else "None"

        title = f"Leave Request: {employee.full_name}"
        message = (
            f"{employee.full_name} has requested {total_days} day(s) of leave "
            f"from {leave_request.start_date} to {leave_request.end_date}. "
            f"Affected projects: {projects_str}."
        )
        link = f"/team-lead/leave?request={leave_request.leave_id}"

        for account_id in recipients:
            NotificationService.create_notification(
                db=db,
                user_id=account_id,
                type=LEAVE_REQUESTED,
                title=title,
                message=message,
                link=link,
            )

    @staticmethod
    def list_my_leave_history(
        db: Session,
        current_user: UserAccount,
        status_filter: Optional[LeaveStatus] = None,
        year: Optional[int] = None,
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedLeaveRequestsOut:
        """List leave requests for the authenticated employee with isolation and pagination."""
        employee = scope.resolve_employee(db, current_user)
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No employee profile linked to this account",
            )

        total = LeaveRepository.count_employee_requests(
            db=db,
            emp_id=employee.emp_id,
            status=status_filter,
            year=year,
        )

        rows = LeaveRepository.list_employee_requests(
            db=db,
            emp_id=employee.emp_id,
            status=status_filter,
            year=year,
            page=page,
            limit=limit,
        )

        items = [
            LeaveRequestOut(
                leave_id=req.leave_id,
                emp_id=req.emp_id,
                leave_type_id=req.leave_type_id,
                leave_type_name=type_name,
                start_date=req.start_date,
                end_date=req.end_date,
                total_days=req.total_days,
                reason=req.reason,
                status=req.status,
                applied_at=req.applied_at,
                reviewed_at=req.reviewed_at,
                reviewed_by_account_id=req.reviewed_by_account_id,
                review_remarks=req.review_remarks,
            )
            for req, type_name in rows
        ]

        return PaginatedLeaveRequestsOut(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )

    @staticmethod
    def cancel_leave_request(
        db: Session,
        current_user: UserAccount,
        leave_id: int,
    ) -> LeaveRequestOut:
        """
        Cancel a pending leave request (owner only).
        Updates status to CANCELLED, logs UPDATE audit row, and commits.
        """
        employee = scope.resolve_employee(db, current_user)
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No employee profile linked to this account",
            )

        record = LeaveRepository.get_leave_request_with_type(db, leave_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Leave request not found",
            )

        leave_request, type_name = record

        # Only the owner can cancel
        if leave_request.emp_id != employee.emp_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only cancel your own leave requests",
            )

        # Only PENDING requests can be cancelled
        if leave_request.status != LeaveStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending requests can be cancelled",
            )

        old_status = leave_request.status.value if hasattr(leave_request.status, "value") else str(leave_request.status)
        leave_request.status = LeaveStatus.CANCELLED
        new_status = leave_request.status.value if hasattr(leave_request.status, "value") else str(leave_request.status)

        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="LEAVE_REQUEST",
            entity_ref_id=str(leave_request.leave_id),
            account_id=current_user.account_id,
            old_value={"status": old_status},
            new_value={"status": new_status},
            commit=False,
        )
        db.commit()
        db.refresh(leave_request)

        return LeaveRequestOut(
            leave_id=leave_request.leave_id,
            emp_id=leave_request.emp_id,
            leave_type_id=leave_request.leave_type_id,
            leave_type_name=type_name,
            start_date=leave_request.start_date,
            end_date=leave_request.end_date,
            total_days=leave_request.total_days,
            reason=leave_request.reason,
            status=leave_request.status,
            applied_at=leave_request.applied_at,
            reviewed_at=leave_request.reviewed_at,
            reviewed_by_account_id=leave_request.reviewed_by_account_id,
            review_remarks=leave_request.review_remarks,
        )

    @staticmethod
    def get_employee_leave_balances(
        db: Session,
        emp_id: int,
        year: Optional[int] = None,
    ) -> EmployeeLeaveBalanceResponse:
        """
        Calculate year-wise leave balances for an employee across all active leave types.
        - used_days = APPROVED requests counted by start_date year.
        - pending_days = PENDING requests counted by start_date year.
        - available_days = yearly_quota - used_days - pending_days.
        Negative balances are NOT clamped to zero.
        """
        if year is None:
            year = date.today().year

        active_types = LeaveRepository.list_active_leave_types(db)
        balances: List[LeaveBalanceItem] = []

        for lt in active_types:
            used_days = LeaveRepository.get_leave_days_by_status(
                db=db,
                emp_id=emp_id,
                leave_type_id=lt.leave_type_id,
                year=year,
                status=LeaveStatus.APPROVED,
            )
            pending_days = LeaveRepository.get_leave_days_by_status(
                db=db,
                emp_id=emp_id,
                leave_type_id=lt.leave_type_id,
                year=year,
                status=LeaveStatus.PENDING,
            )
            available_days = lt.yearly_quota - used_days - pending_days

            balances.append(
                LeaveBalanceItem(
                    leave_type_id=lt.leave_type_id,
                    leave_type_name=lt.name,
                    yearly_quota=lt.yearly_quota,
                    used_days=used_days,
                    pending_days=pending_days,
                    available_days=available_days,
                    is_paid=lt.is_paid,
                )
            )

        return EmployeeLeaveBalanceResponse(
            employee_id=emp_id,
            year=year,
            balances=balances,
        )


# ────────────────────────────────────────────────────────────────────
# Custom exceptions (router catches these → raises HTTPException)
# ────────────────────────────────────────────────────────────────────

class LeavePolicyNotFoundError(Exception):
    pass


class DuplicateLeavePolicyNameError(Exception):
    pass


class LeavePolicyInactiveError(Exception):
    pass


# ────────────────────────────────────────────────────────────────────
# S4-BE-2 — Leave Policy / Leave Type Service
# ────────────────────────────────────────────────────────────────────

class LeavePolicyService:
    """Service layer for leave type (policy) CRUD operations — S4-BE-2."""

    @staticmethod
    def list_policies(
        db: Session,
        include_inactive: bool = False,
    ) -> List[LeavePolicyResponse]:
        """
        Return all leave types.

        HR / SYSTEM_ADMIN may pass include_inactive=True to see deactivated
        policies.  Employees/Team Leads/PMs always see only active ones.
        """
        rows = LeaveRepository.list_leave_types(db, include_inactive=include_inactive)
        return [LeavePolicyResponse.model_validate(r) for r in rows]

    @staticmethod
    def get_policy(db: Session, leave_type_id: int) -> LeavePolicyResponse:
        """Fetch a single policy by ID (raises LeavePolicyNotFoundError if missing)."""
        lt = LeaveRepository.get_leave_type(db, leave_type_id)
        if not lt:
            raise LeavePolicyNotFoundError(f"Leave policy #{leave_type_id} not found.")
        return LeavePolicyResponse.model_validate(lt)

    @staticmethod
    def create_policy(
        db: Session,
        payload: LeavePolicyCreate,
        actor: UserAccount,
        ip_address: Optional[str] = None,
    ) -> LeavePolicyResponse:
        """
        Create a new leave type / policy.

        Rules:
        - Name must be unique (case-insensitive).
        - yearly_quota ≥ 0 (0 = managed externally).
        """
        # Duplicate name guard
        existing = LeaveRepository.get_leave_type_by_name(db, payload.name)
        if existing:
            raise DuplicateLeavePolicyNameError(
                f"A leave policy named '{payload.name}' already exists."
            )

        lt = LeaveRepository.create_leave_type(
            db=db,
            name=payload.name,
            yearly_quota=payload.yearly_quota,
            is_paid=payload.is_paid,
            description=payload.description,
        )

        write_audit_log(
            db=db,
            action=AuditAction.CREATE,
            entity_name="LEAVE_TYPE",
            entity_ref_id=str(lt.leave_type_id),
            account_id=actor.account_id,
            new_value={
                "name": lt.name,
                "yearly_quota": lt.yearly_quota,
                "is_paid": lt.is_paid,
            },
            ip_address=ip_address,
        )

        return LeavePolicyResponse.model_validate(lt)

    @staticmethod
    def update_policy(
        db: Session,
        leave_type_id: int,
        payload: LeavePolicyUpdate,
        actor: UserAccount,
        ip_address: Optional[str] = None,
    ) -> LeavePolicyResponse:
        """
        Partial-update a leave policy.

        Rules:
        - Policy must exist.
        - Only HR / SYSTEM_ADMIN may update (enforced at router layer).
        - If is_active is set to True we allow it even if currently inactive
          (reactivation).
        """
        lt = LeaveRepository.get_leave_type(db, leave_type_id)
        if not lt:
            raise LeavePolicyNotFoundError(f"Leave policy #{leave_type_id} not found.")

        old_snapshot = {
            "yearly_quota": lt.yearly_quota,
            "is_paid": lt.is_paid,
            "description": lt.description,
            "is_active": lt.is_active,
        }

        updated = LeaveRepository.update_leave_type(
            db=db,
            leave_type=lt,
            yearly_quota=payload.yearly_quota,
            is_paid=payload.is_paid,
            description=payload.description,
            is_active=payload.is_active,
        )

        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="LEAVE_TYPE",
            entity_ref_id=str(leave_type_id),
            account_id=actor.account_id,
            old_value=old_snapshot,
            new_value={
                "yearly_quota": updated.yearly_quota,
                "is_paid": updated.is_paid,
                "description": updated.description,
                "is_active": updated.is_active,
            },
            ip_address=ip_address,
        )

        return LeavePolicyResponse.model_validate(updated)

    @staticmethod
    def deactivate_policy(
        db: Session,
        leave_type_id: int,
        actor: UserAccount,
        ip_address: Optional[str] = None,
    ) -> LeavePolicyResponse:
        """
        Soft-delete a leave policy by setting is_active = False.

        Does not delete the row so existing LeaveRequest FK references remain valid.
        """
        lt = LeaveRepository.get_leave_type(db, leave_type_id)
        if not lt:
            raise LeavePolicyNotFoundError(f"Leave policy #{leave_type_id} not found.")

        if not lt.is_active:
            raise LeavePolicyInactiveError(
                f"Leave policy #{leave_type_id} is already inactive."
            )

        updated = LeaveRepository.update_leave_type(db=db, leave_type=lt, is_active=False)

        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="LEAVE_TYPE",
            entity_ref_id=str(leave_type_id),
            account_id=actor.account_id,
            old_value={"is_active": True},
            new_value={"is_active": False},
            ip_address=ip_address,
        )

        return LeavePolicyResponse.model_validate(updated)

    # ────────────────────────────────────────────────────────────────
    # Shared helper used by S4-BE-1 (leave balance calculation)
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def get_balance(
        db: Session,
        emp_id: int,
        leave_type_id: int,
    ) -> LeaveBalanceResponse:
        """Calculate remaining leave days for an employee for the current year."""
        lt = LeaveRepository.get_leave_type(db, leave_type_id)
        if not lt:
            raise LeavePolicyNotFoundError(f"Leave policy #{leave_type_id} not found.")
        if not lt.is_active:
            raise LeavePolicyInactiveError(
                f"Leave policy '{lt.name}' is deactivated and cannot be used."
            )

        year = datetime.now(timezone.utc).year
        used = LeaveRepository.used_days_in_year(db, emp_id, leave_type_id, year)
        remaining = max(0, lt.yearly_quota - used)

        return LeaveBalanceResponse(
            leave_type_id=lt.leave_type_id,
            leave_type_name=lt.name,
            yearly_quota=lt.yearly_quota,
            used_days=used,
            remaining_days=remaining,
        )
