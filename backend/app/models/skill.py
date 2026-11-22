from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, UniqueConstraint, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.models.enums import SkillChangeAction, SkillChangeStatus, SkillProficiency


class Skill(Base):
    __tablename__ = "skill"

    skill_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    category = Column(String(100), nullable=False)


class EmployeeSkill(Base):
    __tablename__ = "employee_skill"

    employee_skill_id = Column(Integer, primary_key=True, autoincrement=True)
    emp_id = Column(Integer, ForeignKey("employee.emp_id", ondelete="CASCADE"), nullable=False)
    skill_id = Column(Integer, ForeignKey("skill.skill_id", ondelete="CASCADE"), nullable=False)
    proficiency = Column(Enum(SkillProficiency, name="skill_proficiency_enum"), nullable=False)
    years_of_experience = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("emp_id", "skill_id", name="uq_employee_skill"),
        CheckConstraint("years_of_experience >= 0", name="chk_years_experience"),
    )


class SkillChangeRequest(Base):
    """An employee's request to add, update or remove a skill, pending review (S1-BE-4)."""
    __tablename__ = "skill_change_request"

    request_id = Column(Integer, primary_key=True, autoincrement=True)
    emp_id = Column(Integer, ForeignKey("employee.emp_id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = Column(Integer, ForeignKey("skill.skill_id", ondelete="SET NULL"), nullable=True)
    proposed_skill_name = Column(String(100), nullable=True)
    action = Column(Enum(SkillChangeAction, name="skill_change_action_enum"), nullable=False)
    proficiency = Column(Enum(SkillProficiency, name="skill_proficiency_enum"), nullable=True)
    years_of_experience = Column(Integer, nullable=True)
    justification = Column(Text, nullable=False)
    status = Column(
        Enum(SkillChangeStatus, name="skill_change_status_enum"),
        default=SkillChangeStatus.PENDING,
        server_default=SkillChangeStatus.PENDING.value,
        nullable=False,
    )
    reviewer_account_id = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="SET NULL"), nullable=True)
    review_remarks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "years_of_experience IS NULL OR years_of_experience >= 0",
            name="chk_skill_change_years_experience",
        ),
    )
