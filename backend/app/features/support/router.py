import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.user_account import UserAccount
from app.features.support.schemas import (
    TicketCreateIn,
    TicketOut,
    TicketAssignIn,
    TicketNoteIn,
    TicketStatusUpdateIn,
    TicketActivityOut,
    QueueMetricsOut,
)
from app.features.support import service

router = APIRouter(prefix="/api/v1/support", tags=["Support"])


@router.post(
    "/tickets",
    response_model=TicketOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit support ticket",
    description="Employee submits technical support ticket. Auto-generates sequential ticket number and initial CREATED activity.",
)
def submit_ticket(
    payload: TicketCreateIn,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.create_ticket(db, payload, current_user)


@router.get(
    "/tickets/my",
    response_model=List[TicketOut],
    status_code=status.HTTP_200_OK,
    summary="Get my support tickets",
    description="Returns tickets submitted by the currently authenticated user.",
)
def get_my_tickets(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.get_my_tickets(db, current_user)


@router.get(
    "/tickets/queue/metrics",
    response_model=QueueMetricsOut,
    status_code=status.HTTP_200_OK,
    summary="Get ticket queue metrics",
    description="Aggregated count summary of tickets across statuses for IT triage dashboard.",
)
def get_queue_metrics(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.get_queue_metrics(db, current_user)


@router.get(
    "/tickets",
    response_model=List[TicketOut],
    status_code=status.HTTP_200_OK,
    summary="List and filter triage ticket queue",
    description="IT staff queue view with query filters for status, category, priority, and assigned staff.",
)
def list_tickets(
    status: Optional[str] = Query(None, description="Filter by status: open, in_progress, resolved, escalated"),
    category: Optional[str] = Query(None, description="Filter by category: hardware, software, network, access, other"),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee UUID"),
    priority: Optional[str] = Query(None, description="Filter by priority: LOW, MEDIUM, HIGH, CRITICAL"),
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.list_tickets(
        db=db,
        status_filter=status,
        category=category,
        assigned_to=assigned_to,
        priority=priority,
        skip=skip,
        limit=limit,
        current_user=current_user,
    )


@router.get(
    "/tickets/{id}",
    response_model=TicketOut,
    status_code=status.HTTP_200_OK,
    summary="Get ticket details",
    description="Returns ticket detail including chronological activities. Scoped to owner unless IT Support / Admin.",
)
def get_ticket_detail(
    id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.get_ticket_detail_scoped(db, id, current_user)


@router.put(
    "/tickets/{id}/assign",
    response_model=TicketOut,
    status_code=status.HTTP_200_OK,
    summary="Assign ticket to IT staff",
    description="Assigns ticket to designated IT Support staff member, verifying assignee holds IT_SUPPORT role.",
)
def assign_ticket(
    id: int,
    payload: TicketAssignIn,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.assign_ticket(db, id, payload, current_user)


@router.post(
    "/tickets/{id}/notes",
    response_model=TicketActivityOut,
    status_code=status.HTTP_201_CREATED,
    summary="Append troubleshooting note",
    description="Appends internal troubleshooting note to ticket activity log and updates ticket updated_at.",
)
def add_note(
    id: int,
    payload: TicketNoteIn,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.add_troubleshooting_note(db, id, payload, current_user)


@router.put(
    "/tickets/{id}/status",
    response_model=TicketOut,
    status_code=status.HTTP_200_OK,
    summary="Transition ticket status",
    description="Transitions ticket status (open -> in_progress -> resolved). Dispatches notification to reporter on resolution.",
)
def update_status(
    id: int,
    payload: TicketStatusUpdateIn,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.update_ticket_status(db, id, payload, current_user)
