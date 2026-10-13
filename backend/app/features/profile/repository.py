from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.department import Department
from app.models.team import Team, TeamMember
from app.models.skill import Skill, EmployeeSkill


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
