"""Leave review queue and approve / reject decisions (S4-BE-4)."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import scope
from app.core.audit import write_audit_log
from app.core.notification_types import LEAVE_APPROVED, LEAVE_REJECTED, STAFF_LEAVE_APPROVED
from app.features.leave.repository import LeaveRepository
from app.features.leave.schemas import (
    LeaveRequestOut,
    PendingLeaveQueueItem,
    PendingLeaveQueueResponse,
)
from app.features.notifications.service import NotificationService
from app.models.employee import Employee
from app.models.enums import AuditAction, LeaveStatus, UserType
from app.models.leave import LeaveRequest, LeaveType
from app.models.user_account import UserAccount


class LeaveReviewService:
    @staticmethod
    def _role(user: UserAccount) -> str:
        value = user.user_type.value if hasattr(user.user_type, "value") else str(user.user_type)
        return value.strip().upper()

    @classmethod
    def _team_lead_emp_id(cls, db: Session, current_user: UserAccount) -> Optional[int]:
        employee = scope.resolve_employee(db, current_user)
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No employee profile linked to this team lead account.",
            )
        return employee.emp_id

    @classmethod
    def list_pending_requests(
        cls,
        db: Session,
        current_user: UserAccount,
        status_filter: Optional[LeaveStatus],
        page: int,
        limit: int,
    ) -> PendingLeaveQueueResponse:
        role = cls._role(current_user)
        if role == UserType.TEAM_LEAD.value:
            team_lead_emp_id = cls._team_lead_emp_id(db, current_user)
        elif role in (UserType.HR.value, UserType.ADMIN.value):
            team_lead_emp_id = None
        else:
            raise HTTPException(status_code=403, detail="Access forbidden")

        total = LeaveRepository.count_review_queue(db, team_lead_emp_id, status_filter)
        rows = LeaveRepository.list_review_queue(db, team_lead_emp_id, status_filter, page, limit)
        conflicts = LeaveRepository.count_conflicting_tasks_for_requests(
            db, [request.leave_id for request, _, _ in rows]
        )
        items = [
            PendingLeaveQueueItem(
                leave_id=request.leave_id,
                employee_id=request.emp_id,
                employee_name=employee_name,
                leave_type_name=leave_type_name,
                start_date=request.start_date,
                end_date=request.end_date,
                total_days=request.total_days,
                reason=request.reason,
                status=request.status,
                applied_at=request.applied_at,
                conflicting_task_count=conflicts.get(request.leave_id, 0),
            )
            for request, employee_name, leave_type_name in rows
        ]
        return PendingLeaveQueueResponse(items=items, total=total, page=page, limit=limit)

    @staticmethod
    def _load_and_authorize(
        db: Session,
        leave_id: int,
        current_user: UserAccount,
    ) -> tuple[LeaveRequest, Employee]:
        request = LeaveRepository.get_leave_request_for_update(db, leave_id)
        if request is None:
            raise HTTPException(status_code=404, detail="Leave request not found")

        applicant = db.get(Employee, request.emp_id)
        if applicant is None:
            # A request whose employee was removed should not be decidable by an unrelated account.
            raise HTTPException(status_code=403, detail="Leave request is outside your review scope")
        if applicant.account_id == current_user.account_id:
            raise HTTPException(status_code=403, detail="You cannot review your own leave request")

        role = LeaveReviewService._role(current_user)
        if role == UserType.TEAM_LEAD.value:
            lead = scope.resolve_employee(db, current_user)
            if lead is None or not scope.is_team_lead_of(db, lead.emp_id, applicant.emp_id):
                raise HTTPException(status_code=403, detail="Leave request is outside your review scope")
        elif role not in (UserType.HR.value, UserType.ADMIN.value):
            raise HTTPException(status_code=403, detail="Access forbidden")

        if request.status != LeaveStatus.PENDING:
            raise HTTPException(status_code=400, detail="Request already processed")
        return request, applicant

    @staticmethod
    def _leave_request_out(db: Session, request: LeaveRequest) -> LeaveRequestOut:
        leave_type = db.get(LeaveType, request.leave_type_id)
        return LeaveRequestOut(
            leave_id=request.leave_id,
            emp_id=request.emp_id,
            leave_type_id=request.leave_type_id,
            leave_type_name=leave_type.name if leave_type else None,
            start_date=request.start_date,
            end_date=request.end_date,
            total_days=request.total_days,
            reason=request.reason,
            status=request.status,
            applied_at=request.applied_at,
            reviewed_at=request.reviewed_at,
            reviewed_by_account_id=request.reviewed_by_account_id,
            review_remarks=request.review_remarks,
        )

    @staticmethod
    def _notify(
        db: Session,
        account_id,
        event_type: str,
        title: str,
        message: str,
        leave_id: int,
    ) -> None:
        if account_id is None:
            return
        NotificationService.create_notification(
            db=db,
            user_id=account_id,
            type=event_type,
            title=title,
            message=message,
            link=f"/leave/requests/{leave_id}",
        )

    @staticmethod
    def _record_audit(
        db: Session,
        current_user: UserAccount,
        request: LeaveRequest,
        action: AuditAction,
        new_value: dict,
    ) -> None:
        if not write_audit_log(
            db=db,
            action=action,
            entity_name="LEAVE_REQUEST",
            entity_ref_id=request.leave_id,
            account_id=current_user.account_id,
            old_value={"status": LeaveStatus.PENDING.value},
            new_value=new_value,
            commit=False,
        ):
            raise HTTPException(status_code=500, detail="Unable to record leave review audit event")

    @classmethod
    def approve(
        cls,
        db: Session,
        leave_id: int,
        current_user: UserAccount,
        review_remarks: Optional[str] = None,
    ) -> LeaveRequestOut:
        request, applicant = cls._load_and_authorize(db, leave_id, current_user)

        if LeaveRepository.has_overlapping_request(
            db, applicant.emp_id, request.start_date, request.end_date, exclude_leave_id=request.leave_id
        ):
            raise HTTPException(status_code=409, detail="Overlapping leave request exists")

        leave_type = db.get(LeaveType, request.leave_type_id)
        if leave_type is None:
            raise HTTPException(status_code=400, detail="Leave type is no longer available")
        year = request.start_date.year
        used_days = LeaveRepository.get_leave_days_by_status(
            db, applicant.emp_id, request.leave_type_id, year, LeaveStatus.APPROVED
        )
        other_pending_days = LeaveRepository.get_leave_days_by_status(
            db,
            applicant.emp_id,
            request.leave_type_id,
            year,
            LeaveStatus.PENDING,
            exclude_leave_id=request.leave_id,
        )
        available_days = leave_type.yearly_quota - used_days - other_pending_days
        if used_days + other_pending_days + request.total_days > leave_type.yearly_quota:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient leave balance (Available: {available_days} days)",
            )

        request.status = LeaveStatus.APPROVED
        request.reviewed_by_account_id = current_user.account_id
        request.reviewed_at = datetime.now(timezone.utc)
        request.review_remarks = review_remarks

        cls._notify(
            db,
            applicant.account_id,
            LEAVE_APPROVED,
            "Leave request approved",
            f"Your leave request #{request.leave_id} was approved.",
            request.leave_id,
        )
        for account_id in scope.staffing_pm_account_ids_for(db, applicant.emp_id):
            if account_id != applicant.account_id:
                cls._notify(
                    db,
                    account_id,
                    STAFF_LEAVE_APPROVED,
                    "Team member leave approved",
                    f"Leave request #{request.leave_id} was approved for {applicant.full_name}.",
                    request.leave_id,
                )

        if cls._role(current_user) in (UserType.HR.value, UserType.ADMIN.value):
            for account_id in scope.team_lead_account_ids_for(db, applicant.emp_id):
                if account_id not in (applicant.account_id, current_user.account_id):
                    cls._notify(
                        db,
                        account_id,
                        LEAVE_APPROVED,
                        "Team member leave approved",
                        f"Leave request #{request.leave_id} was approved for {applicant.full_name}.",
                        request.leave_id,
                    )

        cls._record_audit(
            db,
            current_user,
            request,
            AuditAction.APPROVE,
            {"status": request.status.value, "review_remarks": review_remarks},
        )
        db.commit()
        db.refresh(request)
        return cls._leave_request_out(db, request)

    @classmethod
    def reject(
        cls,
        db: Session,
        leave_id: int,
        current_user: UserAccount,
        review_remarks: str,
    ) -> LeaveRequestOut:
        request, applicant = cls._load_and_authorize(db, leave_id, current_user)
        request.status = LeaveStatus.REJECTED
        request.reviewed_by_account_id = current_user.account_id
        request.reviewed_at = datetime.now(timezone.utc)
        request.review_remarks = review_remarks

        cls._notify(
            db,
            applicant.account_id,
            LEAVE_REJECTED,
            "Leave request rejected",
            f"Your leave request #{request.leave_id} was rejected. Reviewer remarks: {review_remarks}",
            request.leave_id,
        )
        cls._record_audit(
            db,
            current_user,
            request,
            AuditAction.UPDATE,
            {"status": request.status.value, "review_remarks": review_remarks},
        )
        db.commit()
        db.refresh(request)
        return cls._leave_request_out(db, request)
