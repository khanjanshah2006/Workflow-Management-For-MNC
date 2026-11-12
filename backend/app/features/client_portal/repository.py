"""
Repository layer for Client Portal (US-20, US-21).

All queries enforce strict client-scoped isolation.  No query in this
module joins or returns employee, task, or internal-comment data.
"""

from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.enums import CommonStatus, MilestoneStatus
from app.models.milestone import ProjectMilestone
from app.models.project import Project, ProjectAssignment
from app.models.team import Team, TeamMember


class ClientPortalRepository:
    """Data-access methods scoped to the authenticated client."""

    @staticmethod
    def get_client_by_account_id(db: Session, account_id) -> Optional[Client]:
        """Resolve the Client profile linked to a UserAccount."""
        return (
            db.query(Client)
            .filter(Client.account_id == account_id)
            .first()
        )

    @staticmethod
    def get_projects_by_client_id(db: Session, client_id: int) -> List[Project]:
        """Return every project belonging to *this* client."""
        return (
            db.query(Project)
            .filter(Project.client_id == client_id)
            .order_by(Project.project_id)
            .all()
        )

    @staticmethod
    def get_milestone_counts_for_project(
        db: Session, project_id: int
    ) -> Tuple[int, int]:
        """
        Return ``(total, completed)`` milestone counts for a project.

        Only non-deleted milestones are counted.
        """
        total = (
            db.query(func.count(ProjectMilestone.id))
            .filter(
                ProjectMilestone.project_id == project_id,
                ProjectMilestone.is_deleted == False,  # noqa: E712
            )
            .scalar()
        ) or 0

        completed = (
            db.query(func.count(ProjectMilestone.id))
            .filter(
                ProjectMilestone.project_id == project_id,
                ProjectMilestone.is_deleted == False,  # noqa: E712
                ProjectMilestone.status == MilestoneStatus.COMPLETED,
            )
            .scalar()
        ) or 0

        return total, completed

    @staticmethod
    def get_project_by_id_and_client_id(
        db: Session, project_id: int, client_id: int
    ) -> Optional[Project]:
        """Fetch a single project only if it belongs to the given client."""
        return (
            db.query(Project)
            .filter(
                Project.project_id == project_id,
                Project.client_id == client_id,
            )
            .first()
        )

    @staticmethod
    def get_milestones_by_project_id(
        db: Session, project_id: int
    ) -> List[ProjectMilestone]:
        """Active milestones for a project, ordered by target_date ascending."""
        return (
            db.query(ProjectMilestone)
            .filter(
                ProjectMilestone.project_id == project_id,
                ProjectMilestone.is_deleted == False,  # noqa: E712
            )
            .order_by(ProjectMilestone.target_date.asc())
            .all()
        )

    @staticmethod
    def get_project_by_id(db: Session, project_id: int) -> Optional[Project]:
        """Fetch a project by ID regardless of client ownership (for PM/ADMIN)."""
        return (
            db.query(Project)
            .filter(Project.project_id == project_id)
            .first()
        )

    @staticmethod
    def update_team_visibility(
        db: Session, project: Project, is_visible: bool
    ) -> Project:
        """Persist updated is_team_visible_to_client flag on a project."""
        project.is_team_visible_to_client = is_visible
        db.flush()
        db.refresh(project)
        return project

    @staticmethod
    def get_deliverables_by_project_id(
        db: Session, project_id: int
    ) -> List[Deliverable]:
        """Return deliverables submitted for a project ordered by submission time."""
        return (
            db.query(Deliverable)
            .filter(Deliverable.project_id == project_id)
            .order_by(Deliverable.submitted_at.asc(), Deliverable.deliverable_id.asc())
            .all()
        )

    @staticmethod
    def get_project_team_members(
        db: Session, project_id: int
    ) -> List[Tuple[str, str]]:
        """
        Return deduplicated list of ``(full_name, role_label)`` for employees
        assigned to the project via Team/TeamMember or ProjectAssignment.
        """
        members_by_emp_id: Dict[int, Tuple[str, str]] = {}

        team_rows = (
            db.query(Employee.emp_id, Employee.full_name, Employee.designation)
            .join(TeamMember, TeamMember.emp_id == Employee.emp_id)
            .join(Team, Team.team_id == TeamMember.team_id)
            .filter(
                Team.project_id == project_id,
                Employee.status == CommonStatus.ACTIVE,
            )
            .all()
        )
        for emp_id, full_name, designation in team_rows:
            members_by_emp_id[emp_id] = (full_name, designation)

        assign_rows = (
            db.query(
                Employee.emp_id,
                Employee.full_name,
                ProjectAssignment.role_in_project,
            )
            .join(ProjectAssignment, ProjectAssignment.emp_id == Employee.emp_id)
            .filter(
                ProjectAssignment.project_id == project_id,
                ProjectAssignment.released_on.is_(None),
                Employee.status == CommonStatus.ACTIVE,
            )
            .all()
        )
        for emp_id, full_name, role_in_project in assign_rows:
            members_by_emp_id[emp_id] = (full_name, role_in_project)

        return list(members_by_emp_id.values())

