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
    def get_task_kpis(db: Session, now: datetime) -> Dict[str, int]:
        """
        Query 3: Return organizational task KPIs:
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
    def get_department_summaries_and_totals(
        db: Session, delayed_project_ids: Set[int]
    ) -> Tuple[List[Dict[str, Any]], Tuple[int, int], int]:
        """
        Queries 4, 5, 6, 7:
        Return:
          - summaries: List of department summary dicts (including Unassigned bucket)
          - (global_completed_ms, global_total_ms): Organizational milestone counts
          - total_active_employees: Count of all active employees organization-wide
        All in 4 grouped queries, keeping total overview queries strictly <= 8.
        """
        # Query 4: All defined departments
        departments = db.query(Department.dept_id, Department.name).all()
        dept_name_by_id: Dict[Optional[int], str] = {d[0]: d[1] for d in departments}

        # Query 5: Grouped project rollups by PM dept_id
        project_rows = (
            db.query(
                Project.project_id,
                Project.status,
                ProjectManager.dept_id,
            )
            .outerjoin(ProjectManager, Project.pm_id == ProjectManager.pm_id)
            .all()
        )

        # Query 6: Grouped milestone counts by project
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

        # Derive global milestone counts from ms_by_proj
        global_completed_ms = sum(m[0] for m in ms_by_proj.values())
        global_total_ms = sum(m[1] for m in ms_by_proj.values())

        # Query 7: Employee counts by employee.dept_id
        emp_rows = (
            db.query(Employee.dept_id, func.count(Employee.emp_id))
            .filter(Employee.status == CommonStatus.ACTIVE)
            .group_by(Employee.dept_id)
            .all()
        )
        emp_by_dept: Dict[Optional[int], int] = {e[0]: int(e[1] or 0) for e in emp_rows}
        total_active_employees = sum(emp_by_dept.values())

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
        return summaries, (global_completed_ms, global_total_ms), total_active_employees

    # ------------------------------------------------------------------
    # Department Drilldown (GET /api/v1/executive/dashboard/departments/{id})
    # ------------------------------------------------------------------

    @staticmethod
    def get_department_by_id(db: Session, dept_id: int) -> Optional[Department]:
        """Query D1: Fetch department by primary key ID."""
        return db.query(Department).filter(Department.dept_id == dept_id).first()

    @staticmethod
    def get_department_projects_data(
        db: Session,
        dept_id: int,
        today: date,
        team_count_map: Optional[Dict[int, int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all projects attributed to this department along with their
        task %, milestone completion, delayed flag, team count, and assigned headcount.
        Uses team_count_map if provided to avoid a redundant query.
        """
        # D2: Projects attributed to this PM dept_id
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

        # D3: Milestones aggregated by project_id
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

        # D4: Tasks aggregated by project_id
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

        # D5: Teams count aggregated by project_id (if not precomputed)
        if team_count_map is None:
            team_counts = (
                db.query(Team.project_id, func.count(Team.team_id))
                .filter(Team.project_id.in_(proj_ids))
                .group_by(Team.project_id)
                .all()
            )
            resolved_team_counts: Dict[int, int] = {tc[0]: int(tc[1] or 0) for tc in team_counts}
        else:
            resolved_team_counts = team_count_map

        # D6: Assigned headcount by project_id
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
                    "team_count": resolved_team_counts.get(p.project_id, 0),
                    "assigned_headcount": headcount_map.get(p.project_id, 0),
                }
            )

        return results

    @staticmethod
    def get_department_teams_data(
        db: Session, dept_id: int
    ) -> Tuple[List[Dict[str, Any]], Dict[int, int]]:
        """
        Fetch teams belonging to a department through their project
        (team.project_id -> project -> PM's dept_id) in a single grouped query.
        Returns:
            (teams_list, team_counts_by_project_id)
        """
        team_rows = (
            db.query(
                Team.team_id,
                Team.name,
                Team.project_id,
                Project.name,
                func.count(func.distinct(TeamMember.team_member_id)),
                func.count(
                    func.distinct(
                        case((Task.status != TaskStatus.DONE, Task.task_id), else_=None)
                    )
                ),
            )
            .join(Project, Team.project_id == Project.project_id)
            .join(ProjectManager, Project.pm_id == ProjectManager.pm_id)
            .outerjoin(TeamMember, Team.team_id == TeamMember.team_id)
            .outerjoin(Task, Team.team_id == Task.team_id)
            .filter(ProjectManager.dept_id == dept_id)
            .group_by(Team.team_id, Team.name, Team.project_id, Project.name)
            .order_by(Team.team_id)
            .all()
        )

        team_counts_by_proj: Dict[int, int] = {}
        teams: List[Dict[str, Any]] = []
        for tid, tname, pid, pname, member_count, open_tasks in team_rows:
            team_counts_by_proj[pid] = team_counts_by_proj.get(pid, 0) + 1
            teams.append(
                {
                    "team_id": tid,
                    "name": tname,
                    "project_name": pname,
                    "member_count": int(member_count or 0),
                    "open_tasks": int(open_tasks or 0),
                }
            )

        return teams, team_counts_by_proj

    @staticmethod
    def get_department_resource_allocation(
        db: Session, dept_id: int
    ) -> Dict[str, Any]:
        """
        Fetch headcount and allocation for all active employees within a department in 1 query:
          - total_employees: active employees in department
          - allocated_employees: active employees with >= 1 active ProjectAssignment
          - unallocated_employees: total - allocated
          - headcount_by_designation: grouped count by employee designation
        """
        emp_rows = (
            db.query(
                Employee.emp_id,
                Employee.designation,
                func.count(ProjectAssignment.assignment_id),
            )
            .outerjoin(
                ProjectAssignment,
                and_(
                    ProjectAssignment.emp_id == Employee.emp_id,
                    ProjectAssignment.released_on.is_(None),
                ),
            )
            .filter(
                Employee.dept_id == dept_id,
                Employee.status == CommonStatus.ACTIVE,
            )
            .group_by(Employee.emp_id, Employee.designation)
            .all()
        )

        total_employees = len(emp_rows)
        allocated_employees = sum(1 for r in emp_rows if (r[2] or 0) > 0)
        unallocated_employees = max(0, total_employees - allocated_employees)

        headcount_by_designation: Dict[str, int] = {}
        for r in emp_rows:
            desig = r[1] or "Unassigned"
            headcount_by_designation[desig] = headcount_by_designation.get(desig, 0) + 1

        return {
            "total_employees": total_employees,
            "allocated_employees": allocated_employees,
            "unallocated_employees": unallocated_employees,
            "headcount_by_designation": headcount_by_designation,
        }
