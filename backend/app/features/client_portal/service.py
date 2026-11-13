"""
Service layer for Client Portal (US-20, US-21).

Business logic lives here; the router stays thin.
"""

from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user_account import UserAccount
from app.features.client_portal.repository import ClientPortalRepository
from app.features.client_portal.schemas import (
    ClientMilestoneResponse,
    ClientProjectSummaryResponse,
    MilestoneSummaryCount,
)


# ------------------------------------------------------------------
# Custom exceptions
# ------------------------------------------------------------------

class ClientProfileNotFoundError(Exception):
    """Raised when the authenticated user has no linked Client record."""


class ProjectNotFoundForClientError(Exception):
    """Raised when the requested project does not belong to this client."""


# ------------------------------------------------------------------
# Service
# ------------------------------------------------------------------

class ClientPortalService:
    """Orchestrates client-portal queries with strict data isolation."""

    @staticmethod
    def _resolve_client(db: Session, current_user: UserAccount):
        """
        Map the authenticated UserAccount to a Client profile.

        Raises HTTPException 403 if no matching client record exists.
        """
        client = ClientPortalRepository.get_client_by_account_id(
            db, current_user.account_id
        )
        if client is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not registered as an active client.",
            )
        return client

    @staticmethod
    def get_client_projects(
        db: Session, current_user: UserAccount
    ) -> List[ClientProjectSummaryResponse]:
        """
        List every project contracted by the authenticated client, enriched
        with milestone completion metrics.
        """
        client = ClientPortalService._resolve_client(db, current_user)

        projects = ClientPortalRepository.get_projects_by_client_id(
            db, client.client_id
        )

        results: List[ClientProjectSummaryResponse] = []
        for proj in projects:
            total, completed = ClientPortalRepository.get_milestone_counts_for_project(
                db, proj.project_id
            )
            pending = total - completed
            completion_pct = round((completed / total) * 100, 1) if total > 0 else 0.0

            # Map model → response; intentionally omit pm_id, internal fields
            results.append(
                ClientProjectSummaryResponse(
                    project_id=proj.project_id,
                    project_code=proj.project_code,
                    name=proj.name,
                    description=proj.description,
                    status=proj.status.value if hasattr(proj.status, "value") else str(proj.status),
                    start_date=proj.start_date,
                    target_end_date=proj.end_date,
                    completion_pct=completion_pct,
                    milestones_summary=MilestoneSummaryCount(
                        total=total, completed=completed, pending=pending
                    ),
                )
            )

        return results

    @staticmethod
    def get_project_milestones(
        db: Session, project_id: int, current_user: UserAccount
    ) -> List[ClientMilestoneResponse]:
        """
        Return milestones for a project that belongs to the authenticated client.

        Returns 404 if the project does not exist **or** belongs to another
        client (prevents ID enumeration).
        """
        client = ClientPortalService._resolve_client(db, current_user)

        project = ClientPortalRepository.get_project_by_id_and_client_id(
            db, project_id, client.client_id
        )
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )

        milestones = ClientPortalRepository.get_milestones_by_project_id(
            db, project_id
        )

        return [
            ClientMilestoneResponse(
                id=m.id,
                project_id=m.project_id,
                title=m.title,
                description=m.description,
                target_date=m.target_date,
                status=m.status.value if hasattr(m.status, "value") else str(m.status),
                completed_at=m.completed_at,
            )
            for m in milestones
        ]

