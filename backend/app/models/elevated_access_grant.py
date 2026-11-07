from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class ElevatedAccessGrant(Base):
    """Time-bound temporary role privilege grant (US-45)."""
    __tablename__ = "elevated_access_grant"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="CASCADE"), nullable=False, index=True)
    granted_role = Column(String(50), nullable=False)
    granted_by = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="SET NULL"), nullable=False)
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    reason = Column(Text, nullable=False)
