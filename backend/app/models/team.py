from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Enum, UniqueConstraint, func
from app.db.base import Base
from app.models.enums import TeamStatus


class Team(Base):
    __tablename__ = "team"

    team_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("project.project_id", ondelete="SET NULL"), nullable=True, index=True)
    lead_emp_id = Column(Integer, ForeignKey("employee.emp_id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(Enum(TeamStatus, name="team_status_enum"), default=TeamStatus.ACTIVE, nullable=False)


class TeamMember(Base):
    __tablename__ = "team_member"

    team_member_id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("team.team_id", ondelete="CASCADE"), nullable=False)
    emp_id = Column(Integer, ForeignKey("employee.emp_id", ondelete="CASCADE"), nullable=False, index=True)
    joined_on = Column(Date, server_default=func.current_date(), nullable=False)

    __table_args__ = (
        UniqueConstraint("team_id", "emp_id", name="uq_team_member"),
    )
