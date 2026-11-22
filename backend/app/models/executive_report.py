from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, ForeignKey, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.models.enums import ReportFormat


class ExecutiveReport(Base):
    """Generated executive report file and its metadata (S7-BE-2)."""
    __tablename__ = "executive_report"

    report_id = Column(Integer, primary_key=True, autoincrement=True)
    generated_by_account_id = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="SET NULL"), nullable=True)
    report_title = Column(String(255), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    report_format = Column(Enum(ReportFormat, name="report_format_enum"), nullable=False)
    include_department_breakdown = Column(Boolean, default=False, nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    file_id = Column(Integer, ForeignKey("stored_file.file_id", ondelete="SET NULL"), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
