"""Business logic for the leave feature (US-16, S4-BE-1)."""
from datetime import date, timedelta
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import scope
from app.features.leave.repository import LeaveRepository
from app.features.leave.schemas import (
    LeaveRequestCreate,
    LeaveRequestOut,
)
from app.models.enums import LeaveStatus
from app.models.leave import LeaveType
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
