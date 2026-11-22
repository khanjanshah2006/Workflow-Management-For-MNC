from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.models.enums import SkillProficiency, SkillRequestAction, SkillRequestStatus


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
    """Skill change proposal submitted by an employee (US-34)."""
    __tablename__ = "skill_change_request"

    request_id = Column(Integer, primary_key=True, autoincrement=True)
    emp_id = Column(Integer, ForeignKey("employee.emp_id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(Enum(SkillRequestAction, name="skill_request_action_enum"), nullable=False)
    skill_id = Column(Integer, ForeignKey("skill.skill_id", ondelete="SET NULL"), nullable=True, index=True)
    proposed_skill_name = Column(String(100), nullable=True)
    proficiency = Column(Enum(SkillProficiency, name="skill_proficiency_enum"), nullable=True)
    years_of_experience = Column(Integer, default=0, nullable=False)
    justification = Column(Text, nullable=True)
    status = Column(
        Enum(SkillRequestStatus, name="skill_request_status_enum"),
        default=SkillRequestStatus.PENDING,
        nullable=False,
        index=True,
    )
    remarks = Column(Text, nullable=True)
    reviewed_by_account_id = Column(UUID(as_uuid=True), ForeignKey("user_account.account_id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @property
    def id(self) -> int:
        return self.request_id
