from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Enum, CheckConstraint, Index
from sqlalchemy import func
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import PriorityLevel, TaskStatus


class Task(Base):
    __tablename__ = "task"

    task_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("project.project_id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("team.team_id", ondelete="CASCADE"), nullable=False, index=True)
    milestone_id = Column(Integer, ForeignKey("project_milestone.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_to = Column(Integer, ForeignKey("employee.emp_id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("employee.emp_id", ondelete="SET NULL"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Enum(PriorityLevel, name="priority_level_enum"), default=PriorityLevel.MEDIUM, nullable=False)
    status = Column(Enum(TaskStatus, name="task_status_enum"), default=TaskStatus.TODO, nullable=False, index=True)
    progress_pct = Column(Integer, default=0, nullable=False)
    start_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    rejection_count = Column(Integer, default=0, nullable=False)
    rejection_feedback = Column(Text, nullable=True)
    blocker_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "due_date IS NULL OR start_date IS NULL OR due_date >= start_date",
            name="chk_task_dates",
        ),
        CheckConstraint(
            "progress_pct >= 0 AND progress_pct <= 100",
            name="chk_task_progress_pct",
        ),
    )

    submissions = relationship(
        "TaskSubmission",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskSubmission.submitted_at.asc()",
    )
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")
    project = relationship("Project", foreign_keys=[project_id])
    milestone = relationship("Milestone", foreign_keys=[milestone_id])
    assignee = relationship("Employee", foreign_keys=[assigned_to])
    creator = relationship("Employee", foreign_keys=[created_by])


class TaskComment(Base):
    __tablename__ = "task_comment"

    comment_id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("task.task_id", ondelete="CASCADE"), nullable=False, index=True)
    author_emp_id = Column(Integer, ForeignKey("employee.emp_id", ondelete="SET NULL"), nullable=True)
    author_name = Column(String(150), nullable=True)
    author_role = Column(String(30), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    edited_at = Column(DateTime(timezone=True), nullable=True)

    task = relationship("Task", back_populates="comments")


class TaskSubmission(Base):
    __tablename__ = "task_submission"

    submission_id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("task.task_id", ondelete="CASCADE"), nullable=False, index=True)
    submitted_by = Column(Integer, ForeignKey("employee.emp_id", ondelete="SET NULL"), nullable=True, index=True)
    remarks = Column(Text, nullable=False)
    file_url = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    task = relationship("Task", back_populates="submissions")
    submitter = relationship("Employee", foreign_keys=[submitted_by])
