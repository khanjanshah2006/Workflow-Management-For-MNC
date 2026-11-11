"""
Repository layer for Client Portal (US-20, US-21).

All queries enforce strict client-scoped isolation.  No query in this
module joins or returns employee, task, or internal-comment data.
"""

from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.enums import MilestoneStatus
from app.models.milestone import ProjectMilestone
from app.models.project import Project


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

