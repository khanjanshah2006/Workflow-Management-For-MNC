from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, CheckConstraint, func
from app.db.base import Base
from app.models.enums import DeliverableStatus, FeedbackDecision


class Deliverable(Base):
    __tablename__ = "deliverable"

    deliverable_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("project.project_id", ondelete="CASCADE"), nullable=False, index=True)
    milestone_id = Column(Integer, ForeignKey("milestone.milestone_id", ondelete="SET NULL"), nullable=True)
    submitted_by = Column(Integer, ForeignKey("employee.emp_id", ondelete="SET NULL"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    file_url = Column(Text, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(Enum(DeliverableStatus, name="deliverable_status_enum"), default=DeliverableStatus.SUBMITTED, nullable=False)


class DeliverableFeedback(Base):
    __tablename__ = "deliverable_feedback"

    feedback_id = Column(Integer, primary_key=True, autoincrement=True)
    deliverable_id = Column(Integer, ForeignKey("deliverable.deliverable_id", ondelete="CASCADE"), nullable=False, index=True)
    given_by_client_id = Column(Integer, ForeignKey("client.client_id", ondelete="CASCADE"), nullable=False)
    decision = Column(Enum(FeedbackDecision, name="feedback_decision_enum"), nullable=False)
    comments = Column(Text, nullable=True)
    rating = Column(Integer, nullable=False)
    given_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="chk_feedback_rating"),
    )
