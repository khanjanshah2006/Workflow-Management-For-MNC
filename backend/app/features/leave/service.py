"""Business logic for the leave feature (S4)."""
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.features.leave.repository import LeaveRepository
from app.features.leave.schemas import (
    ConflictingTaskItem,
    LeaveConflictReportOut,
    MilestoneConflictItem,
    TeamCoverageItem,
)
from app.models.user_account import UserAccount

logger = logging.getLogger(__name__)


class LeaveService:
    """Service handling leave management operations, conflict detection, and review triage."""

    @staticmethod
    def get_leave_conflicts(
        db: Session,
        leave_id: int,
        current_user: UserAccount,
    ) -> LeaveConflictReportOut:
        """
        Evaluate leave conflicts for a given leave request (US-17).
        Identifies:
        1. Conflicting active tasks due within the leave window.
        2. Milestone overlaps on applicant projects.
        3. Teammate workload coverage and reassignment availability.
        Enforces 404 for missing request and 403 for out-of-scope reviewers.
        """
        # 1. Fetch leave request details
        details = LeaveRepository.get_leave_request_with_details(db, leave_id)
        if not details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Leave request with ID {leave_id} not found.",
            )

        leave_request, applicant, leave_type = details

        # 2. Scope check: TL must lead applicant's active team, PM must manage applicant's project, HR/Admin global
        is_scoped = LeaveRepository.check_reviewer_scope(
            db=db,
            current_user=current_user,
            applicant_emp_id=leave_request.emp_id,
        )
        if not is_scoped:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You are not authorized to view conflicts for this leave request.",
            )

        # 3. Read availability threshold (system parameter)
        threshold = LeaveRepository.get_availability_threshold(db)

        # 4. Conflicting tasks: status in ACTIVE (TODO, IN_PROGRESS, BLOCKED, REJECTED), due_date in window
        conflicting_task_rows = LeaveRepository.get_conflicting_tasks(
            db=db,
            emp_id=leave_request.emp_id,
            start_date=leave_request.start_date,
            end_date=leave_request.end_date,
        )

        conflicting_tasks = [
            ConflictingTaskItem(
                task_id=task.task_id,
                title=task.title,
                priority=task.priority.value if hasattr(task.priority, "value") else str(task.priority),
                status=task.status.value if hasattr(task.status, "value") else str(task.status),
                due_date=task.due_date,
                project_id=task.project_id,
                milestone_id=task.milestone_id,
                milestone_title=milestone_title,
            )
            for task, milestone_title in conflicting_task_rows
        ]

        conflicting_project_ids = {t.project_id for t in conflicting_tasks}

        # 5. Milestone conflicts: target_date in window on staffed projects or conflicting task projects
        milestone_conflict_rows = LeaveRepository.get_milestone_conflicts(
            db=db,
            emp_id=leave_request.emp_id,
            start_date=leave_request.start_date,
            end_date=leave_request.end_date,
            conflicting_project_ids=conflicting_project_ids,
        )

        milestone_conflicts = [
            MilestoneConflictItem(
                milestone_id=m.id,
                title=m.title,
                project_id=m.project_id,
                target_date=m.target_date,
                open_tasks_assigned_to_applicant=open_count,
            )
            for m, open_count in milestone_conflict_rows
        ]

        # 6. Team coverage: distinct active teammates sharing active team with applicant
        coverage_rows = LeaveRepository.get_team_coverage(
            db=db,
            applicant_emp_id=leave_request.emp_id,
            start_date=leave_request.start_date,
            end_date=leave_request.end_date,
            threshold=threshold,
        )

        team_coverage = [
            TeamCoverageItem(
                emp_id=item["emp_id"],
                full_name=item["full_name"],
                active_tasks_count=item["active_tasks_count"],
                has_leave_overlap=item["has_leave_overlap"],
                has_pending_leave_overlap=item["has_pending_leave_overlap"],
                is_available_for_reassignment=item["is_available_for_reassignment"],
            )
            for item in coverage_rows
        ]

        # 7. has_conflicts: true if conflicting tasks or milestone conflicts exist
        has_conflicts = bool(conflicting_tasks or milestone_conflicts)

        # 8. Status string representation
        status_str = (
            leave_request.status.value
            if hasattr(leave_request.status, "value")
            else str(leave_request.status)
        )

        return LeaveConflictReportOut(
            leave_id=leave_request.leave_id,
            employee_id=applicant.emp_id,
            employee_name=applicant.full_name,
            leave_type_name=leave_type.name,
            status=status_str,
            start_date=leave_request.start_date,
            end_date=leave_request.end_date,
            total_days=leave_request.total_days,
            has_conflicts=has_conflicts,
            conflicting_tasks=conflicting_tasks,
            milestone_conflicts=milestone_conflicts,
            team_coverage=team_coverage,
            availability_threshold=threshold,
        )
