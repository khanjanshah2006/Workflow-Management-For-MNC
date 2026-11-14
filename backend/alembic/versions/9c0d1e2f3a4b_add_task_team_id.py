"""add task team_id

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-11-09 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c0d1e2f3a4b"
down_revision: Union[str, Sequence[str], None] = "8b9c0d1e2f3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE task_status_enum ADD VALUE IF NOT EXISTS 'REJECTED'")
        op.execute("ALTER TYPE user_type_enum ADD VALUE IF NOT EXISTS 'TEAM_LEAD'")

    # Add team_id to task table
    op.add_column("task", sa.Column("team_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_task_team_id", "task", "team", ["team_id"], ["team_id"], ondelete="SET NULL")
    op.create_index(op.f("ix_task_team_id"), "task", ["team_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_task_team_id"), table_name="task")
    op.drop_constraint("fk_task_team_id", "task", type_="foreignkey")
    op.drop_column("task", "team_id")

