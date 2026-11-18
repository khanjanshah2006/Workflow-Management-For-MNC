"""Re-assert TEAM_LEAD, IT_SUPPORT and SYSTEM_ADMIN in user_type_enum.

Some databases (including the shared Supabase DB) were stamped past the
revisions that add these values without actually having them, so creating
Team Lead / IT Support / System Admin users failed. ADD VALUE IF NOT EXISTS
makes this a no-op wherever the values already exist.

Revision ID: d5a9b2c3f4e6
Revises: c4f8a1d2e9b3
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d5a9b2c3f4e6"
down_revision: Union[str, Sequence[str], None] = "c4f8a1d2e9b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_context().dialect.name == "postgresql":
        for role in ("TEAM_LEAD", "IT_SUPPORT", "SYSTEM_ADMIN"):
            op.execute(f"ALTER TYPE user_type_enum ADD VALUE IF NOT EXISTS '{role}'")


def downgrade() -> None:
    # Postgres cannot drop enum values, and earlier revisions own them anyway.
    pass
