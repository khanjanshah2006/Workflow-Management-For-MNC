"""
Repository layer for Executive Dashboard & Analytics (US-24, S7).

Performance invariant:
  All data access is executed via a strictly constant number of grouped queries
  (<= 8 queries per endpoint), independent of project, team, or department volume.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import coalesce

from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import CommonStatus, MilestoneStatus, ProjectStatus, TaskStatus
from app.models.milestone import ProjectMilestone
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.task import Task
from app.models.team import Team, TeamMember


class ExecutiveRepository:
    """Optimized data-access queries for executive-level oversight."""

    # ------------------------------------------------------------------
    # Executive Overview (GET /api/v1/executive/dashboard)
    # ------------------------------------------------------------------

    @staticmethod
    def get_project_counts_by_status(db: Session) -> Dict[str, int]:
        """Query 1: Return project counts grouped by lifecycle status."""
        rows = (
            db.query(Project.status, func.count(Project.project_id))
            .group_by(Project.status)
            .all()
        )
        counts: Dict[str, int] = {
            ProjectStatus.PLANNED.value: 0,
            ProjectStatus.ACTIVE.value: 0,
            ProjectStatus.ON_HOLD.value: 0,
            ProjectStatus.COMPLETED.value: 0,
            ProjectStatus.CANCELLED.value: 0,
        }
        for status_val, count in rows:
            key = status_val.value if hasattr(status_val, "value") else str(status_val)
            counts[key] = count
        return counts

    @staticmethod
    def get_delayed_project_ids(db: Session, today: date) -> Set[int]:
        """
        Query 2: Return IDs of delayed projects.

        Delayed definition: status in {ACTIVE, ON_HOLD} with >= 1 non-deleted,
        pending milestone where target_date < today.
        """
        delayed_rows = (
            db.query(Project.project_id)
            .join(ProjectMilestone, ProjectMilestone.project_id == Project.project_id)
            .filter(
                Project.status.in_([ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD]),
                ProjectMilestone.is_deleted == False,  # noqa: E712
                ProjectMilestone.status != MilestoneStatus.COMPLETED,
                ProjectMilestone.target_date < today,
            )
            .distinct()
            .all()
        )
        return {row[0] for row in delayed_rows}

    @staticmethod
    def get_global_milestone_velocity(db: Session) -> Tuple[int, int]:
        """Query 3: Return (completed_count, total_count) of all non-deleted milestones."""
        row = (
            db.query(
                func.count(ProjectMilestone.id),
                func.sum(
                    case((ProjectMilestone.status == MilestoneStatus.COMPLETED, 1), else_=0)
                ),
            )
            .filter(ProjectMilestone.is_deleted == False)  # noqa: E712
            .first()
        )
        total = row[0] or 0
        completed = row[1] or 0
        return int(completed), int(total)

    @staticmethod
    def get_task_kpis(db: Session, now: datetime) -> Dict[str, int]:
        """
        Query 4: Return organizational task KPIs:
          - open_tasks: status != DONE
          - overdue_tasks: status != DONE and due_date < now
          - completed_last_30_days: status == DONE and (completed_at or updated_at) >= now - 30d
        """
        thirty_days_ago = now - timedelta(days=30)
        row = (
            db.query(
                func.sum(case((Task.status != TaskStatus.DONE, 1), else_=0)),
                func.sum(
                    case(
                        (
                            and_(
                                Task.status != TaskStatus.DONE,
                                Task.due_date.isnot(None),
                                Task.due_date < now,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (
                            and_(
                                Task.status == TaskStatus.DONE,
                                coalesce(Task.completed_at, Task.updated_at) >= thirty_days_ago,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
            )
            .first()
        )
        return {
            "open_tasks": int(row[0] or 0),
            "overdue_tasks": int(row[1] or 0),
            "completed_last_30_days": int(row[2] or 0),
        }

    @staticmethod
    def get_total_active_employees(db: Session) -> int:
        """Query 5: Return count of all active employees organization-wide."""
        count = (
            db.query(func.count(Employee.emp_id))
            .filter(Employee.status == CommonStatus.ACTIVE)
            .scalar()
        )
        return int(count or 0)

    @staticmethod
    def get_department_summaries_data(
        db: Session, delayed_project_ids: Set[int]
    ) -> List[Dict[str, Any]]:
        """
        Query 6 & 7: Return department summaries using fixed set-based queries.

        Department attribution:
          Project belongs to its assigned PM's dept_id (project.pm_id -> pm.dept_id).
          Projects with no PM or where PM has no dept_id roll into the 'Unassigned' bucket (dept_id = None).
        """
        # A. All defined departments
        departments = db.query(Department.dept_id, Department.name).all()
        dept_name_by_id: Dict[Optional[int], str] = {d[0]: d[1] for d in departments}

        # B. Grouped project rollups by PM dept_id
        # Project -> ProjectManager (LEFT OUTER JOIN)
        project_rows = (
            db.query(
                Project.project_id,
                Project.status,
                ProjectManager.dept_id,
            )
            .outerjoin(ProjectManager, Project.pm_id == ProjectManager.pm_id)
            .all()
        )

        # C. Grouped milestone counts by project
        milestone_rows = (
            db.query(
                ProjectMilestone.project_id,
                func.count(ProjectMilestone.id),
                func.sum(
                    case((ProjectMilestone.status == MilestoneStatus.COMPLETED, 1), else_=0)
                ),
            )
            .filter(ProjectMilestone.is_deleted == False)  # noqa: E712
            .group_by(ProjectMilestone.project_id)
            .all()
        )
        ms_by_proj: Dict[int, Tuple[int, int]] = {
            m[0]: (int(m[2] or 0), int(m[1] or 0)) for m in milestone_rows
        }

        # D. Employee counts by employee.dept_id
        emp_rows = (
            db.query(Employee.dept_id, func.count(Employee.emp_id))
            .filter(Employee.status == CommonStatus.ACTIVE)
            .group_by(Employee.dept_id)
            .all()
        )
        emp_by_dept: Dict[Optional[int], int] = {e[0]: int(e[1] or 0) for e in emp_rows}

        # Aggregate metrics per department bucket
        dept_metrics: Dict[Optional[int], Dict[str, Any]] = {}

        # Initialize known departments
        for dept_id, name in dept_name_by_id.items():
            dept_metrics[dept_id] = {
                "dept_id": dept_id,
                "dept_name": name,
                "total_projects": 0,
                "active_projects": 0,
                "at_risk_projects": 0,
                "total_employees": emp_by_dept.get(dept_id, 0),
                "ms_completed": 0,
                "ms_total": 0,
            }

        # Initialize Unassigned bucket if needed
        unassigned_key: Optional[int] = None
        dept_metrics[unassigned_key] = {
            "dept_id": None,
            "dept_name": "Unassigned",
            "total_projects": 0,
            "active_projects": 0,
            "at_risk_projects": 0,
            "total_employees": emp_by_dept.get(None, 0),
            "ms_completed": 0,
            "ms_total": 0,
        }

        # Roll up projects
        for pid, pstatus, pdept in project_rows:
            bucket_key = pdept if pdept in dept_name_by_id else None
            bucket = dept_metrics[bucket_key]
            bucket["total_projects"] += 1
            pstatus_val = pstatus.value if hasattr(pstatus, "value") else str(pstatus)
            if pstatus_val == ProjectStatus.ACTIVE.value:
                bucket["active_projects"] += 1
            if pid in delayed_project_ids:
                bucket["at_risk_projects"] += 1

            ms_comp, ms_tot = ms_by_proj.get(pid, (0, 0))
            bucket["ms_completed"] += ms_comp
            bucket["ms_total"] += ms_tot

        # Format list, omitting Unassigned if completely empty (0 projects, 0 employees)
        summaries: List[Dict[str, Any]] = []
        for key in list(dept_metrics.keys()):
            item = dept_metrics[key]
            if key is None and item["total_projects"] == 0 and item["total_employees"] == 0:
                continue

            ms_tot = item.pop("ms_total")
            ms_comp = item.pop("ms_completed")
            velocity = round((ms_comp / ms_tot) * 100, 1) if ms_tot > 0 else 0.0
            item["milestone_velocity_pct"] = velocity
            summaries.append(item)

        # Sort: named departments by dept_id ASC, Unassigned at the end
        summaries.sort(key=lambda s: (s["dept_id"] is None, s["dept_id"] or 0))
        return summaries

    # ------------------------------------------------------------------
    # Department Drilldown (GET /api/v1/executive/dashboard/departments/{id})
    # ------------------------------------------------------------------

    @staticmethod
    def get_department_by_id(db: Session, dept_id: int) -> Optional[Department]:
        """Fetch department by primary key ID."""
        return db.query(Department).filter(Department.dept_id == dept_id).first()

    @staticmethod
    def get_department_projects_data(
        db: Session, dept_id: int, today: date
    ) -> List[Dict[str, Any]]:
        """
        Fetch all projects attributed to this department (PM's dept_id == dept_id)
        along with their task %, milestone completion, delayed flag, team count,
        and assigned headcount in fixed queries.
        """
        # 1. Projects attributed to this PM dept_id
        projects = (
            db.query(Project)
            .join(ProjectManager, Project.pm_id == ProjectManager.pm_id)
            .filter(ProjectManager.dept_id == dept_id)
            .order_by(Project.project_id)
            .all()
        )
        if not projects:
            return []

        proj_ids = [p.project_id for p in projects]

        # 2. Milestones aggregated by project_id
        ms_rows = (
            db.query(
                ProjectMilestone.project_id,
                func.count(ProjectMilestone.id),
                func.sum(
                    case((ProjectMilestone.status == MilestoneStatus.COMPLETED, 1), else_=0)
                ),
                func.sum(
                    case(
                        (
                            and_(
                                ProjectMilestone.status != MilestoneStatus.COMPLETED,
                                ProjectMilestone.target_date < today,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
            )
            .filter(
                ProjectMilestone.project_id.in_(proj_ids),
                ProjectMilestone.is_deleted == False,  # noqa: E712
            )
            .group_by(ProjectMilestone.project_id)
            .all()
        )
        ms_map: Dict[int, Tuple[int, int, bool]] = {
            m[0]: (int(m[1] or 0), int(m[2] or 0), (int(m[3] or 0) > 0)) for m in ms_rows
        }

        # 3. Tasks aggregated by project_id
        task_rows = (
            db.query(
                Task.project_id,
                func.count(Task.task_id),
                func.sum(case((Task.status == TaskStatus.DONE, 1), else_=0)),
            )
            .filter(Task.project_id.in_(proj_ids))
            .group_by(Task.project_id)
            .all()
        )
        task_map: Dict[int, Tuple[int, int]] = {
            t[0]: (int(t[1] or 0), int(t[2] or 0)) for t in task_rows
        }

        # 4. Teams count aggregated by project_id
        team_counts = (
            db.query(Team.project_id, func.count(Team.team_id))
            .filter(Team.project_id.in_(proj_ids))
            .group_by(Team.project_id)
            .all()
        )
        team_count_map: Dict[int, int] = {tc[0]: int(tc[1] or 0) for tc in team_counts}

        # 5. Assigned headcount by project_id (distinct active employees with active assignment)
        headcount_rows = (
            db.query(
                ProjectAssignment.project_id,
                func.count(func.distinct(ProjectAssignment.emp_id)),
            )
            .join(Employee, ProjectAssignment.emp_id == Employee.emp_id)
            .filter(
                ProjectAssignment.project_id.in_(proj_ids),
                ProjectAssignment.released_on.is_(None),
                Employee.status == CommonStatus.ACTIVE,
            )
            .group_by(ProjectAssignment.project_id)
            .all()
        )
        headcount_map: Dict[int, int] = {hc[0]: int(hc[1] or 0) for hc in headcount_rows}

        results: List[Dict[str, Any]] = []
        for p in projects:
            tot_ms, comp_ms, has_overdue_ms = ms_map.get(p.project_id, (0, 0, False))
            tot_tasks, comp_tasks = task_map.get(p.project_id, (0, 0))
            task_pct = int(round((comp_tasks / tot_tasks) * 100)) if tot_tasks > 0 else 0

            p_status_val = p.status.value if hasattr(p.status, "value") else str(p.status)
            is_delayed = (
                p_status_val in [ProjectStatus.ACTIVE.value, ProjectStatus.ON_HOLD.value]
                and has_overdue_ms
            )

            results.append(
                {
                    "project_id": p.project_id,
                    "project_code": p.project_code,
                    "name": p.name,
                    "status": p_status_val,
                    "task_completion_pct": task_pct,
                    "milestones_completed": comp_ms,
                    "milestones_total": tot_ms,
                    "is_delayed": is_delayed,
                    "team_count": team_count_map.get(p.project_id, 0),
                    "assigned_headcount": headcount_map.get(p.project_id, 0),
                }
            )

        return results

    @staticmethod
    def get_department_teams_data(db: Session, dept_id: int) -> List[Dict[str, Any]]:
        """
        Fetch teams belonging to a department through their project
        (team.project_id -> project -> PM's dept_id).
        """
        # Fetch teams joined with Project and PM
        team_rows = (
            db.query(
                Team.team_id,
                Team.name,
                Project.name,
            )
            .join(Project, Team.project_id == Project.project_id)
            .join(ProjectManager, Project.pm_id == ProjectManager.pm_id)
            .filter(ProjectManager.dept_id == dept_id)
            .order_by(Team.team_id)
            .all()
        )
        if not team_rows:
            return []

        team_ids = [t[0] for t in team_rows]

        # Member counts per team
        member_counts = (
            db.query(TeamMember.team_id, func.count(TeamMember.team_member_id))
            .filter(TeamMember.team_id.in_(team_ids))
            .group_by(TeamMember.team_id)
            .all()
        )
        member_map: Dict[int, int] = {mc[0]: int(mc[1] or 0) for mc in member_counts}

        # Open tasks per team
        open_task_rows = (
            db.query(Task.team_id, func.count(Task.task_id))
            .filter(
                Task.team_id.in_(team_ids),
                Task.status != TaskStatus.DONE,
            )
            .group_by(Task.team_id)
            .all()
        )
        task_map: Dict[int, int] = {ot[0]: int(ot[1] or 0) for ot in open_task_rows}

        return [
            {
                "team_id": tid,
                "name": tname,
                "project_name": pname,
                "member_count": member_map.get(tid, 0),
                "open_tasks": task_map.get(tid, 0),
            }
            for tid, tname, pname in team_rows
        ]

    @staticmethod
    def get_department_resource_allocation(
        db: Session, dept_id: int
    ) -> Dict[str, Any]:
        """
        Fetch headcount and allocation for all active employees within a department.
          - total_employees: active employees in department
          - allocated_employees: active employees with >= 1 active ProjectAssignment
          - unallocated_employees: total - allocated
          - headcount_by_designation: grouped count by employee designation
        """
        # 1. Total employees and designations
        emp_rows = (
            db.query(Employee.designation, func.count(Employee.emp_id))
            .filter(
                Employee.dept_id == dept_id,
                Employee.status == CommonStatus.ACTIVE,
            )
            .group_by(Employee.designation)
            .all()
        )
        headcount_by_designation: Dict[str, int] = {
            r[0] or "Unassigned": int(r[1] or 0) for r in emp_rows
        }
        total_employees = sum(headcount_by_designation.values())

        # 2. Distinct allocated employees in this department
        allocated_count = (
            db.query(func.count(func.distinct(Employee.emp_id)))
            .join(ProjectAssignment, ProjectAssignment.emp_id == Employee.emp_id)
            .filter(
                Employee.dept_id == dept_id,
                Employee.status == CommonStatus.ACTIVE,
                ProjectAssignment.released_on.is_(None),
            )
            .scalar()
        ) or 0
        allocated_employees = int(allocated_count)
        unallocated_employees = max(0, total_employees - allocated_employees)

        return {
            "total_employees": total_employees,
            "allocated_employees": allocated_employees,
            "unallocated_employees": unallocated_employees,
            "headcount_by_designation": headcount_by_designation,
        }
