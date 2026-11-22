"""Database queries and data-access layer for Leave Management (S4)."""
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import and_, case, func, or_, select
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
    """Repository handling database access for leave requests, balances, and conflict detection."""

    # ── S4-BE-1 / US-16 / US-40 Queries ──────────────────────────────────────

    @staticmethod
    def get_leave_type(db: Session, leave_type_id: int) -> Optional[LeaveType]:
        """Fetch a LeaveType by primary key."""
        return db.scalar(select(LeaveType).where(LeaveType.leave_type_id == leave_type_id))

    # ── US-18 / S4-BE-2 Leave policy queries ─────────────────────────────────

    @staticmethod
    def get_leave_type_by_name(
        db: Session, name: str, exclude_id: Optional[int] = None
    ) -> Optional[LeaveType]:
        """Case-insensitive name lookup, optionally ignoring one row (for renames)."""
        stmt = select(LeaveType).where(func.lower(LeaveType.name) == name.strip().lower())
        if exclude_id is not None:
            stmt = stmt.where(LeaveType.leave_type_id != exclude_id)
        return db.scalar(stmt)

    @staticmethod
    def list_leave_types(db: Session, include_inactive: bool = False) -> Sequence[LeaveType]:
        """Return leave types ordered by name; active only unless include_inactive."""
        stmt = select(LeaveType).order_by(LeaveType.name.asc())
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
        """Add a new active leave type and flush to get its ID. The caller commits."""
        leave_type = LeaveType(
            name=name,
            yearly_quota=yearly_quota,
            is_paid=is_paid,
            description=description,
            is_active=True,
        )
        db.add(leave_type)
        db.flush()
        return leave_type

    # ── S4-BE-1 Leave request queries ────────────────────────────────────────

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
        exclude_leave_id: Optional[int] = None,
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
        if exclude_leave_id is not None:
            stmt = stmt.where(LeaveRequest.leave_id != exclude_leave_id)
        result = db.scalar(stmt)
        return int(result or 0)

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
    def get_leave_request_for_update(db: Session, leave_id: int) -> Optional[LeaveRequest]:
        """Load and lock a leave row before performing a review decision."""
        stmt = select(LeaveRequest).where(LeaveRequest.leave_id == leave_id).with_for_update()
        return db.scalar(stmt)

    @staticmethod
    def count_review_queue(
        db: Session,
        team_lead_emp_id: Optional[int],
        status: Optional[LeaveStatus],
    ) -> int:
        stmt = select(func.count(LeaveRequest.leave_id))
        if team_lead_emp_id is not None:
            member_ids = (
                select(TeamMember.emp_id)
                .join(Team, Team.team_id == TeamMember.team_id)
                .where(Team.lead_emp_id == team_lead_emp_id, Team.status == TeamStatus.ACTIVE)
            )
            stmt = stmt.where(LeaveRequest.emp_id.in_(member_ids), LeaveRequest.emp_id != team_lead_emp_id)
        if status is not None:
            stmt = stmt.where(LeaveRequest.status == status)
        return int(db.scalar(stmt) or 0)

    @staticmethod
    def list_review_queue(
        db: Session,
        team_lead_emp_id: Optional[int],
        status: Optional[LeaveStatus],
        page: int,
        limit: int,
    ):
        stmt = (
            select(LeaveRequest, Employee.full_name, LeaveType.name)
            .join(Employee, Employee.emp_id == LeaveRequest.emp_id)
            .join(LeaveType, LeaveType.leave_type_id == LeaveRequest.leave_type_id)
        )
        if team_lead_emp_id is not None:
            member_ids = (
                select(TeamMember.emp_id)
                .join(Team, Team.team_id == TeamMember.team_id)
                .where(Team.lead_emp_id == team_lead_emp_id, Team.status == TeamStatus.ACTIVE)
            )
            stmt = stmt.where(LeaveRequest.emp_id.in_(member_ids), LeaveRequest.emp_id != team_lead_emp_id)
        if status is not None:
            stmt = stmt.where(LeaveRequest.status == status)
        stmt = stmt.order_by(LeaveRequest.start_date.asc(), LeaveRequest.leave_id.asc())
        stmt = stmt.offset((page - 1) * limit).limit(limit)
        return list(db.execute(stmt).all())

    @staticmethod
    def count_conflicting_tasks_for_requests(db: Session, leave_ids: list[int]) -> dict[int, int]:
        """Count unfinished tasks due during each leave in one grouped query."""
        if not leave_ids:
            return {}
        stmt = (
            select(LeaveRequest.leave_id, func.count(Task.task_id))
            .select_from(LeaveRequest)
            .outerjoin(
                Task,
                and_(
                    Task.assigned_to == LeaveRequest.emp_id,
                    Task.due_date >= LeaveRequest.start_date,
                    Task.due_date <= LeaveRequest.end_date,
                    Task.status != TaskStatus.DONE,
                ),
            )
            .where(LeaveRequest.leave_id.in_(leave_ids))
            .group_by(LeaveRequest.leave_id)
        )
        return {leave_id: int(count) for leave_id, count in db.execute(stmt).all()}

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

    # ── S4-BE-3 / US-17 Conflict Detection Queries ───────────────────────────

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
            managed_projects = staffing_projects_for(db, applicant_emp_id)
            for proj in managed_projects:
                if proj.pm_id == pm.pm_id:
                    return True

            applicant_team_projects = (
                select(Team.project_id)
                .join(TeamMember, Team.team_id == TeamMember.team_id)
                .where(
                    TeamMember.emp_id == applicant_emp_id,
                    Team.status == TeamStatus.ACTIVE,
                    Team.project_id.isnot(None),
                )
            )
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
            (or_(Task.priority == PriorityLevel.CRITICAL, Task.priority == "CRITICAL"), 1),
            (or_(Task.priority == PriorityLevel.HIGH, Task.priority == "HIGH"), 2),
            (or_(Task.priority == PriorityLevel.MEDIUM, Task.priority == "MEDIUM"), 3),
            (or_(Task.priority == PriorityLevel.LOW, Task.priority == "LOW"), 4),
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

        applicant_team_projects = (
            db.query(Team.project_id)
            .join(TeamMember, Team.team_id == TeamMember.team_id)
            .filter(
                TeamMember.emp_id == emp_id,
                Team.status == TeamStatus.ACTIVE,
                Team.project_id.isnot(None),
            )
            .all()
        )
        for row in applicant_team_projects:
            all_project_ids.add(row[0])

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
            .order_by(ProjectMilestone.target_date.asc())
            .all()
        )

        if not milestones:
            return []

        ms_ids = [m.id for m in milestones]
        active_task_statuses = [
            TaskStatus.TODO,
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.REJECTED,
        ]

        task_counts = (
            db.query(Task.milestone_id, func.count(Task.task_id))
            .filter(
                Task.milestone_id.in_(ms_ids),
                Task.assigned_to == emp_id,
                Task.status.in_(active_task_statuses),
            )
            .group_by(Task.milestone_id)
            .all()
        )
        count_map = {row[0]: row[1] for row in task_counts}

        return [(m, count_map.get(m.id, 0)) for m in milestones]

    @staticmethod
    def get_team_coverage(
        db: Session,
        applicant_emp_id: int,
        start_date: date,
        end_date: date,
        threshold: int,
    ) -> List[Dict[str, Any]]:
        """
        Distinct active teammates sharing at least one active team with applicant.
        Computes active_tasks_count (via one batch grouped query), leave overlap,
        and reassignment availability without N+1 queries.
        """
        applicant_teams = (
            select(TeamMember.team_id)
            .join(Team, Team.team_id == TeamMember.team_id)
            .where(
                TeamMember.emp_id == applicant_emp_id,
                Team.status == TeamStatus.ACTIVE,
            )
        )

        teammates = (
            db.query(Employee)
            .join(TeamMember, TeamMember.emp_id == Employee.emp_id)
            .join(Team, Team.team_id == TeamMember.team_id)
            .filter(
                TeamMember.team_id.in_(applicant_teams),
                Employee.emp_id != applicant_emp_id,
                Employee.status == CommonStatus.ACTIVE,
                Team.status == TeamStatus.ACTIVE,
            )
            .distinct()
            .order_by(Employee.full_name.asc())
            .all()
        )

        if not teammates:
            return []

        teammate_ids = [tm.emp_id for tm in teammates]

        workload_statuses = [
            TaskStatus.TODO,
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.REJECTED,
            TaskStatus.IN_REVIEW,
        ]

        task_counts = (
            db.query(Task.assigned_to, func.count(Task.task_id))
            .filter(
                Task.assigned_to.in_(teammate_ids),
                Task.status.in_(workload_statuses),
            )
            .group_by(Task.assigned_to)
            .all()
        )
        task_count_map = {row[0]: row[1] for row in task_counts}

        overlapping_leaves = (
            db.query(LeaveRequest.emp_id, LeaveRequest.status)
            .filter(
                LeaveRequest.emp_id.in_(teammate_ids),
                LeaveRequest.status.in_([LeaveStatus.APPROVED, LeaveStatus.PENDING]),
                LeaveRequest.start_date <= end_date,
                LeaveRequest.end_date >= start_date,
            )
            .all()
        )

        approved_overlap_set = {row[0] for row in overlapping_leaves if row[1] == LeaveStatus.APPROVED}
        pending_overlap_set = {row[0] for row in overlapping_leaves if row[1] == LeaveStatus.PENDING}

        coverage_items = []
        for tm in teammates:
            active_cnt = task_count_map.get(tm.emp_id, 0)
            has_approved = tm.emp_id in approved_overlap_set
            has_pending = tm.emp_id in pending_overlap_set
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
