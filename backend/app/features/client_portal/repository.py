"""
Repository layer for Client Portal (US-20, US-21, US-22, US-41, US-42).

All client-facing queries enforce strict client-scoped isolation.  No query
returns employee PII, task tables, or internal comments without proper authorization.
"""

from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.deliverable import Deliverable, DeliverableFeedback
from app.models.employee import Employee
from app.models.enums import CommonStatus, DeliverableStatus, FeedbackDecision, MilestoneStatus
from app.models.milestone import ProjectMilestone
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.team import Team, TeamMember


class ClientPortalRepository:
    """Data-access methods scoped to the authenticated client and project management."""

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
        """Fetch a project by primary key regardless of client ownership."""
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

    # ------------------------------------------------------------------
    # Deliverables & Feedback queries (US-22)
    # ------------------------------------------------------------------

    @staticmethod
    def get_pm_by_account_id(db: Session, account_id) -> Optional[ProjectManager]:
        """Resolve the ProjectManager profile linked to a UserAccount."""
        return (
            db.query(ProjectManager)
            .filter(ProjectManager.account_id == account_id)
            .first()
        )

    @staticmethod
    def get_pm_by_id(db: Session, pm_id: int) -> Optional[ProjectManager]:
        """Fetch a ProjectManager record by primary key."""
        return (
            db.query(ProjectManager)
            .filter(ProjectManager.pm_id == pm_id)
            .first()
        )

    @staticmethod
    def get_employee_by_account_id(db: Session, account_id) -> Optional[Employee]:
        """Resolve an Employee record linked to a UserAccount (if present)."""
        return (
            db.query(Employee)
            .filter(Employee.account_id == account_id)
            .first()
        )

    @staticmethod
    def get_milestone_by_id_and_project(
        db: Session, milestone_id: int, project_id: int
    ) -> Optional[ProjectMilestone]:
        """Verify an active milestone belongs to the given project."""
        return (
            db.query(ProjectMilestone)
            .filter(
                ProjectMilestone.id == milestone_id,
                ProjectMilestone.project_id == project_id,
                ProjectMilestone.is_deleted == False,  # noqa: E712
            )
            .first()
        )

    @staticmethod
    def get_max_deliverable_version(
        db: Session, project_id: int, title: str
    ) -> int:
        """Return the highest published version for a project deliverable title."""
        max_ver = (
            db.query(func.max(Deliverable.version))
            .filter(
                Deliverable.project_id == project_id,
                Deliverable.title == title,
            )
            .scalar()
        )
        return max_ver or 0

    @staticmethod
    def create_deliverable(
        db: Session,
        project_id: int,
        milestone_id: Optional[int],
        submitted_by: Optional[int],
        title: str,
        description: Optional[str],
        file_url: str,
        version: int,
    ) -> Deliverable:
        """Insert and flush a newly published deliverable."""
        deliverable = Deliverable(
            project_id=project_id,
            milestone_id=milestone_id,
            submitted_by=submitted_by,
            title=title,
            description=description,
            file_url=file_url,
            version=version,
            status=DeliverableStatus.SUBMITTED,
        )
        db.add(deliverable)
        db.flush()
        db.refresh(deliverable)
        return deliverable

    @staticmethod
    def get_deliverables_by_project_id(
        db: Session, project_id: int
    ) -> List[Deliverable]:
        """List deliverables for a project, newest version / submission first."""
        return (
            db.query(Deliverable)
            .filter(Deliverable.project_id == project_id)
            .order_by(Deliverable.submitted_at.desc(), Deliverable.deliverable_id.desc())
            .all()
        )

    @staticmethod
    def get_deliverable_by_id(
        db: Session, deliverable_id: int
    ) -> Optional[Deliverable]:
        """Fetch a single deliverable by primary key."""
        return (
            db.query(Deliverable)
            .filter(Deliverable.deliverable_id == deliverable_id)
            .first()
        )

    @staticmethod
    def get_feedbacks_for_deliverables(
        db: Session, deliverable_ids: List[int]
    ) -> Dict[int, List[DeliverableFeedback]]:
        """Batch-fetch feedback entries keyed by deliverable_id."""
        if not deliverable_ids:
            return {}
        rows = (
            db.query(DeliverableFeedback)
            .filter(DeliverableFeedback.deliverable_id.in_(deliverable_ids))
            .order_by(DeliverableFeedback.given_at.desc(), DeliverableFeedback.feedback_id.desc())
            .all()
        )
        grouped: Dict[int, List[DeliverableFeedback]] = {did: [] for did in deliverable_ids}
        for row in rows:
            grouped.setdefault(row.deliverable_id, []).append(row)
        return grouped

    @staticmethod
    def create_deliverable_feedback(
        db: Session,
        deliverable_id: int,
        given_by_client_id: int,
        decision: FeedbackDecision,
        comments: Optional[str],
        rating: int,
    ) -> DeliverableFeedback:
        """Record a client feedback/signoff row and flush."""
        feedback = DeliverableFeedback(
            deliverable_id=deliverable_id,
            given_by_client_id=given_by_client_id,
            decision=decision,
            comments=comments,
            rating=rating,
        )
        db.add(feedback)
        db.flush()
        db.refresh(feedback)
        return feedback

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
