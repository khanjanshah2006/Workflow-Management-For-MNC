from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey, func, text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class SystemBackupLog(Base):
    __tablename__ = "system_backup_log"
    __table_args__ = (
        CheckConstraint(
            "status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')",
            name="ck_system_backup_log_status",
        ),
    )

    backup_id = Column(Integer, primary_key=True, autoincrement=True)
    triggered_by_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_account.account_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    backup_type = Column(String(50), default="ON_DEMAND", nullable=False)
    # A failed backup may not have produced a file.
    file_path = Column(String(500), nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    status = Column(String(50), default="IN_PROGRESS", server_default=text("'IN_PROGRESS'"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
