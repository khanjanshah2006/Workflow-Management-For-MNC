import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql.expression import false

from app.db.base import Base


class Notification(Base):
    """
    Centralised notification record (US-19, S2-BE-4).

    Ownership is keyed on account_id (FK → user_account.account_id) to match
    every other model in this codebase.  The PK is a UUID so records are safe
    to create across concurrent workers without a DB round-trip for the next
    integer sequence value.

    Compound index on (account_id, is_read) supports the common query pattern:
        WHERE account_id = :uid AND is_read = false   -- unread-first fetch
    without a full-table scan.
    """

    __tablename__ = "notification"

    # ── Primary key ──────────────────────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    # ── Ownership ─────────────────────────────────────────────────────────────
    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_account.account_id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Payload ───────────────────────────────────────────────────────────────
    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    link = Column(String(255), nullable=True)

    # ── State ─────────────────────────────────────────────────────────────────
    # server_default=false() keeps the DB column consistent even for rows
    # inserted via raw SQL (migrations, seeds) that omit the column.
    is_read = Column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    __table_args__ = (
        # Covers the primary query shape:
        #   WHERE account_id = ? AND is_read = false   ORDER BY created_at DESC
        Index("ix_notification_account_id_is_read", "account_id", "is_read"),
    )
