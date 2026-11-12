"""add team_id to task

Revision ID: 9c0d1e2f3a4b
Revises: 4b29f01e7a32
Create Date: 2026-11-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c0d1e2f3a4b'
down_revision: Union[str, Sequence[str], None] = '4b29f01e7a32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    task_columns = [col['name'] for col in inspector.get_columns('task')]

    if 'team_id' not in task_columns:
        op.add_column(
            'task',
            sa.Column('team_id', sa.Integer(), sa.ForeignKey('team.team_id', ondelete='SET NULL'), nullable=True)
        )
        op.create_index(op.f('ix_task_team_id'), 'task', ['team_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    task_columns = [col['name'] for col in inspector.get_columns('task')]

    if 'team_id' in task_columns:
        op.drop_index(op.f('ix_task_team_id'), table_name='task')
        op.drop_column('task', 'team_id')
