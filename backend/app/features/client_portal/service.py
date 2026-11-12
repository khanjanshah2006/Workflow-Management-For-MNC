"""
Service layer for Client Portal (US-20, US-21).

Business logic lives here; the router stays thin.
"""

from io import BytesIO
from typing import List, Optional

from fastapi import HTTPException, status
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.core.audit import write_audit_log
from app.models.enums import AuditAction, UserType
from app.models.user_account import UserAccount
from app.features.client_portal.repository import ClientPortalRepository
from app.features.client_portal.schemas import (
    ClientMilestoneResponse,
    ClientProjectSummaryResponse,
    ClientVisibilityResponse,
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

    @staticmethod
    def _mask_role(role_or_designation: Optional[str]) -> str:
        """Map an internal designation/role to a generic client-safe role label."""
        text = (role_or_designation or "").lower()
        if "qa" in text or "test" in text or "quality" in text:
            return "QA"
        if "lead" in text:
            return "Tech Lead"
        if "manager" in text or "pm" in text:
            return "Project Manager"
        if "design" in text or "ui" in text or "ux" in text:
            return "Designer"
        return "Developer"

    @staticmethod
    def toggle_client_visibility(
        db: Session,
        project_id: int,
        is_visible: bool,
        actor: UserAccount,
        ip_address: Optional[str] = None,
    ) -> ClientVisibilityResponse:
        """Toggle whether team member identities are visible to clients (US-42)."""
        project = ClientPortalRepository.get_project_by_id(db, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found.",
            )

        old_val = {"is_team_visible_to_client": project.is_team_visible_to_client}
        updated = ClientPortalRepository.update_team_visibility(db, project, is_visible)

        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="PROJECT",
            entity_ref_id=str(project.project_id),
            account_id=actor.account_id,
            old_value=old_val,
            new_value={"is_team_visible_to_client": is_visible},
            ip_address=ip_address,
        )
        db.commit()
        return ClientVisibilityResponse.model_validate(updated)

    @staticmethod
    def generate_project_report_pdf(
        db: Session,
        project_id: int,
        current_user: UserAccount,
    ) -> bytes:
        """
        Generate a downloadable PDF progress report for a project (US-41).

        Includes Project Title, Overall Progress %, Milestone Roadmap Table,
        Deliverable Signoff Status, and Project Team (masked when
        ``is_team_visible_to_client`` is False).
        """
        if current_user.user_type == UserType.CLIENT:
            client = ClientPortalService._resolve_client(db, current_user)
            project = ClientPortalRepository.get_project_by_id_and_client_id(
                db, project_id, client.client_id
            )
        else:
            project = ClientPortalRepository.get_project_by_id(db, project_id)

        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )

        total_ms, completed_ms = ClientPortalRepository.get_milestone_counts_for_project(
            db, project.project_id
        )
        overall_progress = round((completed_ms / total_ms) * 100, 1) if total_ms > 0 else 0.0

        milestones = ClientPortalRepository.get_milestones_by_project_id(
            db, project.project_id
        )
        deliverables = ClientPortalRepository.get_deliverables_by_project_id(
            db, project.project_id
        )
        team_members = ClientPortalRepository.get_project_team_members(
            db, project.project_id
        )

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, title=f"Project Report - {project.name}")
        styles = getSampleStyleSheet()
        elements = []

        # 1. Project Title & Overall Progress %
        elements.append(Paragraph(f"Project Progress Report: {project.name}", styles["Title"]))
        elements.append(Spacer(1, 8))
        proj_status = project.status.value if hasattr(project.status, "value") else str(project.status)
        elements.append(
            Paragraph(
                f"<b>Project Code:</b> {project.project_code} &nbsp;|&nbsp; "
                f"<b>Status:</b> {proj_status} &nbsp;|&nbsp; "
                f"<b>Overall Progress:</b> {overall_progress}% ({completed_ms}/{total_ms} milestones)",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 16))

        # 2. Milestone Roadmap Table
        elements.append(Paragraph("Milestone Roadmap", styles["Heading2"]))
        ms_rows = [["Milestone", "Target Date", "Status"]]
        if milestones:
            for m in milestones:
                m_status = m.status.value if hasattr(m.status, "value") else str(m.status)
                ms_rows.append([m.title, str(m.target_date), m_status.upper()])
        else:
            ms_rows.append(["No milestones defined", "-", "-"])

        ms_table = Table(ms_rows, colWidths=[260, 120, 120])
        ms_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(ms_table)
        elements.append(Spacer(1, 16))

        # 3. Deliverable Signoff Status
        elements.append(Paragraph("Deliverable Signoff Status", styles["Heading2"]))
        deliv_rows = [["Deliverable", "Version", "Signoff Status"]]
        if deliverables:
            for d in deliverables:
                d_status = d.status.value if hasattr(d.status, "value") else str(d.status)
                deliv_rows.append([d.title, f"v{d.version}", d_status])
        else:
            deliv_rows.append(["No deliverables submitted yet", "-", "-"])

        deliv_table = Table(deliv_rows, colWidths=[260, 80, 160])
        deliv_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(deliv_table)
        elements.append(Spacer(1, 16))

        # 4. Project Team (anonymized when is_team_visible_to_client == False)
        elements.append(Paragraph("Project Team", styles["Heading2"]))
        if project.is_team_visible_to_client:
            team_rows = [["Member Name", "Role / Designation"]]
            if team_members:
                for full_name, role_label in team_members:
                    team_rows.append([full_name, role_label])
            else:
                team_rows.append(["No active team members", "-"])
        else:
            team_rows = [["Role", "Visibility"]]
            if team_members:
                for _, role_label in team_members:
                    team_rows.append(
                        [ClientPortalService._mask_role(role_label), "Anonymized"]
                    )
            else:
                team_rows.append(["No active team members", "Anonymized"])

        team_table = Table(team_rows, colWidths=[260, 240])
        team_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(team_table)

        doc.build(elements)
        return buffer.getvalue()

