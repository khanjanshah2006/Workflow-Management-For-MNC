from sqlalchemy import Column, Integer, String, Text, Date, ForeignKey, Enum, CheckConstraint, func
from app.db.base import Base
from app.models.enums import PriorityLevel, ProjectStatus


class Project(Base):
    __tablename__ = "project"

    project_id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("client.client_id", ondelete="RESTRICT"), nullable=False, index=True)
    pm_id = Column(Integer, ForeignKey("project_manager.pm_id", ondelete="RESTRICT"), nullable=False, index=True)
    project_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    priority = Column(Enum(PriorityLevel, name="priority_level_enum"), default=PriorityLevel.MEDIUM, nullable=False)
    status = Column(Enum(ProjectStatus, name="project_status_enum"), default=ProjectStatus.PLANNED, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="chk_project_dates"),
    )


class ProjectAssignment(Base):
    __tablename__ = "project_assignment"

    assignment_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("project.project_id", ondelete="CASCADE"), nullable=False, index=True)
    emp_id = Column(Integer, ForeignKey("employee.emp_id", ondelete="CASCADE"), nullable=False, index=True)
    role_in_project = Column(String(100), nullable=False)
    assigned_on = Column(Date, server_default=func.current_date(), nullable=False)
    released_on = Column(Date, nullable=True)

    __table_args__ = (
        CheckConstraint("released_on IS NULL OR released_on >= assigned_on", name="chk_assignment_dates"),
    )
