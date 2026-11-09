from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class SystemParameter(Base):
    """Global system-wide configuration parameter (US-46)."""
    __tablename__ = "system_parameter"

    key = Column(String(100), primary_key=True)
    value = Column(String(500), nullable=False)
    value_type = Column(String(20), nullable=False, default="string")  # 'string', 'integer', 'boolean', 'json'
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="SET NULL"), nullable=True)
