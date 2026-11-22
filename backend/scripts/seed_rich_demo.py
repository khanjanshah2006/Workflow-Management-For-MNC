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
from app.core import scope
from app.core.security import hash_password
from app.features.executive.reports import ExecutiveReportService
from app.features.executive.schemas import ExecutiveReportCreateRequest
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.deliverable import Deliverable, DeliverableFeedback
from app.models.department import Department
from app.models.elevated_access_grant import ElevatedAccessGrant
from app.models.employee import Employee
from app.models.enums import (
    AuditAction,
    DeliverableStatus,
    FeedbackDecision,
    LeaveStatus,
    MilestoneStatus,
    PriorityLevel,
    ProjectStatus,
    ReportFormat,
    SkillProficiency,
    TaskStatus,
    TeamStatus,
    UserType,
)
from app.models.executive_report import ExecutiveReport
from app.models.leave import LeaveRequest, LeaveType
from app.models.milestone import ProjectMilestone
from app.models.notification import Notification
from app.models.project import Project, ProjectAssignment
from app.models.project_manager import ProjectManager
from app.models.skill import EmployeeSkill, Skill
from app.models.support import SupportTicket, TicketActivity
from app.models.system_backup_log import SystemBackupLog
from app.models.system_parameter import SystemParameter
from app.models.task import Task, TaskComment, TaskSubmission
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount
from scripts.seed_wave3_demo import (
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
    ("sofia", "sofia.alvarez@company.com", "Sofia Alvarez", "RD-PM-003", "qe", date(2022, 9, 12)),
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
    ("hannah", "hannah.wright@company.com", "Hannah Wright", "RD-EMP-011", UserType.EMPLOYEE, "delivery",
     "UI/UX Designer", date(2023, 4, 24)),
    ("yuki", "yuki.tanaka@company.com", "Yuki Tanaka", "RD-EMP-012", UserType.EMPLOYEE, "data",
     "Data Analyst", date(2023, 6, 12)),
    ("carlos", "carlos.mendes@company.com", "Carlos Mendes", "RD-EMP-013", UserType.EMPLOYEE, "delivery",
     "Software Engineer", date(2023, 8, 21)),
    ("fatima", "fatima.zahra@company.com", "Fatima Zahra", "RD-EMP-014", UserType.EMPLOYEE, "delivery",
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
    ("rachel", "rachel.green@company.com", "Rachel Green", "RD-EMP-026", UserType.EMPLOYEE, "hr",
     "HR Coordinator", date(2025, 6, 2)),
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


# Alpha Core Team members in join order: wave3's three, then the two added below.
ALPHA_MEMBERS = ("sarah", "matrix", "kyle", "carlos", "fatima")

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
        ("orion", "ORION-QA", "Orion Test Automation", "sofia", "stark", -60, 75,
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
            project_id=projects[project].project_id, lead_emp_id=people[lead].emp_id,
            dept_id=people[lead].dept_id, status=status,
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
        T("GL Account Mapping Script", REV, 6, who="fatima"),
        T("Inventory Valuation Report", IP, 9),
        T("Role-Based Menu Permissions", IP, -10),
        T("Tax Code Configuration", REJ, 3, who="matrix", rej=2),  # not Kyle: his leave is next Mon-Tue
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
        T("Performance Profiling", IP, 10, who="hannah"),  # Ravi keeps exactly 3 tasks in his leave
        T("Analytics Event Tracking", REV, 5, rej=1),
        T("Biometric Login", REJ, 8, who="hannah", rej=1),
        T("Localization (ES, FR)", BLK, 12, who="tom"),
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
        T("Reconciliation Queries", REV, 4, who="yuki"),  # Elena keeps exactly 2 tasks in her leave
        T("Data Lineage Docs", IP, -10),
        T("Partitioning Strategy", REJ, 7, who="zoe", rej=1),
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


# Seed audit rows carry RFC 5737 documentation addresses, which never appear in real traffic.
# That marks them without touching the JSON the services parse, and keeps _audit_once from ever
# matching (and rewriting) a row the app itself wrote.
SEED_IP = "198.51.100.10"


def _audit_once(db: Session, account_id, action, entity, ref, old, new, created_at, ip=SEED_IP,
                refresh=False) -> AuditLog:
    """Insert the seed audit row if missing (keyed by entity, ref, action, ip, new_value), then backdate it.

    `ip` must be a documentation address. Plain strings are stored as-is, like write_audit_log does.
    With refresh=True new_value leaves the key and old/new are rewritten, for values with moving dates."""
    new_json = new if new is None or isinstance(new, str) else json.dumps(new)
    old_json = json.dumps(old) if old is not None else None
    lookup = {"entity_name": entity, "entity_ref_id": str(ref), "action": action, "ip_address": ip}
    if not refresh:
        lookup["new_value"] = new_json
    row = db.query(AuditLog).filter_by(**lookup).first()
    if row is None:
        row = AuditLog(
            account_id=account_id, action=action, entity_name=entity, entity_ref_id=str(ref),
            old_value=old_json, new_value=new_json, ip_address=ip,
        )
        db.add(row)
    row.old_value, row.new_value = old_json, new_json
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

    # Fixed member order (not a DB query), so members added through the app never reshuffle the picks.
    pools = {key: members for key, _, _, _, _, members in TEAMS} | {"alpha": ALPHA_MEMBERS}
    tasks = {}
    for project_key, rows in TASKS.items():
        project, team = projects[project_key], teams[project_key]
        lead = employees[team.lead_emp_id]
        pool = [people[key] for key in pools[project_key]]
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
    ("rachel", "casual", 9, 9, LeaveStatus.PENDING, None, None,
     "Attending my graduation ceremony."),
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


TICKETS = (
    # subject, category, priority, status, reporter email, assignee key (ivan/nina), hours ago, escalation reason
    ("VPN drops every 20 minutes", "network", "HIGH", "open",
     "ravi.kumar@company.com", "ivan", 6, None),
    ("Request access to Supabase staging", "access", "MEDIUM", "open",
     "elena.petrova@company.com", None, 3, None),
    ("Laptop battery is swelling", "hardware", "HIGH", "open",
     "tom.becker@company.com", None, 20, None),
    ("Outlook calendar not syncing on mobile", "software", "LOW", "open",
     "hr@company.com", "nina", 28, None),
    ("Need a Figma editor licence", "access", "LOW", "open",
     "hannah.wright@company.com", None, 10, None),
    ("Docker Desktop fails to start after update", "software", "MEDIUM", "in_progress",
     "lucas.silva@company.com", "ivan", 30, None),
    ("Second monitor keeps flickering", "hardware", "LOW", "in_progress",
     "yuki.tanaka@company.com", "nina", 52, None),
    ("Cannot connect to office Wi-Fi on floor 3", "network", "MEDIUM", "in_progress",
     "pm@company.com", "nina", 26, None),
    ("Jira SSO login loop", "access", "HIGH", "in_progress",
     "marcus.chen@company.com", "ivan", 40, None),
    ("Production database credentials expired", "access", "CRITICAL", "escalated",
     "omar.haddad@company.com", "ivan", 36,
     "Rotating production credentials needs System Administrator access."),
    ("Suspicious login alerts on my account", "other", "HIGH", "escalated",
     "ben.carter@company.com", "nina", 22,
     "Possible account compromise; needs a security review by a System Administrator."),
    ("Build server out of disk space", "software", "CRITICAL", "escalated",
     "noah.fischer@company.com", "ivan", 14,
     "Expanding the build host disk needs System Administrator access."),
    ("Printer on floor 2 jams constantly", "hardware", "LOW", "resolved",
     "aisha.khan@company.com", "nina", 120, None),
    ("Password reset for QA test account", "access", "MEDIUM", "resolved",
     "priya.nair@company.com", "ivan", 80, None),
    ("Slow file share access from home", "network", "MEDIUM", "resolved",
     "daniel.okafor@company.com", "ivan", 200, None),
    ("Install Power BI Desktop", "software", "LOW", "resolved",
     "zoe.martin@company.com", "nina", 150, None),
    ("Keyboard keys sticking", "hardware", "LOW", "closed",
     "sarah.connor@company.com", "nina", 400, None),
    ("Email signature template request", "other", "LOW", "closed",
     "mei.lin@company.com", "nina", 330, None),
)

# Status steps each ticket went through after creation.
TICKET_PATHS = {
    "open": (),
    "in_progress": ("in_progress",),
    "escalated": ("in_progress", "escalated"),
    "resolved": ("in_progress", "resolved"),
    "closed": ("in_progress", "resolved", "closed"),
}

DELIVERABLES = (
    # project, title, milestone, status, days ago submitted, feedback (rating, comments) or None
    ("phoenix", "UX Design Package", "phoenix_design", DeliverableStatus.ACCEPTED, 38,
     (5, "Beautiful work, the onboarding flow is exactly what we wanted.")),
    ("phoenix", "Alpha Build Release Notes", "phoenix_alpha", DeliverableStatus.CHANGES_REQUESTED, 11,
     (3, "Please list the known issues and the supported OS versions.")),
    ("phoenix", "Beta Build v0.9", "phoenix_beta", DeliverableStatus.SUBMITTED, 1, None),
    ("vega", "Portal Go-Live Package", "vega_golive", DeliverableStatus.ACCEPTED, 88,
     (4, "Smooth launch. A few minor styling issues remain.")),
    ("vega", "Support Handover Pack", "vega_handover", DeliverableStatus.ACCEPTED, 34,
     (5, "Very thorough handover, our support team is confident.")),
    ("atlas", "Data Model Specification", "atlas_model", DeliverableStatus.ACCEPTED, 49,
     (4, "Clear model. Please keep the data dictionary up to date.")),
    ("orion", "Test Strategy Document", "orion_strategy", DeliverableStatus.CHANGES_REQUESTED, 29,
     (2, "Coverage targets for the carrier integrations are missing.")),
    ("helios", "Cloud Readiness Report", "helios_assessment", DeliverableStatus.SUBMITTED, 69, None),
    ("zephyr", "Security Audit Scope", "zephyr_kickoff", DeliverableStatus.SUBMITTED, 24, None),
)

# These accounts keep every seeded notification unread, so each has several to show.
ALWAYS_UNREAD = (
    "sarah.connor@company.com", "ravi.kumar@company.com", "john.teamlead@company.com",
    "pm@company.com", "hr@company.com",
)


def _seed_support(db: Session, ctx: dict) -> dict:
    """Support tickets in every status with activity trails and SUPPORT_TICKET audit rows.

    Returns {"tickets": {subject: SupportTicket}}.
    """
    accounts = ctx["accounts"]
    now = datetime.now(timezone.utc)
    taken = {number for (number,) in db.query(SupportTicket.ticket_number)}
    next_number = 1

    tickets = {}
    for subject, category, priority, status, reporter_email, assignee, hours_ago, reason in TICKETS:
        reporter = db.query(UserAccount).filter_by(email=reporter_email).one()
        it_account = accounts[assignee].account_id if assignee else None
        it_name = ctx["people"][assignee].full_name if assignee else None
        created_at = now - timedelta(hours=hours_ago)
        stamps = [created_at + timedelta(hours=3 * i) for i in range(len(TICKET_PATHS[status]) + 2)]

        ticket = db.query(SupportTicket).filter_by(subject=subject).first()
        if ticket is None:
            while f"TKT-{next_number:03d}" in taken:
                next_number += 1
            ticket = SupportTicket(subject=subject, ticket_number=f"TKT-{next_number:03d}")
            taken.add(ticket.ticket_number)
            db.add(ticket)
        ticket.description = f"{subject}. Reported through the IT service desk."
        ticket.category, ticket.priority, ticket.status = category, priority, status
        ticket.escalation_reason = reason
        ticket.reporter_id, ticket.assigned_to = reporter.account_id, it_account
        ticket.created_at = created_at
        ticket.updated_at = stamps[-1] if TICKET_PATHS[status] else created_at
        ticket.resolved_at = None
        db.flush()
        tickets[subject] = ticket

        def activity(action, note, actor, at, old=None, new=None):
            _get_or_create(
                db, TicketActivity, {"ticket_id": ticket.id, "action": action, "note": note},
                actor_id=actor, old_status=old, new_status=new, created_at=at,
            )

        activity("CREATED", f"Ticket {ticket.ticket_number} created by employee", reporter.account_id, created_at)
        _audit_once(
            db, reporter.account_id, AuditAction.CREATE, "SUPPORT_TICKET", ticket.id, None,
            f"Created ticket {ticket.ticket_number}: {subject}", created_at,
        )
        if it_account:
            activity("ASSIGNED", f"Assigned to {it_name}", it_account, stamps[1])
        previous = "open"
        for step, at in zip(TICKET_PATHS[status], stamps[2:]):
            if step == "escalated":
                activity("ESCALATED", reason, it_account, at)
                _audit_once(
                    db, it_account, AuditAction.UPDATE, "SUPPORT_TICKET", ticket.id, {"status": previous},
                    {"status": "escalated", "escalation_reason": reason}, at,
                )
            else:
                activity("STATUS_CHANGED", f"Status changed from {previous} to {step}", it_account, at, previous, step)
            if step == "resolved":
                ticket.resolved_at = at
            previous = step

    return {"tickets": tickets}


def _seed_deliverables(db: Session, ctx: dict) -> dict:
    """Client deliverables in every status, with client feedback rows and DELIVERABLE audit rows.

    Returns {"deliverables": {title: Deliverable}}.
    """
    projects, milestones, teams = ctx["projects"], ctx["milestones"], ctx["teams"]
    clients = {c.client_id: c for c in ctx["clients"].values()}
    now = datetime.now(timezone.utc)

    deliverables = {}
    for project_key, title, milestone, status, days_ago, feedback in DELIVERABLES:
        project = projects[project_key]
        submitted_at = now - timedelta(days=days_ago)
        deliverable = deliverables[title] = _get_or_create(
            db, Deliverable, {"project_id": project.project_id, "title": title},
            milestone_id=milestones[milestone].id, submitted_by=teams[project_key].lead_emp_id,
            description=f"{title} for {project.name}.", version=1, status=status, submitted_at=submitted_at,
            file_url=f"/uploads/deliverables/{project.project_code.lower()}-{_slug(title)}-v1.pdf",
        )
        if feedback is None:
            continue
        rating, comments = feedback
        client = clients[project.client_id]
        decision = FeedbackDecision(status.value)
        given_at = submitted_at + timedelta(days=1)
        _get_or_create(
            db, DeliverableFeedback,
            {"deliverable_id": deliverable.deliverable_id, "given_by_client_id": client.client_id},
            decision=decision, comments=comments, rating=rating, given_at=given_at,
        )
        _audit_once(
            db, client.account_id,
            AuditAction.APPROVE if decision == FeedbackDecision.ACCEPTED else AuditAction.UPDATE,
            "DELIVERABLE", deliverable.deliverable_id, {"status": "SUBMITTED"},
            {"status": status.value, "decision": decision.value, "rating": rating, "comments": comments},
            given_at,
        )

    return {"deliverables": deliverables}


def _seed_notifications(db: Session, today: date, ctx: dict) -> None:
    """Notifications in the exact type/title/message/link shapes the services write.

    Keyed by (account_id, type, title, link): some messages embed dates that move with `today`,
    so the message is refreshed instead. Rows are only ever inserted once, so is_read survives.
    """
    people, tasks, leaves = ctx["people"], ctx["tasks"], ctx["leaves"]
    employees = {e.emp_id: e for e in people.values()}
    now = datetime.now(timezone.utc)
    items = []  # (account_id, type, title, message, link)

    def by_email(account_ids):
        return [
            a.account_id
            for a in db.query(UserAccount).filter(UserAccount.account_id.in_(account_ids)).order_by(UserAccount.email)
        ]

    # Leave (LeaveService._send_submission_notifications and LeaveReviewService).
    sarah_pending = db.query(LeaveRequest).filter_by(
        emp_id=people["sarah"].emp_id, status=LeaveStatus.PENDING).first()
    sarah_rejected = db.query(LeaveRequest).filter_by(
        emp_id=people["sarah"].emp_id, status=LeaveStatus.REJECTED).first()
    for request in [leaves[k] for k in ("elena", "tom", "ben")] + [sarah_pending]:
        employee = employees[request.emp_id]
        recipients = set(scope.team_lead_account_ids_for(db, employee.emp_id))
        recipients |= set(scope.staffing_pm_account_ids_for(db, employee.emp_id))
        recipients.discard(employee.account_id)
        projects_str = ", ".join(p.name for p in scope.staffing_projects_for(db, employee.emp_id)) or "None"
        for account_id in by_email(recipients):
            items.append((
                account_id, "LEAVE_REQUESTED", f"Leave Request: {employee.full_name}",
                f"{employee.full_name} has requested {request.total_days} day(s) of leave "
                f"from {request.start_date} to {request.end_date}. Affected projects: {projects_str}.",
                f"/team-lead/leave?request={request.leave_id}",
            ))
    for key in ("ravi", "carlos", "yuki"):
        request, employee = leaves[key], people[key]
        link = f"/leave/requests/{request.leave_id}"
        items.append((employee.account_id, "LEAVE_APPROVED", "Leave request approved",
                      f"Your leave request #{request.leave_id} was approved.", link))
        if request.start_date < today:
            continue  # past leave: staffing PMs were told long ago, keep the feed short
        team_message = f"Leave request #{request.leave_id} was approved for {employee.full_name}."
        for account_id in by_email(scope.staffing_pm_account_ids_for(db, employee.emp_id)):
            items.append((account_id, "STAFF_LEAVE_APPROVED", "Team member leave approved", team_message, link))
        if request.reviewed_by_account_id == ctx["accounts"]["hr"].account_id:
            for account_id in by_email(scope.team_lead_account_ids_for(db, employee.emp_id)):
                items.append((account_id, "LEAVE_APPROVED", "Team member leave approved", team_message, link))
    for request in (leaves["zoe"], leaves["noah"], sarah_rejected):
        items.append((
            employees[request.emp_id].account_id, "LEAVE_REJECTED", "Leave request rejected",
            f"Your leave request #{request.leave_id} was rejected. Reviewer remarks: {request.review_remarks}",
            f"/leave/requests/{request.leave_id}",
        ))
    # HR is not a recipient in code; these copies give the HR inbox something to show.
    for key in ("elena", "tom", "ben"):
        request, employee = leaves[key], people[key]
        projects_str = ", ".join(p.name for p in scope.staffing_projects_for(db, employee.emp_id)) or "None"
        items.append((
            ctx["accounts"]["hr"].account_id, "LEAVE_REQUESTED", f"Leave Request: {employee.full_name}",
            f"{employee.full_name} has requested {request.total_days} day(s) of leave "
            f"from {request.start_date} to {request.end_date}. Affected projects: {projects_str}.",
            f"/team-lead/leave?request={request.leave_id}",
        ))

    # Tasks (TaskService, TaskCommentService, OverdueService).
    def task_by_title(title):
        return tasks.get(title) or db.query(Task).filter_by(title=title).one()

    def lead_of(task):
        return employees[task.created_by]

    for title in ("Implement JWT Refresh Token Flow", "Audit Logging Integration", "API Documentation Review",
                  "Offline Data Sync"):
        task = task_by_title(title)
        items.append((employees[task.assigned_to].account_id, "TASK_ASSIGNED", "New Task Assigned",
                      f"You have been assigned to task #{task.task_id}: '{task.title}'", f"/tasks/{task.task_id}"))
    for title in ("Vendor Master Data Migration", "In-App Purchase Sandbox Tests", "Pen Test Findings Report"):
        task = task_by_title(title)
        items.append((
            lead_of(task).account_id, "TASK_SUBMITTED", "Task Submitted for Review",
            f"Task #{task.task_id} '{task.title}' has been submitted for review by "
            f"{employees[task.assigned_to].full_name}.",
            f"/api/v1/tasks/{task.task_id}/submissions",
        ))
    for title in ("Purchase Order Approval Workflow",):
        task = task_by_title(title)
        items.append((lead_of(task).account_id, "TASK_RESUBMITTED", "Task Resubmitted",
                      f"Task #{task.task_id} '{task.title}' has been resubmitted for review.",
                      f"/api/v1/tasks/{task.task_id}"))
    for title in ("Profile Photo Upload", "Data Quality Rules", "MFA Enforcement Rollout"):
        task = task_by_title(title)
        items.append((employees[task.assigned_to].account_id, "TASK_REJECTED", "Task Rejected - Revision Requested",
                      f"Task #{task.task_id} '{task.title}' was rejected. Feedback: {task.rejection_feedback}",
                      f"/tasks/{task.task_id}"))
    for title in ("Beta Tester Invite Emails", "Web App Vulnerability Scan"):
        task = task_by_title(title)
        items.append((employees[task.assigned_to].account_id, "TASK_APPROVED", "Task Approved",
                      f"Task #{task.task_id} '{task.title}' has been approved.", f"/tasks/{task.task_id}"))
    for title in ("Deep Link Routing", "Network Topology Design", "Incident Response Playbook"):
        task = task_by_title(title)
        items.append((
            lead_of(task).account_id, "TASK_BLOCKED", "Task Flagged as Blocked",
            f"Task #{task.task_id} '{task.title}' has been flagged as BLOCKED. Reason: {task.blocker_reason}",
            f"/tasks/{task.task_id}",
        ))
    for title, author, recipient in (
        ("Offline Data Sync", "lead", "assignee"),
        ("Flaky Test Triage", "assignee", "lead"),
        ("Vendor Master Data Migration", "assignee", "lead"),
    ):
        task = task_by_title(title)
        author_name = (lead_of(task) if author == "lead" else employees[task.assigned_to]).full_name
        to = lead_of(task) if recipient == "lead" else employees[task.assigned_to]
        items.append((to.account_id, "TASK_COMMENT", "New task comment",
                      f"{author_name} commented on task #{task.task_id} '{task.title}'.", f"/tasks/{task.task_id}"))
    for title in ("Role-Based Menu Permissions",):
        task = task_by_title(title)
        days = (today - task.due_date).days
        link = f"/tasks/{task.task_id}"
        if task.overdue_notified_at is None:  # these notifications count as sent; the sweep skips the task
            task.overdue_notified_at = now
        items.append((lead_of(task).account_id, "TASK_OVERDUE", "Task Overdue",
                      f"Task #{task.task_id} '{task.title}' is {days} day(s) overdue "
                      f"(due {task.due_date.isoformat()}).", link))
        items.append((employees[task.assigned_to].account_id, "TASK_DEADLINE_MISSED", "Deadline Missed",
                      f"You missed the deadline for task #{task.task_id} '{task.title}' "
                      f"(due {task.due_date.isoformat()}).", link))

    # Escalated tickets notify every active System Administrator (SupportTicketService).
    sysadmin = ctx["accounts"]["sysadmin"].account_id
    for ticket in ctx["tickets"].values():
        if ticket.status == "escalated":
            items.append((
                sysadmin, "TICKET_ESCALATED", f"Support Ticket {ticket.ticket_number} Escalated",
                f"Support ticket '{ticket.ticket_number}' ({ticket.subject}) has been escalated "
                f"to System Administrator. Reason: {ticket.escalation_reason}",
                None,
            ))

    # Client feedback notifies the project's PM (ClientPortalService.submit_deliverable_feedback).
    pm_accounts = {pm.pm_id: pm.account_id for pm in ctx["pms"].values()}
    clients = {c.client_id: c for c in ctx["clients"].values()}
    for deliverable in ctx["deliverables"].values():
        if deliverable.status == DeliverableStatus.SUBMITTED:
            continue
        project = db.get(Project, deliverable.project_id)
        label = "accepted" if deliverable.status == DeliverableStatus.ACCEPTED else "requested changes on"
        items.append((
            pm_accounts[project.pm_id], "DELIVERABLE_FEEDBACK",
            f"Deliverable {deliverable.status.value}: {deliverable.title}",
            f"{clients[project.client_id].company_name} {label} deliverable "
            f"'{deliverable.title}' (v{deliverable.version}) for project {project.project_code}.",
            f"/projects/{project.project_id}/deliverables",
        ))

    always_unread = {a.account_id for a in db.query(UserAccount).filter(UserAccount.email.in_(ALWAYS_UNREAD))}
    for i, (account_id, type_, title, message, link) in enumerate(items):
        row = db.query(Notification).filter_by(account_id=account_id, type=type_, title=title, link=link).first()
        if row is None:
            db.add(Notification(
                account_id=account_id, type=type_, title=title, message=message, link=link,
                is_read=account_id not in always_unread and i % 3 != 0,
                created_at=now - timedelta(hours=2 * (len(items) - i)),
            ))
            db.flush()
        else:
            row.message = message


LOGINS = (
    # email, ip address, hours ago
    ("john.teamlead@company.com", "198.51.100.11", 1),
    ("sarah.connor@company.com", "198.51.100.12", 2),
    ("ravi.kumar@company.com", "198.51.100.13", 3),
    ("pm@company.com", "198.51.100.14", 4),
    ("hr@company.com", "198.51.100.15", 5),
    ("executive@company.com", "198.51.100.16", 6),
    ("admin@company.com", "198.51.100.17", 7),
    ("sysadmin@company.com", "198.51.100.18", 8),
    ("it.support@company.com", "198.51.100.19", 9),
    ("ana.lopez@company.com", "198.51.100.20", 10),
    ("mei.lin@company.com", "198.51.100.21", 11),
    ("client.globex@company.com", "198.51.100.23", 12),
)

# One IP tries 6 accounts within minutes: more than FAILED_LOGIN_THRESHOLD (5) inside the
# 15-minute window, so the anomaly detector raises FAILED_LOGIN_BURST right after seeding.
BURST_IP = "203.0.113.45"
BURST_EMAILS = (
    "admin@company.com", "sysadmin@company.com", "root@company.com",
    "administrator@company.com", "it.support@company.com", "test@company.com",
)

BACKUPS = (
    # file_path (None for the failed run), backup_type, status, hours ago, size in MB
    ("backups/wms_scheduled_backup_d4.sql", "SCHEDULED", "COMPLETED", 102, 41),
    ("backups/wms_scheduled_backup_d3.sql", "SCHEDULED", "COMPLETED", 78, 42),
    ("backups/wms_scheduled_backup_d2.sql", "SCHEDULED", "COMPLETED", 54, 42),
    ("backups/wms_scheduled_backup_d1.sql", "SCHEDULED", "COMPLETED", 30, 43),
    (None, "SCHEDULED", "FAILED", 6, None),
    ("backups/wms_on_demand_backup.sql", "ON_DEMAND", "COMPLETED", 2, 43),
)

GRANTS = (
    # user email, role, reason, granted / expires / revoked as hours from now (None = not revoked)
    ("it.support@company.com", "SYSTEM_ADMIN", "On-call backup admin", -2, 48, None),
    ("it.helpdesk@company.com", "ADMIN", "Temporary access for the quarterly user audit", -240, -168, None),
    ("ana.lopez@company.com", "PM", "Covering Phoenix PM duties during a planned absence", -120, 48, -72),
)

REPORTS = (
    # title, format, period start (callable on today), department breakdown
    ("Monthly Delivery Review", "PDF", lambda t: t - timedelta(days=30), False),
    ("Quarterly Portfolio KPIs", "CSV", lambda t: t - timedelta(days=90), False),
    ("Year-to-Date Executive Summary", "PDF", lambda t: date(t.year, 1, 1), True),
)


def _seed_admin_ops(db: Session, ctx: dict) -> None:
    """Project/team/staffing audit trail, logins, a failed-login burst, backup logs and elevated grants."""
    projects, teams, milestones, people = ctx["projects"], ctx["teams"], ctx["milestones"], ctx["people"]
    pm_accounts = {pm.pm_id: pm.account_id for pm in ctx["pms"].values()}
    now = datetime.now(timezone.utc)
    latest = now - timedelta(hours=1)

    def at(day: date, hour: int = 9) -> datetime:
        return min(datetime.combine(day, time(hour, 0), tzinfo=timezone.utc), latest)

    def account(email: str) -> UserAccount:
        return db.query(UserAccount).filter_by(email=email).one()

    # Projects and teams, in the shapes ProjectService writes.
    for key, project in projects.items():
        if key == "alpha":
            continue
        pm = pm_accounts[project.pm_id]
        _audit_once(
            db, pm, AuditAction.CREATE, "PROJECT", project.project_id, None,
            {"project_code": project.project_code, "name": project.name,
             "pm_id": project.pm_id, "client_id": project.client_id},
            at(project.start_date - timedelta(days=7)),
        )
        if project.status in (ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED, ProjectStatus.CANCELLED):
            changed = project.end_date if project.status != ProjectStatus.ON_HOLD else now.date() - timedelta(days=20)
            _audit_once(
                db, pm, AuditAction.UPDATE, "PROJECT", project.project_id, {"status": "ACTIVE"},
                {"status": project.status.value}, at(changed, 16),
            )
        if key in teams:
            team = teams[key]
            _audit_once(
                db, pm, AuditAction.CREATE, "TEAM", team.team_id, None,
                {"name": team.name, "project_id": project.project_id, "lead_emp_id": team.lead_emp_id},
                at(project.start_date, 11),
            )
            if team.status == TeamStatus.DISBANDED:  # no service writes this; same shape as a status change
                _audit_once(
                    db, pm, AuditAction.UPDATE, "TEAM", team.team_id, {"status": "ACTIVE"},
                    {"status": "DISBANDED"}, at(project.end_date + timedelta(days=1), 10),
                )

    # A few staffing rows: Nova's planned staffing and the two releases.
    for project_key, person in (("nova", "ravi"), ("nova", "hannah"), ("nova", "lucas"), ("nova", "fatima"),
                                ("vega", "zoe"), ("lyra", "hannah")):
        project = projects[project_key]
        assignment = db.query(ProjectAssignment).filter_by(
            project_id=project.project_id, emp_id=people[person].emp_id).one()
        pm = pm_accounts[project.pm_id]
        _audit_once(
            db, pm, AuditAction.CREATE, "PROJECT_ASSIGNMENT", assignment.assignment_id, None,
            {"project_id": project.project_id, "emp_id": assignment.emp_id,
             "role_in_project": assignment.role_in_project},
            at(assignment.assigned_on, 12),
        )
        if assignment.released_on:  # no service writes releases; the date moves with today
            _audit_once(
                db, pm, AuditAction.UPDATE, "PROJECT_ASSIGNMENT", assignment.assignment_id,
                {"released_on": None}, {"released_on": str(assignment.released_on)},
                at(assignment.released_on, 17), refresh=True,
            )

    # Milestones: a few creations and completions (values embed dates, so refresh).
    def milestone_value(milestone):
        return {
            "project_id": milestone.project_id, "title": milestone.title, "description": milestone.description,
            "target_date": str(milestone.target_date), "status": milestone.status.value,
            "completed_at": str(milestone.completed_at) if milestone.completed_at else None,
        }

    for key in ("phoenix_beta", "zephyr_pentest", "atlas_reports", "phoenix_alpha", "vega_golive"):
        milestone = milestones[key]
        project = db.get(Project, milestone.project_id)
        pm = pm_accounts[project.pm_id]
        created = milestone_value(milestone) | {"status": "pending", "completed_at": None}
        _audit_once(db, pm, AuditAction.CREATE, "PROJECT_MILESTONE", milestone.id, None, created,
                    at(project.start_date + timedelta(days=1)), refresh=True)
        if milestone.status == MilestoneStatus.COMPLETED:
            _audit_once(db, pm, AuditAction.UPDATE, "PROJECT_MILESTONE", milestone.id, created,
                        milestone_value(milestone), at(milestone.target_date, 18), refresh=True)

    # Successful logins (AuthService.login) and a fresh failed-login burst.
    for email, ip, hours_ago in LOGINS:
        user = account(email)
        _audit_once(
            db, user.account_id, AuditAction.LOGIN, "USER_ACCOUNT", user.account_id, None,
            {"email": user.email, "user_type": user.user_type.value, "mfa_verified": False},
            now - timedelta(hours=hours_ago), ip=ip,
        )
    for minutes_ago, email in zip(range(6, 0, -1), BURST_EMAILS):
        user = db.query(UserAccount).filter_by(email=email).first()
        _audit_once(
            db, user.account_id if user else None, AuditAction.LOGIN, "USER_ACCOUNT",
            user.account_id if user else "UNKNOWN", None, {"status": "FAILED", "attempted_email": email},
            now - timedelta(minutes=minutes_ago), ip=BURST_IP,
        )

    # Backups: the latest scheduled run failed, then an admin re-ran it on demand.
    sysadmin = ctx["accounts"]["sysadmin"].account_id
    for file_path, backup_type, status, hours_ago, size_mb in BACKUPS:
        lookup = {"file_path": file_path} if file_path else {"file_path": None, "status": "FAILED"}
        backup = _get_or_create(
            db, SystemBackupLog, lookup,
            backup_type=backup_type, status=status, created_at=now - timedelta(hours=hours_ago),
            file_size_bytes=size_mb * 1024 * 1024 if size_mb else None,
            triggered_by_account_id=sysadmin if backup_type == "ON_DEMAND" else None,
        )
        if backup_type == "ON_DEMAND":
            _audit_once(
                db, sysadmin, AuditAction.CREATE, "SYSTEM_BACKUP", backup.backup_id, None,
                {"status": status, "backup_name": file_path.rsplit("/", 1)[-1],
                 "file_size_bytes": backup.file_size_bytes},
                backup.created_at,
            )

    # Elevated access grants: one active, one expired, one revoked.
    admin = ctx["accounts"]["admin"].account_id
    for email, role, reason, granted, expires, revoked in GRANTS:
        _get_or_create(
            db, ElevatedAccessGrant, {"user_id": account(email).account_id, "granted_role": role, "reason": reason},
            granted_by=admin, granted_at=now + timedelta(hours=granted), expires_at=now + timedelta(hours=expires),
            revoked_at=now + timedelta(hours=revoked) if revoked is not None else None,
        )


def _seed_executive_reports(db: Session) -> None:
    """Generate the executive reports through ExecutiveReportService, as executive@company.com.

    generate_report commits, so this runs after everything else is committed. A report is
    skipped when its row and file exist; a row whose file is gone is removed and regenerated.
    """
    executive = db.query(UserAccount).filter_by(email="executive@company.com").one()
    today = date.today()  # generate_report validates periods against the real date
    for title, report_format, period_start, breakdown in REPORTS:
        existing = db.query(ExecutiveReport).filter_by(report_title=title).first()
        if existing is not None:
            if Path(existing.file_path).is_file():
                continue
            db.query(AuditLog).filter_by(entity_name="EXECUTIVE_REPORT", entity_ref_id=str(existing.report_id)).delete()
            db.delete(existing)
            db.commit()
        ExecutiveReportService.generate_report(
            db,
            ExecutiveReportCreateRequest(
                report_title=title, period_start=period_start(today), period_end=today,
                format=ReportFormat(report_format), include_department_breakdown=breakdown,
            ),
            executive,
        )


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
    ctx.update(_seed_support(db, ctx))
    ctx.update(_seed_deliverables(db, ctx))
    _seed_notifications(db, today, ctx)
    _seed_admin_ops(db, ctx)

    db.commit()
    _seed_executive_reports(db)  # last: generate_report commits on its own


def main() -> None:
    url = os.environ["DATABASE_URL"]
    if not url.startswith("sqlite") and os.getenv("SEED_ALLOW_NON_SQLITE") != "1":
        sys.exit(
            f"Refusing to seed {url.split('@')[-1]}: DATABASE_URL is not SQLite. "
            "Set SEED_ALLOW_NON_SQLITE=1 to seed it deliberately."
        )

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
