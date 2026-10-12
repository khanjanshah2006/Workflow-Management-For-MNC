"""add password_hash to user_account

Revision ID: 3a105c8d9e21
Revises: 2e204e5a4c37
Create Date: 2026-10-12 13:24:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a105c8d9e21'
down_revision: Union[str, None] = '2e204e5a4c37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_account',
        sa.Column('password_hash', sa.String(length=255), nullable=False, server_default='')
    )
    # Remove the server_default after adding column
    op.alter_column('user_account', 'password_hash', server_default=None)


def downgrade() -> None:
    op.drop_column('user_account', 'password_hash')
