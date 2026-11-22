from sqlalchemy import Column, Integer, String, LargeBinary, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class StoredFile(Base):
    """A file kept in the database (bytea) rather than on local disk (S9-BE-5)."""
    __tablename__ = "stored_file"

    file_id = Column(Integer, primary_key=True, autoincrement=True)
    purpose = Column(String(40), nullable=False)  # e.g. TASK_SUBMISSION, EXECUTIVE_REPORT
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    data = Column(LargeBinary, nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
