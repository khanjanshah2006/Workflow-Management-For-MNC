from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.models.enums import AuditAction


class AuditLog(Base):
    __tablename__ = "audit_log"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(Enum(AuditAction, name="audit_action_enum"), nullable=False)
    entity_name = Column(String(100), nullable=False, index=True)
    entity_ref_id = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
