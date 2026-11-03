from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth import get_current_user
from app.core.rbac import require_role
from app.models.user_account import UserAccount
from app.features.support import service
from app.features.support.schemas import (
    TicketCreateIn,
    TicketAssignIn,
    TicketNoteIn,
    TicketStatusUpdateIn,
    TicketOut,
    TicketActivityOut,
)

router = APIRouter(tags=["IT Support Tickets"])

ALLOWED_TRIAGE_ROLES = ["IT_SUPPORT", "SYSTEM_ADMIN", "IT Support", "System Administrator"]


@router.post(
    "/tickets",
    response_model=TicketOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit support ticket (Employee)",
)
def submit_ticket(
    payload: TicketCreateIn,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Employee submits a new technical support ticket (US-26 / FR-ITS-01).
    Auto-generates sequential ticket_number (e.g. TKT-001) and initial CREATED activity.
    """
    return service.create_ticket(db=db, payload=payload, actor=current_user)


@router.get(
    "/tickets/my",
    response_model=List[TicketOut],
    summary="Get my reported support tickets (Employee)",
)
def get_my_tickets(
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns tickets submitted by the currently authenticated user (US-26).
    """
    return service.get_my_tickets(db=db, actor=current_user)


@router.get(
    "/tickets",
    response_model=List[TicketOut],
    summary="IT staff queue view with query filters",
)
def get_tickets(
    status: Optional[str] = Query(None, description="Filter by status: open, in_progress, resolved, etc."),
    category: Optional[str] = Query(None, description="Filter by category: hardware, software, network, access, etc."),
    assigned_to: Optional[UUID] = Query(None, description="Filter by assigned IT staff UUID"),
    skip: int = Query(0, ge=0, description="Offset pagination skip"),
    limit: int = Query(50, ge=1, le=100, description="Limit records returned"),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Queue view for IT Support staff and System Administrators (US-27).
    Supports query filters: ?status=open&category=hardware&assigned_to=uuid.
    """
    require_role(current_user, allowed=ALLOWED_TRIAGE_ROLES)
    return service.list_tickets(
        db=db,
        status=status,
        category=category,
        assigned_to=assigned_to,
        skip=skip,
        limit=limit,
        actor=current_user,
    )


@router.get(
    "/tickets/{id}",
    response_model=TicketOut,
    summary="Get support ticket details and activity history",
)
def get_ticket_details(
    id: int = Path(..., description="The integer ID of the ticket"),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve full ticket details with chronological activity history (US-26, US-27).
    Enforces that ordinary employees can only view their own tickets (403).
    """
    return service.get_ticket_detail_scoped(db=db, ticket_id=id, actor=current_user)


@router.put(
    "/tickets/{id}/assign",
    response_model=TicketOut,
    summary="Assign ticket to IT staff member",
)
def assign_ticket(
    id: int = Path(..., description="The integer ID of the ticket to assign"),
    payload: TicketAssignIn = ...,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Assign ticket to an IT staff member (US-27).
    Verifies that target assignee holds the IT_SUPPORT role.
    """
    require_role(current_user, allowed=ALLOWED_TRIAGE_ROLES)
    return service.assign_ticket(db=db, ticket_id=id, payload=payload, actor=current_user)


@router.post(
    "/tickets/{id}/notes",
    response_model=TicketActivityOut,
    status_code=status.HTTP_201_CREATED,
    summary="Append troubleshooting note",
)
def add_note(
    id: int = Path(..., description="The integer ID of the ticket"),
    payload: TicketNoteIn = ...,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Append an internal troubleshooting note to ticket_activity (US-27).
    Updates ticket updated_at and records NOTE_ADDED activity entry.
    """
    require_role(current_user, allowed=ALLOWED_TRIAGE_ROLES)
    return service.add_troubleshooting_note(db=db, ticket_id=id, payload=payload, actor=current_user)


@router.put(
    "/tickets/{id}/status",
    response_model=TicketOut,
    summary="Transition ticket status",
)
def update_status(
    id: int = Path(..., description="The integer ID of the ticket"),
    payload: TicketStatusUpdateIn = ...,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Transition ticket status (e.g. open -> in_progress -> resolved) (US-27).
    When status becomes 'resolved', notifies the reporter via notification service.
    """
    require_role(current_user, allowed=ALLOWED_TRIAGE_ROLES)
    return service.update_ticket_status(db=db, ticket_id=id, payload=payload, actor=current_user)
