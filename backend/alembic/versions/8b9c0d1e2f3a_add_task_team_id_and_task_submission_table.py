"""add task team_id and task_submission table

Revision ID: 8b9c0d1e2f3a
Revises: 4b29f01e7a32
Create Date: 2026-11-09 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8b9c0d1e2f3a"
down_revision: Union[str, Sequence[str], None] = "4b29f01e7a32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE task_status_enum ADD VALUE IF NOT EXISTS 'REJECTED'")
        op.execute("ALTER TYPE user_type_enum ADD VALUE IF NOT EXISTS 'TEAM_LEAD'")

    # 1. Add team_id to task table
    op.add_column("task", sa.Column("team_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_task_team_id", "task", "team", ["team_id"], ["team_id"], ondelete="SET NULL")
    op.create_index(op.f("ix_task_team_id"), "task", ["team_id"], unique=False)

    # 2. Create task_submission table
    op.create_table(
        "task_submission",
        sa.Column("submission_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("submitted_by", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("file_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["task.task_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submitted_by"], ["employee.emp_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("submission_id"),
    )
    op.create_index(op.f("ix_task_submission_task_id"), "task_submission", ["task_id"], unique=False)
    op.create_index(op.f("ix_task_submission_submitted_by"), "task_submission", ["submitted_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_task_submission_submitted_by"), table_name="task_submission")
    op.drop_index(op.f("ix_task_submission_task_id"), table_name="task_submission")
    op.drop_table("task_submission")
    op.drop_index(op.f("ix_task_team_id"), table_name="task")
    op.drop_constraint("fk_task_team_id", "task", type_="foreignkey")
    op.drop_column("task", "team_id")
