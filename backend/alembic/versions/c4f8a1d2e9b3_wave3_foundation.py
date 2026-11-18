"""Wave 3 foundation: roles, leave review fields, overdue flag, executive reports.

All Wave 3 schema changes live in this single revision (W3-BE-0).

Revision ID: c4f8a1d2e9b3
Revises: 7e2a91c4b6d8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c4f8a1d2e9b3"
down_revision: Union[str, Sequence[str], None] = "7e2a91c4b6d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PARAMS = (
    (
        "REPEATED_REJECTION_THRESHOLD",
        "2",
        "Rejection count at which a task is flagged as repeatedly rejected (US-38).",
    ),
    (
        "LEAVE_REASSIGN_MAX_ACTIVE_TASKS",
        "5",
        "Teammates with fewer active tasks than this are available for leave reassignment.",
    ),
)


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def upgrade() -> None:
    # 1. Enum values (Postgres only; SQLite stores enums as plain strings).
    if _is_postgres():
        op.execute("ALTER TYPE user_type_enum ADD VALUE IF NOT EXISTS 'MNC_EXECUTIVE'")
        op.execute("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'EXPORT'")

    # 2. leave_type
    op.add_column(
        "leave_type",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_check_constraint("chk_leave_type_quota", "leave_type", "yearly_quota >= 0")

    # 3. leave_request
    op.drop_column("leave_request", "reviewed_by_hr_id")
    op.add_column(
        "leave_request",
        sa.Column("reviewed_by_account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_leave_request_reviewed_by_account_id",
        "leave_request",
        "user_account",
        ["reviewed_by_account_id"],
        ["account_id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_leave_request_leave_type_id", "leave_request", ["leave_type_id"])
    op.create_index(
        "ix_leave_request_emp_dates", "leave_request", ["emp_id", "start_date", "end_date"]
    )
    op.create_check_constraint("chk_leave_total_days", "leave_request", "total_days > 0")

    # 4. task
    op.add_column(
        "task",
        sa.Column("overdue_notified_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 5. executive_report
    op.create_table(
        "executive_report",
        sa.Column("report_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("generated_by_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("report_title", sa.String(length=255), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("report_format", sa.Enum("PDF", "CSV", name="report_format_enum"), nullable=False),
        sa.Column("include_department_breakdown", sa.Boolean(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["generated_by_account_id"], ["user_account.account_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("report_id"),
    )

    # 6. Default system parameters (skip keys an admin already created).
    for key, value, description in _PARAMS:
        op.execute(
            sa.text(
                "INSERT INTO system_parameter (key, value, value_type, description, updated_at) "
                "SELECT :key, :value, 'integer', :description, CURRENT_TIMESTAMP "
                "WHERE NOT EXISTS (SELECT 1 FROM system_parameter WHERE key = :key)"
            ).bindparams(key=key, value=value, description=description)
        )


def downgrade() -> None:
    # Enum values MNC_EXECUTIVE and EXPORT stay: Postgres cannot drop enum values.
    op.execute(
        sa.text("DELETE FROM system_parameter WHERE key IN (:k1, :k2)").bindparams(
            k1=_PARAMS[0][0], k2=_PARAMS[1][0]
        )
    )

    op.drop_table("executive_report")
    if _is_postgres():
        op.execute("DROP TYPE IF EXISTS report_format_enum")

    op.drop_column("task", "overdue_notified_at")

    op.drop_constraint("chk_leave_total_days", "leave_request", type_="check")
    op.drop_index("ix_leave_request_emp_dates", table_name="leave_request")
    op.drop_index("ix_leave_request_leave_type_id", table_name="leave_request")
    op.drop_constraint(
        "fk_leave_request_reviewed_by_account_id", "leave_request", type_="foreignkey"
    )
    op.drop_column("leave_request", "reviewed_by_account_id")
    op.add_column(
        "leave_request",
        sa.Column("reviewed_by_hr_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "leave_request_reviewed_by_hr_id_fkey",
        "leave_request",
        "hr_manager",
        ["reviewed_by_hr_id"],
        ["hr_id"],
        ondelete="SET NULL",
    )

    op.drop_constraint("chk_leave_type_quota", "leave_type", type_="check")
    op.drop_column("leave_type", "is_active")
