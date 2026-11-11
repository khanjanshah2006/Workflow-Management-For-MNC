from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.rbac import require_role
from app.models.user_account import UserAccount
from app.features.support.schemas import EscalateTicketRequest, SupportTicketResponse
from app.features.support.service import SupportTicketService

router = APIRouter(prefix="/api/v1/support", tags=["Support"])


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

