"""add admin to user_type_enum

Revision ID: 4b29f01e7a32
Revises: 3a105c8d9e21
Create Date: 2026-10-13 01:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b29f01e7a32'
down_revision: Union[str, Sequence[str], None] = '3a105c8d9e21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE user_type_enum ADD VALUE IF NOT EXISTS 'ADMIN'")


def downgrade() -> None:
    pass
