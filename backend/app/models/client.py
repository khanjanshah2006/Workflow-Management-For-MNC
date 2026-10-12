from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.models.enums import CommonStatus


class Client(Base):
    __tablename__ = "client"

    client_id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="SET NULL"), unique=True, nullable=True, index=True)
    company_name = Column(String(200), nullable=False)
    contact_person = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    status = Column(Enum(CommonStatus, name="common_status_enum"), default=CommonStatus.ACTIVE, nullable=False)
