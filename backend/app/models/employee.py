from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.models.enums import CommonStatus


class Employee(Base):
    __tablename__ = "employee"

    emp_id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="SET NULL"), unique=True, nullable=True, index=True)
    dept_id = Column(Integer, ForeignKey("department.dept_id", ondelete="SET NULL"), nullable=True, index=True)
    emp_code = Column(String(50), unique=True, nullable=False, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    designation = Column(String(100), nullable=False)
    date_of_joining = Column(Date, nullable=False)
    status = Column(Enum(CommonStatus, name="common_status_enum"), default=CommonStatus.ACTIVE, nullable=False)
