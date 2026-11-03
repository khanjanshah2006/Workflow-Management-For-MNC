import uuid
from datetime import datetime, timezone
from typing import List, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.exceptions import NotFoundError, ValidationError, ForbiddenError
from app.core.rbac import require_role, is_it_support, has_any_role
from app.core.audit import write_audit_log
from app.models.support import SupportTicket, TicketActivity
from app.models.user_account import UserAccount
from app.models.enums import AuditAction, TicketStatus, TicketActivityType
from app.features.support.schemas import (
    TicketCreateIn,
    TicketAssignIn,
    TicketNoteIn,
    TicketStatusUpdateIn,
)
from app.services import notification_service

ALLOWED_TRIAGE_ROLES = ["IT_SUPPORT", "SYSTEM_ADMIN", "IT Support", "System Administrator"]
VALID_STATUSES = {
    TicketStatus.OPEN.value,
    TicketStatus.IN_PROGRESS.value,
    TicketStatus.RESOLVED.value,
    TicketStatus.ESCALATED.value,
    TicketStatus.CLOSED.value,
}


def get_ticket_or_404(db: Session, ticket_id: int) -> SupportTicket:
    """Fetch ticket by integer primary key or raise NotFoundError."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise NotFoundError(f"Support ticket with ID {ticket_id} not found")
    return ticket


def get_ticket_detail_scoped(db: Session, ticket_id: int, actor: Any) -> SupportTicket:
    """
    Get ticket detail ensuring ordinary employees cannot see other employees' tickets (US-26).
    IT_SUPPORT and SYSTEM_ADMIN can view all tickets.
    """
    ticket = get_ticket_or_404(db, ticket_id)

    # If actor is IT staff or admin, allow access
    if has_any_role(actor, ALLOWED_TRIAGE_ROLES):
        return ticket

    # For ordinary employees, verify ownership
    actor_account_id = getattr(actor, "account_id", None)
    if not actor_account_id or str(ticket.reporter_id) != str(actor_account_id):
        raise ForbiddenError("Access forbidden: ordinary employees cannot view other employees' tickets")

    return ticket


def get_my_tickets(db: Session, actor: Any) -> List[SupportTicket]:
    """
    Retrieve all support tickets reported by the currently authenticated user (US-26).
    """
    actor_account_id = getattr(actor, "account_id", None)
    if not actor_account_id:
        raise ValidationError("Authentication required: actor account_id missing")

    return (
        db.query(SupportTicket)
        .filter(SupportTicket.reporter_id == actor_account_id)
        .order_by(desc(SupportTicket.created_at))
        .all()
    )


def list_tickets(
    db: Session,
    status: Optional[str] = None,
    category: Optional[str] = None,
    assigned_to: Optional[Union[uuid.UUID, str]] = None,
    skip: int = 0,
    limit: int = 50,
    actor: Optional[Any] = None,
) -> List[SupportTicket]:
    """
    IT staff queue view with query filters:
    ?status=open&category=hardware&assigned_to=uuid
    Restricted to IT_SUPPORT and SYSTEM_ADMIN roles.
    """
    if actor is not None:
        require_role(actor, allowed=ALLOWED_TRIAGE_ROLES)

    query = db.query(SupportTicket)

    # Filter by status
    if status:
        query = query.filter(SupportTicket.status.ilike(status.strip()))

    # Filter by category
    if category:
        query = query.filter(SupportTicket.category.ilike(category.strip()))

    # Filter by assigned_to
    if assigned_to:
        if isinstance(assigned_to, str):
            try:
                assigned_uuid = uuid.UUID(assigned_to.strip())
            except ValueError:
                raise ValidationError(f"Invalid assigned_to UUID string: {assigned_to}")
        else:
            assigned_uuid = assigned_to
        query = query.filter(SupportTicket.assigned_to == assigned_uuid)

    return query.order_by(desc(SupportTicket.created_at)).offset(skip).limit(limit).all()


def assign_ticket(
    db: Session,
    ticket_id: int,
    payload: TicketAssignIn,
    actor: Any,
) -> SupportTicket:
    """
    Assign ticket to an IT staff member.
    Verifies target assignee holds IT_SUPPORT role.
    Appends ASSIGNED activity and writes audit log.
    """
    require_role(actor, allowed=ALLOWED_TRIAGE_ROLES)

    ticket = get_ticket_or_404(db, ticket_id)

    # 1. Look up target assignee user account
    target_assignee = db.query(UserAccount).filter(UserAccount.account_id == payload.assigned_to).first()
    if not target_assignee:
        raise NotFoundError(f"Target assignee user account with ID {payload.assigned_to} not found")

    # 2. Verify assignee holds IT_SUPPORT role
    if not is_it_support(target_assignee):
        raise ValidationError(
            f"Target assignee '{target_assignee.email}' does not hold the IT_SUPPORT role. "
            f"Tickets can only be assigned to IT Support staff."
        )

    old_assigned_to = str(ticket.assigned_to) if ticket.assigned_to else "Unassigned"
    now_utc = datetime.now(timezone.utc)

    # 3. Update ticket assignment and timestamp
    ticket.assigned_to = target_assignee.account_id
    ticket.updated_at = now_utc

    # 4. Create ASSIGNED activity entry
    activity = TicketActivity(
        ticket_id=ticket.id,
        actor_id=getattr(actor, "account_id", None),
        action=TicketActivityType.ASSIGNED.value,
        note=f"Assigned to {target_assignee.email} ({target_assignee.account_id})",
        created_at=now_utc,
    )
    db.add(activity)

    # 5. Write audit log
    write_audit_log(
        db,
        actor=actor,
        action=AuditAction.ASSIGN,
        entity_name="SUPPORT_TICKET",
        entity_ref_id=str(ticket.id),
        old_value=old_assigned_to,
        new_value=str(target_assignee.account_id),
    )

    db.commit()
    db.refresh(ticket)
    return ticket


def add_troubleshooting_note(
    db: Session,
    ticket_id: int,
    payload: TicketNoteIn,
    actor: Any,
) -> TicketActivity:
    """
    Append internal troubleshooting note to ticket_activity.
    Updates ticket updated_at and creates NOTE_ADDED activity entry.
    """
    require_role(actor, allowed=ALLOWED_TRIAGE_ROLES)

    ticket = get_ticket_or_404(db, ticket_id)
    now_utc = datetime.now(timezone.utc)

    # 1. Create NOTE_ADDED activity entry
    activity = TicketActivity(
        ticket_id=ticket.id,
        actor_id=getattr(actor, "account_id", None),
        action=TicketActivityType.NOTE_ADDED.value,
        note=payload.note,
        created_at=now_utc,
    )
    db.add(activity)

    # 2. Update ticket updated_at
    ticket.updated_at = now_utc

    # 3. Write audit log
    note_preview = (payload.note[:70] + "...") if len(payload.note) > 70 else payload.note
    write_audit_log(
        db,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_name="SUPPORT_TICKET",
        entity_ref_id=str(ticket.id),
        new_value=f"NOTE_ADDED: {note_preview}",
    )

    db.commit()
    db.refresh(activity)
    db.refresh(ticket)
    return activity


def update_ticket_status(
    db: Session,
    ticket_id: int,
    payload: TicketStatusUpdateIn,
    actor: Any,
) -> SupportTicket:
    """
    Transition status (open -> in_progress -> resolved).
    If marking resolved, notifies reporter via notification service.
    Appends STATUS_CHANGED activity entry and writes audit log.
    """
    require_role(actor, allowed=ALLOWED_TRIAGE_ROLES)

    ticket = get_ticket_or_404(db, ticket_id)

    target_status = payload.status.strip().lower()
    if target_status not in VALID_STATUSES:
        valid_options = ", ".join(sorted(VALID_STATUSES))
        raise ValidationError(f"Invalid status '{payload.status}'. Must be one of: {valid_options}")

    old_status = ticket.status.lower()
    now_utc = datetime.now(timezone.utc)

    # Update ticket status and updated_at
    ticket.status = target_status
    ticket.updated_at = now_utc

    # If marking resolved, record resolution timestamp and notify reporter
    if target_status == TicketStatus.RESOLVED.value:
        ticket.resolved_at = now_utc

        # Person 1 Notification Service trigger
        notification_service.notify(
            db=db,
            recipient_id=ticket.reporter_id,
            type="TICKET_RESOLVED",
            title=f"Support Ticket #{ticket.ticket_number} Resolved",
            message=(
                f"Your support ticket #{ticket.ticket_number} ('{ticket.subject}') has been resolved. "
                + (f"Notes: {payload.resolution_notes}" if payload.resolution_notes else "Please verify the resolution.")
            ),
            related_entity_id=ticket.id,
        )

    # Append activity log entry
    activity = TicketActivity(
        ticket_id=ticket.id,
        actor_id=getattr(actor, "account_id", None),
        action=TicketActivityType.STATUS_CHANGED.value,
        old_status=old_status,
        new_status=target_status,
        note=payload.resolution_notes or f"Status changed from {old_status} to {target_status}",
        created_at=now_utc,
    )
    db.add(activity)

    # Write audit log
    write_audit_log(
        db,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_name="SUPPORT_TICKET",
        entity_ref_id=str(ticket.id),
        old_value=old_status,
        new_value=target_status,
    )

    db.commit()
    db.refresh(ticket)
    return ticket


def create_ticket(
    db: Session,
    payload: TicketCreateIn,
    actor: Any,
) -> SupportTicket:
    """
    Create a new support ticket (FR-ITS-01 / US-26).
    Auto-increments human-readable ticket_number sequence (e.g. TKT-001).
    Auto-creates initial CREATED record in ticket_activity.
    """
    now_utc = datetime.now(timezone.utc)
    reporter_id = getattr(actor, "account_id", None)
    if not reporter_id:
        raise ValidationError("Reporter account_id is required to create a ticket")

    # Generate sequential unique ticket number: TKT-001, TKT-002, ...
    count = db.query(SupportTicket).count() + 1
    ticket_number = f"TKT-{count:03d}"
    while db.query(SupportTicket).filter(SupportTicket.ticket_number == ticket_number).first():
        count += 1
        ticket_number = f"TKT-{count:03d}"

    ticket_subject = payload.subject or payload.title or "Support Issue"

    ticket = SupportTicket(
        ticket_number=ticket_number,
        subject=ticket_subject,
        description=payload.description,
        category=(payload.category or "other").lower(),
        priority=(payload.priority or "MEDIUM").upper(),
        status=TicketStatus.OPEN.value,
        reporter_id=reporter_id,
        created_at=now_utc,
        updated_at=now_utc,
    )
    db.add(ticket)
    db.flush()

    activity = TicketActivity(
        ticket_id=ticket.id,
        actor_id=reporter_id,
        action=TicketActivityType.CREATED.value,
        note="Ticket submitted by reporter",
        created_at=now_utc,
    )
    db.add(activity)

    write_audit_log(
        db,
        actor=actor,
        action=AuditAction.CREATE,
        entity_name="SUPPORT_TICKET",
        entity_ref_id=str(ticket.id),
        new_value=f"Created ticket {ticket_number}: {ticket_subject}",
    )

    db.commit()
    db.refresh(ticket)
    return ticket
