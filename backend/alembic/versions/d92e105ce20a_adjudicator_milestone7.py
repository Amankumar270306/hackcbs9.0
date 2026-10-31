"""adjudicator_milestone7

Revision ID: d92e105ce20a
Revises: c81f084be19b
Create Date: 2026-10-31 21:15:00.000000

"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd92e105ce20a'
down_revision: Union[str, Sequence[str], None] = 'c81f084be19b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema for Adjudicator: Cross-Agent Consensus & Reconciliation (Milestone 7)."""
    # 1. adjudication_runs
    op.execute("""
    CREATE TABLE IF NOT EXISTS adjudication_runs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
        status VARCHAR(50) NOT NULL DEFAULT 'pending',
        model_name VARCHAR(100) NOT NULL DEFAULT 'gemini-1.5-flash',
        prompt_version VARCHAR(50) NOT NULL DEFAULT 'v1.0',
        input_source_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
        requirements_processed_count INTEGER NOT NULL DEFAULT 0,
        threats_processed_count INTEGER NOT NULL DEFAULT 0,
        controls_processed_count INTEGER NOT NULL DEFAULT 0,
        decisions_generated_count INTEGER NOT NULL DEFAULT 0,
        contradictions_detected_count INTEGER NOT NULL DEFAULT 0,
        execution_duration_ms INTEGER,
        error_message TEXT,
        execution_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT ck_adjudication_run_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
    );
    CREATE INDEX IF NOT EXISTS ix_adj_runs_org ON adjudication_runs(organization_id);
    CREATE INDEX IF NOT EXISTS ix_adj_runs_audit ON adjudication_runs(audit_id);
    CREATE INDEX IF NOT EXISTS ix_adj_runs_status ON adjudication_runs(status);
    """)

    # 2. adjudication_decisions
    op.execute("""
    CREATE TABLE IF NOT EXISTS adjudication_decisions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
        adjudication_run_id UUID NOT NULL REFERENCES adjudication_runs(id) ON DELETE CASCADE,
        decision_category VARCHAR(50) NOT NULL,
        related_entity_type VARCHAR(50) NOT NULL,
        related_entity_id UUID,
        outcome_status VARCHAR(60) NOT NULL,
        summary TEXT NOT NULL,
        reasoning TEXT NOT NULL,
        confidence_score NUMERIC(4, 2) NOT NULL DEFAULT 0.50,
        is_provisional BOOLEAN NOT NULL DEFAULT FALSE,
        requires_human_review BOOLEAN NOT NULL DEFAULT FALSE,
        is_stale BOOLEAN NOT NULL DEFAULT FALSE,
        evidence_limitations TEXT,
        assumptions JSONB NOT NULL DEFAULT '[]'::jsonb,
        missing_information JSONB NOT NULL DEFAULT '[]'::jsonb,
        recommended_action TEXT,
        review_status VARCHAR(50) NOT NULL DEFAULT 'pending_review',
        reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
        reviewed_at TIMESTAMPTZ,
        review_notes TEXT,
        decision_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT ck_adj_decision_category CHECK (
            decision_category IN ('requirement_compliance', 'threat_mitigation', 'control_effectiveness', 'cross_cutting')
        ),
        CONSTRAINT ck_adj_decision_entity_type CHECK (
            related_entity_type IN ('requirement', 'threat', 'control', 'general')
        ),
        CONSTRAINT ck_adj_decision_outcome CHECK (
            outcome_status IN (
                'supported_by_documented_evidence',
                'partially_supported',
                'insufficient_evidence',
                'contradictory_evidence',
                'documented_nonconformance',
                'not_applicable',
                'requires_human_review',
                'documented_mitigations_supported',
                'partially_mitigated',
                'insufficient_mitigation_evidence',
                'documented_control_weakness'
            )
        ),
        CONSTRAINT ck_adj_decision_review_status CHECK (
            review_status IN ('pending_review', 'approved', 'rejected', 'edited', 'more_info_requested')
        )
    );
    CREATE INDEX IF NOT EXISTS ix_adj_decisions_org ON adjudication_decisions(organization_id);
    CREATE INDEX IF NOT EXISTS ix_adj_decisions_audit ON adjudication_decisions(audit_id);
    CREATE INDEX IF NOT EXISTS ix_adj_decisions_run ON adjudication_decisions(adjudication_run_id);
    CREATE INDEX IF NOT EXISTS ix_adj_decisions_category ON adjudication_decisions(decision_category);
    CREATE INDEX IF NOT EXISTS ix_adj_decisions_entity ON adjudication_decisions(related_entity_type, related_entity_id);
    CREATE INDEX IF NOT EXISTS ix_adj_decisions_outcome ON adjudication_decisions(outcome_status);
    CREATE INDEX IF NOT EXISTS ix_adj_decisions_review ON adjudication_decisions(review_status);
    CREATE INDEX IF NOT EXISTS ix_adj_decisions_stale ON adjudication_decisions(is_stale);
    """)

    # 3. adjudication_sources
    op.execute("""
    CREATE TABLE IF NOT EXISTS adjudication_sources (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
        decision_id UUID NOT NULL REFERENCES adjudication_decisions(id) ON DELETE CASCADE,
        source_agent VARCHAR(50) NOT NULL,
        source_entity_type VARCHAR(60) NOT NULL,
        source_entity_id UUID NOT NULL,
        source_version VARCHAR(50),
        source_role VARCHAR(50) NOT NULL DEFAULT 'supporting',
        citation_reference VARCHAR(255),
        exact_excerpt TEXT,
        chunk_id UUID,
        document_id UUID,
        page_number INTEGER,
        section_heading VARCHAR(255),
        is_citation_valid BOOLEAN NOT NULL DEFAULT TRUE,
        citation_validation_notes TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT ck_adj_source_agent CHECK (
            source_agent IN ('legal_analyst', 'adversarial_strategist', 'defence_auditor', 'document_extractor', 'human_reviewer')
        ),
        CONSTRAINT ck_adj_source_entity_type CHECK (
            source_entity_type IN ('regulatory_requirement', 'threat_scenario', 'discovered_control', 'control_assessment', 'finding', 'document_chunk')
        ),
        CONSTRAINT ck_adj_source_role CHECK (
            source_role IN ('supporting', 'contradictory', 'contextual', 'informational')
        )
    );
    CREATE INDEX IF NOT EXISTS ix_adj_sources_org ON adjudication_sources(organization_id);
    CREATE INDEX IF NOT EXISTS ix_adj_sources_audit ON adjudication_sources(audit_id);
    CREATE INDEX IF NOT EXISTS ix_adj_sources_decision ON adjudication_sources(decision_id);
    CREATE INDEX IF NOT EXISTS ix_adj_sources_entity ON adjudication_sources(source_entity_type, source_entity_id);
    CREATE INDEX IF NOT EXISTS ix_adj_sources_validity ON adjudication_sources(is_citation_valid);
    """)

    # 4. adjudication_contradictions
    op.execute("""
    CREATE TABLE IF NOT EXISTS adjudication_contradictions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
        adjudication_run_id UUID NOT NULL REFERENCES adjudication_runs(id) ON DELETE CASCADE,
        contradiction_category VARCHAR(50) NOT NULL,
        title VARCHAR(255) NOT NULL,
        description TEXT NOT NULL,
        conflicting_claims JSONB NOT NULL DEFAULT '[]'::jsonb,
        source_references JSONB NOT NULL DEFAULT '[]'::jsonb,
        impact TEXT NOT NULL,
        severity VARCHAR(50) NOT NULL DEFAULT 'medium',
        resolution_status VARCHAR(50) NOT NULL DEFAULT 'unresolved',
        resolution_notes TEXT,
        resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,
        resolved_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT ck_adj_contradiction_category CHECK (
            contradiction_category IN ('requirement_vs_control', 'threat_vs_control', 'contradictory_documents', 'ai_vs_human_review', 'cross_agent')
        ),
        CONSTRAINT ck_adj_contradiction_severity CHECK (
            severity IN ('critical', 'high', 'medium', 'low')
        ),
        CONSTRAINT ck_adj_contradiction_resolution CHECK (
            resolution_status IN ('unresolved', 'resolved', 'clarification_requested', 'dismissed')
        )
    );
    CREATE INDEX IF NOT EXISTS ix_adj_contra_org ON adjudication_contradictions(organization_id);
    CREATE INDEX IF NOT EXISTS ix_adj_contra_audit ON adjudication_contradictions(audit_id);
    CREATE INDEX IF NOT EXISTS ix_adj_contra_run ON adjudication_contradictions(adjudication_run_id);
    CREATE INDEX IF NOT EXISTS ix_adj_contra_category ON adjudication_contradictions(contradiction_category);
    CREATE INDEX IF NOT EXISTS ix_adj_contra_status ON adjudication_contradictions(resolution_status);
    """)

    # 5. adjudication_audit_history
    op.execute("""
    CREATE TABLE IF NOT EXISTS adjudication_audit_history (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
        decision_id UUID REFERENCES adjudication_decisions(id) ON DELETE CASCADE,
        contradiction_id UUID REFERENCES adjudication_contradictions(id) ON DELETE CASCADE,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        action VARCHAR(50) NOT NULL,
        previous_status VARCHAR(50),
        new_status VARCHAR(50) NOT NULL,
        previous_content JSONB,
        updated_content JSONB,
        justification TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT ck_adj_history_action CHECK (
            action IN ('approved', 'rejected', 'edited', 'requested_information', 'resolved_contradiction', 'reassessed', 'marked_unresolved')
        )
    );
    CREATE INDEX IF NOT EXISTS ix_adj_history_org ON adjudication_audit_history(organization_id);
    CREATE INDEX IF NOT EXISTS ix_adj_history_audit ON adjudication_audit_history(audit_id);
    CREATE INDEX IF NOT EXISTS ix_adj_history_decision ON adjudication_audit_history(decision_id);
    CREATE INDEX IF NOT EXISTS ix_adj_history_contradiction ON adjudication_audit_history(contradiction_id);
    CREATE INDEX IF NOT EXISTS ix_adj_history_user ON adjudication_audit_history(user_id);
    CREATE INDEX IF NOT EXISTS ix_adj_history_created ON adjudication_audit_history(created_at);
    """)


def downgrade() -> None:
    """Downgrade schema for Adjudicator (Milestone 7)."""
    op.execute("""
    DROP TABLE IF EXISTS adjudication_audit_history CASCADE;
    DROP TABLE IF EXISTS adjudication_contradictions CASCADE;
    DROP TABLE IF EXISTS adjudication_sources CASCADE;
    DROP TABLE IF EXISTS adjudication_decisions CASCADE;
    DROP TABLE IF EXISTS adjudication_runs CASCADE;
    """)
