from sqlalchemy import Column, Integer, String, Boolean, Text, Date, DateTime, ForeignKey, Enum, CheckConstraint, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import expression
from app.db.base import Base
from app.models.enums import LeaveStatus


class LeaveType(Base):
    __tablename__ = "leave_type"

    leave_type_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    yearly_quota = Column(Integer, nullable=False)
    is_paid = Column(Boolean, default=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, server_default=expression.true(), nullable=False)

    __table_args__ = (
        CheckConstraint("yearly_quota >= 0", name="chk_leave_type_quota"),
    )


class LeaveRequest(Base):
    __tablename__ = "leave_request"

    leave_id = Column(Integer, primary_key=True, autoincrement=True)
    emp_id = Column(Integer, ForeignKey("employee.emp_id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id = Column(Integer, ForeignKey("leave_type.leave_type_id", ondelete="RESTRICT"), nullable=False, index=True)
    reviewed_by_account_id = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="SET NULL"), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    total_days = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(Enum(LeaveStatus, name="leave_status_enum"), default=LeaveStatus.PENDING, nullable=False, index=True)
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_remarks = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="chk_leave_dates"),
        CheckConstraint("total_days > 0", name="chk_leave_total_days"),
        Index("ix_leave_request_emp_dates", "emp_id", "start_date", "end_date"),
    )
