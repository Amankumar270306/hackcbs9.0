"""document_management_milestone3

Revision ID: e78ef3acc5d8
Revises: 374272b8449c
Create Date: 2026-10-31 16:44:27.654310

"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e78ef3acc5d8'
down_revision: Union[str, Sequence[str], None] = '374272b8449c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema for Milestone 3 Document Management."""
    # 1. Update audit_documents table
    op.execute("ALTER TABLE audit_documents ALTER COLUMN audit_run_id DROP NOT NULL")

    op.execute("ALTER TABLE audit_documents ADD COLUMN IF NOT EXISTS uploaded_by UUID")
    op.execute("ALTER TABLE audit_documents ADD COLUMN IF NOT EXISTS original_filename VARCHAR(255)")
    op.execute("ALTER TABLE audit_documents ADD COLUMN IF NOT EXISTS stored_filename VARCHAR(255)")
    op.execute("ALTER TABLE audit_documents ADD COLUMN IF NOT EXISTS file_extension VARCHAR(20)")
    op.execute("ALTER TABLE audit_documents ADD COLUMN IF NOT EXISTS storage_key VARCHAR(1024)")
    op.execute("ALTER TABLE audit_documents ADD COLUMN IF NOT EXISTS file_hash_sha256 VARCHAR(64)")
    op.execute("ALTER TABLE audit_documents ADD COLUMN IF NOT EXISTS processing_error TEXT")
    op.execute("ALTER TABLE audit_documents ADD COLUMN IF NOT EXISTS extracted_text_length INTEGER DEFAULT 0 NOT NULL")
    op.execute("ALTER TABLE audit_documents ADD COLUMN IF NOT EXISTS page_count INTEGER")
    op.execute("ALTER TABLE audit_documents ADD COLUMN IF NOT EXISTS chunk_count INTEGER DEFAULT 0 NOT NULL")
    op.execute("ALTER TABLE audit_documents ADD COLUMN IF NOT EXISTS extracted_text TEXT")
    op.execute("ALTER TABLE audit_documents ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE audit_documents ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ")

    # Backfill fields for existing documents
    op.execute("""
        UPDATE audit_documents SET
            original_filename = COALESCE(original_filename, file_name),
            stored_filename = COALESCE(stored_filename, file_name),
            storage_key = COALESCE(storage_key, storage_path),
            file_hash_sha256 = COALESCE(file_hash_sha256, checksum_sha256),
            file_extension = COALESCE(file_extension, SUBSTRING(file_name FROM '\\.([^\\.]+)$'))
        WHERE original_filename IS NULL
    """)

    # Foreign keys and constraints on audit_documents
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_audit_docs_uploader') THEN
                ALTER TABLE audit_documents ADD CONSTRAINT fk_audit_docs_uploader
                    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_audit_docs_org_audit') THEN
                ALTER TABLE audit_documents ADD CONSTRAINT fk_audit_docs_org_audit
                    FOREIGN KEY (organization_id, audit_id) REFERENCES audits(organization_id, id) ON DELETE CASCADE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_audit_docs_org_audit_id') THEN
                ALTER TABLE audit_documents ADD CONSTRAINT uq_audit_docs_org_audit_id
                    UNIQUE (organization_id, audit_id, id);
            END IF;
        END $$;
    """)

    # Status check constraint update
    op.execute("ALTER TABLE audit_documents DROP CONSTRAINT IF EXISTS ck_audit_doc_status")
    op.execute("ALTER TABLE audit_documents DROP CONSTRAINT IF EXISTS ck_audit_documents_ck_audit_doc_status")
    op.execute(
        "ALTER TABLE audit_documents ADD CONSTRAINT ck_audit_doc_status "
        "CHECK (status IN ('uploaded', 'queued', 'processing', 'indexed', 'completed', 'failed'))"
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_docs_audit_id ON audit_documents (audit_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_docs_deleted_at ON audit_documents (deleted_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_docs_checksum ON audit_documents (checksum_sha256)")

    # 2. Update document_chunks table
    op.execute("ALTER TABLE document_chunks ALTER COLUMN audit_run_id DROP NOT NULL")

    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS audit_id UUID")
    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS page_start INTEGER")
    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS page_end INTEGER")
    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS section_title VARCHAR(255)")
    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS token_count INTEGER")
    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS character_count INTEGER DEFAULT 0 NOT NULL")

    # Backfill chunks audit_id and character_count from audit_documents
    op.execute("""
        UPDATE document_chunks c
        SET
            audit_id = d.audit_id,
            character_count = COALESCE(NULLIF(c.character_count, 0), LENGTH(c.content))
        FROM audit_documents d
        WHERE c.audit_document_id = d.id AND c.audit_id IS NULL
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_doc_chunks_doc_id') THEN
                ALTER TABLE document_chunks ADD CONSTRAINT fk_doc_chunks_doc_id
                    FOREIGN KEY (audit_document_id) REFERENCES audit_documents(id) ON DELETE CASCADE;
            END IF;
        END $$;
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_doc_chunks_audit_id ON document_chunks (audit_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_doc_chunks_audit_id")
    op.execute("ALTER TABLE document_chunks DROP CONSTRAINT IF EXISTS fk_doc_chunks_doc_id")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS character_count")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS token_count")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS section_title")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS page_end")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS page_start")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS audit_id")
    op.execute("ALTER TABLE document_chunks ALTER COLUMN audit_run_id SET NOT NULL")

    op.execute("DROP INDEX IF EXISTS ix_audit_docs_checksum")
    op.execute("DROP INDEX IF EXISTS ix_audit_docs_deleted_at")
    op.execute("DROP INDEX IF EXISTS ix_audit_docs_audit_id")
    op.execute("ALTER TABLE audit_documents DROP CONSTRAINT IF EXISTS uq_audit_docs_org_audit_id")
    op.execute("ALTER TABLE audit_documents DROP CONSTRAINT IF EXISTS fk_audit_docs_org_audit")
    op.execute("ALTER TABLE audit_documents DROP CONSTRAINT IF EXISTS fk_audit_docs_uploader")

    op.execute("ALTER TABLE audit_documents DROP COLUMN IF EXISTS deleted_at")
    op.execute("ALTER TABLE audit_documents DROP COLUMN IF EXISTS processed_at")
    op.execute("ALTER TABLE audit_documents DROP COLUMN IF EXISTS extracted_text")
    op.execute("ALTER TABLE audit_documents DROP COLUMN IF EXISTS chunk_count")
    op.execute("ALTER TABLE audit_documents DROP COLUMN IF EXISTS page_count")
    op.execute("ALTER TABLE audit_documents DROP COLUMN IF EXISTS extracted_text_length")
    op.execute("ALTER TABLE audit_documents DROP COLUMN IF EXISTS processing_error")
    op.execute("ALTER TABLE audit_documents DROP COLUMN IF EXISTS file_hash_sha256")
    op.execute("ALTER TABLE audit_documents DROP COLUMN IF EXISTS storage_key")
    op.execute("ALTER TABLE audit_documents DROP COLUMN IF EXISTS file_extension")
    op.execute("ALTER TABLE audit_documents DROP COLUMN IF EXISTS stored_filename")
    op.execute("ALTER TABLE audit_documents DROP COLUMN IF EXISTS original_filename")
    op.execute("ALTER TABLE audit_documents DROP COLUMN IF EXISTS uploaded_by")
    op.execute("ALTER TABLE audit_documents ALTER COLUMN audit_run_id SET NOT NULL")
