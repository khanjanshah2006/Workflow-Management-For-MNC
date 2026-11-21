"""Idempotent rich demo seed.

Builds on seed_wave3_demo with accounts for every role, more projects, tasks,
leave, tickets, notifications and admin data, so every dashboard has something
to show. Rows are upserted by natural keys, so re-running it refreshes the demo
instead of duplicating it.

Usage (from backend/):
    python scripts/seed_rich_demo.py

All accounts share the password in env SEED_PASSWORD (default: Password@123).
"""
import json
import os
import random
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///wms_dev.db"

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import Session

import app.models  # noqa: F401  Register all models on metadata
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import (
    AuditAction,
    LeaveStatus,
    MilestoneStatus,
    PriorityLevel,
    ProjectStatus,
    SkillProficiency,
    TaskStatus,
    TeamStatus,
    UserType,
)
from app.models.leave import LeaveRequest, LeaveType
from app.models.milestone import ProjectMilestone
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.skill import EmployeeSkill, Skill
from app.models.system_parameter import SystemParameter
from app.models.task import Task, TaskComment, TaskSubmission
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount
from scripts.seed_wave3_demo import (  # noqa: F401  later phases use the rest
    DEFAULT_PASSWORD,
    PROJECT_CODE,
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


TEAMS = (
    # key, name, project key, lead key, status, members. Each lead's ACTIVE team is created
    # before any DISBANDED team they lead: TaskRepository.get_team_for_employee takes the first one.
    ("phoenix", "Phoenix Squad", "phoenix", "ana", TeamStatus.ACTIVE, ("tom", "hannah", "ethan", "ravi")),
    ("atlas", "Atlas Data Team", "atlas", "marcus", TeamStatus.ACTIVE, ("elena", "yuki", "zoe")),
    ("orion", "Orion QA Team", "orion", "grace", TeamStatus.ACTIVE, ("aisha", "priya", "olivia")),
    ("helios", "Helios Cloud Team", "helios", "omar", TeamStatus.ACTIVE, ("noah", "samir")),
    ("zephyr", "Zephyr Security Team", "zephyr", "leo", TeamStatus.ACTIVE, ("ben", "lucas")),
    ("vega", "Vega Portal Team", "vega", "marcus", TeamStatus.DISBANDED, ("zoe", "yuki")),
    ("lyra", "Lyra HR Team", "lyra", "ana", TeamStatus.DISBANDED, ("hannah", "ethan")),
)

ASSIGNMENTS = (
    # project key, person key, role, released_on offset from today (None = still staffed)
    ("alpha", "carlos", "Developer", None),
    ("alpha", "fatima", "Developer", None),
    ("alpha", "ravi", "Integration Consultant", None),
    ("alpha", "priya", "Test Automation", None),
    ("phoenix", "ana", "Team Lead", None),
    ("phoenix", "tom", "Mobile Developer", None),
    ("phoenix", "hannah", "UI/UX Designer", None),
    ("phoenix", "ethan", "Developer", None),
    ("phoenix", "ravi", "Backend Developer", None),
    ("phoenix", "noah", "DevOps Engineer", None),
    ("phoenix", "aisha", "QA Engineer", None),
    ("atlas", "marcus", "Team Lead", None),
    ("atlas", "elena", "Data Engineer", None),
    ("atlas", "yuki", "Data Analyst", None),
    ("atlas", "zoe", "BI Developer", None),
    ("atlas", "ravi", "Data Integration", None),
    ("atlas", "olivia", "Data QA", None),
    ("orion", "grace", "Team Lead", None),
    ("orion", "aisha", "QA Engineer", None),
    ("orion", "priya", "Test Automation", None),
    ("orion", "olivia", "QA Analyst", None),
    ("helios", "omar", "Team Lead", None),
    ("helios", "noah", "DevOps Engineer", None),
    ("helios", "samir", "Cloud Engineer", None),
    ("zephyr", "leo", "Team Lead", None),
    ("zephyr", "ben", "Security Engineer", None),
    ("zephyr", "lucas", "Backend Developer", None),
    ("zephyr", "ravi", "Backend Developer", None),
    ("zephyr", "omar", "Cloud Security Advisor", None),
    ("nova", "ravi", "Solution Architect", None),
    ("nova", "hannah", "UI/UX Designer", None),
    ("nova", "lucas", "Backend Developer", None),
    ("nova", "fatima", "Frontend Developer", None),
    ("vega", "marcus", "Team Lead", None),
    ("vega", "yuki", "Data Analyst", None),
    ("vega", "zoe", "BI Developer", -90),
    ("lyra", "ana", "Team Lead", None),
    ("lyra", "ethan", "Developer", None),
    ("lyra", "hannah", "UI/UX Designer", -120),
)


def _seed_projects(db: Session, today: date, ctx: dict) -> dict:
    """Projects in every status, milestones, teams and staffing.

    Returns {"projects", "milestones", "teams"} keyed by short name, including the
    wave3 rows: projects["alpha"], teams["alpha"] and milestones alpha_sprint1,
    alpha_sprint2, alpha_uat.
    """
    people, pms, clients = ctx["people"], ctx["pms"], ctx["clients"]
    now = datetime.now(timezone.utc)
    next_monday = today + timedelta(days=7 - today.weekday())

    def day(offset: int) -> date:
        return today + timedelta(days=offset)

    alpha = db.query(Project).filter_by(project_code=PROJECT_CODE).one()
    projects = {"alpha": alpha}
    for key, code, name, pm, client, start, end, priority, status, visible, description in (
        ("phoenix", "PHOENIX-MOB", "Phoenix Mobile App", "priya", "globex", -90, 60,
         PriorityLevel.HIGH, ProjectStatus.ACTIVE, True, "Customer-facing mobile app for Globex."),
        ("atlas", "ATLAS-DWH", "Atlas Data Warehouse", "mei", "initech", -120, 90,
         PriorityLevel.HIGH, ProjectStatus.ACTIVE, True, "Consolidate Initech reporting into one warehouse."),
        ("orion", "ORION-QA", "Orion Test Automation", "daniel", "stark", -60, 75,
         PriorityLevel.MEDIUM, ProjectStatus.ACTIVE, False, "Automated regression suite for Stark's TMS."),
        ("helios", "HELIOS-CLOUD", "Helios Cloud Migration", "daniel", "umbrella", -150, 120,
         PriorityLevel.MEDIUM, ProjectStatus.ON_HOLD, False, "Move Umbrella Health workloads to the cloud."),
        ("zephyr", "ZEPHYR-SEC", "Zephyr Security Hardening", "daniel", "umbrella", -45, 50,
         PriorityLevel.CRITICAL, ProjectStatus.ACTIVE, False, "Security audit and remediation programme."),
        ("nova", "NOVA-CRM", "Nova CRM Rollout", "priya", "initech", 21, 200,
         PriorityLevel.MEDIUM, ProjectStatus.PLANNED, False, "CRM rollout for Initech's sales teams."),
        ("vega", "VEGA-PORTAL", "Vega Customer Portal", "mei", "globex", -300, -30,
         PriorityLevel.MEDIUM, ProjectStatus.COMPLETED, True, "Self-service customer portal for Globex."),
        ("lyra", "LYRA-HR", "Lyra HR Suite", "priya", "stark", -200, -120,
         PriorityLevel.LOW, ProjectStatus.CANCELLED, False, "HR suite for Stark Logistics, cancelled by the client."),
    ):
        projects[key] = _get_or_create(
            db, Project, {"project_code": code},
            client_id=clients[client].client_id, pm_id=pms[pm].pm_id, name=name, description=description,
            start_date=day(start), end_date=day(end), priority=priority, status=status,
            is_team_visible_to_client=visible,
        )

    milestones = {
        key: db.query(ProjectMilestone).filter_by(project_id=alpha.project_id, title=title).one()
        for key, title in (
            ("alpha_sprint1", "Sprint 1 Deliverables"),
            ("alpha_sprint2", "Sprint 2 Deliverables"),
            ("alpha_uat", "UAT Sign-off"),
        )
    }
    # At-risk (pending, due today..today+3) once Phase 3 attaches open tasks:
    # phoenix_beta and zephyr_pentest. atlas_reports falls inside next week (Elena's leave).
    done, pending = MilestoneStatus.COMPLETED, MilestoneStatus.PENDING
    for key, project, title, target, status in (
        ("phoenix_design", "phoenix", "UX Design Sign-off", day(-40), done),
        ("phoenix_alpha", "phoenix", "Alpha Build", day(-12), done),
        ("phoenix_beta", "phoenix", "Beta Release", day(2), pending),
        ("phoenix_launch", "phoenix", "App Store Launch", day(35), pending),
        ("atlas_model", "atlas", "Data Model Approved", day(-50), done),
        ("atlas_ingest", "atlas", "Source Ingestion Complete", day(-6), pending),
        ("atlas_reports", "atlas", "Executive Reports Live", next_monday + timedelta(days=2), pending),
        ("atlas_cutover", "atlas", "Production Cutover", day(60), pending),
        ("orion_strategy", "orion", "Test Strategy Approved", day(-30), done),
        ("orion_regression", "orion", "Regression Suite Automated", day(6), pending),
        ("orion_perf", "orion", "Performance Baseline", day(20), pending),
        ("orion_uat", "orion", "UAT Support Complete", day(50), pending),
        ("helios_assessment", "helios", "Cloud Readiness Assessment", day(-70), done),
        ("helios_landing", "helios", "Landing Zone Ready", day(-15), pending),
        ("helios_wave1", "helios", "Wave 1 Migration", day(40), pending),
        ("zephyr_kickoff", "zephyr", "Security Audit Kickoff", day(-25), done),
        ("zephyr_pentest", "zephyr", "Penetration Test Report", day(1), pending),
        ("zephyr_remediation", "zephyr", "Critical Findings Remediated", day(12), pending),
        ("zephyr_compliance", "zephyr", "Compliance Certification", day(45), pending),
        ("nova_kickoff", "nova", "Project Kickoff", day(21), pending),
        ("nova_requirements", "nova", "Requirements Baseline", day(45), pending),
        ("vega_design", "vega", "Portal Design Approved", day(-200), done),
        ("vega_golive", "vega", "Portal Go-Live", day(-90), done),
        ("vega_handover", "vega", "Support Handover", day(-35), done),
        ("lyra_discovery", "lyra", "Discovery Workshop", day(-170), done),
    ):
        milestones[key] = _get_or_create(
            db, ProjectMilestone, {"project_id": projects[project].project_id, "title": title},
            target_date=target, status=status, is_deleted=False,
            completed_at=now - (today - target) if status is done else None,
        )

    alpha_team = db.query(Team).filter_by(name="Alpha Core Team").one()
    teams = {"alpha": alpha_team}
    for member in ("carlos", "fatima"):
        _get_or_create(db, TeamMember, {"team_id": alpha_team.team_id, "emp_id": people[member].emp_id})
    for key, name, project, lead, status, members in TEAMS:
        teams[key] = _get_or_create(
            db, Team, {"name": name},
            project_id=projects[project].project_id, lead_emp_id=people[lead].emp_id, status=status,
            description=f"Delivery team for {projects[project].name}.",
        )
        for member in members:
            _get_or_create(db, TeamMember, {"team_id": teams[key].team_id, "emp_id": people[member].emp_id})

    # assigned_on is set explicitly so released_on >= assigned_on holds on every run.
    for project, person, role, released in ASSIGNMENTS:
        _get_or_create(
            db, ProjectAssignment, {"project_id": projects[project].project_id, "emp_id": people[person].emp_id},
            role_in_project=role, assigned_on=projects[project].start_date,
            released_on=None if released is None else day(released),
        )

    return {"projects": projects, "milestones": milestones, "teams": teams}


TODO, IP, REV, DONE, BLK, REJ = (
    TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW,
    TaskStatus.DONE, TaskStatus.BLOCKED, TaskStatus.REJECTED,
)


def T(title, status, due, ms=None, who=None, rej=0, nw=False):
    """One task row. `due` is days from today, or from next Monday when nw=True.
    `who` fixes the assignee (else rng picks a team member). `rej` is the rejection
    count; an IN_REVIEW task with rej > 0 was resubmitted after its last rejection."""
    return title, status, due, ms, who, rej, nw


TASKS = {
    "alpha": (
        T("Vendor Master Data Migration", REV, -1, who="carlos"),
        T("Purchase Order Approval Workflow", REV, 4, who="fatima", rej=1),
        T("GL Account Mapping Script", REV, 6),
        T("Inventory Valuation Report", IP, 9),
        T("Role-Based Menu Permissions", IP, -10),
        T("Tax Code Configuration", REJ, 3, rej=2),
    ),
    "phoenix": (
        T("Onboarding Screen Designs", DONE, -45, ms="phoenix_design", who="hannah"),
        T("Design System Tokens", DONE, -42, ms="phoenix_design"),
        T("User Login Flow", DONE, -20, ms="phoenix_alpha"),
        T("Push Notification Service", DONE, -15, ms="phoenix_alpha"),
        T("Alpha Build Pipeline", DONE, -13, ms="phoenix_alpha"),
        T("Beta Tester Invite Emails", DONE, -2, ms="phoenix_beta"),
        T("Crash Reporting Integration", IP, 1, ms="phoenix_beta"),
        T("Beta Feedback Form", IP, 2, ms="phoenix_beta"),
        T("In-App Purchase Sandbox Tests", REV, 2, ms="phoenix_beta"),
        T("Accessibility Audit Fixes", IP, -4),
        T("Dark Mode Support", TODO, -2),
        T("Profile Photo Upload", REJ, -1, rej=2),
        T("Deep Link Routing", BLK, -3),
        # Phase 4: Ravi's approved leave covers the week after next.
        T("Offline Data Sync", TODO, 8, who="ravi", nw=True),
        T("Payment Gateway SDK Upgrade", IP, 9, who="ravi", nw=True),
        T("Order History API", TODO, 10, who="ravi", nw=True),
        T("App Store Screenshots", TODO, 30, ms="phoenix_launch"),
        T("Release Notes Draft", TODO, 33, ms="phoenix_launch"),
        T("Performance Profiling", IP, 10),
        T("Analytics Event Tracking", REV, 5, rej=1),
        T("Biometric Login", REJ, 8, rej=1),
        T("Localization (ES, FR)", BLK, 12),
    ),
    "atlas": (
        T("Star Schema Design", DONE, -55, ms="atlas_model"),
        T("Source System Inventory", DONE, -52, ms="atlas_model"),
        T("Data Dictionary", DONE, -48, ms="atlas_model"),
        T("CRM Source Connector", DONE, -20, ms="atlas_ingest"),
        T("ERP Extract Jobs", IP, -8, ms="atlas_ingest"),
        T("Incremental Load Logic", BLK, -7, ms="atlas_ingest"),
        T("Data Quality Rules", REJ, -5, ms="atlas_ingest", rej=3),
        T("Finance Feed Ingestion", IP, -3, ms="atlas_ingest"),
        # Phase 4: Elena's pending leave covers next week.
        T("Sales Dashboard Dataset", IP, 1, ms="atlas_reports", who="elena", nw=True),
        T("Revenue KPI Definitions", TODO, 3, who="elena", nw=True),
        T("Executive Report Layouts", REV, 2, ms="atlas_reports", who="zoe", nw=True),
        T("Row-Level Security", TODO, 15),
        T("Warehouse Cost Monitoring", TODO, 25),
        T("Cutover Runbook", TODO, 50, ms="atlas_cutover"),
        T("Historical Backfill", IP, 20),
        T("Reconciliation Queries", REV, 4),
        T("Data Lineage Docs", IP, -10),
        T("Partitioning Strategy", REJ, 7, rej=1),
    ),
    "orion": (
        T("Test Strategy Document", DONE, -32, ms="orion_strategy"),
        T("Test Environment Setup", DONE, -31, ms="orion_strategy"),
        T("Smoke Test Suite", IP, -12),
        T("Shipment Booking Regression Tests", IP, 5, ms="orion_regression"),
        T("Carrier API Contract Tests", IP, 4, ms="orion_regression"),
        T("Invoice Module Regression Tests", REV, 3, ms="orion_regression", rej=2),
        T("Flaky Test Triage", BLK, -2),
        T("Test Data Generator", IP, -5),
        T("CI Test Parallelisation", REJ, -1, rej=1),
        T("Load Test Scripts", TODO, 15, ms="orion_perf"),
        T("Performance Baseline Report", TODO, 19, ms="orion_perf"),
        T("UAT Test Cases", TODO, 40, ms="orion_uat"),
        T("Defect Triage Dashboard", REV, 2),
        T("Mobile Device Matrix", TODO, -3),
        T("Accessibility Test Pack", IP, 9),
        T("Test Coverage Report", DONE, -8),
    ),
    "helios": (
        T("Application Portfolio Assessment", DONE, -72, ms="helios_assessment"),
        T("Network Topology Design", BLK, -18, ms="helios_landing"),
        T("IAM Baseline Policies", BLK, -16, ms="helios_landing"),
        T("VPC and Subnet Provisioning", IP, -15, ms="helios_landing"),
        T("Logging and Monitoring Stack", TODO, -10),
        T("Backup Policy Definition", REJ, -8, rej=2),
        T("Cost Estimation Model", REV, -6),
        T("Database Migration Plan", TODO, 30, ms="helios_wave1"),
        T("Wave 1 App Inventory", TODO, 35, ms="helios_wave1"),
        T("DR Runbook", IP, -4),
        T("Container Registry Setup", IP, 10),
        T("Cloud Governance Charter", TODO, 20),
    ),
    "zephyr": (
        T("Asset Inventory and Scoping", DONE, -27, ms="zephyr_kickoff"),
        T("Threat Model Workshop", DONE, -26, ms="zephyr_kickoff"),
        T("Web App Vulnerability Scan", DONE, -3, ms="zephyr_pentest"),
        T("External Pen Test", IP, 1, ms="zephyr_pentest"),
        T("Pen Test Findings Report", REV, 1, ms="zephyr_pentest"),
        T("Patch Critical CVEs", IP, 10, ms="zephyr_remediation"),
        T("Rotate Service Credentials", TODO, 11, ms="zephyr_remediation"),
        T("WAF Rule Tuning", BLK, 8, ms="zephyr_remediation"),
        T("MFA Enforcement Rollout", REJ, -2, rej=2),
        T("SIEM Alert Rules", IP, -6),
        T("Secrets Vault Migration", REJ, 5, rej=1),
        T("Security Awareness Training", TODO, 20),
        T("ISO 27001 Evidence Pack", TODO, 40, ms="zephyr_compliance"),
        T("Firewall Rule Review", IP, -1),
        T("Endpoint Hardening Baseline", REV, 3),
        T("Incident Response Playbook", BLK, -4),
    ),
    "vega": (
        T("Portal Wireframes", DONE, -210, ms="vega_design"),
        T("Customer Login Integration", DONE, -150, ms="vega_golive"),
        T("Account Dashboard", DONE, -130, ms="vega_golive"),
        T("Invoice Download Feature", DONE, -120, ms="vega_golive"),
        T("Support Ticket Widget", DONE, -110, ms="vega_golive"),
        T("Portal Analytics Setup", DONE, -100, ms="vega_golive"),
        T("Go-Live Checklist", DONE, -92, ms="vega_golive"),
        T("Hypercare Fixes", DONE, -60, ms="vega_handover"),
        T("Knowledge Base Articles", DONE, -45, ms="vega_handover"),
        T("Support Handover Session", DONE, -36, ms="vega_handover"),
    ),
    # Stopped when the project was cancelled (today-120); CANCELLED projects never count as overdue.
    "lyra": (
        T("HR Discovery Interviews", DONE, -175, ms="lyra_discovery"),
        T("Current-State Process Maps", DONE, -172, ms="lyra_discovery"),
        T("Employee Data Model", DONE, -150),
        T("Leave Module Prototype", DONE, -135),
        T("Payroll Integration Spike", IP, -125),
        T("Org Chart Viewer", IP, -115),
        T("Benefits Enrollment Screens", TODO, -105),
        T("HRIS Vendor Data Export", BLK, -122),
    ),
}

BLOCKER_REASONS = (
    "Waiting on the client to provide API credentials.",
    "Blocked by an open infrastructure ticket with IT Operations.",
    "Upstream dependency has not been merged yet.",
    "Awaiting security sign-off before proceeding.",
    "Shared test environment is down; waiting on a fix.",
    "Waiting on a vendor licence renewal.",
)

REJECTION_FEEDBACK = (
    "Edge cases from the acceptance criteria are not covered.",
    "Unit tests are missing for the new error paths.",
    "Output does not match the agreed specification.",
    "Naming and structure need cleanup before this can merge.",
    "Performance regresses noticeably on the large dataset.",
    "Documentation for the change is incomplete.",
    "Validation messages are inconsistent with the style guide.",
    "Please address the open review comments first.",
)

COMMENTS = (
    # task title, author ("lead" | "assignee" | "pm"), content
    ("Vendor Master Data Migration", "assignee", "Migrated 12k vendor rows; 40 duplicates flagged for review."),
    ("Vendor Master Data Migration", "lead", "Thanks, reviewing the duplicate list today."),
    ("Purchase Order Approval Workflow", "lead", "Second approval tier is still skipped for amounts over 50k."),
    ("Purchase Order Approval Workflow", "assignee", "Fixed the threshold check and added tests, resubmitted."),
    ("Tax Code Configuration", "pm", "Acme finance needs this before the UAT window, please prioritise."),
    ("Crash Reporting Integration", "assignee", "SDK is wired in; symbol upload still failing on CI."),
    ("Crash Reporting Integration", "lead", "Ping Noah about the CI secret, he set up the pipeline."),
    ("Beta Feedback Form", "pm", "Globex wants a screenshot attachment option on the form."),
    ("In-App Purchase Sandbox Tests", "assignee", "All sandbox purchase flows pass on iOS and Android."),
    ("Profile Photo Upload", "lead", "Large images still crash the cropper, see the attached log."),
    ("Profile Photo Upload", "assignee", "Looking into downscaling before the cropper opens."),
    ("Deep Link Routing", "assignee", "Blocked until Globex confirms the universal link domain."),
    ("Offline Data Sync", "lead", "Ravi, please hand over notes before your leave."),
    ("Analytics Event Tracking", "lead", "Event names now match the tracking plan, thanks."),
    ("ERP Extract Jobs", "assignee", "Extract runs but takes 3h; tuning the batch size."),
    ("Data Quality Rules", "lead", "Null checks still miss the legacy region codes."),
    ("Data Quality Rules", "pm", "Initech flagged this as a go-live blocker."),
    ("Sales Dashboard Dataset", "assignee", "Dataset is 70% done; will brief Yuki before my leave."),
    ("Executive Report Layouts", "pm", "Layouts look good, waiting on the final colour palette."),
    ("Invoice Module Regression Tests", "lead", "Second pass is close; two assertions still use stale fixtures."),
    ("Flaky Test Triage", "assignee", "Five flaky tests traced to the shared staging database."),
    ("Defect Triage Dashboard", "pm", "Stark would like this view shared with their QA lead."),
    ("Network Topology Design", "assignee", "On hold until Umbrella approves the address ranges."),
    ("Backup Policy Definition", "lead", "Retention periods must match the HIPAA requirements."),
    ("Cost Estimation Model", "pm", "Client paused the project; keep this ready for the restart."),
    ("External Pen Test", "assignee", "External scan complete; manual testing starts tomorrow."),
    ("Pen Test Findings Report", "lead", "Please add CVSS scores to every finding."),
    ("MFA Enforcement Rollout", "pm", "Umbrella needs MFA for all admins before the audit."),
    ("MFA Enforcement Rollout", "assignee", "Reworking the rollout plan to include service accounts."),
    ("Incident Response Playbook", "assignee", "Waiting on Umbrella's legal team for the escalation contacts."),
)


def _audit_once(db: Session, account_id, action, entity, ref, old, new, created_at, ip=None) -> AuditLog:
    """Insert the audit row if missing (keyed by entity, ref, action, new_value), then backdate it."""
    new_json = json.dumps(new) if new is not None else None
    row = (
        db.query(AuditLog)
        .filter_by(entity_name=entity, entity_ref_id=str(ref), action=action, new_value=new_json)
        .first()
    )
    if row is None:
        row = AuditLog(
            account_id=account_id, action=action, entity_name=entity, entity_ref_id=str(ref),
            old_value=json.dumps(old) if old is not None else None, new_value=new_json, ip_address=ip,
        )
        db.add(row)
    row.created_at = created_at
    db.flush()
    return row


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _seed_tasks(db: Session, today: date, ctx: dict, rng: random.Random) -> dict:
    """Tasks in every status with submissions, comments and TaskService-shaped audit history.

    Returns {"tasks": {title: Task}} for the tasks created here (wave3 tasks are not included).
    """
    projects, milestones, teams, pms = ctx["projects"], ctx["milestones"], ctx["teams"], ctx["pms"]
    people = ctx["people"]
    employees = {e.emp_id: e for e in people.values()}
    pm_by_id = {pm.pm_id: pm for pm in pms.values()}
    now = datetime.now(timezone.utc)
    latest = now - timedelta(hours=1)
    next_monday = today + timedelta(days=7 - today.weekday())
    priorities = (PriorityLevel.LOW, PriorityLevel.MEDIUM, PriorityLevel.HIGH, PriorityLevel.CRITICAL)

    tasks = {}
    for project_key, rows in TASKS.items():
        project, team = projects[project_key], teams[project_key]
        lead = employees[team.lead_emp_id]
        pool = [
            employees[m.emp_id]
            for m in db.query(TeamMember).filter_by(team_id=team.team_id).order_by(TeamMember.team_member_id)
        ]
        for title, status, due, ms, who, rej, nw in rows:
            # Same number of draws per row, so every row sees the same random stream on every run.
            picked = rng.choice(pool)
            priority = rng.choices(priorities, weights=(2, 4, 3, 1))[0]
            duration = rng.randint(3, 14)
            progress = rng.choice((20, 30, 40, 50, 60, 70, 80))
            blocker = rng.choice(BLOCKER_REASONS)
            feedback = rng.sample(REJECTION_FEEDBACK, 3)

            assignee = people[who] if who else picked
            due_date = (next_monday if nw else today) + timedelta(days=due)
            start_date = due_date - timedelta(days=duration)
            if status != TODO:
                start_date = min(start_date, today - timedelta(days=1))

            # Timeline: create, then one step per day from the start date, capped before now.
            steps = 1
            if status == BLK:
                steps += 1
            elif status in (REV, REJ):
                steps += 2 * rej + (1 if status == REV else 0)
            elif status == DONE:
                steps += 2
            first = datetime.combine(start_date, time(9, 0), tzinfo=timezone.utc)
            first -= max(timedelta(0), first + timedelta(days=steps - 1) - latest)
            stamps = iter(first + timedelta(days=i) for i in range(steps))

            task = _get_or_create(
                db, Task, {"project_id": project.project_id, "title": title},
                team_id=team.team_id, assigned_to=assignee.emp_id, created_by=lead.emp_id,
                milestone_id=milestones[ms].id if ms else None, priority=priority, status=status,
                progress_pct={TODO: 0, IP: progress, BLK: progress, REV: 90, REJ: 90, DONE: 100}[status],
                blocker_reason=blocker if status == BLK else None,
                rejection_count=rej, rejection_feedback=feedback[rej - 1] if rej else None,
                start_date=start_date, due_date=due_date, completed_at=None,
                description=f"{title} for {project.name}.",
            )
            tasks[title] = task
            ref = task.task_id

            created_at = next(stamps)
            task.created_at = created_at
            _audit_once(
                db, lead.account_id, AuditAction.CREATE, "TASK", ref, None,
                {"title": title, "project_id": project.project_id, "team_id": team.team_id,
                 "assigned_to": assignee.emp_id, "status": "TODO"},
                created_at,
            )

            def submit(version: int) -> None:
                remarks = "Ready for review." if version == 1 else f"Revision {version - 1}: addressed the review feedback."
                file_name = f"{_slug(title)}-v{version}.pdf"
                file_url = f"/uploads/task_submissions/{file_name}"
                at = next(stamps)
                submission = _get_or_create(
                    db, TaskSubmission, {"task_id": ref, "remarks": remarks},
                    submitted_by=assignee.emp_id, file_url=file_url, file_name=file_name,
                    file_size_bytes=180_000 + 7_000 * version, submitted_at=at,
                )
                if version == 1:
                    old, new = {"status": "IN_PROGRESS"}, {
                        "status": "IN_REVIEW", "submission_id": submission.submission_id, "file_name": file_name,
                    }
                else:
                    old, new = {"status": "REJECTED"}, {
                        "status": "IN_REVIEW", "submission_id": submission.submission_id,
                        "revised_remarks": remarks, "new_file_url": file_url,
                    }
                _audit_once(db, assignee.account_id, AuditAction.UPDATE, "TASK", ref, old, new, at)

            if status == BLK:
                _audit_once(
                    db, assignee.account_id, AuditAction.UPDATE, "TASK", ref,
                    {"status": "IN_PROGRESS", "progress_pct": progress, "blocker_reason": None},
                    {"status": "BLOCKED", "progress_pct": progress, "blocker_reason": blocker},
                    next(stamps),
                )
            for count in range(1, rej + 1):
                submit(count)
                _audit_once(
                    db, lead.account_id, AuditAction.UPDATE, "TASK", ref, {"status": "IN_REVIEW"},
                    {"status": "REJECTED", "rejection_feedback": feedback[count - 1], "rejection_count": count},
                    next(stamps),
                )
            if status == REV:
                submit(rej + 1)
            if status == DONE:
                submit(1)
                task.completed_at = next(stamps)
                _audit_once(
                    db, lead.account_id, AuditAction.APPROVE, "TASK", ref, {"status": "IN_REVIEW"},
                    {"status": "DONE", "progress_pct": 100}, task.completed_at,
                )

    for i, (title, author, content) in enumerate(COMMENTS):
        task = tasks[title]
        if author == "pm":
            pm = pm_by_id[db.get(Project, task.project_id).pm_id]
            values = {"author_emp_id": None, "author_name": pm.full_name, "author_role": "PM"}
        else:
            emp_id = task.assigned_to if author == "assignee" else task.created_by
            role = "EMPLOYEE" if author == "assignee" else "TEAM_LEAD"
            values = {"author_emp_id": emp_id, "author_name": employees[emp_id].full_name, "author_role": role}
        _get_or_create(
            db, TaskComment, {"task_id": task.task_id, "content": content},
            created_at=now - timedelta(hours=2 * (len(COMMENTS) - i)), **values,
        )

    return {"tasks": tasks}


LEAVE_TYPES = (
    # key, name, yearly_quota, is_paid, is_active, description. Annual/Sick/Casual come from wave3.
    ("parental", "Parental", 30, True, True, "Leave for the birth or adoption of a child."),
    ("bereavement", "Bereavement", 5, True, True, "Leave following the death of a family member."),
    ("unpaid", "Unpaid", 30, False, True, "Unpaid leave, subject to approval."),
    ("sabbatical", "Sabbatical", 60, False, False, "Extended career break. Currently not offered."),
)

LEAVE_REQUESTS = (
    # person, leave type, start/end as days from next Monday, status, reviewer key, review remarks, reason.
    # One request per person, so no overlaps and every quota holds. Sarah and Kyle are wave3's.
    ("elena", "annual", 0, 4, LeaveStatus.PENDING, None, None,
     "Family trip abroad that was booked months ago."),
    ("tom", "bereavement", 1, 2, LeaveStatus.PENDING, None, None,
     "Attending a family funeral out of town."),
    ("aisha", "annual", 14, 16, LeaveStatus.PENDING, None, None,
     "Short break to move into a new apartment."),
    ("samir", "casual", 7, 7, LeaveStatus.PENDING, None, None,
     "Personal errands that need a full working day."),
    ("ben", "annual", 21, 25, LeaveStatus.PENDING, None, None,
     "Year-end holiday with family."),
    ("ravi", "annual", 7, 11, LeaveStatus.APPROVED, "ana", "Approved. Please hand over your Phoenix tasks.",
     "Attending my sister's wedding in Pune."),
    ("carlos", "parental", 14, 18, LeaveStatus.APPROVED, "hr", "Approved. Congratulations!",
     "Paternity leave for the birth of our first child."),
    ("yuki", "sick", -13, -12, LeaveStatus.APPROVED, "marcus", "Get well soon.",
     "Down with the flu, doctor advised rest."),
    ("olivia", "annual", -35, -33, LeaveStatus.APPROVED, "grace", "Approved, enjoy the time off.",
     "Long weekend trip planned with friends."),
    ("lucas", "casual", -38, -38, LeaveStatus.APPROVED, "hr", "Approved.",
     "Need a day to sort out visa paperwork."),
    ("zoe", "annual", 0, 4, LeaveStatus.REJECTED, "marcus",
     "Elena is already out that week and the executive reports milestone is due. Please pick another week.",
     "Taking a week off to visit my parents."),
    ("noah", "unpaid", 7, 11, LeaveStatus.REJECTED, "hr",
     "Unpaid leave cannot be approved while the Helios restart plan is being prepared.",
     "Extra week off to extend a planned trip."),
    ("ethan", "annual", 14, 15, LeaveStatus.CANCELLED, None, None,
     "Concert trip, may not be able to go."),
    ("priya", "casual", -21, -21, LeaveStatus.CANCELLED, None, None,
     "Home repair appointment, later rescheduled."),
)


def _seed_leave(db: Session, today: date, ctx: dict) -> dict:
    """Leave types and requests in every status, with the review audit rows LeaveReviewService writes.

    Returns {"leave_types": {key: LeaveType}, "leaves": {person key: LeaveRequest}}.
    leave_types includes wave3's annual, sick and casual.
    """
    people, accounts = ctx["people"], ctx["accounts"]
    now = datetime.now(timezone.utc)
    next_monday = today + timedelta(days=7 - today.weekday())

    leave_types = {
        key: db.query(LeaveType).filter_by(name=name).one()
        for key, name in (("annual", "Annual"), ("sick", "Sick"), ("casual", "Casual"))
    }
    for key, name, quota, is_paid, is_active, description in LEAVE_TYPES:
        leave_types[key] = _get_or_create(
            db, LeaveType, {"name": name},
            yearly_quota=quota, is_paid=is_paid, is_active=is_active, description=description,
        )

    leaves = {}
    for person, leave_type, start, end, status, reviewer, remarks, reason in LEAVE_REQUESTS:
        employee = people[person]
        start_date = next_monday + timedelta(days=start)
        end_date = next_monday + timedelta(days=end)
        applied_at = min(
            datetime.combine(start_date - timedelta(days=10), time(10, 0), tzinfo=timezone.utc),
            now - timedelta(days=2),
        )
        decided = status in (LeaveStatus.APPROVED, LeaveStatus.REJECTED)
        reviewer_account = accounts[reviewer].account_id if reviewer else None
        reviewed_at = applied_at + timedelta(days=1) if decided else None
        leaves[person] = request = _get_or_create(
            db, LeaveRequest, {"emp_id": employee.emp_id, "reason": reason},
            leave_type_id=leave_types[leave_type].leave_type_id, start_date=start_date, end_date=end_date,
            total_days=_business_days(start_date, end_date), status=status, applied_at=applied_at,
            reviewed_by_account_id=reviewer_account, reviewed_at=reviewed_at, review_remarks=remarks,
        )

        if decided:
            action = AuditAction.APPROVE if status == LeaveStatus.APPROVED else AuditAction.UPDATE
            _audit_once(
                db, reviewer_account, action, "LEAVE_REQUEST", request.leave_id,
                {"status": "PENDING"}, {"status": status.value, "review_remarks": remarks}, reviewed_at,
            )
        elif status == LeaveStatus.CANCELLED:
            _audit_once(
                db, employee.account_id, AuditAction.UPDATE, "LEAVE_REQUEST", request.leave_id,
                {"status": "PENDING"}, {"status": "CANCELLED"}, applied_at + timedelta(hours=6),
            )

    return {"leave_types": leave_types, "leaves": leaves}


def seed_rich_demo(db: Session, today: date | None = None, password: str | None = None) -> None:
    today = today or date.today()
    password = password or os.getenv("SEED_PASSWORD", DEFAULT_PASSWORD)
    seed_wave3_demo(db, today, password)

    pw_hash = hash_password(password)  # bcrypt is slow: hash once, reuse for every account
    rng = random.Random(42)

    ctx = _seed_people(db, pw_hash)
    ctx.update(_seed_projects(db, today, ctx))
    ctx.update(_seed_tasks(db, today, ctx, rng))
    ctx.update(_seed_leave(db, today, ctx))

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
