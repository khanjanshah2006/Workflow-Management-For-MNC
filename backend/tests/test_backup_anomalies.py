import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, UserType
from app.models.system_backup_log import SystemBackupLog
from app.models.user_account import UserAccount


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class TestBackupAndAnomalyAlerts(unittest.TestCase):
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
        self.db.query(SystemBackupLog).delete()
        self.db.query(UserAccount).delete()
        self.db.commit()
        self.admin = self.make_user(UserType.SYSTEM_ADMIN)
        self.general_admin = self.make_user(UserType.ADMIN)

    def tearDown(self):
        self.db.close()

    def make_user(self, role):
        user = UserAccount(
            account_id=uuid.uuid4(), email=f"{uuid.uuid4().hex}@example.com",
            password_hash=hash_password("TestPassword123!"),
            user_type=role, is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        return user

    def headers(self, user):
        token = create_access_token(data={
            "sub": str(user.account_id), "email": user.email,
            "user_type": user.user_type.value,
        })
        return {"Authorization": f"Bearer {token}"}

    def audit(self, action, entity, ref, new_value, ip="203.0.113.5",
              account_id=None, old_value=None, created_at=None):
        row = AuditLog(
            account_id=account_id, action=action, entity_name=entity,
            entity_ref_id=str(ref), new_value=new_value, old_value=old_value,
            ip_address=ip, created_at=created_at or datetime.now(timezone.utc),
        )
        self.db.add(row)
        self.db.commit()
        return row

    def test_admin_role_is_allowed_and_it_support_forbidden(self):
        response = self.client.get(
            "/api/v1/admin/anomaly-alerts",
            headers=self.headers(self.general_admin),
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            "/api/v1/admin/anomaly-alerts",
            headers=self.headers(self.make_user(UserType.IT_SUPPORT)),
        )
        self.assertEqual(response.status_code, 403)

    def test_system_admin_can_read_alerts(self):
        response = self.client.get(
            "/api/v1/admin/anomaly-alerts",
            headers=self.headers(self.admin),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_alerts"], 0)

    def test_six_failed_logins_trigger_alert_but_five_do_not(self):
        for _ in range(5):
            self.audit(AuditAction.LOGIN, "USER_ACCOUNT", "UNKNOWN",
                       '{"status":"FAILED","attempted_email":"victim@example.com"}')
        response = self.client.get(
            "/api/v1/admin/anomaly-alerts",
            headers=self.headers(self.admin),
        )
        self.assertEqual(response.json()["total_alerts"], 0)
        self.audit(AuditAction.LOGIN, "USER_ACCOUNT", "UNKNOWN",
                   '{"status":"FAILED","attempted_email":"victim@example.com"}')
        response = self.client.get(
            "/api/v1/admin/anomaly-alerts",
            headers=self.headers(self.admin),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_alerts"], 2)  # IP and account grouping

    def test_successful_login_is_not_counted(self):
        self.audit(AuditAction.LOGIN, "USER_ACCOUNT", "UNKNOWN",
                   '{"status":"SUCCESS","attempted_email":"victim@example.com"}')
        response = self.client.get(
            "/api/v1/admin/anomaly-alerts",
            headers=self.headers(self.admin),
        )
        self.assertEqual(response.json()["total_alerts"], 0)

    def test_privilege_promotion_is_detected_not_demotion(self):
        target = self.make_user(UserType.EMPLOYEE)
        self.audit(
            AuditAction.UPDATE, "USER_ACCOUNT", target.account_id,
            '{"user_type":"SYSTEM_ADMIN"}', account_id=self.admin.account_id,
            old_value='{"user_type":"EMPLOYEE"}',
        )
        response = self.client.get(
            "/api/v1/admin/anomaly-alerts",
            headers=self.headers(self.admin),
        )
        alerts = response.json()["alerts"]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["alert_type"], "PRIVILEGE_ESCALATION")
        self.assertEqual(alerts[0]["severity"], "CRITICAL")

    def test_missing_pg_dump_records_failed_backup(self):
        with patch.object(
            settings, "database_url_raw", "postgresql://postgres:secret@localhost:5432/testdb"
        ), patch.object(
            settings, "backup_dir", os.path.join(os.getcwd(), "test-backups")
        ), patch.object(
            settings, "pg_dump_path", ""
        ), patch("app.features.admin.service.shutil.which", return_value=None):
            response = self.client.post(
                "/api/v1/admin/backup/trigger",
                headers=self.headers(self.admin),
            )
        self.assertEqual(response.status_code, 503)
        row = self.db.query(SystemBackupLog).order_by(SystemBackupLog.backup_id.desc()).first()
        self.assertEqual(row.status, "FAILED")
        self.assertIsNone(row.file_path)


    def test_backup_failure_triggers_anomaly_alert(self):
        failed_log = SystemBackupLog(
            triggered_by_account_id=self.admin.account_id,
            backup_type="ON_DEMAND",
            file_path="Error: connection refused",
            status="FAILED",
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(failed_log)
        self.db.commit()

        response = self.client.get(
            "/api/v1/admin/anomaly-alerts",
            headers=self.headers(self.admin),
        )
        self.assertEqual(response.status_code, 200)
        alerts = response.json()["alerts"]
        backup_alerts = [a for a in alerts if a["alert_type"] == "BACKUP_FAILURE"]
        self.assertEqual(len(backup_alerts), 1)
        self.assertEqual(backup_alerts[0]["severity"], "HIGH")
        self.assertIn("fail", backup_alerts[0]["title"].lower())

    def test_backup_status_reflects_logs(self):
        success_log = SystemBackupLog(
            triggered_by_account_id=self.admin.account_id,
            backup_type="ON_DEMAND",
            file_path="backup_success.dump",
            file_size_bytes=1048576,
            status="COMPLETED",
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(success_log)
        self.db.commit()

        general_headers = create_access_token(data={
            "sub": str(self.general_admin.account_id), "email": self.general_admin.email,
            "user_type": self.general_admin.user_type.value,
        })
        response = self.client.get(
            "/api/v1/admin/system/backup-status",
            headers={"Authorization": f"Bearer {general_headers}"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "HEALTHY")
        self.assertIsNotNone(data["last_successful_backup"])


if __name__ == "__main__":
    unittest.main()
