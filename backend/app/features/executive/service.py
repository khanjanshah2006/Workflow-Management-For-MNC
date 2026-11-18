"""
Service layer for Executive Dashboard & Analytics (US-24, S7).

Exposes reusable analytical and metric calculation functions for S7-BE-2.
Enforces strict PII redaction and read-only semantics.
"""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.features.executive.repository import ExecutiveRepository
from app.features.executive.schemas import (
    DepartmentProjectItem,
    DepartmentResourceAllocation,
    DepartmentSummaryItem,
    DepartmentTeamItem,
    ExecutiveDepartmentDrilldownResponse,
    ExecutiveOverviewResponse,
    ProjectsByStatus,
    TaskKpis,
)


def calculate_milestone_velocity(completed: int, total: int) -> float:
    """
    Reusable metric calculation helper (US-24, S7-BE-2).

    Milestone velocity: completed / total non-deleted milestones * 100,
    1 decimal place, 0.0 when there are none.
    """
    if total <= 0:
        return 0.0
    return round((completed / total) * 100.0, 1)


class ExecutiveService:
    """Orchestrates executive oversight metrics and department drilldowns."""

    @staticmethod
    def get_dashboard_overview(
        db: Session, now: Optional[datetime] = None
    ) -> ExecutiveOverviewResponse:
        """
        Produce high-level organizational metrics roll-up (GET /api/v1/executive/dashboard).

        Guaranteed fixed query count (<= 8 queries) regardless of data size.
        """
        current_time = now or datetime.now(timezone.utc)
        current_date = current_time.date()

        # 1. Project status breakdown
        status_counts = ExecutiveRepository.get_project_counts_by_status(db)
        total_projects = sum(status_counts.values())
        active_projects = status_counts.get("ACTIVE", 0)
        completed_projects = status_counts.get("COMPLETED", 0)

        # 2. Delayed projects (status in ACTIVE/ON_HOLD with overdue pending milestone)
        delayed_ids = ExecutiveRepository.get_delayed_project_ids(db, today=current_date)
        delayed_projects = len(delayed_ids)

        # 3. Task KPIs
        task_kpis_dict = ExecutiveRepository.get_task_kpis(db, now=current_time)
        task_kpis = TaskKpis(**task_kpis_dict)

        # 4. Department summaries, global milestone velocity totals, and employee count (Queries 4-7)
        (
            dept_summaries_data,
            (comp_ms, tot_ms),
            total_employees,
        ) = ExecutiveRepository.get_department_summaries_and_totals(
            db, delayed_project_ids=delayed_ids
        )
        overall_velocity = calculate_milestone_velocity(comp_ms, tot_ms)
        dept_summaries = [DepartmentSummaryItem(**d) for d in dept_summaries_data]

        return ExecutiveOverviewResponse(
            generated_at=current_time,
            total_projects=total_projects,
            projects_by_status=ProjectsByStatus(**status_counts),
            active_projects=active_projects,
            delayed_projects=delayed_projects,
            completed_projects=completed_projects,
            overall_milestone_velocity_pct=overall_velocity,
            task_kpis=task_kpis,
            total_employees=total_employees,
            department_summaries=dept_summaries,
        )

    @staticmethod
    def get_department_drilldown(
        db: Session, dept_id: int, now: Optional[datetime] = None
    ) -> ExecutiveDepartmentDrilldownResponse:
        """
        Produce granular project, team, and staffing breakdown for a specific department
        (GET /api/v1/executive/dashboard/departments/{id}).

        Raises 404 if the department does not exist.
        """
        current_time = now or datetime.now(timezone.utc)
        current_date = current_time.date()

        # 1. Verify department existence
        dept = ExecutiveRepository.get_department_by_id(db, dept_id=dept_id)
        if dept is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {dept_id} not found.",
            )

        # 2. Teams under this department's projects (and team counts per project)
        teams_data, team_counts_by_proj = ExecutiveRepository.get_department_teams_data(
            db, dept_id=dept_id
        )
        teams = [DepartmentTeamItem(**t) for t in teams_data]

        # 3. Projects attributed to this department
        projects_data = ExecutiveRepository.get_department_projects_data(
            db, dept_id=dept_id, today=current_date, team_count_map=team_counts_by_proj
        )
        projects = [DepartmentProjectItem(**p) for p in projects_data]

        # 4. Resource allocation (allocated, unallocated, by designation)
        allocation_data = ExecutiveRepository.get_department_resource_allocation(
            db, dept_id=dept_id
        )
        resource_allocation = DepartmentResourceAllocation(**allocation_data)

        return ExecutiveDepartmentDrilldownResponse(
            dept_id=dept.dept_id,
            dept_name=dept.name,
            projects=projects,
            teams=teams,
            resource_allocation=resource_allocation,
        )
