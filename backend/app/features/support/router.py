from typing import List
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.models.user_account import UserAccount
from app.features.support.schemas import (
    EscalateTicketRequest,
    SupportTicketResponse,
    TicketCreateIn,
    TicketOut,
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
    current_user: UserAccount = Depends(require_role(["IT_SUPPORT"])),
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
