import uuid
from datetime import datetime, timezone
from typing import List, Optional, Union, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.core.audit import write_audit_log
from app.models.support import SupportTicket, TicketActivity
from app.models.user_account import UserAccount
from app.features.support.schemas import (
    TicketCreateIn,
    TicketAssignIn,
    TicketNoteIn,
    TicketStatusUpdateIn,
    QueueMetricsOut,
)

try:
    from app.features.notifications.service import NotificationService
except ImportError:
    NotificationService = None

ALLOWED_TRIAGE_ROLES = {"IT_SUPPORT", "SYSTEM_ADMIN", "ADMIN"}
VALID_STATUSES = {"open", "in_progress", "resolved", "escalated", "closed"}


def _get_user_role_str(user: Any) -> str:
    user_type = getattr(user, "user_type", "")
    return user_type.value if hasattr(user_type, "value") else str(user_type)


def require_triage_role(user: Any) -> None:
    role = _get_user_role_str(user).upper()
    if role not in ALLOWED_TRIAGE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: insufficient role permissions for triage operations",
        )


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
    Get ticket detail ensuring ordinary employees cannot see other employees' tickets (US-26, US-27).
    IT_SUPPORT and ADMIN roles can view all tickets.
    """
    ticket = get_ticket_or_404(db, ticket_id)
    role = _get_user_role_str(current_user).upper()

    if role in ALLOWED_TRIAGE_ROLES:
        return ticket

    actor_account_id = getattr(current_user, "account_id", None)
    if not actor_account_id or str(ticket.reporter_id) != str(actor_account_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: ordinary employees cannot view other employees' tickets",
        )
    return ticket


def get_my_tickets(db: Session, current_user: Any) -> List[SupportTicket]:
    """Retrieve all support tickets reported by the currently authenticated user (US-26)."""
    actor_account_id = getattr(current_user, "account_id", None)
    if not actor_account_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

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
    """Employee submits ticket (US-26)."""
    actor_account_id = getattr(current_user, "account_id", None)
    if not actor_account_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    ticket_number = generate_ticket_number(db)
    now_utc = datetime.now(timezone.utc)

    ticket = SupportTicket(
        ticket_number=ticket_number,
        subject=payload.subject or payload.title,
        description=payload.description,
        category=(payload.category or "other").lower(),
        priority=(payload.priority or "MEDIUM").upper(),
        status="open",
        reporter_id=actor_account_id,
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(ticket)
    db.flush()

    activity = TicketActivity(
        ticket_id=ticket.id,
        actor_id=actor_account_id,
        action="CREATED",
        note=f"Ticket {ticket.ticket_number} created by employee",
        created_at=now_utc,
    )
    db.add(activity)

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


def list_tickets(
    db: Session,
    status_filter: Optional[str] = None,
    category: Optional[str] = None,
    assigned_to: Optional[Union[uuid.UUID, str]] = None,
    priority: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: Optional[Any] = None,
) -> List[SupportTicket]:
    """
    IT staff queue view with query filters (US-27):
    ?status=open&category=hardware&assigned_to=uuid&priority=HIGH
    """
    if current_user is not None:
        require_triage_role(current_user)

    query = db.query(SupportTicket)

    if status_filter:
        query = query.filter(SupportTicket.status.ilike(status_filter.strip()))
    if category:
        query = query.filter(SupportTicket.category.ilike(category.strip()))
    if priority:
        query = query.filter(SupportTicket.priority.ilike(priority.strip()))
    if assigned_to:
        if isinstance(assigned_to, str):
            try:
                assigned_uuid = uuid.UUID(assigned_to.strip())
            except ValueError:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid UUID: {assigned_to}")
        else:
            assigned_uuid = assigned_to
        query = query.filter(SupportTicket.assigned_to == assigned_uuid)

    return query.order_by(desc(SupportTicket.created_at)).offset(skip).limit(limit).all()


def get_queue_metrics(db: Session, current_user: Any) -> Dict[str, int]:
    """Aggregate queue metrics for IT Support triage dashboard (US-27)."""
    require_triage_role(current_user)

    open_count = db.query(func.count(SupportTicket.id)).filter(SupportTicket.status == "open").scalar() or 0
    in_progress_count = db.query(func.count(SupportTicket.id)).filter(SupportTicket.status == "in_progress").scalar() or 0
    resolved_count = db.query(func.count(SupportTicket.id)).filter(SupportTicket.status == "resolved").scalar() or 0
    escalated_count = db.query(func.count(SupportTicket.id)).filter(SupportTicket.status == "escalated").scalar() or 0
    unassigned_count = db.query(func.count(SupportTicket.id)).filter(SupportTicket.assigned_to.is_(None)).scalar() or 0
    total_tickets = db.query(func.count(SupportTicket.id)).scalar() or 0

    return {
        "open_count": open_count,
        "in_progress_count": in_progress_count,
        "resolved_count": resolved_count,
        "escalated_count": escalated_count,
        "unassigned_count": unassigned_count,
        "total_tickets": total_tickets,
    }


def assign_ticket(
    db: Session,
    ticket_id: int,
    payload: TicketAssignIn,
    current_user: Any,
) -> SupportTicket:
    """
    Assign ticket to an IT staff member (US-27).
    Verifies target assignee holds IT_SUPPORT or ADMIN role.
    """
    require_triage_role(current_user)
    ticket = get_ticket_or_404(db, ticket_id)

    target_assignee = db.query(UserAccount).filter(UserAccount.account_id == payload.assigned_to).first()
    if not target_assignee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target assignee user account with ID {payload.assigned_to} not found",
        )

    assignee_role = _get_user_role_str(target_assignee).upper()
    if assignee_role not in ALLOWED_TRIAGE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Target assignee '{target_assignee.email}' does not hold the IT_SUPPORT role. Tickets can only be assigned to IT Support staff.",
        )

    now_utc = datetime.now(timezone.utc)
    old_assigned = str(ticket.assigned_to) if ticket.assigned_to else "Unassigned"

    ticket.assigned_to = target_assignee.account_id
    ticket.updated_at = now_utc

    note_msg = f"Assigned to {target_assignee.email} ({target_assignee.account_id})"
    if payload.reassignment_reason:
        note_msg += f". Note: {payload.reassignment_reason}"

    activity = TicketActivity(
        ticket_id=ticket.id,
        actor_id=getattr(current_user, "account_id", None),
        action="ASSIGNED",
        note=note_msg,
        created_at=now_utc,
    )
    db.add(activity)

    write_audit_log(
        db,
        action="UPDATE",
        entity_name="SUPPORT_TICKET",
        entity_ref_id=str(ticket.id),
        account_id=getattr(current_user, "account_id", None),
        old_value=old_assigned,
        new_value=str(target_assignee.account_id),
    )

    db.commit()
    db.refresh(ticket)
    return ticket


def add_troubleshooting_note(
    db: Session,
    ticket_id: int,
    payload: TicketNoteIn,
    current_user: Any,
) -> TicketActivity:
    """
    Append internal troubleshooting note to ticket_activity (US-27).
    Updates ticket updated_at and creates NOTE_ADDED activity entry.
    """
    require_triage_role(current_user)
    ticket = get_ticket_or_404(db, ticket_id)
    now_utc = datetime.now(timezone.utc)

    activity = TicketActivity(
        ticket_id=ticket.id,
        actor_id=getattr(current_user, "account_id", None),
        action="NOTE_ADDED",
        note=payload.note,
        created_at=now_utc,
    )
    db.add(activity)

    ticket.updated_at = now_utc

    write_audit_log(
        db,
        action="UPDATE",
        entity_name="SUPPORT_TICKET",
        entity_ref_id=str(ticket.id),
        account_id=getattr(current_user, "account_id", None),
        new_value=f"NOTE_ADDED: {payload.note[:70]}",
    )

    db.commit()
    db.refresh(activity)
    db.refresh(ticket)
    return activity


def update_ticket_status(
    db: Session,
    ticket_id: int,
    payload: TicketStatusUpdateIn,
    current_user: Any,
) -> SupportTicket:
    """
    Transition status (open -> in_progress -> resolved) (US-27).
    If marking resolved, notifies reporter via notification service.
    """
    require_triage_role(current_user)
    ticket = get_ticket_or_404(db, ticket_id)

    target_status = payload.status.strip().lower()
    if target_status not in VALID_STATUSES:
        valid_opts = ", ".join(sorted(VALID_STATUSES))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status '{payload.status}'. Must be one of: {valid_opts}",
        )

    old_status = ticket.status.lower()
    now_utc = datetime.now(timezone.utc)

    ticket.status = target_status
    ticket.updated_at = now_utc

    if target_status == "resolved":
        ticket.resolved_at = now_utc

        if NotificationService:
            try:
                NotificationService.create_notification(
                    db=db,
                    user_id=ticket.reporter_id,
                    type="TICKET_RESOLVED",
                    title=f"Support Ticket #{ticket.ticket_number} Resolved",
                    message=(
                        f"Your support ticket #{ticket.ticket_number} ('{ticket.subject}') has been resolved. "
                        + (f"Notes: {payload.resolution_notes}" if payload.resolution_notes else "Please verify the resolution.")
                    ),
                    link=f"/support/tickets/{ticket.id}",
                )
            except Exception:
                pass

    activity = TicketActivity(
        ticket_id=ticket.id,
        actor_id=getattr(current_user, "account_id", None),
        action="STATUS_CHANGED",
        old_status=old_status,
        new_status=target_status,
        note=payload.resolution_notes or f"Status changed from {old_status} to {target_status}",
        created_at=now_utc,
    )
    db.add(activity)

    write_audit_log(
        db,
        action="UPDATE",
        entity_name="SUPPORT_TICKET",
        entity_ref_id=str(ticket.id),
        account_id=getattr(current_user, "account_id", None),
        old_value=old_status,
        new_value=target_status,
    )

    db.commit()
    db.refresh(ticket)
    return ticket
