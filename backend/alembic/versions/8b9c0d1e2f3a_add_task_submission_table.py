"""tasks: add task_submission table

Revision ID: 8b9c0d1e2f3a
Revises: 4b29f01e7a32
Create Date: 2026-11-09 13:40:00.000000

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
    op.create_table(
        "task_submission",
        sa.Column("submission_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("submitted_by", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["task.task_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"],
            ["employee.emp_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("submission_id"),
    )
    op.create_index(
        op.f("ix_task_submission_task_id"),
        "task_submission",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_submission_submitted_by"),
        "task_submission",
        ["submitted_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_task_submission_submitted_by"), table_name="task_submission")
    op.drop_index(op.f("ix_task_submission_task_id"), table_name="task_submission")
    op.drop_table("task_submission")
