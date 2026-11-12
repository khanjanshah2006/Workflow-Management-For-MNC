"""enhance task model for S3 — add team_id, progress_pct, rejection fields, updated_at

Revision ID: ad1b2c3d4e5f
Revises: 9c0d1e2f3a4b
Create Date: 2026-11-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "ad1b2c3d4e5f"
down_revision: Union[str, None] = "9c0d1e2f3a4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add REJECTED to task_status_enum (PostgreSQL only — irreversible but safe)
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE task_status_enum ADD VALUE IF NOT EXISTS 'REJECTED'")

    # 2. Add team_id (nullable first so existing rows don't violate NOT NULL)
    op.add_column("task", sa.Column("team_id", sa.Integer(), nullable=True))

    # 3. Add progress_pct
    op.add_column(
        "task",
        sa.Column("progress_pct", sa.Integer(), server_default="0", nullable=False),
    )

    # 4. Add rejection_count
    op.add_column(
        "task",
        sa.Column("rejection_count", sa.Integer(), server_default="0", nullable=False),
    )

    # 5. Add rejection_feedback
    op.add_column("task", sa.Column("rejection_feedback", sa.Text(), nullable=True))

    # 6. Add blocker_reason
    op.add_column("task", sa.Column("blocker_reason", sa.Text(), nullable=True))

    # 7. Add updated_at
    op.add_column(
        "task",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )

    # 8. Create FK from task.team_id -> team.team_id
    op.create_foreign_key(
        "fk_task_team_id",
        "task",
        "team",
        ["team_id"],
        ["team_id"],
        ondelete="CASCADE",
    )

    # 9. Create index on team_id
    op.create_index("ix_task_team_id", "task", ["team_id"])

    # 10. Add check constraint for progress_pct
    if bind.dialect.name == "postgresql":
        op.create_check_constraint(
            "chk_task_progress_pct",
            "task",
            "progress_pct >= 0 AND progress_pct <= 100",
        )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.drop_constraint("chk_task_progress_pct", "task", type_="check")

    op.drop_index("ix_task_team_id", table_name="task")
    op.drop_constraint("fk_task_team_id", "task", type_="foreignkey")

    op.drop_column("task", "updated_at")
    op.drop_column("task", "blocker_reason")
    op.drop_column("task", "rejection_feedback")
    op.drop_column("task", "rejection_count")
    op.drop_column("task", "progress_pct")
    op.drop_column("task", "team_id")

    # Note: PostgreSQL does NOT support removing enum values.
    # The REJECTED value remains in task_status_enum after downgrade.

