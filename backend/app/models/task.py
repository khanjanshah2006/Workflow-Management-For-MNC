from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Enum, CheckConstraint, func
from app.db.base import Base
from app.models.enums import PriorityLevel, TaskStatus


class Task(Base):
    __tablename__ = "task"

    task_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("project.project_id", ondelete="CASCADE"), nullable=False, index=True)
    milestone_id = Column(Integer, ForeignKey("milestone.milestone_id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_to = Column(Integer, ForeignKey("employee.emp_id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("employee.emp_id", ondelete="SET NULL"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Enum(PriorityLevel, name="priority_level_enum"), default=PriorityLevel.MEDIUM, nullable=False)
    status = Column(Enum(TaskStatus, name="task_status_enum"), default=TaskStatus.TODO, nullable=False, index=True)
    start_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("due_date IS NULL OR start_date IS NULL OR due_date >= start_date", name="chk_task_dates"),
    )


class TaskComment(Base):
    __tablename__ = "task_comment"

    comment_id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("task.task_id", ondelete="CASCADE"), nullable=False, index=True)
    author_emp_id = Column(Integer, ForeignKey("employee.emp_id", ondelete="SET NULL"), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    edited_at = Column(DateTime(timezone=True), nullable=True)
