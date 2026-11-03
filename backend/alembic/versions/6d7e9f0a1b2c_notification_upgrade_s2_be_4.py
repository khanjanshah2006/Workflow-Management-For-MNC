"""notification: upgrade table for S2-BE-4 (UUID PK, link column, server_default is_read, compound index)

Revision ID: 6d7e9f0a1b2c
Revises: 4b29f01e7a32
Create Date: 2026-11-04 00:00:00.000000

What this migration does (notification table only — no other tables touched):
  1. Drops the old single-column index ix_notification_account_id.
  2. Drops the Integer PK (notification_id) and replaces it with a UUID column (id)
     using gen_random_uuid() as a server-side default so existing rows get a value.
  3. Widens title from VARCHAR(200) → VARCHAR(255).
  4. Adds the nullable link VARCHAR(255) column.
  5. Sets server_default='false' on is_read (Python default already existed; this
     makes it explicit at the DB level so raw SQL inserts are also safe).
  6. Creates the compound index ix_notification_account_id_is_read covering the
     primary query shape: WHERE account_id = ? AND is_read = false.

Downgrade reverses every step cleanly.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
# revision identifiers
# ---------------------------------------------------------------------------
revision: str = "6d7e9f0a1b2c"
down_revision: Union[str, Sequence[str], None] = "4b29f01e7a32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Drop old single-column index if it exists ───────────────────────
    op.execute("DROP INDEX IF EXISTS ix_notification_account_id")

    # ── 2. Replace Integer PK with UUID PK ─────────────────────────────────
    # 2a. Drop the existing primary-key constraint on notification_id.
    op.drop_constraint("notification_pkey", "notification", type_="primary")

    # 2b. Remove the old integer surrogate key column entirely.
    op.drop_column("notification", "notification_id")

    # 2c. Add 'id' UUID column.  server_default uses PostgreSQL's built-in
    #     gen_random_uuid() (available since PG 13, enabled on Supabase by
    #     default) so any existing rows receive a unique UUID automatically.
    op.add_column(
        "notification",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
    )

    # 2d. Promote the new column to primary key.
    op.create_primary_key("notification_pkey", "notification", ["id"])

    # 2e. Remove the temporary server_default now that all rows have a value.
    #     The Python model supplies uuid.uuid4 at insert time; no DB default
    #     is needed during normal operation.
    op.alter_column(
        "notification",
        "id",
        server_default=None,
        existing_type=postgresql.UUID(as_uuid=True),
        existing_nullable=False,
    )

    # ── 3. Widen title VARCHAR(200) → VARCHAR(255) ──────────────────────────
    op.alter_column(
        "notification",
        "title",
        type_=sa.String(255),
        existing_type=sa.String(200),
        existing_nullable=False,
    )

    # ── 4. Add nullable link column ─────────────────────────────────────────
    op.add_column(
        "notification",
        sa.Column("link", sa.String(255), nullable=True),
    )

    # ── 5. Add server_default='false' to is_read ────────────────────────────
    op.alter_column(
        "notification",
        "is_read",
        server_default=sa.text("false"),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )

    # ── 6. Create compound index ─────────────────────────────────────────────
    op.create_index(
        "ix_notification_account_id_is_read",
        "notification",
        ["account_id", "is_read"],
        unique=False,
    )


def downgrade() -> None:
    # Reverse every step in the opposite order.

    # 6. Drop compound index
    op.drop_index("ix_notification_account_id_is_read", table_name="notification")

    # 5. Remove server_default from is_read
    op.alter_column(
        "notification",
        "is_read",
        server_default=None,
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )

    # 4. Drop link column
    op.drop_column("notification", "link")

    # 3. Narrow title back to VARCHAR(200)
    op.alter_column(
        "notification",
        "title",
        type_=sa.String(200),
        existing_type=sa.String(255),
        existing_nullable=False,
    )

    # 2. Restore Integer PK (notification_id)
    # 2a. Drop UUID PK constraint and column
    op.drop_constraint("notification_pkey", "notification", type_="primary")
    op.drop_column("notification", "id")

    # 2b. Re-add notification_id as a regular integer column first,
    #     then make it a serial PK via the SEQUENCE approach that Alembic uses.
    op.add_column(
        "notification",
        sa.Column(
            "notification_id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
            # Assign temporary sequential values to satisfy NOT NULL on existing rows.
            server_default=sa.text(
                "nextval(pg_catalog.pg_get_serial_sequence('notification','notification_id'))"
            ),
        ),
    )
    op.create_primary_key("notification_pkey", "notification", ["notification_id"])
    # Remove the temporary server_default — autoincrement handles future inserts.
    op.alter_column(
        "notification",
        "notification_id",
        server_default=None,
        existing_type=sa.Integer(),
        existing_nullable=False,
    )

    # 1. Restore the original single-column index
    op.create_index(
        "ix_notification_account_id", "notification", ["account_id"], unique=False
    )

