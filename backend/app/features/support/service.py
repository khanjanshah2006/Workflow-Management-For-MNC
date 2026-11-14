import uuid
from datetime import datetime, timezone
from typing import List, Optional, Union, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.core.audit import write_audit_log
from app.models.enums import AuditAction
from app.models.support import SupportTicket, TicketActivity
from app.models.user_account import UserAccount
from app.features.support.repository import SupportTicketRepository
from app.features.support.schemas import EscalateTicketRequest, TicketCreateIn

ALLOWED_TRIAGE_ROLES = {"IT_SUPPORT", "SYSTEM_ADMIN", "ADMIN"}


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
            ticket_id=ticket.id if hasattr(ticket, "id") else ticket.ticket_id,
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


def get_ticket_or_404(db: Session, ticket_id: int) -> SupportTicket:
    """Fetch ticket by integer primary key or raise 404."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket with ID {ticket_id} not found",
        )
    return ticket


def get_ticket_detail_scoped(db: Session, ticket_id: int, current_user: Any) -> SupportTicket:
    """
    Get ticket detail ensuring ordinary employees cannot see other employees' tickets (US-26).
    IT_SUPPORT and ADMIN roles can view all tickets.
    """
    ticket = get_ticket_or_404(db, ticket_id)
    user_type = getattr(current_user, "user_type", "")
    user_type_str = user_type.value if hasattr(user_type, "value") else str(user_type)

    if user_type_str.upper() in ALLOWED_TRIAGE_ROLES:
        return ticket

    actor_account_id = getattr(current_user, "account_id", None)
    if not actor_account_id or str(ticket.reporter_id) != str(actor_account_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: ordinary employees cannot view other employees' tickets",
        )
    return ticket


def get_my_tickets(db: Session, current_user: Any) -> List[SupportTicket]:
    """
    Retrieve all support tickets reported by the currently authenticated user (US-26).
    """
    actor_account_id = getattr(current_user, "account_id", None)
    if not actor_account_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return (
        db.query(SupportTicket)
        .filter(SupportTicket.reporter_id == actor_account_id)
        .order_by(desc(SupportTicket.created_at))
        .all()
    )


def generate_ticket_number(db: Session) -> str:
    """Auto-increments human-readable ticket_number sequence (e.g. TKT-001)."""
    count = db.query(func.count(SupportTicket.id)).scalar() or 0
    return f"TKT-{count + 1:03d}"


def create_ticket(db: Session, payload: TicketCreateIn, current_user: Any) -> SupportTicket:
    """
    Employee submits ticket (US-26).
    Auto-generates sequential ticket_number and initial CREATED activity entry.
    """
    actor_account_id = getattr(current_user, "account_id", None)
    if not actor_account_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    ticket_number = generate_ticket_number(db)
    now_utc = datetime.now(timezone.utc)

    ticket = SupportTicket(
        ticket_number=ticket_number,
        subject=payload.subject or payload.title,
        description=payload.description,
        category=payload.category or "other",
        priority=payload.priority or "MEDIUM",
        status="open",
        reporter_id=actor_account_id,
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(ticket)
    db.flush()

    # Initial activity entry
    activity = TicketActivity(
        ticket_id=ticket.id,
        actor_id=actor_account_id,
        action="CREATED",
        note=f"Ticket {ticket.ticket_number} created by employee",
        created_at=now_utc,
    )
    db.add(activity)

    # Write audit log
    write_audit_log(
        db,
        action="CREATE",
        entity_name="SUPPORT_TICKET",
        entity_ref_id=str(ticket.id),
        account_id=actor_account_id,
        new_value=f"Created ticket {ticket.ticket_number}: {ticket.subject}",
    )

    db.commit()
    db.refresh(ticket)
    return ticket
