"""Idempotent rich demo seed.

Builds on seed_wave3_demo with accounts for every role, more projects, tasks,
leave, tickets, notifications and admin data, so every dashboard has something
to show. Rows are upserted by natural keys, so re-running it refreshes the demo
instead of duplicating it.

Usage (from backend/):
    python scripts/seed_rich_demo.py

All accounts share the password in env SEED_PASSWORD (default: Password@123).
"""
import os
import random
import sys
from datetime import date
from pathlib import Path

if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///wms_dev.db"

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import Session

import app.models  # noqa: F401  Register all models on metadata
from app.core.security import hash_password
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import SkillProficiency, UserType
from app.models.project_manager import ProjectManager
from app.models.skill import EmployeeSkill, Skill
from app.models.system_parameter import SystemParameter
from app.models.user_account import UserAccount
from scripts.seed_wave3_demo import (  # noqa: F401  later phases use the rest
    DEFAULT_PASSWORD,
    _account,
    _business_days,
    _get_or_create,
    seed_wave3_demo,
)

DEPARTMENTS = (
    # key, name, description
    ("data", "Data & Analytics", "Data platforms, warehousing and reporting"),
    ("qe", "Quality Engineering", "Testing, automation and release quality"),
    ("itops", "IT Operations", "Internal IT, support desk and platform administration"),
    ("hr", "Human Resources", "People operations"),
)

PROJECT_MANAGERS = (
    # key, email, name, emp_code, dept key, date_of_joining
    ("daniel", "daniel.okafor@company.com", "Daniel Okafor", "RD-PM-001", "engineering", date(2021, 9, 6)),
    ("mei", "mei.lin@company.com", "Mei Lin", "RD-PM-002", "data", date(2022, 4, 18)),
)

EMPLOYEES = (
    # key, email, name, emp_code, user_type, dept key, designation, date_of_joining
    ("ana", "ana.lopez@company.com", "Ana Lopez", "RD-EMP-001", UserType.TEAM_LEAD, "engineering",
     "Team Lead - Mobile", date(2021, 3, 15)),
    ("marcus", "marcus.chen@company.com", "Marcus Chen", "RD-EMP-002", UserType.TEAM_LEAD, "data",
     "Team Lead - Data Engineering", date(2021, 7, 1)),
    ("grace", "grace.kim@company.com", "Grace Kim", "RD-EMP-003", UserType.TEAM_LEAD, "qe",
     "QA Team Lead", date(2021, 11, 8)),
    ("omar", "omar.haddad@company.com", "Omar Haddad", "RD-EMP-004", UserType.TEAM_LEAD, "engineering",
     "Team Lead - Cloud Platform", date(2022, 2, 14)),
    ("leo", "leo.novak@company.com", "Leo Novak", "RD-EMP-005", UserType.TEAM_LEAD, "engineering",
     "Team Lead - Security", date(2022, 5, 23)),
    ("ravi", "ravi.kumar@company.com", "Ravi Kumar", "RD-EMP-006", UserType.EMPLOYEE, "engineering",
     "Senior Software Engineer", date(2021, 5, 10)),
    ("elena", "elena.petrova@company.com", "Elena Petrova", "RD-EMP-007", UserType.EMPLOYEE, "data",
     "Data Engineer", date(2022, 8, 1)),
    ("tom", "tom.becker@company.com", "Tom Becker", "RD-EMP-008", UserType.EMPLOYEE, "engineering",
     "Mobile Developer", date(2022, 10, 17)),
    ("aisha", "aisha.khan@company.com", "Aisha Khan", "RD-EMP-009", UserType.EMPLOYEE, "qe",
     "QA Engineer", date(2023, 1, 9)),
    ("lucas", "lucas.silva@company.com", "Lucas Silva", "RD-EMP-010", UserType.EMPLOYEE, "engineering",
     "Backend Developer", date(2023, 3, 6)),
    ("hannah", "hannah.wright@company.com", "Hannah Wright", "RD-EMP-011", UserType.EMPLOYEE, "engineering",
     "UI/UX Designer", date(2023, 4, 24)),
    ("yuki", "yuki.tanaka@company.com", "Yuki Tanaka", "RD-EMP-012", UserType.EMPLOYEE, "data",
     "Data Analyst", date(2023, 6, 12)),
    ("carlos", "carlos.mendes@company.com", "Carlos Mendes", "RD-EMP-013", UserType.EMPLOYEE, "engineering",
     "Software Engineer", date(2023, 8, 21)),
    ("fatima", "fatima.zahra@company.com", "Fatima Zahra", "RD-EMP-014", UserType.EMPLOYEE, "engineering",
     "Frontend Developer", date(2023, 10, 2)),
    ("noah", "noah.fischer@company.com", "Noah Fischer", "RD-EMP-015", UserType.EMPLOYEE, "engineering",
     "DevOps Engineer", date(2024, 1, 8)),
    ("priya", "priya.nair@company.com", "Priya Nair", "RD-EMP-016", UserType.EMPLOYEE, "qe",
     "Test Automation Engineer", date(2024, 2, 19)),
    ("ben", "ben.carter@company.com", "Ben Carter", "RD-EMP-017", UserType.EMPLOYEE, "engineering",
     "Security Engineer", date(2024, 4, 15)),
    ("zoe", "zoe.martin@company.com", "Zoe Martin", "RD-EMP-018", UserType.EMPLOYEE, "data",
     "BI Developer", date(2024, 6, 3)),
    ("samir", "samir.patel@company.com", "Samir Patel", "RD-EMP-019", UserType.EMPLOYEE, "engineering",
     "Cloud Engineer", date(2024, 9, 9)),
    ("olivia", "olivia.brown@company.com", "Olivia Brown", "RD-EMP-020", UserType.EMPLOYEE, "qe",
     "QA Analyst", date(2025, 1, 13)),
    ("ethan", "ethan.ross@company.com", "Ethan Ross", "RD-EMP-021", UserType.EMPLOYEE, "engineering",
     "Full Stack Developer", date(2025, 3, 3)),
    ("ivan", "it.support@company.com", "Ivan Petrov", "RD-EMP-022", UserType.IT_SUPPORT, "itops",
     "IT Support Specialist", date(2022, 7, 11)),
    ("nina", "it.helpdesk@company.com", "Nina Shah", "RD-EMP-023", UserType.IT_SUPPORT, "itops",
     "Helpdesk Analyst", date(2024, 11, 4)),
    ("sysadmin", "sysadmin@company.com", "Victor Hale", "RD-EMP-024", UserType.SYSTEM_ADMIN, "itops",
     "Systems Administrator", date(2021, 2, 1)),
    ("admin", "admin@company.com", "Alex Morgan", "RD-EMP-025", UserType.ADMIN, "itops",
     "Platform Administrator", date(2021, 1, 11)),
)

CLIENTS = (
    # key, email, company, contact person
    ("globex", "client.globex@company.com", "Globex", "Hank Morrison"),
    ("initech", "client.initech@company.com", "Initech", "Peter Gibbs"),
    ("umbrella", "client.umbrella@company.com", "Umbrella Health", "Rachel Chambers"),
    ("stark", "client.stark@company.com", "Stark Logistics", "Paula Stark"),
)

SKILLS = (
    # name, category
    ("Python", "Backend"),
    ("Java", "Backend"),
    ("React", "Frontend"),
    ("TypeScript", "Frontend"),
    ("Kotlin", "Mobile"),
    ("Swift", "Mobile"),
    ("SQL", "Data"),
    ("Apache Spark", "Data"),
    ("Power BI", "Data"),
    ("Selenium", "Quality"),
    ("AWS", "Cloud"),
    ("Kubernetes", "DevOps"),
    ("Terraform", "DevOps"),
    ("Penetration Testing", "Security"),
    ("ITIL", "IT Service Management"),
)

B, I, E = SkillProficiency.BEGINNER, SkillProficiency.INTERMEDIATE, SkillProficiency.EXPERT

EMPLOYEE_SKILLS = {
    # person key: ((skill, proficiency, years), ...)
    "ana": (("Kotlin", E, 8), ("Swift", I, 5), ("React", I, 3)),
    "marcus": (("SQL", E, 9), ("Apache Spark", E, 6), ("Python", I, 5)),
    "grace": (("Selenium", E, 7), ("Python", I, 4), ("SQL", I, 4)),
    "omar": (("AWS", E, 7), ("Kubernetes", E, 5), ("Terraform", I, 4)),
    "leo": (("Penetration Testing", E, 8), ("Python", I, 5), ("AWS", I, 3)),
    "ravi": (("Python", E, 7), ("Java", I, 4), ("SQL", I, 5)),
    "elena": (("SQL", E, 5), ("Apache Spark", I, 3), ("Python", I, 3)),
    "tom": (("Kotlin", I, 3), ("Swift", I, 3)),
    "aisha": (("Selenium", I, 3), ("Python", B, 1)),
    "lucas": (("Java", E, 5), ("SQL", I, 3), ("Kubernetes", B, 1)),
    "hannah": (("React", I, 3), ("TypeScript", B, 2)),
    "yuki": (("SQL", I, 3), ("Power BI", I, 2), ("Python", B, 1)),
    "carlos": (("Java", I, 3), ("React", I, 2), ("SQL", B, 2)),
    "fatima": (("React", E, 4), ("TypeScript", E, 4)),
    "noah": (("Kubernetes", I, 3), ("Terraform", I, 2), ("AWS", I, 3)),
    "priya": (("Selenium", E, 4), ("Java", I, 3)),
    "ben": (("Penetration Testing", I, 3), ("Python", I, 2)),
    "zoe": (("Power BI", E, 4), ("SQL", I, 3)),
    "samir": (("AWS", I, 2), ("Terraform", B, 1), ("Python", B, 1)),
    "olivia": (("Selenium", B, 1), ("SQL", B, 1)),
    "ethan": (("React", I, 2), ("Python", I, 2), ("TypeScript", B, 1)),
    "ivan": (("ITIL", E, 6), ("AWS", B, 1)),
    "nina": (("ITIL", I, 2),),
    "sysadmin": (("Kubernetes", E, 8), ("Terraform", E, 6), ("ITIL", I, 5)),
    "admin": (("ITIL", E, 9), ("AWS", I, 4)),
}

SYSTEM_PARAMETERS = (
    # key, value, value_type, description
    ("session_timeout_minutes", "60", "integer", "User session idle timeout in minutes"),
    ("max_upload_size_mb", "25", "integer", "Maximum file attachment size in megabytes"),
    ("allow_client_signup", "false", "boolean", "Whether public clients can register accounts"),
    ("REPEATED_REJECTION_THRESHOLD", "2", "integer",
     "Rejection count at which a task is flagged as repeatedly rejected (US-38)."),
    ("LEAVE_REASSIGN_MAX_ACTIVE_TASKS", "5", "integer",
     "Teammates with fewer active tasks than this are available for leave reassignment."),
)


def _seed_people(db: Session, pw_hash: str) -> dict:
    """Departments, accounts, profiles, skills and system parameters.

    Returns {"depts", "accounts", "people", "pms", "clients"}, each a dict keyed by
    short name. Wave 3 rows are included (people: john, sarah, matrix, kyle,
    employee; pms: priya; clients: acme; accounts: hr, executive).
    """
    depts = {
        "engineering": db.query(Department).filter_by(name="Engineering").one(),
        "delivery": db.query(Department).filter_by(name="Delivery").one(),
    }
    for key, name, description in DEPARTMENTS:
        depts[key] = _get_or_create(db, Department, {"name": name}, description=description)

    people = {
        key: db.query(Employee).filter_by(email=email).one()
        for key, email in (
            ("john", "john.teamlead@company.com"),
            ("sarah", "sarah.connor@company.com"),
            ("matrix", "john.matrix@company.com"),
            ("kyle", "kyle.reese@company.com"),
            ("employee", "employee@company.com"),
        )
    }
    pms = {"priya": db.query(ProjectManager).filter_by(email="pm@company.com").one()}
    clients = {"acme": db.query(Client).filter_by(email="client@acme.com").one()}
    accounts = {
        key: db.query(UserAccount).filter_by(email=email).one()
        for key, email in (("hr", "hr@company.com"), ("executive", "executive@company.com"))
    }

    for key, email, name, code, dept, joined in PROJECT_MANAGERS:
        accounts[key] = _account(db, email, UserType.PM, pw_hash)
        pms[key] = _get_or_create(
            db, ProjectManager, {"email": email},
            account_id=accounts[key].account_id, dept_id=depts[dept].dept_id, emp_code=code,
            full_name=name, date_of_joining=joined,
        )

    for key, email, name, code, user_type, dept, designation, joined in EMPLOYEES:
        accounts[key] = _account(db, email, user_type, pw_hash)
        people[key] = _get_or_create(
            db, Employee, {"email": email},
            account_id=accounts[key].account_id, dept_id=depts[dept].dept_id, emp_code=code,
            full_name=name, designation=designation, date_of_joining=joined,
        )

    # The admin may have enrolled MFA in a previous demo; reset so the shared password works.
    accounts["admin"].is_mfa_enabled = False
    accounts["admin"].mfa_secret = None

    for key, email, company, contact in CLIENTS:
        accounts[key] = _account(db, email, UserType.CLIENT, pw_hash)
        clients[key] = _get_or_create(
            db, Client, {"email": email},
            account_id=accounts[key].account_id, company_name=company, contact_person=contact,
        )

    skills = {name: _get_or_create(db, Skill, {"name": name}, category=category) for name, category in SKILLS}
    for key, entries in EMPLOYEE_SKILLS.items():
        for skill, proficiency, years in entries:
            _get_or_create(
                db, EmployeeSkill, {"emp_id": people[key].emp_id, "skill_id": skills[skill].skill_id},
                proficiency=proficiency, years_of_experience=years,
            )

    # Insert only if missing: admins may have tuned these, never overwrite.
    for key, value, value_type, description in SYSTEM_PARAMETERS:
        if db.get(SystemParameter, key) is None:
            db.add(SystemParameter(key=key, value=value, value_type=value_type, description=description))
    db.flush()

    return {"depts": depts, "accounts": accounts, "people": people, "pms": pms, "clients": clients}


def seed_rich_demo(db: Session, today: date | None = None, password: str | None = None) -> None:
    today = today or date.today()
    password = password or os.getenv("SEED_PASSWORD", DEFAULT_PASSWORD)
    seed_wave3_demo(db, today, password)

    pw_hash = hash_password(password)  # bcrypt is slow: hash once, reuse for every account
    rng = random.Random(42)  # noqa: F841  later phases draw from it

    _seed_people(db, pw_hash)

    db.commit()


def main() -> None:
    from app.db.base import Base
    from app.db.session import SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_rich_demo(db)
        print("Rich demo data seeded. All demo accounts use SEED_PASSWORD (default Password@123).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
