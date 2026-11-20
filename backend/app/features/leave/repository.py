"""Database queries for the leave feature (US-16, US-18, US-40, S4-BE-1, S4-BE-2)."""
from datetime import date
from typing import Optional, Sequence, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import LeaveStatus
from app.models.leave import LeaveRequest, LeaveType


class LeaveRepository:
    """Repository handling database access for leave requests, policies, and balances."""

    # ──────────────────────────────────────────────
    # S4-BE-2  Leave Policy / Leave Type operations
    # ──────────────────────────────────────────────

    @staticmethod
    def get_leave_type(db: Session, leave_type_id: int) -> Optional[LeaveType]:
        """Fetch a LeaveType by primary key (active or inactive)."""
        return db.scalar(select(LeaveType).where(LeaveType.leave_type_id == leave_type_id))

    @staticmethod
    def get_leave_type_by_name(db: Session, name: str) -> Optional[LeaveType]:
        """Case-insensitive lookup by name (used for duplicate-name checks)."""
        return db.scalar(
            select(LeaveType).where(func.lower(LeaveType.name) == name.strip().lower())
        )

    @staticmethod
    def list_leave_types(db: Session, include_inactive: bool = False) -> Sequence[LeaveType]:
        """Return all leave types ordered by leave_type_id.

        Args:
            include_inactive: If True return all rows including deactivated ones.
                              HR/SYSTEM_ADMIN can pass True; employees see only active.
        """
        stmt = select(LeaveType).order_by(LeaveType.leave_type_id.asc())
        if not include_inactive:
            stmt = stmt.where(LeaveType.is_active.is_(True))
        return list(db.scalars(stmt))

    @staticmethod
    def create_leave_type(
        db: Session,
        name: str,
        yearly_quota: int,
        is_paid: bool,
        description: Optional[str],
    ) -> LeaveType:
        """Insert a new leave type row and return the persisted record."""
        lt = LeaveType(
            name=name.strip(),
            yearly_quota=yearly_quota,
            is_paid=is_paid,
            description=description,
            is_active=True,
        )
        db.add(lt)
        db.commit()
        db.refresh(lt)
        return lt

    @staticmethod
    def update_leave_type(
        db: Session,
        leave_type: LeaveType,
        *,
        yearly_quota: Optional[int] = None,
        is_paid: Optional[bool] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> LeaveType:
        """Apply partial updates to a leave type row."""
        if yearly_quota is not None:
            leave_type.yearly_quota = yearly_quota
        if is_paid is not None:
            leave_type.is_paid = is_paid
        if description is not None:
            leave_type.description = description
        if is_active is not None:
            leave_type.is_active = is_active
        db.commit()
        db.refresh(leave_type)
        return leave_type

    # ──────────────────────────────────────────────
    # S4-BE-1  Leave Request operations
    # ──────────────────────────────────────────────

    @staticmethod
    def list_active_leave_types(db: Session) -> Sequence[LeaveType]:
        """Fetch all active leave types ordered by leave_type_id."""
        stmt = (
            select(LeaveType)
            .where(LeaveType.is_active.is_(True))
            .order_by(LeaveType.leave_type_id.asc())
        )
        return list(db.scalars(stmt))

    @staticmethod
    def has_overlapping_request(
        db: Session,
        emp_id: int,
        start_date: date,
        end_date: date,
        exclude_leave_id: Optional[int] = None,
    ) -> bool:
        """
        Check if employee has an overlapping PENDING or APPROVED leave request.
        Two intervals [s1, e1] and [s2, e2] overlap iff s1 <= e2 and e1 >= s2.
        """
        stmt = select(LeaveRequest.leave_id).where(
            LeaveRequest.emp_id == emp_id,
            LeaveRequest.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
        )
        if exclude_leave_id is not None:
            stmt = stmt.where(LeaveRequest.leave_id != exclude_leave_id)
        stmt = stmt.limit(1)
        return db.scalar(stmt) is not None

    @staticmethod
    def get_leave_days_by_status(
        db: Session,
        emp_id: int,
        leave_type_id: int,
        year: int,
        status: LeaveStatus,
    ) -> int:
        """
        Calculate total days of leaves for an employee, leave type, status, and calendar year.
        Uses calendar year of start_date.
        """
        stmt = select(func.coalesce(func.sum(LeaveRequest.total_days), 0)).where(
            LeaveRequest.emp_id == emp_id,
            LeaveRequest.leave_type_id == leave_type_id,
            LeaveRequest.status == status,
            LeaveRequest.start_date >= date(year, 1, 1),
            LeaveRequest.start_date <= date(year, 12, 31),
        )
        result = db.scalar(stmt)
        return int(result or 0)

    @staticmethod
    def used_days_in_year(
        db: Session,
        emp_id: int,
        leave_type_id: int,
        year: int,
    ) -> int:
        """Sum of total_days for APPROVED requests for this employee/type in given calendar year."""
        return LeaveRepository.get_leave_days_by_status(
            db=db,
            emp_id=emp_id,
            leave_type_id=leave_type_id,
            year=year,
            status=LeaveStatus.APPROVED,
        )

    @staticmethod
    def create_leave_request(
        db: Session,
        emp_id: int,
        leave_type_id: int,
        start_date: date,
        end_date: date,
        total_days: int,
        reason: str,
    ) -> LeaveRequest:
        """Create and flush a new PENDING leave request record."""
        leave_request = LeaveRequest(
            emp_id=emp_id,
            leave_type_id=leave_type_id,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            reason=reason,
            status=LeaveStatus.PENDING,
        )
        db.add(leave_request)
        db.flush()
        db.refresh(leave_request)
        return leave_request

    @staticmethod
    def get_leave_request_by_id(db: Session, leave_id: int) -> Optional[LeaveRequest]:
        """Fetch a LeaveRequest by primary key."""
        return db.scalar(select(LeaveRequest).where(LeaveRequest.leave_id == leave_id))

    @staticmethod
    def get_leave_request(db: Session, leave_id: int) -> Optional[LeaveRequest]:
        """Alias for get_leave_request_by_id for backwards-compatibility."""
        return LeaveRepository.get_leave_request_by_id(db, leave_id)

    @staticmethod
    def get_leave_request_with_type(
        db: Session, leave_id: int
    ) -> Optional[Tuple[LeaveRequest, str]]:
        """Fetch a LeaveRequest along with leave_type.name by primary key."""
        stmt = (
            select(LeaveRequest, LeaveType.name)
            .join(LeaveType, LeaveType.leave_type_id == LeaveRequest.leave_type_id)
            .where(LeaveRequest.leave_id == leave_id)
        )
        row = db.execute(stmt).first()
        if row is None:
            return None
        return row[0], row[1]

    @staticmethod
    def count_employee_requests(
        db: Session,
        emp_id: int,
        status: Optional[LeaveStatus] = None,
        year: Optional[int] = None,
    ) -> int:
        """Count total leave requests for an employee matching optional status and year filters."""
        stmt = select(func.count(LeaveRequest.leave_id)).where(LeaveRequest.emp_id == emp_id)
        if status is not None:
            stmt = stmt.where(LeaveRequest.status == status)
        if year is not None:
            stmt = stmt.where(
                LeaveRequest.start_date >= date(year, 1, 1),
                LeaveRequest.start_date <= date(year, 12, 31),
            )
        result = db.scalar(stmt)
        return int(result or 0)

    @staticmethod
    def list_employee_requests(
        db: Session,
        emp_id: int,
        status: Optional[LeaveStatus] = None,
        year: Optional[int] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Sequence[Tuple[LeaveRequest, str]]:
        """
        List leave requests for an employee joined with leave type name,
        ordered by applied_at DESC, with optional status and year filters.
        """
        stmt = (
            select(LeaveRequest, LeaveType.name)
            .join(LeaveType, LeaveType.leave_type_id == LeaveRequest.leave_type_id)
            .where(LeaveRequest.emp_id == emp_id)
        )
        if status is not None:
            stmt = stmt.where(LeaveRequest.status == status)
        if year is not None:
            stmt = stmt.where(
                LeaveRequest.start_date >= date(year, 1, 1),
                LeaveRequest.start_date <= date(year, 12, 31),
            )
        stmt = stmt.order_by(LeaveRequest.applied_at.desc(), LeaveRequest.leave_id.desc())
        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)
        return list(db.execute(stmt).all())
