"""tasks: add progress_pct, blocker_reason, and team_id to task

Revision ID: a1b2c3d4e5f6
Revises: 8b9c0d1e2f3a
Create Date: 2026-11-12 15:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "8b9c0d1e2f3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    task_columns = [col["name"] for col in inspector.get_columns("task")]

    if "team_id" not in task_columns:
        op.add_column("task", sa.Column("team_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_task_team_id_team",
            "task",
            "team",
            ["team_id"],
            ["team_id"],
            ondelete="SET NULL",
        )
        op.create_index(op.f("ix_task_team_id"), "task", ["team_id"], unique=False)

    if "progress_pct" not in task_columns:
        op.add_column(
            "task",
            sa.Column("progress_pct", sa.Integer(), server_default="0", nullable=False),
        )

    if "blocker_reason" not in task_columns:
        op.add_column(
            "task",
            sa.Column("blocker_reason", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    task_columns = [col["name"] for col in inspector.get_columns("task")]

    if "blocker_reason" in task_columns:
        op.drop_column("task", "blocker_reason")

    if "progress_pct" in task_columns:
        op.drop_column("task", "progress_pct")

    if "team_id" in task_columns:
        op.drop_index(op.f("ix_task_team_id"), table_name="task")
        op.drop_column("task", "team_id")
