import os
import unittest
import uuid
from datetime import date, datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, LeaveStatus, UserType
from app.models.leave import LeaveRequest, LeaveType
from app.models.user_account import UserAccount


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


class TestLeavePolicies(unittest.TestCase):
    """Unit and integration test suite for S4-BE-2: HR Leave Policy & Yearly Quota Configuration API."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        self.db = TestingSessionLocal()
        self.db.query(AuditLog).delete()
        self.db.query(LeaveRequest).delete()
        self.db.query(LeaveType).delete()
        self.db.query(UserAccount).delete()
        self.db.commit()

        # Seed test actors
        self.hr_user = self.make_user(UserType.HR)
        self.sys_admin = self.make_user(UserType.SYSTEM_ADMIN)
        self.employee = self.make_user(UserType.EMPLOYEE)
        self.pm_user = self.make_user(UserType.PM)

    def tearDown(self):
        self.db.close()

    def make_user(self, role: UserType) -> UserAccount:
        user = UserAccount(
            account_id=uuid.uuid4(),
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("Pass12345!"),
            user_type=role,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        return user

    def headers(self, user: UserAccount) -> dict:
        token = create_access_token(
            data={
                "sub": str(user.account_id),
                "email": user.email,
                "user_type": user.user_type.value,
            }
        )
        return {"Authorization": f"Bearer {token}"}

    # ─────────────────────────────────────────────────────────────
    # 1. List Policies Tests
    # ─────────────────────────────────────────────────────────────

    def test_list_active_policies_empty(self):
        """GET /api/v1/leave/policies returns empty list when no leave types exist."""
        resp = self.client.get("/api/v1/leave/policies", headers=self.headers(self.employee))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_active_policies_filters_inactive(self):
        """GET /api/v1/leave/policies returns only active policies to employees."""
        active = LeaveType(name="Annual Leave", yearly_quota=20, is_paid=True, is_active=True)
        inactive = LeaveType(name="Obsolete Leave", yearly_quota=5, is_paid=False, is_active=False)
        self.db.add_all([active, inactive])
        self.db.commit()

        resp = self.client.get("/api/v1/leave/policies", headers=self.headers(self.employee))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Annual Leave")
        self.assertTrue(data[0]["is_active"])

    def test_list_all_policies_hr_success(self):
        """GET /api/v1/leave/policies/all returns active and inactive policies for HR."""
        active = LeaveType(name="Annual Leave", yearly_quota=20, is_paid=True, is_active=True)
        inactive = LeaveType(name="Old Sabbatical", yearly_quota=10, is_paid=False, is_active=False)
        self.db.add_all([active, inactive])
        self.db.commit()

        resp = self.client.get("/api/v1/leave/policies/all", headers=self.headers(self.hr_user))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        names = {item["name"] for item in data}
        self.assertIn("Annual Leave", names)
        self.assertIn("Old Sabbatical", names)

    def test_list_all_policies_forbidden_for_employee(self):
        """GET /api/v1/leave/policies/all returns 403 Forbidden for non-HR/Admin."""
        resp = self.client.get("/api/v1/leave/policies/all", headers=self.headers(self.employee))
        self.assertEqual(resp.status_code, 403)

    # ─────────────────────────────────────────────────────────────
    # 2. Create Policy Tests
    # ─────────────────────────────────────────────────────────────

    def test_create_policy_success(self):
        """HR creates a valid leave policy; returns 201 with persisted data and audit log."""
        payload = {
            "name": "Sick Leave",
            "yearly_quota": 12,
            "is_paid": True,
            "description": "Paid time off for medical recovery and doctor appointments",
        }
        resp = self.client.post("/api/v1/leave/policies", json=payload, headers=self.headers(self.hr_user))
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["name"], "Sick Leave")
        self.assertEqual(data["yearly_quota"], 12)
        self.assertTrue(data["is_paid"])
        self.assertTrue(data["is_active"])
        self.assertIn("leave_type_id", data)

        # Verify audit log was recorded
        audit = self.db.query(AuditLog).filter(AuditLog.entity_name == "LEAVE_TYPE").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action, AuditAction.CREATE)
        self.assertEqual(audit.account_id, self.hr_user.account_id)
        self.assertIn("Sick Leave", audit.new_value)

    def test_create_policy_system_admin_success(self):
        """SYSTEM_ADMIN can also create leave policies."""
        payload = {
            "name": "Maternity Leave",
            "yearly_quota": 90,
            "is_paid": True,
            "description": "Maternity benefit leave",
        }
        resp = self.client.post("/api/v1/leave/policies", json=payload, headers=self.headers(self.sys_admin))
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["name"], "Maternity Leave")

    def test_create_policy_forbidden_for_employee_and_pm(self):
        """Employees and PMs receive 403 Forbidden when creating policies."""
        payload = {"name": "Hacking Leave", "yearly_quota": 10, "is_paid": True}
        resp_emp = self.client.post("/api/v1/leave/policies", json=payload, headers=self.headers(self.employee))
        self.assertEqual(resp_emp.status_code, 403)

        resp_pm = self.client.post("/api/v1/leave/policies", json=payload, headers=self.headers(self.pm_user))
        self.assertEqual(resp_pm.status_code, 403)

    def test_create_policy_duplicate_name_rejected(self):
        """Creating a policy with duplicate name (case-insensitive) returns 409 Conflict."""
        existing = LeaveType(name="Casual Leave", yearly_quota=10, is_paid=True)
        self.db.add(existing)
        self.db.commit()

        payload = {"name": "casual leave", "yearly_quota": 15, "is_paid": True}
        resp = self.client.post("/api/v1/leave/policies", json=payload, headers=self.headers(self.hr_user))
        self.assertEqual(resp.status_code, 409)
        self.assertIn("already exists", resp.json()["detail"].lower())

    def test_create_policy_validation_invalid_quota(self):
        """Negative quota or exceeding 366 returns 422 Unprocessable Entity."""
        payload_neg = {"name": "Bad Leave", "yearly_quota": -5, "is_paid": True}
        resp = self.client.post("/api/v1/leave/policies", json=payload_neg, headers=self.headers(self.hr_user))
        self.assertEqual(resp.status_code, 422)

        payload_too_big = {"name": "Bad Leave 2", "yearly_quota": 367, "is_paid": True}
        resp2 = self.client.post("/api/v1/leave/policies", json=payload_too_big, headers=self.headers(self.hr_user))
        self.assertEqual(resp2.status_code, 422)

    def test_create_policy_blank_name_returns_422(self):
        """A whitespace-only name is stripped first, so it fails the 2-char minimum."""
        resp = self.client.post(
            "/api/v1/leave/policies",
            json={"name": "   ", "yearly_quota": 3},
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 422)

    def test_create_policy_accepts_spec_upper_limits(self):
        """yearly_quota 366 and a 1000-char description are valid; name is stored stripped."""
        resp = self.client.post(
            "/api/v1/leave/policies",
            json={"name": "  Leap Leave  ", "yearly_quota": 366, "description": "x" * 1000},
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["name"], "Leap Leave")

        too_long = self.client.post(
            "/api/v1/leave/policies",
            json={"name": "Long Leave", "yearly_quota": 1, "description": "x" * 1001},
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(too_long.status_code, 422)

    # ─────────────────────────────────────────────────────────────
    # 4. Update Policy Tests
    # ─────────────────────────────────────────────────────────────

    def test_update_policy_quota_and_description(self):
        """HR updates yearly_quota and description via PATCH; returns 200 with updated fields."""
        lt = LeaveType(name="Bereavement Leave", yearly_quota=3, is_paid=True, is_active=True)
        self.db.add(lt)
        self.db.commit()

        payload = {"yearly_quota": 5, "description": "Extended bereavement period"}
        resp = self.client.patch(
            f"/api/v1/leave/policies/{lt.leave_type_id}",
            json=payload,
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["yearly_quota"], 5)
        self.assertEqual(data["description"], "Extended bereavement period")
        self.assertTrue(data["is_paid"])  # Unchanged

        # Verify audit log recorded old and new values
        audit = self.db.query(AuditLog).filter(
            AuditLog.entity_name == "LEAVE_TYPE",
            AuditLog.entity_ref_id == str(lt.leave_type_id),
            AuditLog.action == AuditAction.UPDATE,
        ).first()
        self.assertIsNotNone(audit)
        self.assertIn('"yearly_quota": 3', audit.old_value)
        self.assertIn('"yearly_quota": 5', audit.new_value)

    def test_update_policy_reactivate(self):
        """HR can reactivate an inactive policy by passing is_active=True in PATCH."""
        lt = LeaveType(name="Study Leave", yearly_quota=10, is_paid=False, is_active=False)
        self.db.add(lt)
        self.db.commit()

        resp = self.client.patch(
            f"/api/v1/leave/policies/{lt.leave_type_id}",
            json={"is_active": True},
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["is_active"])

    def test_update_policy_forbidden_for_employee(self):
        """Employee cannot update leave policies (403 Forbidden)."""
        lt = LeaveType(name="Test Policy", yearly_quota=5, is_paid=True)
        self.db.add(lt)
        self.db.commit()

        resp = self.client.patch(
            f"/api/v1/leave/policies/{lt.leave_type_id}",
            json={"yearly_quota": 20},
            headers=self.headers(self.employee),
        )
        self.assertEqual(resp.status_code, 403)

    def test_update_policy_not_found(self):
        """Updating a nonexistent policy returns 404."""
        resp = self.client.patch(
            "/api/v1/leave/policies/88888",
            json={"yearly_quota": 10},
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 404)

    # ─────────────────────────────────────────────────────────────
    # 7. Unauthenticated Access Tests
    # ─────────────────────────────────────────────────────────────

    def test_unauthenticated_requests_return_401(self):
        """Requests without Authorization header return 401 Unauthorized."""
        resp1 = self.client.get("/api/v1/leave/policies")
        self.assertEqual(resp1.status_code, 401)

        resp2 = self.client.post("/api/v1/leave/policies", json={"name": "Test", "yearly_quota": 5})
        self.assertEqual(resp2.status_code, 401)


if __name__ == "__main__":
    unittest.main()
