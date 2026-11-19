"""Database queries and data-access layer for Leave Management (S4)."""
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.scope import (
    employee_team_ids,
    get_int_param,
    is_team_lead_of,
    led_team_ids,
    resolve_employee,
    resolve_pm,
    staffing_projects_for,
)
from app.models.employee import Employee
from app.models.enums import (
    CommonStatus,
    LeaveStatus,
    MilestoneStatus,
    PriorityLevel,
    TaskStatus,
    TeamStatus,
)
from app.models.leave import LeaveRequest, LeaveType
from app.models.milestone import ProjectMilestone
from app.models.project import Project
from app.models.task import Task
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


class LeaveRepository:
    """Data-access repository for leave requests, conflict detection, and reviewer scoping."""

    @staticmethod
    def get_leave_request_with_details(
        db: Session, leave_id: int
    ) -> Optional[Tuple[LeaveRequest, Employee, LeaveType]]:
        """Fetch leave request joined with applicant Employee and LeaveType."""
        return (
            db.query(LeaveRequest, Employee, LeaveType)
            .join(Employee, Employee.emp_id == LeaveRequest.emp_id)
            .join(LeaveType, LeaveType.leave_type_id == LeaveRequest.leave_type_id)
            .filter(LeaveRequest.leave_id == leave_id)
            .first()
        )

    @staticmethod
    def check_reviewer_scope(
        db: Session, current_user: UserAccount, applicant_emp_id: int
    ) -> bool:
        """
        Verify if current_user is authorized to review or inspect conflicts for this applicant:
        - HR, ADMIN, SYSTEM_ADMIN: Global scope (True)
        - TEAM_LEAD: Leads an active team the applicant belongs to
        - PM: Manages an active/planned project the applicant is actively assigned to
        - Otherwise: False
        """
        user_type_val = (
            current_user.user_type.value
            if hasattr(current_user.user_type, "value")
            else str(current_user.user_type)
        ).upper()

        if user_type_val in ("HR", "ADMIN", "SYSTEM_ADMIN"):
            return True

        # Check elevated access grants if baseline is another role
        from datetime import datetime, timezone
        from app.models.elevated_access_grant import ElevatedAccessGrant

        now = datetime.now(timezone.utc)
        grant = (
            db.query(ElevatedAccessGrant)
            .filter(
                ElevatedAccessGrant.user_id == current_user.account_id,
                ElevatedAccessGrant.revoked_at.is_(None),
                ElevatedAccessGrant.expires_at > now,
            )
            .first()
        )
        if grant:
            elevated = grant.granted_role.strip().upper()
            if elevated in ("HR", "ADMIN", "SYSTEM_ADMIN"):
                return True
            if elevated == "TEAM_LEAD":
                user_type_val = "TEAM_LEAD"
            elif elevated in ("PM", "PROJECT_MANAGER"):
                user_type_val = "PM"

        # Check Team Lead scope: leads an active team the applicant belongs to
        emp = resolve_employee(db, current_user)
        if emp and is_team_lead_of(db, lead_emp_id=emp.emp_id, target_emp_id=applicant_emp_id):
            return True

        # Check Project Manager scope: manages a project the applicant is assigned to
        pm = resolve_pm(db, current_user)
        if pm:
            staffed_projects = staffing_projects_for(db, applicant_emp_id)
            if any(p.pm_id == pm.pm_id for p in staffed_projects):
                return True

            applicant_team_projects = db.scalars(
                select(Team.project_id)
                .join(TeamMember, TeamMember.team_id == Team.team_id)
                .where(
                    TeamMember.emp_id == applicant_emp_id,
                    Team.status == TeamStatus.ACTIVE,
                    Team.project_id.is_not(None),
                )
            ).all()
            if applicant_team_projects:
                managed_project = db.scalar(
                    select(Project.project_id).where(
                        Project.project_id.in_(applicant_team_projects),
                        Project.pm_id == pm.pm_id,
                    ).limit(1)
                )
                if managed_project:
                    return True

        return False

    @staticmethod
    def get_conflicting_tasks(
        db: Session, emp_id: int, start_date: date, end_date: date
    ) -> List[Tuple[Task, Optional[str]]]:
        """
        Tasks assigned to applicant with status ∈ {TODO, IN_PROGRESS, BLOCKED, REJECTED}
        and due_date ∈ [start_date, end_date] (inclusive). Excludes DONE and IN_REVIEW.
        Ordered by due_date ascending, then priority (CRITICAL > HIGH > MEDIUM > LOW).
        Returns list of (Task, milestone_title).
        """
        active_statuses = [
            TaskStatus.TODO,
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.REJECTED,
        ]

        priority_weight = case(
            {
                PriorityLevel.CRITICAL: 1,
                "CRITICAL": 1,
                PriorityLevel.HIGH: 2,
                "HIGH": 2,
                PriorityLevel.MEDIUM: 3,
                "MEDIUM": 3,
                PriorityLevel.LOW: 4,
                "LOW": 4,
            },
            else_=5,
        )

        query = (
            db.query(Task, ProjectMilestone.title.label("milestone_title"))
            .outerjoin(ProjectMilestone, ProjectMilestone.id == Task.milestone_id)
            .filter(
                Task.assigned_to == emp_id,
                Task.status.in_(active_statuses),
                Task.due_date.isnot(None),
                Task.due_date >= start_date,
                Task.due_date <= end_date,
            )
            .order_by(
                Task.due_date.asc(),
                priority_weight.asc(),
                Task.task_id.asc(),
            )
        )
        return query.all()

    @staticmethod
    def get_milestone_conflicts(
        db: Session,
        emp_id: int,
        start_date: date,
        end_date: date,
        conflicting_project_ids: Set[int],
    ) -> List[Tuple[ProjectMilestone, int]]:
        """
        Pending project milestones occurring in [start_date, end_date] on projects
        from staffing_projects_for(applicant) or projects of conflicting tasks.
        Each carries count of open tasks assigned to applicant.
        """
        staffed_projects = staffing_projects_for(db, emp_id)
        all_project_ids = set(conflicting_project_ids)
        for proj in staffed_projects:
            all_project_ids.add(proj.project_id)

        if not all_project_ids:
            return []

        milestones = (
            db.query(ProjectMilestone)
            .filter(
                ProjectMilestone.project_id.in_(all_project_ids),
                ProjectMilestone.is_deleted.is_(False),
                ProjectMilestone.status == MilestoneStatus.PENDING,
                ProjectMilestone.target_date >= start_date,
                ProjectMilestone.target_date <= end_date,
            )
            .order_by(ProjectMilestone.target_date.asc(), ProjectMilestone.id.asc())
            .all()
        )

        if not milestones:
            return []

        milestone_ids = [m.id for m in milestones]
        active_statuses = [
            TaskStatus.TODO,
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.REJECTED,
        ]

        # Single grouped query to count open tasks on these milestones assigned to applicant
        open_task_counts = dict(
            db.query(Task.milestone_id, func.count(Task.task_id))
            .filter(
                Task.assigned_to == emp_id,
                Task.milestone_id.in_(milestone_ids),
                Task.status.in_(active_statuses),
            )
            .group_by(Task.milestone_id)
            .all()
        )

        return [(m, open_task_counts.get(m.id, 0)) for m in milestones]

    @staticmethod
    def get_team_coverage(
        db: Session,
        applicant_emp_id: int,
        start_date: date,
        end_date: date,
        threshold: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Distinct active teammates sharing an active team with the applicant.
        Returns metrics for each: active_tasks_count, has_leave_overlap,
        has_pending_leave_overlap, and is_available_for_reassignment.
        """
        app_team_ids = employee_team_ids(db, applicant_emp_id)
        all_active_teams = app_team_ids.union(led_team_ids(db, applicant_emp_id))

        if not all_active_teams:
            return []

        # Teammate employee IDs sharing an active team with applicant
        teammate_emp_ids = set(
            db.scalars(
                select(TeamMember.emp_id)
                .join(Team, Team.team_id == TeamMember.team_id)
                .join(Employee, Employee.emp_id == TeamMember.emp_id)
                .where(
                    TeamMember.team_id.in_(all_active_teams),
                    Team.status == TeamStatus.ACTIVE,
                    TeamMember.emp_id != applicant_emp_id,
                    Employee.status == CommonStatus.ACTIVE,
                )
                .distinct()
            ).all()
        )

        # Include any active team leads of these teams (excluding applicant)
        leads = db.scalars(
            select(Team.lead_emp_id)
            .join(Employee, Employee.emp_id == Team.lead_emp_id)
            .where(
                Team.team_id.in_(all_active_teams),
                Team.status == TeamStatus.ACTIVE,
                Team.lead_emp_id.is_not(None),
                Team.lead_emp_id != applicant_emp_id,
                Employee.status == CommonStatus.ACTIVE,
            )
            .distinct()
        ).all()
        teammate_emp_ids.update(leads)

        if not teammate_emp_ids:
            return []

        # Fetch teammate employee records ordered by emp_id
        teammates = (
            db.query(Employee)
            .filter(Employee.emp_id.in_(teammate_emp_ids))
            .order_by(Employee.emp_id.asc())
            .all()
        )

        # 1. Grouped query for active tasks count: status ∈ ACTIVE ∪ {IN_REVIEW}
        task_statuses = [
            TaskStatus.TODO,
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.REJECTED,
            TaskStatus.IN_REVIEW,
        ]
        workload_query = (
            db.query(Task.assigned_to, func.count(Task.task_id))
            .filter(
                Task.assigned_to.in_(teammate_emp_ids),
                Task.status.in_(task_statuses),
            )
            .group_by(Task.assigned_to)
            .all()
        )
        workloads = {emp_id: count for emp_id, count in workload_query}

        # 2. Approved leave overlaps in window W
        approved_overlaps = set(
            db.scalars(
                select(LeaveRequest.emp_id)
                .where(
                    LeaveRequest.emp_id.in_(teammate_emp_ids),
                    LeaveRequest.status == LeaveStatus.APPROVED,
                    LeaveRequest.start_date <= end_date,
                    LeaveRequest.end_date >= start_date,
                )
                .distinct()
            ).all()
        )

        # 3. Pending leave overlaps in window W
        pending_overlaps = set(
            db.scalars(
                select(LeaveRequest.emp_id)
                .where(
                    LeaveRequest.emp_id.in_(teammate_emp_ids),
                    LeaveRequest.status == LeaveStatus.PENDING,
                    LeaveRequest.start_date <= end_date,
                    LeaveRequest.end_date >= start_date,
                )
                .distinct()
            ).all()
        )

        coverage_items = []
        for tm in teammates:
            active_cnt = workloads.get(tm.emp_id, 0)
            has_approved = tm.emp_id in approved_overlaps
            has_pending = tm.emp_id in pending_overlaps
            is_available = (not has_approved) and (active_cnt < threshold)

            coverage_items.append(
                {
                    "emp_id": tm.emp_id,
                    "full_name": tm.full_name,
                    "active_tasks_count": active_cnt,
                    "has_leave_overlap": has_approved,
                    "has_pending_leave_overlap": has_pending,
                    "is_available_for_reassignment": is_available,
                }
            )

        return coverage_items

    @staticmethod
    def get_availability_threshold(db: Session) -> int:
        """Fetch LEAVE_REASSIGN_MAX_ACTIVE_TASKS system parameter with fallback to 5."""
        return get_int_param(db, "LEAVE_REASSIGN_MAX_ACTIVE_TASKS", 5)
