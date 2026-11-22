from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.department import Department
from app.models.team import Team, TeamMember
from app.models.skill import Skill, EmployeeSkill, SkillChangeRequest
from app.models.enums import SkillProficiency, SkillRequestAction, SkillRequestStatus
from app.core import scope


class ProfileRepository:
    """Repository handling database queries for employee profile and skills."""

    @staticmethod
    def get_by_account_id(db: Session, account_id: UUID) -> Optional[Employee]:
        """Fetch employee record by linked user account UUID."""
        return db.query(Employee).filter(Employee.account_id == account_id).first()

    @staticmethod
    def get_department(db: Session, dept_id: int) -> Optional[Department]:
        """Fetch department by department ID."""
        return db.query(Department).filter(Department.dept_id == dept_id).first()

    @staticmethod
    def get_manager_or_lead(db: Session, employee: Employee) -> Optional[Employee]:
        """
        Locate the employee's team lead or manager.
        Checks if the employee is a member of any team with an active lead.
        """
        lead = (
            db.query(Employee)
            .join(Team, Team.lead_emp_id == Employee.emp_id)
            .join(TeamMember, TeamMember.team_id == Team.team_id)
            .filter(TeamMember.emp_id == employee.emp_id, Employee.emp_id != employee.emp_id)
            .first()
        )
        return lead

    @staticmethod
    def get_employee_skills(db: Session, emp_id: int) -> List[Dict[str, Any]]:
        """
        Fetch all skills assigned to an employee with proficiency ratings and experience.
        Performs an inner join between EmployeeSkill and Skill.
        """
        results = (
            db.query(
                Skill.skill_id,
                Skill.name,
                Skill.category,
                EmployeeSkill.proficiency,
                EmployeeSkill.years_of_experience,
            )
            .join(Skill, EmployeeSkill.skill_id == Skill.skill_id)
            .filter(EmployeeSkill.emp_id == emp_id)
            .order_by(Skill.name.asc())
            .all()
        )

        return [
            {
                "skill_id": r.skill_id,
                "name": r.name,
                "category": r.category,
                "proficiency": r.proficiency,
                "years_of_experience": r.years_of_experience,
            }
            for r in results
        ]

    @staticmethod
    def update_employee_contact(
        db: Session,
        employee: Employee,
        phone: Optional[str] = None,
    ) -> Employee:
        """Update employee contact fields in the database."""
        if phone is not None:
            employee.phone = phone

        db.commit()
        db.refresh(employee)
        return employee

    # ── US-34 Skill Proposals Database Access ────────────────────────────────

    @staticmethod
    def get_skill(db: Session, skill_id: int) -> Optional[Skill]:
        """Fetch a Skill by primary key."""
        return db.scalar(select(Skill).where(Skill.skill_id == skill_id))

    @staticmethod
    def get_skill_by_name(db: Session, name: str) -> Optional[Skill]:
        """Fetch a Skill by name (case-insensitive)."""
        clean_name = name.strip()
        return db.scalar(select(Skill).where(func.lower(Skill.name) == func.lower(clean_name)))

    @staticmethod
    def create_skill(db: Session, name: str, category: str = "General") -> Skill:
        """Create and flush a new skill row."""
        skill = Skill(name=name.strip(), category=category)
        db.add(skill)
        db.flush()
        return skill

    @staticmethod
    def get_employee_skill(db: Session, emp_id: int, skill_id: int) -> Optional[EmployeeSkill]:
        """Fetch an EmployeeSkill association."""
        return db.scalar(
            select(EmployeeSkill).where(
                EmployeeSkill.emp_id == emp_id,
                EmployeeSkill.skill_id == skill_id,
            )
        )

    @staticmethod
    def create_employee_skill(
        db: Session,
        emp_id: int,
        skill_id: int,
        proficiency: SkillProficiency,
        years_of_experience: int,
    ) -> EmployeeSkill:
        """Create and flush an EmployeeSkill association."""
        emp_skill = EmployeeSkill(
            emp_id=emp_id,
            skill_id=skill_id,
            proficiency=proficiency,
            years_of_experience=years_of_experience,
        )
        db.add(emp_skill)
        db.flush()
        return emp_skill

    @staticmethod
    def delete_employee_skill(db: Session, emp_skill: EmployeeSkill) -> None:
        """Delete an EmployeeSkill association."""
        db.delete(emp_skill)
        db.flush()

    @staticmethod
    def get_pending_request_for_skill(
        db: Session,
        emp_id: int,
        skill_id: Optional[int] = None,
        proposed_skill_name: Optional[str] = None,
    ) -> Optional[SkillChangeRequest]:
        """
        Check if employee already has a PENDING skill request for the given skill_id
        or proposed_skill_name.
        """
        filters = [
            SkillChangeRequest.emp_id == emp_id,
            SkillChangeRequest.status == SkillRequestStatus.PENDING,
        ]
        if skill_id is not None:
            stmt = select(SkillChangeRequest).where(*filters, SkillChangeRequest.skill_id == skill_id)
            match = db.scalar(stmt)
            if match:
                return match

        if proposed_skill_name is not None and proposed_skill_name.strip():
            clean = proposed_skill_name.strip()
            stmt = select(SkillChangeRequest).where(
                *filters,
                func.lower(SkillChangeRequest.proposed_skill_name) == func.lower(clean),
            )
            match = db.scalar(stmt)
            if match:
                return match

        return None

    @staticmethod
    def create_skill_change_request(
        db: Session,
        emp_id: int,
        action: SkillRequestAction,
        skill_id: Optional[int] = None,
        proposed_skill_name: Optional[str] = None,
        proficiency: Optional[SkillProficiency] = None,
        years_of_experience: int = 0,
        justification: Optional[str] = None,
    ) -> SkillChangeRequest:
        """Create and flush a new SkillChangeRequest."""
        req = SkillChangeRequest(
            emp_id=emp_id,
            action=action,
            skill_id=skill_id,
            proposed_skill_name=proposed_skill_name.strip() if proposed_skill_name else None,
            proficiency=proficiency,
            years_of_experience=years_of_experience,
            justification=justification.strip() if justification else None,
            status=SkillRequestStatus.PENDING,
        )
        db.add(req)
        db.flush()
        db.refresh(req)
        return req

    @staticmethod
    def get_skill_change_request_by_id(
        db: Session, request_id: int
    ) -> Optional[SkillChangeRequest]:
        """Fetch a SkillChangeRequest by ID."""
        return db.scalar(select(SkillChangeRequest).where(SkillChangeRequest.request_id == request_id))

    @staticmethod
    def get_skill_change_request_with_details(
        db: Session, request_id: int
    ) -> Optional[Tuple[SkillChangeRequest, Optional[str], Optional[str]]]:
        """Fetch a SkillChangeRequest by ID with applicant employee name and skill name."""
        stmt = (
            select(SkillChangeRequest, Employee.full_name, Skill.name)
            .join(Employee, Employee.emp_id == SkillChangeRequest.emp_id)
            .outerjoin(Skill, Skill.skill_id == SkillChangeRequest.skill_id)
            .where(SkillChangeRequest.request_id == request_id)
        )
        return db.execute(stmt).first()

    @staticmethod
    def list_my_skill_requests(
        db: Session, emp_id: int
    ) -> List[Tuple[SkillChangeRequest, Optional[str], Optional[str]]]:
        """
        Fetch all skill requests for an employee, newest first.
        Returns tuples of (SkillChangeRequest, employee_name, skill_name).
        """
        stmt = (
            select(SkillChangeRequest, Employee.full_name, Skill.name)
            .join(Employee, Employee.emp_id == SkillChangeRequest.emp_id)
            .outerjoin(Skill, Skill.skill_id == SkillChangeRequest.skill_id)
            .where(SkillChangeRequest.emp_id == emp_id)
            .order_by(SkillChangeRequest.created_at.desc(), SkillChangeRequest.request_id.desc())
        )
        return list(db.execute(stmt).all())

    @staticmethod
    def count_review_requests(
        db: Session,
        status_filter: Optional[SkillRequestStatus] = None,
        allowed_emp_ids: Optional[List[int]] = None,
    ) -> int:
        """Count total skill requests matching status and reviewer scope."""
        stmt = select(func.count(SkillChangeRequest.request_id))
        if status_filter is not None:
            stmt = stmt.where(SkillChangeRequest.status == status_filter)
        if allowed_emp_ids is not None:
            stmt = stmt.where(SkillChangeRequest.emp_id.in_(allowed_emp_ids))
        return int(db.scalar(stmt) or 0)

    @staticmethod
    def list_review_requests(
        db: Session,
        status_filter: Optional[SkillRequestStatus] = None,
        allowed_emp_ids: Optional[List[int]] = None,
        page: int = 1,
        limit: int = 20,
    ) -> List[Tuple[SkillChangeRequest, Optional[str], Optional[str]]]:
        """
        Fetch paginated skill requests for review matching status and reviewer scope.
        Returns tuples of (SkillChangeRequest, employee_name, skill_name).
        """
        stmt = (
            select(SkillChangeRequest, Employee.full_name, Skill.name)
            .join(Employee, Employee.emp_id == SkillChangeRequest.emp_id)
            .outerjoin(Skill, Skill.skill_id == SkillChangeRequest.skill_id)
        )
        if status_filter is not None:
            stmt = stmt.where(SkillChangeRequest.status == status_filter)
        if allowed_emp_ids is not None:
            stmt = stmt.where(SkillChangeRequest.emp_id.in_(allowed_emp_ids))

        stmt = stmt.order_by(SkillChangeRequest.created_at.desc(), SkillChangeRequest.request_id.desc())
        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)
        return list(db.execute(stmt).all())
