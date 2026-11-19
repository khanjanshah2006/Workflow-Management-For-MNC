"""Business logic for the leave feature (US-16, US-40, S4-BE-1)."""
from datetime import date, timedelta
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import scope
from app.core.audit import write_audit_log
from app.core.notification_types import LEAVE_REQUESTED
from app.features.leave.repository import LeaveRepository
from app.features.leave.schemas import (
    LeaveRequestCreate,
    LeaveRequestOut,
)
from app.features.notifications.service import NotificationService
from app.models.employee import Employee
from app.models.enums import AuditAction, LeaveStatus
from app.models.leave import LeaveRequest, LeaveType
from app.models.user_account import UserAccount


class LeaveService:
    """Service providing core leave operations and validations."""

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
    ) -> List[LeaveRequestOut]:
        """List leave requests for the authenticated employee with isolation."""
        employee = scope.resolve_employee(db, current_user)
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No employee profile linked to this account",
            )

        rows = LeaveRepository.list_employee_requests(
            db=db,
            emp_id=employee.emp_id,
            status=status_filter,
            year=year,
            page=page,
            limit=limit,
        )

        return [
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
