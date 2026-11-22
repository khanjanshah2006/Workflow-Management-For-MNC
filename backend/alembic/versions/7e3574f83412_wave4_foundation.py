"""Wave 4 foundation: team departments, login lockout, stored files, skill change requests.

All Wave 4 schema changes live in this single revision (W4-BE-0).
Every step checks what already exists first, so the upgrade is safe to re-run
against databases that were partly patched by hand.

Revision ID: 7e3574f83412
Revises: d5a9b2c3f4e6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "7e3574f83412"
down_revision: Union[str, Sequence[str], None] = "d5a9b2c3f4e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENUMS = {
    "skill_change_action_enum": ("ADD", "UPDATE", "REMOVE"),
    "skill_change_status_enum": ("PENDING", "APPROVED", "REJECTED"),
}

# (table, column, foreign key name, index name or None); all reference stored_file.file_id
_FILE_LINKS = (
    ("task_submission", "file_id", "fk_task_submission_file_id", None),
    ("executive_report", "file_id", "fk_executive_report_file_id", None),
)


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table: str) -> bool:
    return _inspector().has_table(table)


def _has_column(table: str, column: str) -> bool:
    return any(c["name"] == column for c in _inspector().get_columns(table))


def _has_index(table: str, index: str) -> bool:
    return any(i["name"] == index for i in _inspector().get_indexes(table))


def _has_fk(table: str, fk: str) -> bool:
    return any(f["name"] == fk for f in _inspector().get_foreign_keys(table))


def _enum(name: str, *values: str):
    if _is_postgres():
        return postgresql.ENUM(*values, name=name, create_type=False)
    return sa.Enum(*values, name=name)


def _add_fk_column(table, column, column_type, fk_name, ref_table, ref_column, index_name=None):
    if not _has_column(table, column):
        op.add_column(table, sa.Column(column, column_type, nullable=True))
    if not _has_fk(table, fk_name):
        op.create_foreign_key(fk_name, table, ref_table, [column], [ref_column], ondelete="SET NULL")
    if index_name and not _has_index(table, index_name):
        op.create_index(index_name, table, [column])


def _drop_fk_column(table, column, fk_name, index_name=None):
    if not _has_table(table) or not _has_column(table, column):
        return
    if index_name and _has_index(table, index_name):
        op.drop_index(index_name, table_name=table)
    if _has_fk(table, fk_name):
        op.drop_constraint(fk_name, table, type_="foreignkey")
    op.drop_column(table, column)


def upgrade() -> None:
    # 1. Enum types (Postgres only; SQLite stores enums as plain strings).
    if _is_postgres():
        for name, values in _ENUMS.items():
            labels = ", ".join(f"'{v}'" for v in values)
            op.execute(
                f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({labels}); "
                f"EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
            )

    # 2. team.dept_id (S1-BE-2)
    _add_fk_column(
        "team", "dept_id", sa.Integer(), "fk_team_dept_id",
        "department", "dept_id", index_name="ix_team_dept_id",
    )

    # 3. Login lockout (S9-BE-4)
    if not _has_column("user_account", "failed_login_count"):
        op.add_column(
            "user_account",
            sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False),
        )
    if not _has_column("user_account", "locked_until"):
        op.add_column(
            "user_account",
            sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        )

    # 4. stored_file (S9-BE-5)
    if not _has_table("stored_file"):
        op.create_table(
            "stored_file",
            sa.Column("file_id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("purpose", sa.String(length=40), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("content_type", sa.String(length=100), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("sha256", sa.String(length=64), nullable=False),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["uploaded_by"], ["user_account.account_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("file_id"),
        )

    # 5. File links from submissions and executive reports
    for table, column, fk_name, index_name in _FILE_LINKS:
        _add_fk_column(table, column, sa.Integer(), fk_name, "stored_file", "file_id", index_name)

    # 6. skill_change_request (S1-BE-4)
    if not _has_table("skill_change_request"):
        op.create_table(
            "skill_change_request",
            sa.Column("request_id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("emp_id", sa.Integer(), nullable=False),
            sa.Column("skill_id", sa.Integer(), nullable=True),
            sa.Column("proposed_skill_name", sa.String(length=100), nullable=True),
            sa.Column("action", _enum("skill_change_action_enum", *_ENUMS["skill_change_action_enum"]), nullable=False),
            sa.Column(
                "proficiency",
                _enum("skill_proficiency_enum", "BEGINNER", "INTERMEDIATE", "EXPERT"),
                nullable=True,
            ),
            sa.Column("years_of_experience", sa.Integer(), nullable=True),
            sa.Column("justification", sa.Text(), nullable=False),
            sa.Column(
                "status",
                _enum("skill_change_status_enum", *_ENUMS["skill_change_status_enum"]),
                server_default="PENDING",
                nullable=False,
            ),
            sa.Column("reviewer_account_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("review_remarks", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "years_of_experience IS NULL OR years_of_experience >= 0",
                name="chk_skill_change_years_experience",
            ),
            sa.ForeignKeyConstraint(["emp_id"], ["employee.emp_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["skill_id"], ["skill.skill_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["reviewer_account_id"], ["user_account.account_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("request_id"),
        )
    if not _has_index("skill_change_request", "ix_skill_change_request_emp_id"):
        op.create_index("ix_skill_change_request_emp_id", "skill_change_request", ["emp_id"])


def downgrade() -> None:
    if _has_table("skill_change_request"):
        op.drop_table("skill_change_request")

    for table, column, fk_name, index_name in reversed(_FILE_LINKS):
        _drop_fk_column(table, column, fk_name, index_name)

    if _has_table("stored_file"):
        op.drop_table("stored_file")

    for column in ("locked_until", "failed_login_count"):
        if _has_column("user_account", column):
            op.drop_column("user_account", column)

    _drop_fk_column("team", "dept_id", "fk_team_dept_id", "ix_team_dept_id")

    if _is_postgres():
        for name in _ENUMS:
            op.execute(f"DROP TYPE IF EXISTS {name}")
