import base64
import re
import uuid
import zlib
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.rbac import require_role
from app.db.base import Base
import app.models  # noqa: F401
from app.features.client_portal.router import (
    export_project_report_pdf,
    update_project_client_visibility,
)
from app.features.client_portal.schemas import ClientVisibilityUpdate
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.enums import (
    AuditAction,
    CommonStatus,
    DeliverableStatus,
    MilestoneStatus,
    PriorityLevel,
    ProjectStatus,
    TeamStatus,
    UserType,
)
from app.models.milestone import ProjectMilestone
from app.models.project import Project
from app.models.project_manager import ProjectManager
from app.models.team import Team, TeamMember
from app.models.user_account import UserAccount


def _extract_pdf_text_bytes(pdf_bytes: bytes) -> str:
    """Decode ASCII85 + FlateDecode streams in a ReportLab PDF to inspect rendered text."""
    chunks = [pdf_bytes.decode("latin-1", errors="ignore")]
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.DOTALL):
        raw_stream = match.group(1).strip()
        try:
            decoded_a85 = base64.a85decode(raw_stream, adobe=True)
            decompressed = zlib.decompress(decoded_a85)
            chunks.append(decompressed.decode("latin-1", errors="ignore"))
        except Exception:
            try:
                decompressed = zlib.decompress(raw_stream)
                chunks.append(decompressed.decode("latin-1", errors="ignore"))
            except Exception:
                pass
    return "\n".join(chunks)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def seed_s6(db_session):
    pm_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="pm@example.com",
        password_hash="fake",
        user_type=UserType.PM,
        is_active=True,
    )
    client_a_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="clienta@example.com",
        password_hash="fake",
        user_type=UserType.CLIENT,
        is_active=True,
    )
    client_b_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="clientb@example.com",
        password_hash="fake",
        user_type=UserType.CLIENT,
        is_active=True,
    )
    emp_acc = UserAccount(
        account_id=uuid.uuid4(),
        email="emp@example.com",
        password_hash="fake",
        user_type=UserType.EMPLOYEE,
        is_active=True,
    )
    db_session.add_all([pm_acc, client_a_acc, client_b_acc, emp_acc])
    db_session.flush()

    client_a = Client(
        account_id=client_a_acc.account_id,
        company_name="Alpha Corp",
        contact_person="Alice Client",
        email="clienta@example.com",
        status=CommonStatus.ACTIVE,
    )
    client_b = Client(
        account_id=client_b_acc.account_id,
        company_name="Beta Corp",
        contact_person="Bob Client",
        email="clientb@example.com",
        status=CommonStatus.ACTIVE,
    )
    pm_profile = ProjectManager(
        account_id=pm_acc.account_id,
        emp_code="PM-01",
        full_name="Priya PM",
        email="pm@example.com",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    dev_emp = Employee(
        account_id=emp_acc.account_id,
        emp_code="EMP-01",
        full_name="Alice SecretName",
        email="emp@example.com",
        designation="Backend Developer",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    qa_emp = Employee(
        emp_code="EMP-02",
        full_name="Bob SecretQA",
        email="qa@example.com",
        designation="QA Engineer",
        date_of_joining=date(2025, 1, 1),
        status=CommonStatus.ACTIVE,
    )
    db_session.add_all([client_a, client_b, pm_profile, dev_emp, qa_emp])
    db_session.flush()

    project = Project(
        client_id=client_a.client_id,
        pm_id=pm_profile.pm_id,
        project_code="PRJ-S6",
        name="Client Visibility Portal",
        start_date=date(2026, 11, 1),
        priority=PriorityLevel.HIGH,
        status=ProjectStatus.ACTIVE,
        is_team_visible_to_client=False,
    )
    db_session.add(project)
    db_session.flush()

    team = Team(
        project_id=project.project_id,
        lead_emp_id=dev_emp.emp_id,
        name="Portal Squad",
        status=TeamStatus.ACTIVE,
    )
    db_session.add(team)
    db_session.flush()

    db_session.add_all([
        TeamMember(team_id=team.team_id, emp_id=dev_emp.emp_id),
        TeamMember(team_id=team.team_id, emp_id=qa_emp.emp_id),
    ])

    ms1 = ProjectMilestone(
        project_id=project.project_id,
        title="Architecture Signoff",
        target_date=date(2026, 11, 10),
        status=MilestoneStatus.COMPLETED,
    )
    ms2 = ProjectMilestone(
        project_id=project.project_id,
        title="Beta Release",
        target_date=date(2026, 11, 25),
        status=MilestoneStatus.PENDING,
    )
    db_session.add_all([ms1, ms2])
    db_session.flush()

    deliv = Deliverable(
        project_id=project.project_id,
        milestone_id=ms1.id,
        submitted_by=dev_emp.emp_id,
        title="Architecture Blueprint PDF",
        file_url="/uploads/arch.pdf",
        version=1,
        status=DeliverableStatus.ACCEPTED,
    )
    db_session.add(deliv)
    db_session.commit()

    return {
        "pm_acc": pm_acc,
        "client_a_acc": client_a_acc,
        "client_b_acc": client_b_acc,
        "emp_acc": emp_acc,
        "project": project,
    }


def _fake_request():
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))


@pytest.mark.anyio
async def test_export_pdf_streams_valid_pdf_with_masked_names(db_session, seed_s6):
    project = seed_s6["project"]
    resp = export_project_report_pdf(
        id=project.project_id,
        db=db_session,
        current_user=seed_s6["client_a_acc"],
    )
    assert resp.media_type == "application/pdf"
    assert (
        resp.headers["Content-Disposition"]
        == f'attachment; filename="Project_Report_{project.project_id}.pdf"'
    )

    body = b"".join([chunk async for chunk in resp.body_iterator])
    assert body.startswith(b"%PDF-")

    rendered = _extract_pdf_text_bytes(body)
    assert "Client Visibility Portal" in rendered
    assert "50.0%" in rendered
    assert "Architecture Signoff" in rendered
    assert "Architecture Blueprint PDF" in rendered
    # Employee identities must be anonymized when is_team_visible_to_client == False
    assert "Alice SecretName" not in rendered
    assert "Bob SecretQA" not in rendered
    assert "Developer" in rendered
    assert "QA" in rendered


@pytest.mark.anyio
async def test_toggle_visibility_and_export_shows_names(db_session, seed_s6):
    project = seed_s6["project"]
    updated = update_project_client_visibility(
        id=project.project_id,
        payload=ClientVisibilityUpdate(is_team_visible_to_client=True),
        request=_fake_request(),
        db=db_session,
        current_user=seed_s6["pm_acc"],
    )
    assert updated.is_team_visible_to_client is True

    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_name == "PROJECT",
            AuditLog.entity_ref_id == str(project.project_id),
        )
        .first()
    )
    assert audit is not None
    assert audit.action == AuditAction.UPDATE

    resp = export_project_report_pdf(
        id=project.project_id,
        db=db_session,
        current_user=seed_s6["client_a_acc"],
    )
    body = b"".join([chunk async for chunk in resp.body_iterator])
    rendered = _extract_pdf_text_bytes(body)
    assert "Alice SecretName" in rendered
    assert "Bob SecretQA" in rendered


def test_toggle_visibility_forbidden_for_non_pm_admin(db_session, seed_s6):
    with pytest.raises(HTTPException) as exc_client:
        require_role(seed_s6["client_a_acc"], allowed=["PM", "ADMIN"], db=db_session)
    assert exc_client.value.status_code == 403

    with pytest.raises(HTTPException) as exc_emp:
        require_role(seed_s6["emp_acc"], allowed=["PM", "ADMIN"], db=db_session)
    assert exc_emp.value.status_code == 403


def test_export_pdf_client_isolation_returns_404(db_session, seed_s6):
    with pytest.raises(HTTPException) as exc:
        export_project_report_pdf(
            id=seed_s6["project"].project_id,
            db=db_session,
            current_user=seed_s6["client_b_acc"],
        )
    assert exc.value.status_code == 404
