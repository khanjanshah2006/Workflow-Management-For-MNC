from sqlalchemy import Column, Integer, String, ForeignKey, Enum, UniqueConstraint, CheckConstraint
from app.db.base import Base
from app.models.enums import SkillProficiency


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
