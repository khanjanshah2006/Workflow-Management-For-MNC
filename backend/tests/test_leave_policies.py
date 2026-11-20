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
        """Negative quota or exceeding 365 returns 422 Unprocessable Entity."""
        payload_neg = {"name": "Bad Leave", "yearly_quota": -5, "is_paid": True}
        resp = self.client.post("/api/v1/leave/policies", json=payload_neg, headers=self.headers(self.hr_user))
        self.assertEqual(resp.status_code, 422)

        payload_too_big = {"name": "Bad Leave 2", "yearly_quota": 400, "is_paid": True}
        resp2 = self.client.post("/api/v1/leave/policies", json=payload_too_big, headers=self.headers(self.hr_user))
        self.assertEqual(resp2.status_code, 422)

    # ─────────────────────────────────────────────────────────────
    # 3. Get Single Policy Tests
    # ─────────────────────────────────────────────────────────────

    def test_get_policy_by_id_success(self):
        """Any authenticated user can fetch a single policy by ID."""
        lt = LeaveType(name="Parental Leave", yearly_quota=14, is_paid=True, description="Parental care")
        self.db.add(lt)
        self.db.commit()

        resp = self.client.get(f"/api/v1/leave/policies/{lt.leave_type_id}", headers=self.headers(self.employee))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["leave_type_id"], lt.leave_type_id)
        self.assertEqual(data["name"], "Parental Leave")
        self.assertEqual(data["yearly_quota"], 14)

    def test_get_policy_by_id_not_found(self):
        """Fetching a nonexistent policy returns 404 Not Found."""
        resp = self.client.get("/api/v1/leave/policies/99999", headers=self.headers(self.employee))
        self.assertEqual(resp.status_code, 404)

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
    # 5. Deactivate Policy Tests (Soft-Delete)
    # ─────────────────────────────────────────────────────────────

    def test_deactivate_policy_success(self):
        """HR deactivates a policy; is_active becomes False and audit log records change."""
        lt = LeaveType(name="Volunteering Day", yearly_quota=2, is_paid=True, is_active=True)
        self.db.add(lt)
        self.db.commit()

        resp = self.client.delete(
            f"/api/v1/leave/policies/{lt.leave_type_id}",
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["is_active"])

        # Check DB directly
        self.db.refresh(lt)
        self.assertFalse(lt.is_active)

    def test_deactivate_already_inactive_returns_conflict(self):
        """Calling DELETE on an already deactivated policy returns 409 Conflict."""
        lt = LeaveType(name="Old Policy", yearly_quota=2, is_paid=True, is_active=False)
        self.db.add(lt)
        self.db.commit()

        resp = self.client.delete(
            f"/api/v1/leave/policies/{lt.leave_type_id}",
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 409)

    def test_deactivate_policy_forbidden_for_employee(self):
        """Employee cannot deactivate leave policies (403 Forbidden)."""
        lt = LeaveType(name="Protected Policy", yearly_quota=5, is_paid=True)
        self.db.add(lt)
        self.db.commit()

        resp = self.client.delete(
            f"/api/v1/leave/policies/{lt.leave_type_id}",
            headers=self.headers(self.employee),
        )
        self.assertEqual(resp.status_code, 403)

    # ─────────────────────────────────────────────────────────────
    # 6. Employee Quota Balance Calculation Tests
    # ─────────────────────────────────────────────────────────────

    def test_employee_balance_full_quota_available(self):
        """Balance returns total quota and zero used days when no leaves are approved."""
        lt = LeaveType(name="Casual Leave", yearly_quota=12, is_paid=True, is_active=True)
        self.db.add(lt)
        self.db.commit()

        resp = self.client.get(
            f"/api/v1/leave/policies/{lt.leave_type_id}/balance/101",
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["yearly_quota"], 12)
        self.assertEqual(data["used_days"], 0)
        self.assertEqual(data["remaining_days"], 12)

    def test_employee_balance_reflects_approved_requests(self):
        """Balance correctly subtracts approved requests in the current year."""
        lt = LeaveType(name="Earned Leave", yearly_quota=15, is_paid=True, is_active=True)
        self.db.add(lt)
        self.db.commit()

        current_year = datetime.now(timezone.utc).year
        # 1 Approved request (3 days)
        req_approved = LeaveRequest(
            emp_id=102,
            leave_type_id=lt.leave_type_id,
            start_date=date(current_year, 3, 1),
            end_date=date(current_year, 3, 3),
            total_days=3,
            reason="Family vacation",
            status=LeaveStatus.APPROVED,
        )
        # 1 Pending request (4 days) - should NOT deduct from quota
        req_pending = LeaveRequest(
            emp_id=102,
            leave_type_id=lt.leave_type_id,
            start_date=date(current_year, 5, 1),
            end_date=date(current_year, 5, 4),
            total_days=4,
            reason="Pending trip",
            status=LeaveStatus.PENDING,
        )
        self.db.add_all([req_approved, req_pending])
        self.db.commit()

        resp = self.client.get(
            f"/api/v1/leave/policies/{lt.leave_type_id}/balance/102",
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["yearly_quota"], 15)
        self.assertEqual(data["used_days"], 3)
        self.assertEqual(data["remaining_days"], 12)

    def test_employee_balance_deactivated_policy_rejected(self):
        """Checking balance for a deactivated policy returns 409 Conflict."""
        lt = LeaveType(name="Discontinued Leave", yearly_quota=5, is_paid=False, is_active=False)
        self.db.add(lt)
        self.db.commit()

        resp = self.client.get(
            f"/api/v1/leave/policies/{lt.leave_type_id}/balance/103",
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 409)

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
