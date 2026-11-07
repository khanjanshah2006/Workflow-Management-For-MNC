import uuid
from datetime import datetime, timezone
from typing import List, Optional, Union, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.core.audit import write_audit_log
from app.models.support import SupportTicket, TicketActivity
from app.features.support.schemas import TicketCreateIn

ALLOWED_TRIAGE_ROLES = {"IT_SUPPORT", "SYSTEM_ADMIN", "ADMIN"}


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
