from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.core.roles import IT_STAFF, IT_SUPPORT
from app.models.user_account import UserAccount
from app.features.support.schemas import (
    EscalateTicketRequest,
    SupportTicketResponse,
    TicketCreateIn,
    TicketOut,
    TicketAssignRequest,
    TicketNoteRequest,
    TicketStatusUpdateRequest,
    SupportQueueResponse,
    SupportQueueMetricsResponse,
)
from app.features.support import service
from app.features.support.service import SupportTicketService

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
    "/tickets",
    response_model=SupportQueueResponse,
    status_code=status.HTTP_200_OK,
    summary="IT Support Triage Queue",
    description="Lists support tickets for IT staff with filtering, pagination, and priority-first sorting.",
)
def get_triage_queue(
    status: Optional[str] = Query(None, description="Filter by status (open, in_progress, resolved, closed, escalated)"),
    category: Optional[str] = Query(None, description="Filter by category (hardware, software, network, access, other)"),
    priority: Optional[str] = Query(None, description="Filter by priority (LOW, MEDIUM, HIGH, CRITICAL)"),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee: 'me', 'unassigned', or specific account UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(IT_STAFF)),
):
    return service.get_queue_tickets(
        db=db,
        current_user=current_user,
        status_filter=status,
        category_filter=category,
        priority_filter=priority,
        assigned_to_filter=assigned_to,
        page=page,
        limit=limit,
    )


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
    response_model=SupportQueueMetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Support Queue Metrics",
    description="Returns aggregate counts of tickets by status and unassigned for IT Support dashboard.",
)
def get_queue_metrics(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(IT_STAFF)),
):
    return service.get_queue_metrics(db)


@router.put(
    "/tickets/{id}/assign",
    response_model=TicketOut,
    status_code=status.HTTP_200_OK,
    summary="Assign support ticket",
    description="Assigns ticket to an IT staff member. Automatically moves 'open' tickets to 'in_progress' and notifies assignee.",
)
def assign_support_ticket(
    id: int,
    payload: TicketAssignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(IT_STAFF)),
):
    client_ip = request.client.host if request.client else None
    return service.assign_ticket(
        db=db,
        ticket_id=id,
        payload=payload,
        current_user=current_user,
        ip_address=client_ip,
    )


@router.post(
    "/tickets/{id}/notes",
    response_model=TicketOut,
    status_code=status.HTTP_200_OK,
    summary="Add internal troubleshooting note",
    description="Adds an internal troubleshooting note to the ticket. Hidden from the reporter.",
)
def add_ticket_note(
    id: int,
    payload: TicketNoteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role(IT_STAFF)),
):
    client_ip = request.client.host if request.client else None
    return service.add_ticket_note(
        db=db,
        ticket_id=id,
        payload=payload,
        current_user=current_user,
        ip_address=client_ip,
    )


@router.put(
    "/tickets/{id}/status",
    response_model=TicketOut,
    status_code=status.HTTP_200_OK,
    summary="Update ticket status",
    description="Transition ticket status per state machine. Requires resolution note when resolving. Reporters can reopen resolved tickets.",
)
def update_ticket_status(
    id: int,
    payload: TicketStatusUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    client_ip = request.client.host if request.client else None
    return service.update_ticket_status(
        db=db,
        ticket_id=id,
        payload=payload,
        current_user=current_user,
        ip_address=client_ip,
    )


@router.put(
    "/tickets/{id}/escalate",
    response_model=SupportTicketResponse,
    status_code=status.HTTP_200_OK,
    summary="Escalate support ticket to System Administrator (US-28 / Issue #37)",
    description=(
        "Escalate an unresolved support ticket to System Administrator. "
        "Requires IT_SUPPORT authorization. Ticket status must be 'open' or 'in_progress'. "
        "Records an ESCALATED activity, updates status to 'escalated', and notifies all eligible System Administrators."
    ),
)
def escalate_support_ticket(
    id: int,
    payload: EscalateTicketRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_role([IT_SUPPORT])),
) -> SupportTicketResponse:
    client_ip = request.client.host if request.client else None
    return SupportTicketService.escalate_ticket(
        db=db,
        ticket_id=id,
        payload=payload,
        actor=current_user,
        ip_address=client_ip,
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
