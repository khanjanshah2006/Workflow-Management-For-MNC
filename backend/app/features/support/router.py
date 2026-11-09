from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.user_account import UserAccount
from app.features.support.schemas import TicketCreateIn, TicketOut
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
