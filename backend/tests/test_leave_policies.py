import json
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
        self.admin = self.make_user(UserType.ADMIN)
        self.executive = self.make_user(UserType.MNC_EXECUTIVE)
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

    def test_list_policies_all_authenticated_roles(self):
        """Every logged-in role, including ADMIN and MNC_EXECUTIVE, can list policies, ordered by name."""
        self.db.add_all([
            LeaveType(name="Sick Leave", yearly_quota=10, is_paid=True),
            LeaveType(name="Annual Leave", yearly_quota=20, is_paid=True),
        ])
        self.db.commit()

        for user in (self.employee, self.pm_user, self.hr_user, self.admin, self.executive):
            resp = self.client.get("/api/v1/leave/policies", headers=self.headers(user))
            self.assertEqual(resp.status_code, 200, user.user_type)
            self.assertEqual([p["name"] for p in resp.json()], ["Annual Leave", "Sick Leave"])

    def test_include_inactive_for_hr_and_admin(self):
        """HR and ADMIN see deactivated policies with ?include_inactive=true."""
        self.db.add_all([
            LeaveType(name="Annual Leave", yearly_quota=20, is_paid=True, is_active=True),
            LeaveType(name="Old Sabbatical", yearly_quota=10, is_paid=False, is_active=False),
        ])
        self.db.commit()

        for user in (self.hr_user, self.admin):
            resp = self.client.get(
                "/api/v1/leave/policies?include_inactive=true", headers=self.headers(user)
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual({p["name"] for p in resp.json()}, {"Annual Leave", "Old Sabbatical"})

    def test_inactive_policies_hidden_from_non_hr(self):
        """include_inactive is ignored for roles other than HR and ADMIN."""
        self.db.add_all([
            LeaveType(name="Annual Leave", yearly_quota=20, is_paid=True, is_active=True),
            LeaveType(name="Old Sabbatical", yearly_quota=10, is_paid=False, is_active=False),
        ])
        self.db.commit()

        resp = self.client.get(
            "/api/v1/leave/policies?include_inactive=true", headers=self.headers(self.employee)
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([p["name"] for p in resp.json()], ["Annual Leave"])

    def test_patch_method_not_supported(self):
        """Updates use PUT; PATCH is not routed."""
        lt = LeaveType(name="Annual Leave", yearly_quota=20, is_paid=True)
        self.db.add(lt)
        self.db.commit()
        resp = self.client.patch(
            f"/api/v1/leave/policies/{lt.leave_type_id}",
            json={"yearly_quota": 5},
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 405)

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
        audit = self.db.query(AuditLog).filter(AuditLog.entity_name == "LEAVE_POLICY").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action, AuditAction.CREATE)
        self.assertEqual(audit.account_id, self.hr_user.account_id)
        self.assertIn("Sick Leave", audit.new_value)

    def test_create_policy_admin_success(self):
        """ADMIN can also create leave policies."""
        payload = {
            "name": "Maternity Leave",
            "yearly_quota": 90,
            "is_paid": True,
            "description": "Maternity benefit leave",
        }
        resp = self.client.post("/api/v1/leave/policies", json=payload, headers=self.headers(self.admin))
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
        """HR updates yearly_quota and description via PUT; returns 200 with updated fields."""
        lt = LeaveType(name="Bereavement Leave", yearly_quota=3, is_paid=True, is_active=True)
        self.db.add(lt)
        self.db.commit()

        payload = {"yearly_quota": 5, "description": "Extended bereavement period"}
        resp = self.client.put(
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
            AuditLog.entity_name == "LEAVE_POLICY",
            AuditLog.entity_ref_id == str(lt.leave_type_id),
            AuditLog.action == AuditAction.UPDATE,
        ).first()
        self.assertIsNotNone(audit)
        self.assertIn('"yearly_quota": 3', audit.old_value)
        self.assertIn('"yearly_quota": 5', audit.new_value)

    def test_update_policy_rename(self):
        """PUT can rename a policy; changing only the case of its own name is allowed."""
        lt = LeaveType(name="Casual Leave", yearly_quota=10, is_paid=True)
        self.db.add(lt)
        self.db.commit()

        resp = self.client.put(
            f"/api/v1/leave/policies/{lt.leave_type_id}",
            json={"name": "  CASUAL leave "},
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "CASUAL leave")

    def test_update_policy_rename_collision_returns_409(self):
        """Renaming onto another policy's name (any case) returns 409."""
        self.db.add(LeaveType(name="Sick Leave", yearly_quota=10, is_paid=True))
        lt = LeaveType(name="Casual Leave", yearly_quota=10, is_paid=True)
        self.db.add(lt)
        self.db.commit()

        resp = self.client.put(
            f"/api/v1/leave/policies/{lt.leave_type_id}",
            json={"name": "sick leave"},
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["detail"], "Leave policy with this name already exists")

    def test_update_policy_audits_only_changed_fields(self):
        """old_value/new_value hold only the changed fields; a no-op update writes no audit row."""
        lt = LeaveType(name="Study Leave", yearly_quota=10, is_paid=False)
        self.db.add(lt)
        self.db.commit()
        url = f"/api/v1/leave/policies/{lt.leave_type_id}"

        resp = self.client.put(url, json={"yearly_quota": 12, "is_paid": False}, headers=self.headers(self.hr_user))
        self.assertEqual(resp.status_code, 200)
        audits = self.db.query(AuditLog).filter(AuditLog.entity_name == "LEAVE_POLICY").all()
        self.assertEqual(len(audits), 1)
        self.assertEqual(json.loads(audits[0].old_value), {"yearly_quota": 10})
        self.assertEqual(json.loads(audits[0].new_value), {"yearly_quota": 12})

        resp = self.client.put(url, json={"yearly_quota": 12}, headers=self.headers(self.hr_user))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.db.query(AuditLog).filter(AuditLog.entity_name == "LEAVE_POLICY").count(), 1)

    def test_update_policy_null_for_required_field_returns_422(self):
        """Explicit null for a non-nullable field is rejected instead of hitting the database."""
        lt = LeaveType(name="Annual Leave", yearly_quota=20, is_paid=True)
        self.db.add(lt)
        self.db.commit()
        resp = self.client.put(
            f"/api/v1/leave/policies/{lt.leave_type_id}",
            json={"yearly_quota": None},
            headers=self.headers(self.hr_user),
        )
        self.assertEqual(resp.status_code, 422)

    def test_update_policy_reactivate(self):
        """HR can reactivate an inactive policy by passing is_active=True in PUT."""
        lt = LeaveType(name="Study Leave", yearly_quota=10, is_paid=False, is_active=False)
        self.db.add(lt)
        self.db.commit()

        resp = self.client.put(
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

        resp = self.client.put(
            f"/api/v1/leave/policies/{lt.leave_type_id}",
            json={"yearly_quota": 20},
            headers=self.headers(self.employee),
        )
        self.assertEqual(resp.status_code, 403)

    def test_update_policy_not_found(self):
        """Updating a nonexistent policy returns 404."""
        resp = self.client.put(
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
