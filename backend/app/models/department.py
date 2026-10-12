from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.db.base import Base


class Department(Base):
    __tablename__ = "department"

    dept_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
