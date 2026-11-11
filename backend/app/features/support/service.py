from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.audit import write_audit_log
from app.models.enums import AuditAction
from app.models.support_ticket import SupportTicket
from app.models.user_account import UserAccount
from app.features.support.repository import SupportTicketRepository
from app.features.support.schemas import EscalateTicketRequest


class TicketNotFoundError(HTTPException):
    def __init__(self, ticket_id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket with ID {ticket_id} not found",
        )


class InvalidTicketStatusError(HTTPException):
    def __init__(self, current_status: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot escalate ticket with status '{current_status}'. "
                f"Escalation is only allowed when ticket status is 'open' or 'in_progress'."
            ),
        )


class SupportTicketService:
    @staticmethod
    def escalate_ticket(
        db: Session,
        ticket_id: int,
        payload: EscalateTicketRequest,
        actor: UserAccount,
        ip_address: Optional[str] = None,
    ) -> SupportTicket:
        # 1. Fetch ticket
        ticket = SupportTicketRepository.get_by_id(db, ticket_id)
        if not ticket:
            raise TicketNotFoundError(ticket_id)

        # 2. Validate ticket status: only open or in_progress allowed
        current_status_clean = str(ticket.status).strip().lower()
        if current_status_clean not in ["open", "in_progress"]:
            raise InvalidTicketStatusError(ticket.status)

        old_status = ticket.status

        # 3. Update status to escalated & save escalation reason
        ticket.status = "escalated"
        ticket.escalation_reason = payload.reason
        ticket.updated_at = datetime.now(timezone.utc)

        # 4. Record ESCALATED activity
        SupportTicketRepository.create_activity(
            db=db,
            ticket_id=ticket.ticket_id,
            activity_type="ESCALATED",
            details=payload.reason,
            actor_account_id=actor.account_id,
        )

        # 5. Notify all eligible System Administrators
        eligible_admins = SupportTicketRepository.get_eligible_system_admins(db)
        for admin in eligible_admins:
            SupportTicketRepository.create_notification(
                db=db,
                account_id=admin.account_id,
                type_="TICKET_ESCALATED",
                title=f"Support Ticket {ticket.ticket_number} Escalated",
                message=(
                    f"Support ticket '{ticket.ticket_number}' ({ticket.title}) has been escalated "
                    f"to System Administrator. Reason: {payload.reason}"
                ),
            )

        # 6. Commit transaction and refresh
        db.commit()
        db.refresh(ticket)

        # 7. Write audit log (per api-endpoint-pattern & NFR-ITS-06 / NFR-AU04)
        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="SUPPORT_TICKET",
            entity_ref_id=str(ticket.ticket_id),
            account_id=actor.account_id,
            old_value={"status": old_status},
            new_value={"status": "escalated", "escalation_reason": payload.reason},
            ip_address=ip_address,
        )

        return ticket

