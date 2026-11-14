from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey, Enum, func
from sqlalchemy.sql import expression
from app.db.base import Base
from app.models.enums import MilestoneStatus


class ProjectMilestone(Base):
    __tablename__ = "project_milestone"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("project.project_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    target_date = Column(Date, nullable=False, index=True)
    status = Column(
        Enum(
            MilestoneStatus,
            name="project_milestone_status_enum",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=MilestoneStatus.PENDING,
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_deleted = Column(Boolean, default=False, server_default=expression.false(), nullable=False)

    @property
    def milestone_id(self):
        return self.id

    @property
    def due_date(self):
        return self.target_date


# Alias for backward compatibility with existing imports
Milestone = ProjectMilestone
