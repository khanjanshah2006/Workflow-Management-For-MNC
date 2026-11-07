from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, synonym
from app.db.base import Base


class SupportTicket(Base):
    __tablename__ = "support_ticket"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = synonym("id")
    ticket_number = Column(String(50), unique=True, nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    title = synonym("subject")
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, default="other", index=True)
    priority = Column(String(20), nullable=False, default="MEDIUM")
    status = Column(String(30), nullable=False, default="open", index=True)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    reporter = relationship("UserAccount", foreign_keys=[reporter_id], backref="reported_tickets")
    assignee = relationship("UserAccount", foreign_keys=[assigned_to], backref="assigned_tickets")
    activities = relationship(
        "TicketActivity",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketActivity.created_at.asc()",
    )


class TicketActivity(Base):
    __tablename__ = "ticket_activity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = synonym("id")
    ticket_id = Column(Integer, ForeignKey("support_ticket.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="SET NULL"), nullable=True, index=True)
    performed_by = synonym("actor_id")
    action = Column(String(50), nullable=False)  # CREATED, ASSIGNED, NOTE_ADDED, STATUS_CHANGED, ESCALATED
    activity_type = synonym("action")
    note = Column(Text, nullable=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    ticket = relationship("SupportTicket", back_populates="activities")
    performer = relationship("UserAccount", foreign_keys=[actor_id])
