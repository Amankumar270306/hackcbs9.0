"""regulatory_knowledge_base_milestone4

Revision ID: ba684bc4df0b
Revises: e78ef3acc5d8
Create Date: 2026-10-31 19:24:46.924087

"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ba684bc4df0b'
down_revision: Union[str, Sequence[str], None] = 'e78ef3acc5d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema for Regulatory Knowledge Base and Legal Analyst (Milestone 4)."""
    # 1. regulatory_frameworks
    op.create_table(
        'regulatory_frameworks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('short_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('issuing_authority', sa.String(255), nullable=False),
        sa.Column('jurisdiction', sa.String(100), nullable=False, server_default='Global'),
        sa.Column('framework_type', sa.String(50), nullable=False, server_default='standard'),
        sa.Column('official_source_url', sa.String(1024), nullable=True),
        sa.Column('version', sa.String(50), nullable=False, server_default='1.0'),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('framework_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint(
            "framework_type IN ('regulation', 'legislation', 'standard', 'guideline', 'circular', 'policy', 'other')",
            name='ck_reg_framework_type',
        ),
        sa.CheckConstraint(
            "status IN ('active', 'draft', 'archived', 'deprecated')",
            name='ck_reg_framework_status',
        ),
    )
    op.create_index('ix_reg_framework_org', 'regulatory_frameworks', ['organization_id'])
    op.create_index('ix_reg_framework_short_name', 'regulatory_frameworks', ['short_name'])
    op.create_index('ix_reg_framework_status', 'regulatory_frameworks', ['status'])

    # 2. regulatory_documents
    op.create_table(
        'regulatory_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('framework_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('regulatory_frameworks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('document_number', sa.String(100), nullable=True),
        sa.Column('version', sa.String(50), nullable=False, server_default='1.0'),
        sa.Column('source_url', sa.String(1024), nullable=True),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('stored_filename', sa.String(255), nullable=False),
        sa.Column('storage_key', sa.String(1024), nullable=False),
        sa.Column('file_extension', sa.String(20), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('document_hash', sa.String(64), nullable=False),
        sa.Column('issuing_authority', sa.String(255), nullable=True),
        sa.Column('publication_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='uploaded'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('doc_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint(
            "status IN ('uploaded', 'processing', 'completed', 'failed')",
            name='ck_reg_doc_status',
        ),
    )
    op.create_index('ix_reg_docs_framework', 'regulatory_documents', ['framework_id'])
    op.create_index('ix_reg_docs_org', 'regulatory_documents', ['organization_id'])
    op.create_index('ix_reg_docs_hash', 'regulatory_documents', ['document_hash'])
    op.create_index('ix_reg_docs_status', 'regulatory_documents', ['status'])

    # 3. regulatory_document_chunks
    op.create_table(
        'regulatory_document_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('regulatory_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('regulatory_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('page_start', sa.Integer(), nullable=True),
        sa.Column('page_end', sa.Integer(), nullable=True),
        sa.Column('section_title', sa.String(255), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('character_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('start_char_offset', sa.Integer(), nullable=True),
        sa.Column('end_char_offset', sa.Integer(), nullable=True),
        sa.Column('chunk_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.UniqueConstraint('regulatory_document_id', 'chunk_index', name='uq_reg_chunks_doc_idx'),
    )
    op.create_index('ix_reg_chunks_doc', 'regulatory_document_chunks', ['regulatory_document_id'])
    op.create_index('ix_reg_chunks_page', 'regulatory_document_chunks', ['page_number'])

    # 4. regulatory_extraction_jobs
    op.create_table(
        'regulatory_extraction_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('regulatory_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('regulatory_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('prompt_version', sa.String(50), nullable=False, server_default='v1.0'),
        sa.Column('chunks_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('chunks_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('requirements_extracted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_duration_ms', sa.Integer(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name='ck_reg_job_status',
        ),
    )
    op.create_index('ix_reg_jobs_doc', 'regulatory_extraction_jobs', ['regulatory_document_id'])
    op.create_index('ix_reg_jobs_status', 'regulatory_extraction_jobs', ['status'])

    # 5. Alter requirements table
    op.alter_column('requirements', 'organization_id', nullable=True)
    op.alter_column('requirements', 'audit_run_id', nullable=True)

    op.add_column('requirements', sa.Column('framework_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('regulatory_frameworks.id', ondelete='SET NULL'), nullable=True))
    op.add_column('requirements', sa.Column('regulatory_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('regulatory_documents.id', ondelete='SET NULL'), nullable=True))
    op.add_column('requirements', sa.Column('requirement_code', sa.String(100), nullable=True))
    op.add_column('requirements', sa.Column('requirement_statement', sa.Text(), nullable=True))
    op.add_column('requirements', sa.Column('detailed_description', sa.Text(), nullable=True))
    op.add_column('requirements', sa.Column('obligation_type', sa.String(50), nullable=False, server_default='mandatory'))
    op.add_column('requirements', sa.Column('subcategory', sa.String(100), nullable=True))
    op.add_column('requirements', sa.Column('applicability', sa.String(50), nullable=False, server_default='general'))
    op.add_column('requirements', sa.Column('applicability_conditions', sa.Text(), nullable=True))
    op.add_column('requirements', sa.Column('jurisdiction', sa.String(100), nullable=True))
    op.add_column('requirements', sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('requirements', sa.Column('source_section', sa.String(255), nullable=True))
    op.add_column('requirements', sa.Column('source_page', sa.Integer(), nullable=True))
    op.add_column('requirements', sa.Column('source_excerpt', sa.Text(), nullable=True))
    op.add_column('requirements', sa.Column('source_chunk_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('requirements', sa.Column('confidence_score', sa.Numeric(5, 2), nullable=True))
    op.add_column('requirements', sa.Column('extraction_status', sa.String(50), nullable=False, server_default='completed'))
    op.add_column('requirements', sa.Column('review_status', sa.String(50), nullable=False, server_default='pending_review'))
    op.add_column('requirements', sa.Column('extraction_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column('requirements', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('requirements', sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))

    op.create_check_constraint(
        'ck_req_obligation_type',
        'requirements',
        "obligation_type IN ('mandatory', 'conditional', 'recommended', 'informational', 'unclear')",
    )
    op.create_check_constraint(
        'ck_req_review_status',
        'requirements',
        "review_status IN ('pending_review', 'approved', 'rejected', 'needs_revision')",
    )
    op.create_check_constraint(
        'ck_req_extraction_status',
        'requirements',
        "extraction_status IN ('pending', 'extracting', 'completed', 'failed')",
    )
    op.create_index('ix_requirements_framework_id', 'requirements', ['framework_id'])
    op.create_index('ix_requirements_doc_id', 'requirements', ['regulatory_document_id'])
    op.create_index('ix_requirements_review_status', 'requirements', ['review_status'])
    op.create_index('ix_requirements_code', 'requirements', ['requirement_code'])

    # 6. requirement_sources
    op.create_table(
        'requirement_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('requirement_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('requirements.id', ondelete='CASCADE'), nullable=False),
        sa.Column('regulatory_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('regulatory_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_chunk_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('regulatory_document_chunks.id', ondelete='SET NULL'), nullable=True),
        sa.Column('section_reference', sa.String(255), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('exact_excerpt', sa.Text(), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False, server_default='primary_clause'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_req_sources_req_id', 'requirement_sources', ['requirement_id'])
    op.create_index('ix_req_sources_doc_id', 'requirement_sources', ['regulatory_document_id'])
    op.create_index('ix_req_sources_chunk_id', 'requirement_sources', ['document_chunk_id'])

    # 7. requirement_audit_history
    op.create_table(
        'requirement_audit_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('requirement_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('requirements.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('previous_status', sa.String(50), nullable=True),
        sa.Column('new_status', sa.String(50), nullable=True),
        sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_req_hist_req_id', 'requirement_audit_history', ['requirement_id'])
    op.create_index('ix_req_hist_reviewer', 'requirement_audit_history', ['reviewer_id'])
    op.create_index('ix_req_hist_created', 'requirement_audit_history', ['created_at'])

    # 8. audit_requirements
    op.create_table(
        'audit_requirements',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('audits.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requirement_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('requirements.id', ondelete='CASCADE'), nullable=False),
        sa.Column('applicability_status', sa.String(50), nullable=False, server_default='applicable'),
        sa.Column('applicability_reason', sa.Text(), nullable=True),
        sa.Column('added_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(
            ['organization_id', 'audit_id'],
            ['audits.organization_id', 'audits.id'],
            ondelete='CASCADE',
            name='fk_audit_req_org_audit',
        ),
        sa.UniqueConstraint('audit_id', 'requirement_id', name='uq_audit_requirements_audit_req'),
        sa.CheckConstraint(
            "applicability_status IN ('applicable', 'not_applicable', 'requires_review')",
            name='ck_audit_req_applicability',
        ),
    )
    op.create_index('ix_audit_req_org', 'audit_requirements', ['organization_id'])
    op.create_index('ix_audit_req_audit', 'audit_requirements', ['audit_id'])
    op.create_index('ix_audit_req_requirement', 'audit_requirements', ['requirement_id'])
    op.create_index('ix_audit_req_status', 'audit_requirements', ['applicability_status'])


def downgrade() -> None:
    """Downgrade schema for Regulatory Knowledge Base (Milestone 4)."""
    # 8. audit_requirements
    op.drop_table('audit_requirements')

    # 7. requirement_audit_history
    op.drop_table('requirement_audit_history')

    # 6. requirement_sources
    op.drop_table('requirement_sources')

    # 5. Alter requirements table back
    op.drop_index('ix_requirements_code', table_name='requirements')
    op.drop_index('ix_requirements_review_status', table_name='requirements')
    op.drop_index('ix_requirements_doc_id', table_name='requirements')
    op.drop_index('ix_requirements_framework_id', table_name='requirements')
    op.drop_constraint('ck_req_extraction_status', 'requirements', type_='check')
    op.drop_constraint('ck_req_review_status', 'requirements', type_='check')
    op.drop_constraint('ck_req_obligation_type', 'requirements', type_='check')

    op.drop_column('requirements', 'reviewed_by')
    op.drop_column('requirements', 'reviewed_at')
    op.drop_column('requirements', 'extraction_metadata')
    op.drop_column('requirements', 'review_status')
    op.drop_column('requirements', 'extraction_status')
    op.drop_column('requirements', 'confidence_score')
    op.drop_column('requirements', 'source_chunk_id')
    op.drop_column('requirements', 'source_excerpt')
    op.drop_column('requirements', 'source_page')
    op.drop_column('requirements', 'source_section')
    op.drop_column('requirements', 'effective_date')
    op.drop_column('requirements', 'jurisdiction')
    op.drop_column('requirements', 'applicability_conditions')
    op.drop_column('requirements', 'applicability')
    op.drop_column('requirements', 'subcategory')
    op.drop_column('requirements', 'obligation_type')
    op.drop_column('requirements', 'detailed_description')
    op.drop_column('requirements', 'requirement_statement')
    op.drop_column('requirements', 'requirement_code')
    op.drop_column('requirements', 'regulatory_document_id')
    op.drop_column('requirements', 'framework_id')

    op.alter_column('requirements', 'audit_run_id', nullable=False)
    op.alter_column('requirements', 'organization_id', nullable=False)

    # 4. regulatory_extraction_jobs
    op.drop_table('regulatory_extraction_jobs')

    # 3. regulatory_document_chunks
    op.drop_table('regulatory_document_chunks')

    # 2. regulatory_documents
    op.drop_table('regulatory_documents')

    # 1. regulatory_frameworks
    op.drop_table('regulatory_frameworks')
