from sqlalchemy import Column, Integer, String, Text, Date, ForeignKey, Enum
from app.db.base import Base
from app.models.enums import MilestoneStatus


class Milestone(Base):
    __tablename__ = "milestone"

    milestone_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("project.project_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=False)
    status = Column(Enum(MilestoneStatus, name="milestone_status_enum"), default=MilestoneStatus.PENDING, nullable=False)
