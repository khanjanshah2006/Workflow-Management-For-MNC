import unittest
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.enums import UserType, PriorityLevel, AuditAction
from app.models.user_account import UserAccount
from app.models.employee import Employee
from app.models.support_ticket import SupportTicket, TicketActivity
from app.models.notification import Notification
from app.models.audit_log import AuditLog

# Setup an in-memory SQLite database for testing
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class TestSupportTicketEscalation(unittest.TestCase):
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
        # Clean up database tables before each test
        self.db = TestingSessionLocal()
        self.db.query(TicketActivity).delete()
        self.db.query(SupportTicket).delete()
        self.db.query(Notification).delete()
        self.db.query(AuditLog).delete()
        self.db.query(Employee).delete()
        self.db.query(UserAccount).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _create_user(self, email: str, user_type: UserType, is_active: bool = True) -> UserAccount:
        user = UserAccount(
            account_id=uuid.uuid4(),
            email=email,
            password_hash=hash_password("Secret123!"),
            user_type=user_type,
            is_active=is_active,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _get_auth_headers(self, user: UserAccount) -> dict:
        user_type_val = (
            user.user_type.value
            if hasattr(user.user_type, "value")
            else str(user.user_type)
        )
        token = create_access_token(
            data={"sub": str(user.account_id), "email": user.email, "user_type": user_type_val}
        )
        return {"Authorization": f"Bearer {token}"}

    def _create_ticket(self, ticket_number: str = "TKT-1001", status: str = "open") -> SupportTicket:
        ticket = SupportTicket(
            ticket_number=ticket_number,
            title="Database Latency Alert",
            description="High latency observed on main database cluster.",
            category="Infrastructure",
            priority=PriorityLevel.HIGH,
            status=status,
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def test_successful_escalation_open_ticket(self):
        """
        Verify successful ticket escalation from 'open' status:
        - IT_SUPPORT authorization
        - Reason in payload
        - Status updated to 'escalated'
        - ESCALATED activity created with actor and reason
        - Strictly actual SYSTEM_ADMIN users receive notifications (ADMIN is not assumed equivalent)
        - Inactive sysadmins, general admins, and normal users receive NO notification
        - Audit log is recorded
        """
        it_user = self._create_user("itsupport@mnc.com", UserType.IT_SUPPORT)
        sysadmin1 = self._create_user("sysadmin1@mnc.com", UserType.SYSTEM_ADMIN)
        sysadmin2 = self._create_user("sysadmin2@mnc.com", UserType.SYSTEM_ADMIN)
        general_admin = self._create_user("admin_general@mnc.com", UserType.ADMIN)
        inactive_sysadmin = self._create_user("inactive_sysadmin@mnc.com", UserType.SYSTEM_ADMIN, is_active=False)
        regular_emp = self._create_user("emp@mnc.com", UserType.EMPLOYEE)

        ticket = self._create_ticket("TKT-2001", status="open")
        headers = self._get_auth_headers(it_user)

        response = self.client.put(
            f"/api/v1/support/tickets/{ticket.ticket_id}/escalate",
            headers=headers,
            json={"reason": "Requires root infrastructure failover"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["ticket_id"], ticket.ticket_id)
        self.assertEqual(data["status"], "escalated")
        self.assertEqual(data["escalation_reason"], "Requires root infrastructure failover")

        # Verify DB ticket state
        self.db.expire_all()
        refreshed_ticket = self.db.get(SupportTicket, ticket.ticket_id)
        self.assertEqual(refreshed_ticket.status, "escalated")
        self.assertEqual(refreshed_ticket.escalation_reason, "Requires root infrastructure failover")

        # Verify TicketActivity
        activities = (
            self.db.query(TicketActivity)
            .filter(TicketActivity.ticket_id == ticket.ticket_id)
            .all()
        )
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0].activity_type, "ESCALATED")
        self.assertEqual(activities[0].details, "Requires root infrastructure failover")
        self.assertEqual(activities[0].actor_account_id, it_user.account_id)

        # Verify Notifications sent strictly to eligible SYSTEM_ADMIN users
        notifications = self.db.query(Notification).all()
        self.assertEqual(len(notifications), 2)
        notified_accounts = {n.account_id for n in notifications}
        self.assertIn(sysadmin1.account_id, notified_accounts)
        self.assertIn(sysadmin2.account_id, notified_accounts)
        self.assertNotIn(general_admin.account_id, notified_accounts)
        self.assertNotIn(inactive_sysadmin.account_id, notified_accounts)
        self.assertNotIn(regular_emp.account_id, notified_accounts)

        for n in notifications:
            self.assertEqual(n.type, "TICKET_ESCALATED")
            self.assertIn("TKT-2001", n.title)
            self.assertIn("Requires root infrastructure failover", n.message)
            self.assertFalse(n.is_read)

        # Verify Audit Log
        audit_logs = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.entity_name == "SUPPORT_TICKET",
                AuditLog.entity_ref_id == str(ticket.ticket_id),
            )
            .all()
        )
        self.assertTrue(len(audit_logs) >= 1)
        self.assertEqual(audit_logs[0].action, AuditAction.UPDATE)

    def test_successful_escalation_in_progress_ticket(self):
        """Verify escalation works when ticket is in 'in_progress' status."""
        it_user = self._create_user("it2@mnc.com", UserType.IT_SUPPORT)
        sysadmin = self._create_user("sysadmin_inprog@mnc.com", UserType.SYSTEM_ADMIN)
        ticket = self._create_ticket("TKT-2002", status="in_progress")

        response = self.client.put(
            f"/api/v1/support/tickets/{ticket.ticket_id}/escalate",
            headers=self._get_auth_headers(it_user),
            json={"reason": "Vendor SLA breached, escalating to sysadmin"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "escalated")

        # Verify DB ticket
        self.db.expire_all()
        refreshed = self.db.get(SupportTicket, ticket.ticket_id)
        self.assertEqual(refreshed.status, "escalated")

    def test_unauthorized_access_non_it_support(self):
        """Verify non-IT_SUPPORT users receive 403 Forbidden."""
        ticket = self._create_ticket("TKT-3001", status="open")

        unauthorized_types = [
            UserType.EMPLOYEE,
            UserType.PM,
            UserType.HR,
            UserType.CLIENT,
            UserType.ADMIN,
        ]

        for u_type in unauthorized_types:
            user = self._create_user(f"user_{u_type.value.lower()}@mnc.com", u_type)
            headers = self._get_auth_headers(user)

            response = self.client.put(
                f"/api/v1/support/tickets/{ticket.ticket_id}/escalate",
                headers=headers,
                json={"reason": "Should not be allowed"},
            )
            self.assertEqual(
                response.status_code,
                403,
                f"Expected 403 for user_type {u_type.value}, got {response.status_code}",
            )

    def test_unauthenticated_access(self):
        """Verify request without token returns 401 Unauthorized."""
        ticket = self._create_ticket("TKT-4001", status="open")
        response = self.client.put(
            f"/api/v1/support/tickets/{ticket.ticket_id}/escalate",
            json={"reason": "No auth header provided"},
        )
        self.assertEqual(response.status_code, 401)

    def test_invalid_ticket_status(self):
        """Verify escalation is rejected for tickets not in open or in_progress status."""
        it_user = self._create_user("it_status@mnc.com", UserType.IT_SUPPORT)
        headers = self._get_auth_headers(it_user)

        invalid_statuses = ["escalated", "resolved", "closed"]

        for idx, inv_status in enumerate(invalid_statuses):
            ticket = self._create_ticket(f"TKT-INV-{idx}", status=inv_status)
            response = self.client.put(
                f"/api/v1/support/tickets/{ticket.ticket_id}/escalate",
                headers=headers,
                json={"reason": "Attempting invalid transition"},
            )
            self.assertEqual(
                response.status_code,
                400,
                f"Expected 400 for status {inv_status}, got {response.status_code}",
            )
            self.assertIn("Cannot escalate ticket with status", response.json()["detail"])

    def test_missing_ticket(self):
        """Verify 404 Not Found is returned for non-existent ticket ID."""
        it_user = self._create_user("it_missing@mnc.com", UserType.IT_SUPPORT)
        headers = self._get_auth_headers(it_user)

        response = self.client.put(
            "/api/v1/support/tickets/999999/escalate",
            headers=headers,
            json={"reason": "Non-existent ticket ID"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_missing_or_empty_escalation_reason(self):
        """Verify 422 Unprocessable Entity when reason is empty or missing."""
        it_user = self._create_user("it_validation@mnc.com", UserType.IT_SUPPORT)
        headers = self._get_auth_headers(it_user)
        ticket = self._create_ticket("TKT-VAL", status="open")

        # Empty string
        res1 = self.client.put(
            f"/api/v1/support/tickets/{ticket.ticket_id}/escalate",
            headers=headers,
            json={"reason": ""},
        )
        self.assertEqual(res1.status_code, 422)

        # Missing body field
        res2 = self.client.put(
            f"/api/v1/support/tickets/{ticket.ticket_id}/escalate",
            headers=headers,
            json={},
        )
        self.assertEqual(res2.status_code, 422)


if __name__ == "__main__":
    unittest.main()

