import os
import unittest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.core.security import hash_password
from app.core.deps import get_current_user
from app.core.rbac import require_role
from app.models.enums import UserType, AuditAction
from app.models.user_account import UserAccount
from app.models.audit_log import AuditLog
from app.models.system_parameter import SystemParameter
from app.models.elevated_access_grant import ElevatedAccessGrant
from app.features.admin.router import router as admin_router


class TestAdminSystemParamsAndElevatedAccess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # In-memory SQLite shared pool for tests
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
        # admin_router already defines prefix="/api/v1/admin"
        cls.app.include_router(admin_router)

        # Mock protected test route requiring PM
        @cls.app.get("/api/v1/projects/pm-only-zone", dependencies=[Depends(require_role(["PM"]))])
        def pm_only_route():
            return {"status": "ok", "message": "Welcome PM"}

        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        cls.app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(cls.app)

    def setUp(self):
        # Clean state
        db = self.TestingSessionLocal()
        db.query(AuditLog).delete()
        db.query(ElevatedAccessGrant).delete()
        db.query(SystemParameter).delete()
        db.query(UserAccount).delete()
        db.commit()

        self.admin = UserAccount(
            account_id=uuid4(),
            email=f"admin_{uuid4().hex[:6]}@example.com",
            password_hash=hash_password("AdminPass123!"),
            user_type=UserType.ADMIN,
            is_active=True,
        )
        self.employee = UserAccount(
            account_id=uuid4(),
            email=f"employee_{uuid4().hex[:6]}@example.com",
            password_hash=hash_password("EmpPass123!"),
            user_type=UserType.EMPLOYEE,
            is_active=True,
        )
        db.add_all([self.admin, self.employee])

        # Seed system parameters
        params = [
            SystemParameter(
                key="session_timeout_minutes",
                value="60",
                value_type="integer",
                description="Default session timeout in minutes",
            ),
            SystemParameter(
                key="max_upload_size_mb",
                value="25",
                value_type="integer",
                description="Maximum file upload size in MB",
            ),
            SystemParameter(
                key="allow_client_signup",
                value="false",
                value_type="boolean",
                description="Whether public client self-signup is permitted",
            ),
        ]
        db.add_all(params)
        db.commit()
        db.close()

    def test_list_system_parameters(self):
        self.app.dependency_overrides[get_current_user] = lambda: self.admin
        res = self.client.get("/api/v1/admin/system-params")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 3)
        keys = {p["key"] for p in data}
        self.assertIn("session_timeout_minutes", keys)
        self.assertIn("max_upload_size_mb", keys)
        self.assertIn("allow_client_signup", keys)

    def test_update_system_parameter_valid(self):
        self.app.dependency_overrides[get_current_user] = lambda: self.admin
        res = self.client.put(
            "/api/v1/admin/system-params/session_timeout_minutes",
            json={"value": "120"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["value"], "120")

        # Verify audit log was recorded
        db = self.TestingSessionLocal()
        audit = db.query(AuditLog).filter_by(action=AuditAction.UPDATE).first()
        self.assertIsNotNone(audit)
        self.assertEqual(str(audit.account_id), str(self.admin.account_id))
        self.assertEqual(audit.entity_name, "SYSTEM_PARAMETER")
        self.assertEqual(audit.entity_ref_id, "session_timeout_minutes")
        db.close()

    def test_update_system_parameter_invalid_type(self):
        self.app.dependency_overrides[get_current_user] = lambda: self.admin
        res = self.client.put(
            "/api/v1/admin/system-params/session_timeout_minutes",
            json={"value": "not_an_int"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("not a valid integer", res.json()["detail"])

    def test_update_system_parameter_not_found(self):
        self.app.dependency_overrides[get_current_user] = lambda: self.admin
        res = self.client.put(
            "/api/v1/admin/system-params/non_existent_key",
            json={"value": "foo"},
        )
        self.assertEqual(res.status_code, 404)

    def test_create_elevated_access_past_expiry(self):
        self.app.dependency_overrides[get_current_user] = lambda: self.admin
        past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        res = self.client.post(
            "/api/v1/admin/elevated-access",
            json={
                "user_id": str(self.employee.account_id),
                "granted_role": "PM",
                "expires_at": past_time,
                "reason": "Test past grant",
            },
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("future", res.json()["detail"].lower())

    def test_create_elevated_access_unknown_user(self):
        self.app.dependency_overrides[get_current_user] = lambda: self.admin
        future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        res = self.client.post(
            "/api/v1/admin/elevated-access",
            json={
                "user_id": str(uuid4()),
                "granted_role": "PM",
                "expires_at": future_time,
                "reason": "Test unknown user",
            },
        )
        self.assertEqual(res.status_code, 404)

    def test_create_elevated_access_success_and_active_list(self):
        self.app.dependency_overrides[get_current_user] = lambda: self.admin
        future_time = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        res = self.client.post(
            "/api/v1/admin/elevated-access",
            json={
                "user_id": str(self.employee.account_id),
                "granted_role": "PM",
                "expires_at": future_time,
                "reason": "Acting PM for sprint 9",
            },
        )
        self.assertEqual(res.status_code, 201)
        grant_id = res.json()["id"]
        self.assertEqual(res.json()["granted_role"], "PM")
        self.assertEqual(res.json()["user_id"], str(self.employee.account_id))

        # List active grants
        list_res = self.client.get("/api/v1/admin/elevated-access/active")
        self.assertEqual(list_res.status_code, 200)
        grants = list_res.json()
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0]["id"], grant_id)

    def test_rbac_dynamic_elevation(self):
        # 1. Base Employee cannot access PM endpoint
        self.app.dependency_overrides[get_current_user] = lambda: self.employee
        res1 = self.client.get("/api/v1/projects/pm-only-zone")
        self.assertEqual(res1.status_code, 403)

        # 2. Grant PM elevation
        db = self.TestingSessionLocal()
        future_exp = datetime.now(timezone.utc) + timedelta(days=1)
        grant = ElevatedAccessGrant(
            user_id=self.employee.account_id,
            granted_by=self.admin.account_id,
            granted_role="PM",
            reason="Elevation for release QA",
            expires_at=future_exp,
        )
        db.add(grant)
        db.commit()
        grant_db_id = grant.id
        db.close()

        # 3. Employee now accesses PM endpoint dynamically
        res2 = self.client.get("/api/v1/projects/pm-only-zone")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["message"], "Welcome PM")

        # 4. Revoke grant -> access is immediately revoked
        db = self.TestingSessionLocal()
        g = db.query(ElevatedAccessGrant).filter_by(id=grant_db_id).first()
        g.revoked_at = datetime.now(timezone.utc)
        g.revoked_by_id = self.admin.account_id
        db.commit()
        db.close()

        res3 = self.client.get("/api/v1/projects/pm-only-zone")
        self.assertEqual(res3.status_code, 403)


if __name__ == "__main__":
    unittest.main()
