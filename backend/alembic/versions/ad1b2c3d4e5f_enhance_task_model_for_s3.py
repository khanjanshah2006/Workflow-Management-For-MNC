"""enhance task model for S3 — add team_id, progress_pct, rejection fields, updated_at

Revision ID: ad1b2c3d4e5f
Revises: 5c38d12e9f01
Create Date: 2026-11-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "ad1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = ("5c38d12e9f01", "9b8c7d6e5f4a")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add REJECTED to task_status_enum (PostgreSQL only — irreversible but safe)
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE task_status_enum ADD VALUE IF NOT EXISTS 'REJECTED'")

    inspector = sa.inspect(bind)
    task_columns = [col["name"] for col in inspector.get_columns("task")]
    task_indexes = [idx["name"] for idx in inspector.get_indexes("task")]

    # 2. Add team_id
    if "team_id" not in task_columns:
        op.add_column("task", sa.Column("team_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_task_team_id",
            "task",
            "team",
            ["team_id"],
            ["team_id"],
            ondelete="CASCADE",
        )
        op.create_index("ix_task_team_id", "task", ["team_id"])
    elif "ix_task_team_id" not in task_indexes:
        op.create_index("ix_task_team_id", "task", ["team_id"])

    # 3. Add progress_pct
    if "progress_pct" not in task_columns:
        op.add_column(
            "task",
            sa.Column("progress_pct", sa.Integer(), server_default="0", nullable=False),
        )

    # 4. Add rejection_count
    if "rejection_count" not in task_columns:
        op.add_column(
            "task",
            sa.Column("rejection_count", sa.Integer(), server_default="0", nullable=False),
        )

    # 5. Add rejection_feedback
    if "rejection_feedback" not in task_columns:
        op.add_column("task", sa.Column("rejection_feedback", sa.Text(), nullable=True))

    # 6. Add blocker_reason
    if "blocker_reason" not in task_columns:
        op.add_column("task", sa.Column("blocker_reason", sa.Text(), nullable=True))

    # 7. Add updated_at
    if "updated_at" not in task_columns:
        op.add_column(
            "task",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
        )

    # 8. Add check constraint for progress_pct
    if bind.dialect.name == "postgresql":
        try:
            op.create_check_constraint(
                "chk_task_progress_pct",
                "task",
                "progress_pct >= 0 AND progress_pct <= 100",
            )
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        try:
            op.drop_constraint("chk_task_progress_pct", "task", type_="check")
        except Exception:
            pass

    op.drop_index("ix_task_team_id", table_name="task")
    try:
        op.drop_constraint("fk_task_team_id", "task", type_="foreignkey")
    except Exception:
        pass

    op.drop_column("task", "updated_at")
    op.drop_column("task", "blocker_reason")
    op.drop_column("task", "rejection_feedback")
    op.drop_column("task", "rejection_count")
    op.drop_column("task", "progress_pct")
    op.drop_column("task", "team_id")
