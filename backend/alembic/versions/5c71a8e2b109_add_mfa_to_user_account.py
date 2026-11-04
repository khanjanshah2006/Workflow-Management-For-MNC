"""add mfa to user_account

Revision ID: 5c71a8e2b109
Revises: 4b29f01e7a32
Create Date: 2026-11-03 00:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c71a8e2b109'
down_revision: Union[str, Sequence[str], None] = '4b29f01e7a32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_account',
        sa.Column('mfa_secret', sa.String(length=64), nullable=True)
    )
    op.add_column(
        'user_account',
        sa.Column('is_mfa_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )
    op.alter_column('user_account', 'is_mfa_enabled', server_default=None)


def downgrade() -> None:
    op.drop_column('user_account', 'is_mfa_enabled')
    op.drop_column('user_account', 'mfa_secret')

