import re
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.employee import Employee
from app.models.enums import UserType
from app.models.team import Team
from app.models.user_account import UserAccount


APP_DIR = Path(__file__).resolve().parents[1] / "app"
INVALID_ROLE = re.compile(r"\b(HR_MANAGER|PROJECT_MANAGER)\b")


# ==============================================================================
# Shared fixtures: one in-memory SQLite DB for the module, wired into app.main
# ==============================================================================

@pytest.fixture(scope="module")
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield factory
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    engine.dispose()


@pytest.fixture(scope="module")
def client(session_factory):
    return TestClient(app)


@pytest.fixture
def db(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


# ==============================================================================
# Seed helpers (unique emails/codes so tests can share the module DB)
# ==============================================================================

def make_account(db, user_type: UserType) -> UserAccount:
    account = UserAccount(
        account_id=uuid4(),
        email=f"{user_type.value.lower()}-{uuid4().hex[:8]}@example.com",
        password_hash="hash",
        user_type=user_type,
        is_active=True,
    )
    db.add(account)
    db.commit()
    return account


def make_employee(db, account: UserAccount | None = None) -> Employee:
    code = uuid4().hex[:8]
    employee = Employee(
        account_id=account.account_id if account else None,
        emp_code=f"EMP-{code}",
        full_name=f"Employee {code}",
        email=account.email if account else f"emp-{code}@example.com",
        designation="Engineer",
        date_of_joining=date(2024, 1, 1),
    )
    db.add(employee)
    db.commit()
    return employee


def make_team(db, lead: Employee | None = None) -> Team:
    team = Team(name=f"Team {uuid4().hex[:8]}", lead_emp_id=lead.emp_id if lead else None)
    db.add(team)
    db.commit()
    return team


def auth_headers(account: UserAccount) -> dict[str, str]:
    token = create_access_token(data={
        "sub": str(account.account_id),
        "email": account.email,
        "user_type": account.user_type.value,
    })
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Tests
# ==============================================================================

def test_no_invalid_role_literals():
    hits = []
    for path in sorted(APP_DIR.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if INVALID_ROLE.search(line):
                hits.append(f"{path.relative_to(APP_DIR.parent)}:{lineno}: {line.strip()}")
    assert not hits, "Invalid role literals found:\n" + "\n".join(hits)


def test_team_lead_user_type_can_view_own_team_roster(client, db):
    lead = make_account(db, UserType.TEAM_LEAD)
    team_a = make_team(db, lead=make_employee(db, lead))
    team_b = make_team(db, lead=make_employee(db))
    orphan_lead = make_account(db, UserType.TEAM_LEAD)

    res = client.get(f"/api/v1/teams/{team_a.team_id}/members", headers=auth_headers(lead))
    assert res.status_code == 200

    res = client.get(f"/api/v1/teams/{team_b.team_id}/members", headers=auth_headers(lead))
    assert res.status_code == 403

    res = client.get(f"/api/v1/teams/{team_a.team_id}/members", headers=auth_headers(orphan_lead))
    assert res.status_code == 403
