"""create project_milestone table and migrate existing milestone references

Revision ID: 5c83b12a9e40
Revises: 4b29f01e7a32
Create Date: 2026-11-03 00:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


# revision identifiers, used by Alembic.
revision: str = '5c83b12a9e40'
down_revision: Union[str, None] = '4b29f01e7a32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_foreign_key_name(inspector: reflection.Inspector, table_name: str, referred_table: str) -> Union[str, None]:
    """Find constraint name of a foreign key pointing to referred_table."""
    fks = inspector.get_foreign_keys(table_name)
    for fk in fks:
        if fk.get('referred_table') == referred_table:
            return fk.get('name')
    return None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Ensure project_milestone_status_enum exists in PostgreSQL
    if dialect == "postgresql":
        op.execute(
            "DO $$ BEGIN "
            "CREATE TYPE project_milestone_status_enum AS ENUM ('pending', 'completed'); "
            "EXCEPTION WHEN duplicate_object THEN null; "
            "END $$;"
        )
        # create_existing=False / create_type=False so SQLAlchemy does NOT try CREATE TYPE again
        status_type = sa.Enum('pending', 'completed', name='project_milestone_status_enum', create_type=False)
    else:
        status_type = sa.Enum('pending', 'completed', name='project_milestone_status_enum')

    # 2. Create project_milestone table if it does not exist
    if 'project_milestone' not in existing_tables:
        op.create_table(
            'project_milestone',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('project_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('target_date', sa.Date(), nullable=False),
            sa.Column('status', status_type, nullable=False, server_default='pending'),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['project.project_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_project_milestone_project_id'), 'project_milestone', ['project_id'], unique=False)
        op.create_index(op.f('ix_project_milestone_target_date'), 'project_milestone', ['target_date'], unique=False)

    # 3. If historical 'milestone' table exists, migrate data and update foreign keys
    if 'milestone' in existing_tables:
        # Migrate existing rows safely
        if dialect == "postgresql":
            op.execute("""
                INSERT INTO project_milestone (id, project_id, title, description, target_date, status, created_at, is_deleted)
                SELECT 
                    milestone_id,
                    project_id,
                    title,
                    description,
                    due_date,
                    CASE 
                        WHEN lower(status::text) = 'completed' THEN 'completed'::project_milestone_status_enum 
                        ELSE 'pending'::project_milestone_status_enum 
                    END,
                    CURRENT_TIMESTAMP,
                    false
                FROM milestone
                ON CONFLICT (id) DO NOTHING;
            """)
            op.execute("SELECT setval(pg_get_serial_sequence('project_milestone', 'id'), coalesce(max(id), 1)) FROM project_milestone;")
        else:
            op.execute("""
                INSERT OR IGNORE INTO project_milestone (id, project_id, title, description, target_date, status, created_at, is_deleted)
                SELECT milestone_id, project_id, title, description, due_date, 'pending', CURRENT_TIMESTAMP, 0 FROM milestone;
            """)

        # Drop old FK from task pointing to milestone, and create new FK to project_milestone
        if 'task' in existing_tables:
            task_fk_name = _get_foreign_key_name(inspector, 'task', 'milestone') or 'task_milestone_id_fkey'
            try:
                op.drop_constraint(task_fk_name, 'task', type_='foreignkey')
            except Exception:
                pass
            op.create_foreign_key(
                'fk_task_milestone_id_project_milestone',
                'task',
                'project_milestone',
                ['milestone_id'],
                ['id'],
                ondelete='SET NULL',
            )

        # Drop old FK from deliverable pointing to milestone, and create new FK to project_milestone
        if 'deliverable' in existing_tables:
            deliv_fk_name = _get_foreign_key_name(inspector, 'deliverable', 'milestone') or 'deliverable_milestone_id_fkey'
            try:
                op.drop_constraint(deliv_fk_name, 'deliverable', type_='foreignkey')
            except Exception:
                pass
            op.create_foreign_key(
                'fk_deliverable_milestone_id_project_milestone',
                'deliverable',
                'project_milestone',
                ['milestone_id'],
                ['id'],
                ondelete='SET NULL',
            )

        # Drop old milestone table (use IF EXISTS to handle varying index names across environments)
        op.execute("DROP INDEX IF EXISTS ix_milestone_project_id")
        op.execute("DROP INDEX IF EXISTS idx_milestone_project")
        op.drop_table('milestone')


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Recreate historical 'milestone' table
    if 'milestone' not in existing_tables:
        if dialect == "postgresql":
            status_enum = sa.Enum('PENDING', 'COMPLETED', 'MISSED', name='milestone_status_enum')
        else:
            status_enum = sa.Enum('PENDING', 'COMPLETED', 'MISSED', name='milestone_status_enum')

        op.create_table(
            'milestone',
            sa.Column('milestone_id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('project_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('due_date', sa.Date(), nullable=False),
            sa.Column('status', status_enum, nullable=False, server_default='PENDING'),
            sa.ForeignKeyConstraint(['project_id'], ['project.project_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('milestone_id'),
        )
        op.create_index(op.f('ix_milestone_project_id'), 'milestone', ['project_id'], unique=False)

        # Copy data back from project_milestone if present
        if 'project_milestone' in existing_tables:
            if dialect == "postgresql":
                op.execute("""
                    INSERT INTO milestone (milestone_id, project_id, title, description, due_date, status)
                    SELECT id, project_id, substr(title, 1, 200), description, target_date, 'PENDING'::milestone_status_enum
                    FROM project_milestone;
                """)
            else:
                op.execute("""
                    INSERT INTO milestone (milestone_id, project_id, title, description, due_date, status)
                    SELECT id, project_id, substr(title, 1, 200), description, target_date, 'PENDING'
                    FROM project_milestone;
                """)

    # 2. Revert task & deliverable FKs back to milestone
    if 'task' in existing_tables:
        try:
            op.drop_constraint('fk_task_milestone_id_project_milestone', 'task', type_='foreignkey')
        except Exception:
            pass
        op.create_foreign_key(
            'task_milestone_id_fkey',
            'task',
            'milestone',
            ['milestone_id'],
            ['milestone_id'],
            ondelete='SET NULL',
        )

    if 'deliverable' in existing_tables:
        try:
            op.drop_constraint('fk_deliverable_milestone_id_project_milestone', 'deliverable', type_='foreignkey')
        except Exception:
            pass
        op.create_foreign_key(
            'deliverable_milestone_id_fkey',
            'deliverable',
            'milestone',
            ['milestone_id'],
            ['milestone_id'],
            ondelete='SET NULL',
        )

    # 3. Drop project_milestone table
    if 'project_milestone' in existing_tables:
        op.drop_index(op.f('ix_project_milestone_target_date'), table_name='project_milestone')
        op.drop_index(op.f('ix_project_milestone_project_id'), table_name='project_milestone')
        op.drop_table('project_milestone')

    if dialect == "postgresql":
        op.execute("DROP TYPE IF EXISTS project_milestone_status_enum")
