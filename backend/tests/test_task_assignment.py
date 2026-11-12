import unittest
from datetime import date
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.enums import UserType, CommonStatus, PriorityLevel, TaskStatus, TeamStatus, AuditAction
from app.models.user_account import UserAccount
from app.models.employee import Employee
from app.models.project import Project
from app.models.team import Team, TeamMember
from app.models.task import Task
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.features.tasks.router import router as tasks_router


class TestTaskAssignmentAndReassignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=cls.engine, expire_on_commit=False
        )
        Base.metadata.create_all(bind=cls.engine)

        cls.app = FastAPI()
        cls.app.include_router(tasks_router)

        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        cls.app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(cls.app)

    def setUp(self):
        db = self.TestingSessionLocal()
        db.query(AuditLog).delete()
        db.query(Notification).delete()
        db.query(Task).delete()
        db.query(TeamMember).delete()
        db.query(Team).delete()
        db.query(Project).delete()
        db.query(Employee).delete()
        db.query(UserAccount).delete()
        db.commit()

        # 1. User Accounts
        self.pm_user = UserAccount(
            account_id=uuid4(), email="pm@example.com", password_hash="hash", user_type=UserType.PM, is_active=True
        )
        self.lead_user = UserAccount(
            account_id=uuid4(), email="lead@example.com", password_hash="hash", user_type=UserType.EMPLOYEE, is_active=True
        )
        self.emp1_user = UserAccount(
            account_id=uuid4(), email="emp1@example.com", password_hash="hash", user_type=UserType.EMPLOYEE, is_active=True
        )
        self.emp2_user = UserAccount(
            account_id=uuid4(), email="emp2@example.com", password_hash="hash", user_type=UserType.EMPLOYEE, is_active=True
        )
        self.outsider_user = UserAccount(
            account_id=uuid4(), email="outsider@example.com", password_hash="hash", user_type=UserType.EMPLOYEE, is_active=True
        )
        db.add_all([self.pm_user, self.lead_user, self.emp1_user, self.emp2_user, self.outsider_user])
        db.commit()

        # 2. Employees
        self.pm_emp = Employee(
            emp_id=1, account_id=self.pm_user.account_id, emp_code="EMP001", full_name="Project Manager",
            email="pm@example.com", designation="PM", date_of_joining=date.today(), status=CommonStatus.ACTIVE,
        )
        self.lead_emp = Employee(
            emp_id=2, account_id=self.lead_user.account_id, emp_code="EMP002", full_name="Team Lead",
            email="lead@example.com", designation="Lead Developer", date_of_joining=date.today(), status=CommonStatus.ACTIVE,
        )
        self.emp1 = Employee(
            emp_id=3, account_id=self.emp1_user.account_id, emp_code="EMP003", full_name="Dev One",
            email="emp1@example.com", designation="Software Engineer", date_of_joining=date.today(), status=CommonStatus.ACTIVE,
        )
        self.emp2 = Employee(
            emp_id=4, account_id=self.emp2_user.account_id, emp_code="EMP004", full_name="Dev Two",
            email="emp2@example.com", designation="Senior Engineer", date_of_joining=date.today(), status=CommonStatus.ACTIVE,
        )
        self.outsider_emp = Employee(
            emp_id=5, account_id=self.outsider_user.account_id, emp_code="EMP005", full_name="Outsider Dev",
            email="outsider@example.com", designation="QA", date_of_joining=date.today(), status=CommonStatus.ACTIVE,
        )
        db.add_all([self.pm_emp, self.lead_emp, self.emp1, self.emp2, self.outsider_emp])
        db.commit()

        # 3. Project & Team
        self.project = Project(
            project_id=1, client_id=1, pm_id=1, project_code="PRJ-100", name="Core Project",
            start_date=date.today(),
        )
        db.add(self.project)
        db.commit()

        self.team = Team(
            team_id=1, project_id=1, lead_emp_id=self.lead_emp.emp_id, name="Backend Team",
            status=TeamStatus.ACTIVE,
        )
        db.add(self.team)
        db.commit()

        # Add Lead, Emp1, Emp2 to TeamMember
        db.add_all([
            TeamMember(team_id=1, emp_id=self.lead_emp.emp_id),
            TeamMember(team_id=1, emp_id=self.emp1.emp_id),
            TeamMember(team_id=1, emp_id=self.emp2.emp_id),
        ])
        db.commit()

        # 4. Tasks
        self.task_unassigned = Task(
            task_id=1, project_id=1, team_id=1, assigned_to=None, title="Unassigned Task",
            description="Initial backlog task", priority=PriorityLevel.MEDIUM, status=TaskStatus.TODO,
        )
        self.task_assigned = Task(
            task_id=2, project_id=1, team_id=1, assigned_to=self.emp1.emp_id, title="Active Sprint Task",
            description="In progress task", priority=PriorityLevel.HIGH, status=TaskStatus.IN_PROGRESS,
        )
        db.add_all([self.task_unassigned, self.task_assigned])
        db.commit()
        db.close()

    # ==========================================
    # Task Assignment Tests (US-09)
    # ==========================================

    def test_assign_task_success(self):
        """PM successfully assigns an unassigned task to a valid team member."""
        self.app.dependency_overrides[get_current_user] = lambda: self.pm_user
        res = self.client.put("/api/v1/tasks/1/assign", json={"assignee_id": self.emp1.emp_id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["assigned_to"], self.emp1.emp_id)

        # Verify notification
        db = self.TestingSessionLocal()
        notif = db.query(Notification).filter_by(account_id=self.emp1_user.account_id, type="TASK_ASSIGNED").first()
        self.assertIsNotNone(notif)
        self.assertIn("Unassigned Task", notif.title + notif.message)

        # Verify audit log
        audit = db.query(AuditLog).filter_by(entity_name="TASK", entity_ref_id="1").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action, AuditAction.UPDATE)
        db.close()

    def test_assign_task_team_lead_success(self):
        """Team Lead can assign a task belonging to their team."""
        self.app.dependency_overrides[get_current_user] = lambda: self.lead_user
        res = self.client.put("/api/v1/tasks/1/assign", json={"assignee_id": self.emp2.emp_id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["assigned_to"], self.emp2.emp_id)

    def test_assign_task_outsider_rejected(self):
        """Assigning an employee outside the team returns 400 Bad Request."""
        self.app.dependency_overrides[get_current_user] = lambda: self.pm_user
        res = self.client.put("/api/v1/tasks/1/assign", json={"assignee_id": self.outsider_emp.emp_id})
        self.assertEqual(res.status_code, 400)
        self.assertIn("not an active member of the task team", res.json()["detail"].lower())

    def test_assign_task_unauthorized_employee(self):
        """Regular employee who is not team lead cannot assign tasks (403 Forbidden)."""
        self.app.dependency_overrides[get_current_user] = lambda: self.emp1_user
        res = self.client.put("/api/v1/tasks/1/assign", json={"assignee_id": self.emp2.emp_id})
        self.assertEqual(res.status_code, 403)

    def test_assign_task_nonexistent_task(self):
        """Assigning a nonexistent task ID returns 404 Not Found."""
        self.app.dependency_overrides[get_current_user] = lambda: self.pm_user
        res = self.client.put("/api/v1/tasks/9999/assign", json={"assignee_id": self.emp1.emp_id})
        self.assertEqual(res.status_code, 404)

    def test_assign_task_nonexistent_assignee(self):
        """Assigning to a nonexistent employee ID returns 404 Not Found."""
        self.app.dependency_overrides[get_current_user] = lambda: self.pm_user
        res = self.client.put("/api/v1/tasks/1/assign", json={"assignee_id": 8888})
        self.assertEqual(res.status_code, 404)

    # ==========================================
    # Task Reassignment Tests (US-14)
    # ==========================================

    def test_reassign_task_success(self):
        """PM reassigns task to new team member with valid reason, triggering dual notifications."""
        self.app.dependency_overrides[get_current_user] = lambda: self.pm_user
        reason = "Previous assignee on medical leave; shifting sprint workload."
        res = self.client.put(
            "/api/v1/tasks/2/reassign",
            json={"new_assignee_id": self.emp2.emp_id, "reason": reason},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["assigned_to"], self.emp2.emp_id)

        # Verify dual notifications
        db = self.TestingSessionLocal()
        new_notif = db.query(Notification).filter_by(account_id=self.emp2_user.account_id, type="TASK_ASSIGNED").first()
        prev_notif = db.query(Notification).filter_by(account_id=self.emp1_user.account_id, type="TASK_REASSIGNED").first()
        self.assertIsNotNone(new_notif)
        self.assertIsNotNone(prev_notif)
        self.assertIn("Active Sprint Task", prev_notif.message)
        self.assertIn(reason, prev_notif.message)

        # Verify audit log includes reason and both employee IDs
        audit = db.query(AuditLog).filter_by(entity_name="TASK", entity_ref_id="2").first()
        self.assertIsNotNone(audit)
        self.assertIn("3", audit.old_value)
        self.assertIn("4", audit.new_value)
        self.assertIn(reason, audit.new_value)
        db.close()

    def test_reassign_task_same_assignee_rejected(self):
        """Reassigning task to the same employee returns 400 Bad Request."""
        self.app.dependency_overrides[get_current_user] = lambda: self.pm_user
        res = self.client.put(
            "/api/v1/tasks/2/reassign",
            json={"new_assignee_id": self.emp1.emp_id, "reason": "Redundant reassignment attempt"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("current assignee", res.json()["detail"].lower())

    def test_reassign_task_short_reason_rejected(self):
        """Reassigning without at least 10 characters reason returns 422 Unprocessable Entity."""
        self.app.dependency_overrides[get_current_user] = lambda: self.pm_user
        res = self.client.put(
            "/api/v1/tasks/2/reassign",
            json={"new_assignee_id": self.emp2.emp_id, "reason": "Too short"},
        )
        self.assertEqual(res.status_code, 422)

    def test_reassign_task_outsider_rejected(self):
        """Reassigning to an outsider not in the team returns 400 Bad Request."""
        self.app.dependency_overrides[get_current_user] = lambda: self.pm_user
        res = self.client.put(
            "/api/v1/tasks/2/reassign",
            json={"new_assignee_id": self.outsider_emp.emp_id, "reason": "Invalid transfer outside team"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("not an active member of the task team", res.json()["detail"].lower())

    def test_reassign_task_unauthorized_employee(self):
        """Non-lead employee attempting reassignment returns 403 Forbidden."""
        self.app.dependency_overrides[get_current_user] = lambda: self.emp1_user
        res = self.client.put(
            "/api/v1/tasks/2/reassign",
            json={"new_assignee_id": self.emp2.emp_id, "reason": "Unauthorized reassignment"},
        )
        self.assertEqual(res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
