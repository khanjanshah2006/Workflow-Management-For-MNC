"""Internal scheduled jobs router (S9, US-15).

Provides secure endpoints for recurring system jobs (e.g. overdue task sweeps)
triggered by GitHub Actions cron workflows rather than an in-container cron daemon.
"""
import hmac
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.features.tasks.overdue import OverdueService

router = APIRouter(prefix="/api/v1/internal/jobs", tags=["Internal Jobs"])


@router.post(
    "/overdue-sweep",
    status_code=status.HTTP_200_OK,
    summary="Trigger scheduled overdue task sweep (US-15, S9)",
    description=(
        "Internal endpoint called by external schedulers (GitHub Actions). "
        "Requires secret header X-Job-Token matching JOB_TOKEN. "
        "Returns 404 when JOB_TOKEN is unset so the route remains hidden."
    ),
)
def run_overdue_sweep_job(
    request: Request,
    x_job_token: Optional[str] = Header(None, alias="X-Job-Token"),
    db: Session = Depends(get_db),
):
    """Execute overdue task sweep and notification dispatch without a logged-in user."""
    # Returns 404 when JOB_TOKEN is unset, so the route stays hidden unless configured.
    configured_token = settings.job_token
    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )

    # Requires the header X-Job-Token, compared to JOB_TOKEN with hmac.compare_digest on encoded bytes.
    if not x_job_token or not hmac.compare_digest(
        x_job_token.encode("utf-8"), configured_token.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Job-Token",
        )

    today = date.today()
    client_ip = request.client.host if request.client else None

    # Calls the same service as /tasks/check-overdue and returns {flagged, notified}.
    sweep_result = OverdueService.run_sweep(
        db=db,
        actor=None,
        today=today,
        ip_address=client_ip,
    )

    return {
        "flagged": sweep_result.get("newly_flagged_overdue", 0),
        "notified": sweep_result.get("notifications_sent", 0),
    }
