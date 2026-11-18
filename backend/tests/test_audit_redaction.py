import json
import unittest
from uuid import uuid4

from app.core.audit import _is_sensitive_key, _redact_data, _serialize_value, write_audit_log
from app.db.base import Base
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class TestAuditSecurityRedaction(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.TestingSessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_sensitive_key_detection(self):
        sensitive = [
            "password", "password_hash", "new_password", "old_password",
            "token", "access_token", "refresh_token", "secret", "mfa_secret",
            "credentials", "api_key", "secret_key", "user_password", "clientSecret",
            "AUTH_TOKEN", "bearer_token", "db_password"
        ]
        for key in sensitive:
            self.assertTrue(_is_sensitive_key(key), f"Expected '{key}' to be detected as sensitive")

        non_sensitive = ["email", "username", "account_id", "title", "status", "created_at", "action"]
        for key in non_sensitive:
            self.assertFalse(_is_sensitive_key(key), f"Expected '{key}' to be non-sensitive")

    def test_recursive_redact_data_nested_dict(self):
        payload = {
            "user": "admin",
            "auth": {
                "password": "SuperSecretPassword123!",
                "mfa_secret": "JBSWY3DPEHPK3PXP",
                "nested_profile": {
                    "api_key": "live_key_987654321",
                    "display_name": "Administrator",
                },
            },
            "status": "ACTIVE",
        }
        redacted = _redact_data(payload)
        self.assertEqual(redacted["user"], "admin")
        self.assertEqual(redacted["status"], "ACTIVE")
        self.assertEqual(redacted["auth"]["password"], "[REDACTED]")
        self.assertEqual(redacted["auth"]["mfa_secret"], "[REDACTED]")
        self.assertEqual(redacted["auth"]["nested_profile"]["api_key"], "[REDACTED]")
        self.assertEqual(redacted["auth"]["nested_profile"]["display_name"], "Administrator")

    def test_recursive_redact_data_nested_lists(self):
        payload = {
            "credentials_history": [
                {"token": "old_jwt_token_1", "created_at": "2026-01-01"},
                {"token": "old_jwt_token_2", "created_at": "2026-02-01"},
            ],
            "tags": ["security", "admin"],
        }
        redacted = _redact_data(payload)
        self.assertEqual(redacted["credentials_history"][0]["token"], "[REDACTED]")
        self.assertEqual(redacted["credentials_history"][0]["created_at"], "2026-01-01")
        self.assertEqual(redacted["credentials_history"][1]["token"], "[REDACTED]")
        self.assertEqual(redacted["tags"], ["security", "admin"])

    def test_serialize_value_handles_pre_serialized_json(self):
        json_str = json.dumps({
            "nested": {
                "password": "ClearTextPassword",
                "safe_field": 12345
            }
        })
        serialized = _serialize_value(json_str)
        self.assertIsNotNone(serialized)
        parsed = json.loads(serialized)
        self.assertEqual(parsed["nested"]["password"], "[REDACTED]")
        self.assertEqual(parsed["nested"]["safe_field"], 12345)

    def test_write_audit_log_persists_redacted_values(self):
        user_id = uuid4()
        success = write_audit_log(
            db=self.db,
            action=AuditAction.UPDATE,
            entity_name="USER_ACCOUNT",
            entity_ref_id=str(user_id),
            account_id=user_id,
            old_value={"auth": {"password_hash": "$2b$12$oldhashvalue"}},
            new_value={
                "email": "test@example.com",
                "credentials": {
                    "password": "NewSecretPassword!",
                    "access_token": "eyJh...sampletoken",
                },
            },
            commit=True,
        )
        self.assertTrue(success)

        row = self.db.query(AuditLog).filter_by(entity_ref_id=str(user_id)).first()
        self.assertIsNotNone(row)

        parsed_old = json.loads(row.old_value)
        self.assertEqual(parsed_old["auth"]["password_hash"], "[REDACTED]")

        parsed_new = json.loads(row.new_value)
        self.assertEqual(parsed_new["email"], "test@example.com")
        self.assertEqual(parsed_new["credentials"]["password"], "[REDACTED]")
        self.assertEqual(parsed_new["credentials"]["access_token"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
