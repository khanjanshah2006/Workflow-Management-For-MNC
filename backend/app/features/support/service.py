import uuid
from datetime import datetime, timezone
from typing import List, Optional, Union, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, aliased
from sqlalchemy import desc, func, case, or_

from app.core.audit import write_audit_log
from app.core.roles import IT_STAFF, SYSTEM_ADMIN, IT_SUPPORT
from app.models.enums import AuditAction, UserType
from app.models.support import SupportTicket, TicketActivity
from app.models.user_account import UserAccount
from app.models.employee import Employee
from app.features.support.repository import SupportTicketRepository
from app.features.notifications.service import NotificationService
from app.features.support.schemas import (
    EscalateTicketRequest,
    TicketCreateIn,
    TicketAssignRequest,
    TicketNoteRequest,
    TicketStatusUpdateRequest,
    SupportQueueItem,
    SupportQueueResponse,
    SupportQueueMetricsResponse,
)

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
            old_status=old_status,
            new_status="escalated",
        )

        # 5. Notify all eligible System Administrators via NotificationService
        eligible_admins = SupportTicketRepository.get_eligible_system_admins(db)
        for admin in eligible_admins:
            NotificationService.create_notification(
                db=db,
                user_id=admin.account_id,
                type="TICKET_ESCALATED",
                title=f"Support Ticket {ticket.ticket_number} Escalated",
                message=(
                    f"Support ticket '{ticket.ticket_number}' ({ticket.subject}) has been escalated "
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

        return enrich_ticket_names(db, ticket)


def get_ticket_or_404(db: Session, ticket_id: int) -> SupportTicket:
    """Fetch ticket by integer primary key or raise 404."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket with ID {ticket_id} not found",
        )
    return ticket


def enrich_ticket_names(db: Session, ticket: SupportTicket) -> SupportTicket:
    """Helper to populate reporter_name, assignee_name, and activity actor_names onto ticket."""
    reporter_emp = (
        db.query(Employee).filter(Employee.account_id == ticket.reporter_id).first()
        if ticket.reporter_id
        else None
    )
    assignee_emp = (
        db.query(Employee).filter(Employee.account_id == ticket.assigned_to).first()
        if ticket.assigned_to
        else None
    )

    ticket.reporter_name = reporter_emp.full_name if reporter_emp else None
    ticket.assignee_name = assignee_emp.full_name if assignee_emp else None

    # Populate actor_name for activities
    if hasattr(ticket, "activities") and ticket.activities:
        actor_ids = {a.actor_id for a in ticket.activities if a.actor_id}
        if actor_ids:
            employees = db.query(Employee).filter(Employee.account_id.in_(actor_ids)).all()
            emp_map = {e.account_id: e.full_name for e in employees}
            user_accounts = db.query(UserAccount).filter(UserAccount.account_id.in_(actor_ids)).all()
            acc_map = {u.account_id: u.email for u in user_accounts}
            for act in ticket.activities:
                if act.actor_id:
                    act.actor_name = emp_map.get(act.actor_id) or acc_map.get(act.actor_id)

    return ticket


def get_ticket_detail_scoped(db: Session, ticket_id: int, current_user: Any) -> SupportTicket:
    """
    Get ticket detail ensuring ordinary employees cannot see other employees' tickets (US-26).
    IT_SUPPORT and ADMIN roles can view all tickets.
    Internal notes are hidden from the reporter if they are not IT staff (US-27).
    """
    ticket = get_ticket_or_404(db, ticket_id)
    user_type = getattr(current_user, "user_type", "")
    user_type_str = user_type.value if hasattr(user_type, "value") else str(user_type)
    is_staff = user_type_str.upper() in ALLOWED_TRIAGE_ROLES

    actor_account_id = getattr(current_user, "account_id", None)
    if not is_staff:
        if not actor_account_id or str(ticket.reporter_id) != str(actor_account_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: ordinary employees cannot view other employees' tickets",
            )

    enrich_ticket_names(db, ticket)

    # US-27: If viewer is the reporter and not IT staff, mask internal troubleshooting notes
    if not is_staff and actor_account_id and str(ticket.reporter_id) == str(actor_account_id):
        for act in ticket.activities:
            if act.action == "NOTE_ADDED":
                act.note = None
                act.details = None

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
    tickets = (
        db.query(SupportTicket)
        .filter(SupportTicket.reporter_id == actor_account_id)
        .order_by(desc(SupportTicket.created_at))
        .all()
    )
    for t in tickets:
        enrich_ticket_names(db, t)
    return tickets


def generate_ticket_number(db: Session) -> str:
    """Auto-increments human-readable ticket_number sequence (e.g. TKT-001)."""
    count = db.query(func.count(SupportTicket.id)).scalar() or 0
    return f"TKT-{count + 1:03d}"


def create_ticket(db: Session, payload: TicketCreateIn, current_user: Any) -> SupportTicket:
    """
    Employee submits ticket (US-26 / US-27).
    Auto-generates sequential ticket_number and initial CREATED activity entry.
    Notifies all active IT_SUPPORT accounts upon creation.
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
        old_status=None,
        new_status="open",
        created_at=now_utc,
    )
    db.add(activity)

    # US-27: Notify all active IT Support staff about the new ticket
    it_support_accounts = SupportTicketRepository.get_eligible_it_support(db)
    for staff in it_support_accounts:
        NotificationService.create_notification(
            db=db,
            user_id=staff.account_id,
            type="TICKET_CREATED",
            title=f"New Support Ticket {ticket.ticket_number}",
            message=f"New {ticket.priority} priority support ticket '{ticket.subject}' submitted by employee.",
        )

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
    return enrich_ticket_names(db, ticket)


# -----------------------------------------------------------------------------
# S8-BE-2: IT Support Triage Queue, Status Workflow & Assignment Service Operations
# -----------------------------------------------------------------------------

def get_queue_tickets(
    db: Session,
    current_user: Any,
    status_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    assigned_to_filter: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> SupportQueueResponse:
    """
    IT staff triage queue: filters, priority-first sorting, pagination (US-27).
    CRITICAL priority is placed first, followed by HIGH, MEDIUM, LOW, and created_at DESC.
    """
    ReporterEmp = aliased(Employee)
    AssigneeEmp = aliased(Employee)

    query = (
        db.query(
            SupportTicket,
            ReporterEmp.full_name.label("reporter_name"),
            AssigneeEmp.full_name.label("assignee_name"),
        )
        .outerjoin(ReporterEmp, SupportTicket.reporter_id == ReporterEmp.account_id)
        .outerjoin(AssigneeEmp, SupportTicket.assigned_to == AssigneeEmp.account_id)
    )

    # Status filter
    if status_filter:
        query = query.filter(func.lower(SupportTicket.status) == status_filter.strip().lower())

    # Category filter
    if category_filter:
        query = query.filter(func.lower(SupportTicket.category) == category_filter.strip().lower())

    # Priority filter
    if priority_filter:
        query = query.filter(func.upper(SupportTicket.priority) == priority_filter.strip().upper())

    # Assigned-to filter
    if assigned_to_filter:
        assigned_to_clean = assigned_to_filter.strip().lower()
        if assigned_to_clean == "unassigned":
            query = query.filter(SupportTicket.assigned_to.is_(None))
        elif assigned_to_clean == "me":
            actor_id = getattr(current_user, "account_id", None)
            query = query.filter(SupportTicket.assigned_to == actor_id)
        else:
            try:
                target_uuid = uuid.UUID(assigned_to_filter.strip())
                query = query.filter(SupportTicket.assigned_to == target_uuid)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid assigned_to filter: must be 'me', 'unassigned', or a valid UUID",
                )

    total = query.with_entities(func.count(SupportTicket.id)).scalar() or 0

    # Priority ordering: CRITICAL (1), HIGH (2), MEDIUM (3), LOW (4), other (5)
    priority_rank = case(
        (func.upper(SupportTicket.priority) == "CRITICAL", 1),
        (func.upper(SupportTicket.priority) == "HIGH", 2),
        (func.upper(SupportTicket.priority) == "MEDIUM", 3),
        (func.upper(SupportTicket.priority) == "LOW", 4),
        else_=5,
    )

    offset = (page - 1) * limit
    results = (
        query.order_by(priority_rank.asc(), SupportTicket.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = []
    for row in results:
        ticket = row[0]
        rep_name = row[1]
        ass_name = row[2]
        items.append(
            SupportQueueItem(
                id=ticket.id,
                ticket_number=ticket.ticket_number,
                subject=ticket.subject,
                category=ticket.category,
                priority=ticket.priority,
                status=ticket.status,
                reporter_name=rep_name,
                assignee_name=ass_name,
                created_at=ticket.created_at,
                updated_at=ticket.updated_at,
            )
        )

    return SupportQueueResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
    )


def get_queue_metrics(db: Session) -> SupportQueueMetricsResponse:
    """
    Returns counts for open, in_progress, resolved, closed, escalated, unassigned, total.
    """
    total = db.query(func.count(SupportTicket.id)).scalar() or 0
    open_c = db.query(func.count(SupportTicket.id)).filter(func.lower(SupportTicket.status) == "open").scalar() or 0
    in_prog_c = db.query(func.count(SupportTicket.id)).filter(func.lower(SupportTicket.status) == "in_progress").scalar() or 0
    res_c = db.query(func.count(SupportTicket.id)).filter(func.lower(SupportTicket.status) == "resolved").scalar() or 0
    closed_c = db.query(func.count(SupportTicket.id)).filter(func.lower(SupportTicket.status) == "closed").scalar() or 0
    esc_c = db.query(func.count(SupportTicket.id)).filter(func.lower(SupportTicket.status) == "escalated").scalar() or 0
    unassigned_c = db.query(func.count(SupportTicket.id)).filter(SupportTicket.assigned_to.is_(None)).scalar() or 0

    return SupportQueueMetricsResponse(
        open=open_c,
        in_progress=in_prog_c,
        resolved=res_c,
        closed=closed_c,
        escalated=esc_c,
        unassigned=unassigned_c,
        total=total,
    )


def assign_ticket(
    db: Session,
    ticket_id: int,
    payload: TicketAssignRequest,
    current_user: Any,
    ip_address: Optional[str] = None,
) -> SupportTicket:
    """
    Assign ticket to an IT staff member (IT_SUPPORT or SYSTEM_ADMIN).
    If ticket is 'open', moves it to 'in_progress'.
    Sends notification to assignee and logs audit trail.
    """
    ticket = get_ticket_or_404(db, ticket_id)

    # Validate assignee is an active IT staff member
    assignee = db.query(UserAccount).filter(UserAccount.account_id == payload.assignee_account_id).first()
    if not assignee or not assignee.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignee account not found or is inactive",
        )

    assignee_role = assignee.user_type.value if hasattr(assignee.user_type, "value") else str(assignee.user_type)
    if assignee_role.upper() not in {"IT_SUPPORT", "SYSTEM_ADMIN"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignee must be an active IT Support or System Administrator account",
        )

    old_status = ticket.status
    old_assigned = ticket.assigned_to

    # If ticket status is open, auto-transition to in_progress
    if str(ticket.status).strip().lower() == "open":
        ticket.status = "in_progress"

    ticket.assigned_to = payload.assignee_account_id
    ticket.updated_at = datetime.now(timezone.utc)

    # Activity entry
    assignee_emp = db.query(Employee).filter(Employee.account_id == payload.assignee_account_id).first()
    assignee_display = assignee_emp.full_name if assignee_emp else assignee.email

    activity_note = f"Ticket assigned to {assignee_display}"
    if old_status != ticket.status:
        activity_note += f" (status moved from {old_status} to {ticket.status})"

    SupportTicketRepository.create_activity(
        db=db,
        ticket_id=ticket.id,
        activity_type="ASSIGNED",
        details=activity_note,
        actor_account_id=getattr(current_user, "account_id", None),
        old_status=old_status,
        new_status=ticket.status,
    )

    # Notify assignee
    NotificationService.create_notification(
        db=db,
        user_id=payload.assignee_account_id,
        type="TICKET_ASSIGNED",
        title=f"Support Ticket {ticket.ticket_number} Assigned",
        message=f"You have been assigned support ticket {ticket.ticket_number}: {ticket.subject}",
    )

    # Write audit log
    write_audit_log(
        db=db,
        action="UPDATE",
        entity_name="SUPPORT_TICKET",
        entity_ref_id=str(ticket.id),
        account_id=getattr(current_user, "account_id", None),
        old_value={"assigned_to": str(old_assigned) if old_assigned else None, "status": old_status},
        new_value={"assigned_to": str(payload.assignee_account_id), "status": ticket.status},
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(ticket)
    return enrich_ticket_names(db, ticket)


def add_ticket_note(
    db: Session,
    ticket_id: int,
    payload: TicketNoteRequest,
    current_user: Any,
    ip_address: Optional[str] = None,
) -> SupportTicket:
    """
    Internal troubleshooting note addition by IT staff (US-27).
    Visible to IT staff in detail view, hidden from reporter.
    """
    ticket = get_ticket_or_404(db, ticket_id)

    ticket.updated_at = datetime.now(timezone.utc)

    # Activity entry
    SupportTicketRepository.create_activity(
        db=db,
        ticket_id=ticket.id,
        activity_type="NOTE_ADDED",
        details=payload.note,
        actor_account_id=getattr(current_user, "account_id", None),
        old_status=ticket.status,
        new_status=ticket.status,
    )

    # Audit log
    write_audit_log(
        db=db,
        action="UPDATE",
        entity_name="SUPPORT_TICKET",
        entity_ref_id=str(ticket.id),
        account_id=getattr(current_user, "account_id", None),
        new_value={"note": payload.note[:100]},
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(ticket)
    return enrich_ticket_names(db, ticket)


def update_ticket_status(
    db: Session,
    ticket_id: int,
    payload: TicketStatusUpdateRequest,
    current_user: Any,
    ip_address: Optional[str] = None,
) -> SupportTicket:
    """
    Support ticket status workflow state machine (US-27):
      open -> in_progress -> resolved -> closed
      escalated -> in_progress | resolved (only by SYSTEM_ADMIN)
      resolved -> open (reporter reopening their own ticket)
      Any other transition -> 409 Conflict.
      Transition to 'resolved' requires resolution_note (400 if missing).
    """
    # 1. 404 check
    ticket = get_ticket_or_404(db, ticket_id)

    actor_account_id = getattr(current_user, "account_id", None)
    user_type = getattr(current_user, "user_type", "")
    current_role = user_type.value if hasattr(user_type, "value") else str(user_type)
    current_role = current_role.upper()

    target_status = payload.status.strip().lower()
    current_status = str(ticket.status).strip().lower()

    # 2. 403 / RBAC check
    is_staff = current_role in {"IT_SUPPORT", "SYSTEM_ADMIN"}
    is_reporter = actor_account_id and str(ticket.reporter_id) == str(actor_account_id)

    if not is_staff:
        if not is_reporter:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: you cannot update this ticket",
            )
        # Reporter is ONLY allowed to reopen a resolved ticket to open
        if not (current_status == "resolved" and target_status == "open"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Reporters are only permitted to reopen their own resolved tickets to 'open'",
            )

    # 3. Target cannot be 'escalated' directly via status update
    if target_status == "escalated":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tickets must be escalated using the PUT /tickets/{id}/escalate endpoint",
        )

    # 4. State transitions validation (403 / 409)
    if current_status == "escalated":
        # Only SYSTEM_ADMIN can transition an escalated ticket
        if current_role != "SYSTEM_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only System Administrators can update escalated tickets",
            )
        if target_status not in {"in_progress", "resolved"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Escalated tickets can only transition to 'in_progress' or 'resolved'",
            )
    else:
        # Standard allowed transitions
        allowed_transitions = {
            ("open", "in_progress"),
            ("in_progress", "resolved"),
            ("resolved", "closed"),
            ("resolved", "open"),
        }
        if (current_status, target_status) not in allowed_transitions:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Invalid status transition from '{current_status}' to '{target_status}'.",
            )

    # 5. Validation for resolution_note when resolving
    if target_status == "resolved":
        if not payload.resolution_note or not payload.resolution_note.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resolution note is mandatory when resolving a ticket",
            )
        ticket.resolved_at = datetime.now(timezone.utc)
    elif current_status == "resolved" and target_status != "resolved":
        ticket.resolved_at = None

    old_status = ticket.status
    ticket.status = target_status
    ticket.updated_at = datetime.now(timezone.utc)

    # Activity entry
    activity_note = payload.resolution_note or f"Status transitioned from {old_status} to {target_status}"
    SupportTicketRepository.create_activity(
        db=db,
        ticket_id=ticket.id,
        activity_type="STATUS_CHANGED",
        details=activity_note,
        actor_account_id=actor_account_id,
        old_status=old_status,
        new_status=target_status,
    )

    # Audit log
    write_audit_log(
        db=db,
        action="UPDATE",
        entity_name="SUPPORT_TICKET",
        entity_ref_id=str(ticket.id),
        account_id=actor_account_id,
        old_value={"status": old_status},
        new_value={"status": target_status, "resolution_note": payload.resolution_note},
        ip_address=ip_address,
    )

    # Notifications
    if target_status == "resolved":
        # Notify reporter
        if ticket.reporter_id:
            NotificationService.create_notification(
                db=db,
                user_id=ticket.reporter_id,
                type="TICKET_RESOLVED",
                title=f"Support Ticket {ticket.ticket_number} Resolved",
                message=f"Your ticket '{ticket.subject}' has been resolved: {payload.resolution_note}",
            )
        # If SysAdmin resolved an escalated ticket, notify the IT assignee as well
        if current_status == "escalated" and ticket.assigned_to:
            NotificationService.create_notification(
                db=db,
                user_id=ticket.assigned_to,
                type="TICKET_RESOLVED",
                title=f"Escalated Ticket {ticket.ticket_number} Resolved",
                message=f"System Administrator resolved escalated ticket {ticket.ticket_number}: {payload.resolution_note}",
            )
    elif current_status == "resolved" and target_status == "open":
        # Ticket reopened by reporter: notify assigned IT staff
        if ticket.assigned_to:
            NotificationService.create_notification(
                db=db,
                user_id=ticket.assigned_to,
                type="TICKET_REOPENED",
                title=f"Support Ticket {ticket.ticket_number} Reopened",
                message=f"Support ticket {ticket.ticket_number} has been reopened by the reporter.",
            )

    db.commit()
    db.refresh(ticket)
    return enrich_ticket_names(db, ticket)
