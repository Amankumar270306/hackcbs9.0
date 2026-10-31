"""report_generator_milestone8

Revision ID: 7a9b1c2d3e4f
Revises: d92e105ce20a
Create Date: 2026-10-31 23:15:00.000000

"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7a9b1c2d3e4f'
down_revision: Union[str, Sequence[str], None] = 'd92e105ce20a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema for Report Generator: Multi-Agent Audit Reports (Milestone 8)."""
    # 1. Make audit_run_id nullable on reports
    op.alter_column(
        'reports',
        'audit_run_id',
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    # 2. Add Milestone 8 columns to reports table
    op.add_column('reports', sa.Column('adjudication_run_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('reports', sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('reports', sa.Column('file_checksum', sa.String(length=64), nullable=True))
    op.add_column('reports', sa.Column('file_size', sa.Integer(), nullable=True))
    op.add_column('reports', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('reports', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('reports', sa.Column('is_stale', sa.Boolean(), server_default='false', nullable=False))

    # 3. Add foreign key constraints
    op.create_foreign_key(
        'fk_reports_adjudication_run',
        'reports',
        'adjudication_runs',
        ['adjudication_run_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_reports_created_by',
        'reports',
        'users',
        ['created_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_reports_org_audit',
        'reports',
        'audits',
        ['organization_id', 'audit_id'],
        ['organization_id', 'id'],
        ondelete='CASCADE',
    )

    # 4. Add indexes
    op.create_index('ix_reports_adj_run', 'reports', ['adjudication_run_id'])
    op.create_index('ix_reports_audit_version', 'reports', ['audit_id', 'version'])
    op.create_index('ix_reports_created_by', 'reports', ['created_by_id'])


def downgrade() -> None:
    """Downgrade schema for Report Generator."""
    op.drop_index('ix_reports_created_by', table_name='reports')
    op.drop_index('ix_reports_audit_version', table_name='reports')
    op.drop_index('ix_reports_adj_run', table_name='reports')

    op.drop_constraint('fk_reports_org_audit', 'reports', type_='foreignkey')
    op.drop_constraint('fk_reports_created_by', 'reports', type_='foreignkey')
    op.drop_constraint('fk_reports_adjudication_run', 'reports', type_='foreignkey')

    op.drop_column('reports', 'is_stale')
    op.drop_column('reports', 'summary')
    op.drop_column('reports', 'error_message')
    op.drop_column('reports', 'file_size')
    op.drop_column('reports', 'file_checksum')
    op.drop_column('reports', 'created_by_id')
    op.drop_column('reports', 'adjudication_run_id')

    op.alter_column(
        'reports',
        'audit_run_id',
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )

