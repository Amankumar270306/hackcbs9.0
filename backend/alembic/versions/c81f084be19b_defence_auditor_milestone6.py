"""defence_auditor_milestone6

Revision ID: c81f084be19b
Revises: 25a8ca434fe7
Create Date: 2026-10-31 20:36:00.000000

"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c81f084be19b'
down_revision: Union[str, Sequence[str], None] = '25a8ca434fe7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema for Defence Auditor (Milestone 6)."""
    # 1. defence_analysis_runs
    op.execute("""
    CREATE TABLE IF NOT EXISTS defence_analysis_runs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
        status VARCHAR(50) NOT NULL DEFAULT 'pending',
        model_name VARCHAR(100) NOT NULL DEFAULT 'gemini-1.5-flash',
        prompt_version VARCHAR(50) NOT NULL DEFAULT 'v1.0',
        input_document_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
        input_requirement_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
        input_threat_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
        controls_discovered_count INTEGER NOT NULL DEFAULT 0,
        assessments_count INTEGER NOT NULL DEFAULT 0,
        findings_count INTEGER NOT NULL DEFAULT 0,
        execution_duration_ms INTEGER,
        error_message TEXT,
        execution_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
        started_at TIMESTAMP WITH TIME ZONE,
        completed_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT ck_defence_run_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled'))
    );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_defence_runs_org ON defence_analysis_runs(organization_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_defence_runs_audit ON defence_analysis_runs(audit_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_defence_runs_status ON defence_analysis_runs(status);")

    # 2. discovered_controls
    op.execute("""
    CREATE TABLE IF NOT EXISTS discovered_controls (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
        defence_analysis_run_id UUID REFERENCES defence_analysis_runs(id) ON DELETE SET NULL,
        control_code VARCHAR(50) NOT NULL,
        name VARCHAR(255) NOT NULL,
        description TEXT NOT NULL,
        category VARCHAR(100) NOT NULL,
        control_objective TEXT NOT NULL,
        implementation_status VARCHAR(50) NOT NULL DEFAULT 'documented',
        operational_status VARCHAR(50) NOT NULL DEFAULT 'unverified',
        evidence_maturity VARCHAR(50) NOT NULL DEFAULT 'policy',
        confidence_score NUMERIC(5, 2) NOT NULL DEFAULT 0.90,
        source_references JSONB NOT NULL DEFAULT '[]'::jsonb,
        control_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_discovered_controls_audit_code UNIQUE (audit_id, control_code),
        CONSTRAINT ck_ctrl_impl_status CHECK (implementation_status IN ('documented', 'partially_documented', 'undocumented', 'unknown')),
        CONSTRAINT ck_ctrl_oper_status CHECK (operational_status IN ('active', 'planned', 'unverified', 'unknown')),
        CONSTRAINT ck_ctrl_maturity CHECK (evidence_maturity IN ('policy', 'design', 'implementation', 'operational', 'unknown'))
    );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_disc_ctrls_org ON discovered_controls(organization_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_disc_ctrls_audit ON discovered_controls(audit_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_disc_ctrls_category ON discovered_controls(category);")

    # 3. alter control_assessments
    op.execute("ALTER TABLE control_assessments ALTER COLUMN audit_run_id DROP NOT NULL;")
    op.execute("ALTER TABLE control_assessments ALTER COLUMN requirement_id DROP NOT NULL;")
    op.execute("ALTER TABLE control_assessments ALTER COLUMN rationale DROP NOT NULL;")

    op.execute("ALTER TABLE control_assessments DROP CONSTRAINT IF EXISTS fk_ctrl_assess_org_run_req;")
    op.execute("ALTER TABLE control_assessments DROP CONSTRAINT IF EXISTS fk_ctrl_assess_org_run_threat;")
    op.execute("ALTER TABLE control_assessments DROP CONSTRAINT IF EXISTS ck_control_assessments_ck_ctrl_assess_status;")
    op.execute("ALTER TABLE control_assessments DROP CONSTRAINT IF EXISTS ck_ctrl_assess_status;")
    op.execute("ALTER TABLE control_assessments DROP CONSTRAINT IF EXISTS ck_ctrl_assess_maturity;")
    op.execute("ALTER TABLE control_assessments DROP CONSTRAINT IF EXISTS ck_ctrl_assess_review_status;")

    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS audit_id UUID REFERENCES audits(id) ON DELETE CASCADE;")
    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS control_id UUID REFERENCES discovered_controls(id) ON DELETE CASCADE;")
    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS defence_analysis_run_id UUID REFERENCES defence_analysis_runs(id) ON DELETE SET NULL;")
    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS assessment_explanation TEXT;")
    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS evidence_maturity VARCHAR(50);")
    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS evidence_limitations TEXT;")
    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS missing_information TEXT;")
    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS contradictions TEXT;")
    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS recommended_next_steps TEXT;")
    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS review_status VARCHAR(50) NOT NULL DEFAULT 'pending_review';")
    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS review_reason TEXT;")
    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL;")
    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITH TIME ZONE;")
    op.execute("ALTER TABLE control_assessments ADD COLUMN IF NOT EXISTS assessment_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;")

    op.execute("ALTER TABLE control_assessments DROP CONSTRAINT IF EXISTS fk_ctrl_assess_req_id;")
    op.execute("ALTER TABLE control_assessments ADD CONSTRAINT fk_ctrl_assess_req_id FOREIGN KEY (requirement_id) REFERENCES requirements(id) ON DELETE SET NULL;")
    op.execute("ALTER TABLE control_assessments DROP CONSTRAINT IF EXISTS fk_ctrl_assess_threat_id;")
    op.execute("ALTER TABLE control_assessments ADD CONSTRAINT fk_ctrl_assess_threat_id FOREIGN KEY (threat_id) REFERENCES threats(id) ON DELETE SET NULL;")

    op.execute("""
    ALTER TABLE control_assessments ADD CONSTRAINT ck_ctrl_assess_status
    CHECK (status IN ('effective_documented_control', 'partially_supported_control', 'insufficient_evidence', 'contradictory_evidence', 'confirmed_weakness', 'not_applicable', 'satisfied', 'partially_satisfied', 'not_satisfied', 'not_documented', 'needs_review'));
    """)
    op.execute("""
    ALTER TABLE control_assessments ADD CONSTRAINT ck_ctrl_assess_maturity
    CHECK (evidence_maturity IS NULL OR evidence_maturity IN ('policy', 'design', 'implementation', 'operational'));
    """)
    op.execute("""
    ALTER TABLE control_assessments ADD CONSTRAINT ck_ctrl_assess_review_status
    CHECK (review_status IN ('pending_review', 'approved', 'rejected', 'edited', 'needs_more_information'));
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_assess_audit_id ON control_assessments(audit_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_assess_control_id ON control_assessments(control_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_assess_defence_run ON control_assessments(defence_analysis_run_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_assess_review_status ON control_assessments(review_status);")

    # 4. control_requirement_mappings
    op.execute("""
    CREATE TABLE IF NOT EXISTS control_requirement_mappings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
        control_id UUID NOT NULL REFERENCES discovered_controls(id) ON DELETE CASCADE,
        requirement_id UUID NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
        coverage_level VARCHAR(50) NOT NULL DEFAULT 'supports',
        mapping_rationale TEXT,
        supporting_references JSONB NOT NULL DEFAULT '[]'::jsonb,
        confidence_score NUMERIC(5, 2) NOT NULL DEFAULT 0.90,
        review_status VARCHAR(50) NOT NULL DEFAULT 'pending_review',
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_ctrl_req_map UNIQUE (control_id, requirement_id),
        CONSTRAINT ck_ctrl_req_coverage CHECK (coverage_level IN ('fully_covers', 'partially_covers', 'supports', 'potential_coverage'))
    );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_req_control ON control_requirement_mappings(control_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_req_req ON control_requirement_mappings(requirement_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_req_audit ON control_requirement_mappings(audit_id);")

    # 5. control_threat_mappings
    op.execute("""
    CREATE TABLE IF NOT EXISTS control_threat_mappings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
        control_id UUID NOT NULL REFERENCES discovered_controls(id) ON DELETE CASCADE,
        threat_id UUID NOT NULL REFERENCES threats(id) ON DELETE CASCADE,
        asset_id UUID REFERENCES discovered_assets(id) ON DELETE SET NULL,
        attack_surface_id UUID REFERENCES attack_surfaces(id) ON DELETE SET NULL,
        attack_path_node_id UUID REFERENCES attack_path_nodes(id) ON DELETE SET NULL,
        mitigation_level VARCHAR(50) NOT NULL DEFAULT 'partially_mitigates',
        mapping_rationale TEXT,
        supporting_references JSONB NOT NULL DEFAULT '[]'::jsonb,
        confidence_score NUMERIC(5, 2) NOT NULL DEFAULT 0.90,
        review_status VARCHAR(50) NOT NULL DEFAULT 'pending_review',
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_ctrl_threat_map UNIQUE (control_id, threat_id),
        CONSTRAINT ck_ctrl_threat_mitigation CHECK (mitigation_level IN ('mitigates', 'partially_mitigates', 'detects', 'monitors', 'unverified'))
    );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_threat_control ON control_threat_mappings(control_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_threat_threat ON control_threat_mappings(threat_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_threat_audit ON control_threat_mappings(audit_id);")

    # 6. control_evidence_references
    op.execute("""
    CREATE TABLE IF NOT EXISTS control_evidence_references (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
        control_id UUID NOT NULL REFERENCES discovered_controls(id) ON DELETE CASCADE,
        assessment_id UUID REFERENCES control_assessments(id) ON DELETE CASCADE,
        audit_document_id UUID NOT NULL REFERENCES audit_documents(id) ON DELETE CASCADE,
        document_chunk_id UUID REFERENCES document_chunks(id) ON DELETE SET NULL,
        original_filename VARCHAR(255),
        page_number INTEGER,
        section_title VARCHAR(255),
        exact_excerpt TEXT NOT NULL,
        citation_type VARCHAR(50) NOT NULL DEFAULT 'direct_evidence',
        evidence_maturity VARCHAR(50) NOT NULL DEFAULT 'policy',
        relevance_explanation TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT ck_ctrl_ev_citation_type CHECK (citation_type IN ('direct_evidence', 'contradictory_evidence', 'contextual_evidence', 'inference', 'missing_evidence')),
        CONSTRAINT ck_ctrl_ev_maturity CHECK (evidence_maturity IN ('policy', 'design', 'implementation', 'operational'))
    );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_ev_control ON control_evidence_references(control_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_ev_doc ON control_evidence_references(audit_document_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_ev_chunk ON control_evidence_references(document_chunk_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_ev_audit ON control_evidence_references(audit_id);")

    # 7. control_audit_history
    op.execute("""
    CREATE TABLE IF NOT EXISTS control_audit_history (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        control_id UUID NOT NULL REFERENCES discovered_controls(id) ON DELETE CASCADE,
        assessment_id UUID REFERENCES control_assessments(id) ON DELETE CASCADE,
        reviewer_id UUID REFERENCES users(id) ON DELETE SET NULL,
        action VARCHAR(50) NOT NULL,
        previous_status VARCHAR(50),
        new_status VARCHAR(50),
        changes JSONB NOT NULL DEFAULT '{}'::jsonb,
        reason TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_hist_control ON control_audit_history(control_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_hist_reviewer ON control_audit_history(reviewer_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ctrl_hist_created ON control_audit_history(created_at);")

    # 8. alter findings
    op.execute("ALTER TABLE findings ALTER COLUMN audit_run_id DROP NOT NULL;")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS audit_id UUID REFERENCES audits(id) ON DELETE CASCADE;")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS defence_analysis_run_id UUID REFERENCES defence_analysis_runs(id) ON DELETE SET NULL;")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS finding_category VARCHAR(50);")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS likelihood_score INTEGER;")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS impact_score INTEGER;")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS risk_score INTEGER;")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS is_provisional BOOLEAN NOT NULL DEFAULT false;")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(5, 2);")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS remediation_recommendation TEXT;")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS review_status VARCHAR(50) NOT NULL DEFAULT 'pending_review';")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS review_reason TEXT;")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL;")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITH TIME ZONE;")
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS finding_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;")

    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_ck_findings_severity;")
    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_severity;")
    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_category;")
    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_likelihood;")
    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_impact;")
    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_risk_score;")
    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_review_status;")

    op.execute("""
    ALTER TABLE findings ADD CONSTRAINT ck_findings_severity
    CHECK (severity IN ('low', 'medium', 'high', 'very_high', 'critical'));
    """)
    op.execute("""
    ALTER TABLE findings ADD CONSTRAINT ck_findings_category
    CHECK (finding_category IS NULL OR finding_category IN ('documentation_gap', 'implementation_evidence_gap', 'operational_evidence_gap', 'control_weakness', 'contradictory_evidence', 'coverage_gap'));
    """)
    op.execute("""
    ALTER TABLE findings ADD CONSTRAINT ck_findings_likelihood
    CHECK (likelihood_score IS NULL OR (likelihood_score >= 1 AND likelihood_score <= 5));
    """)
    op.execute("""
    ALTER TABLE findings ADD CONSTRAINT ck_findings_impact
    CHECK (impact_score IS NULL OR (impact_score >= 1 AND impact_score <= 5));
    """)
    op.execute("""
    ALTER TABLE findings ADD CONSTRAINT ck_findings_risk_score
    CHECK (risk_score IS NULL OR (risk_score >= 1 AND risk_score <= 25));
    """)
    op.execute("""
    ALTER TABLE findings ADD CONSTRAINT ck_findings_review_status
    CHECK (review_status IN ('pending_review', 'approved', 'rejected', 'edited', 'needs_more_information'));
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_findings_audit_id ON findings(audit_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_findings_defence_run ON findings(defence_analysis_run_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_findings_category ON findings(finding_category);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_findings_review_status ON findings(review_status);")

    # 9. finding_controls
    op.execute("""
    CREATE TABLE IF NOT EXISTS finding_controls (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        audit_id UUID NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
        finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
        control_id UUID NOT NULL REFERENCES discovered_controls(id) ON DELETE CASCADE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_find_ctrl_finding_control UNIQUE (finding_id, control_id)
    );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_find_ctrl_finding ON finding_controls(finding_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_find_ctrl_control ON finding_controls(control_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_find_ctrl_audit ON finding_controls(audit_id);")

    # 10. finding_audit_history
    op.execute("""
    CREATE TABLE IF NOT EXISTS finding_audit_history (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
        reviewer_id UUID REFERENCES users(id) ON DELETE SET NULL,
        action VARCHAR(50) NOT NULL,
        previous_status VARCHAR(50),
        new_status VARCHAR(50),
        changes JSONB NOT NULL DEFAULT '{}'::jsonb,
        reason TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_find_hist_finding ON finding_audit_history(finding_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_find_hist_reviewer ON finding_audit_history(reviewer_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_find_hist_created ON finding_audit_history(created_at);")


def downgrade() -> None:
    """Downgrade schema for Defence Auditor (Milestone 6)."""
    # 10. finding_audit_history
    op.execute("DROP TABLE IF EXISTS finding_audit_history CASCADE;")

    # 9. finding_controls
    op.execute("DROP TABLE IF EXISTS finding_controls CASCADE;")

    # 8. alter findings
    op.execute("DROP INDEX IF EXISTS ix_findings_review_status;")
    op.execute("DROP INDEX IF EXISTS ix_findings_category;")
    op.execute("DROP INDEX IF EXISTS ix_findings_defence_run;")
    op.execute("DROP INDEX IF EXISTS ix_findings_audit_id;")
    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_review_status;")
    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_risk_score;")
    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_impact;")
    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_likelihood;")
    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_category;")
    op.execute("ALTER TABLE findings DROP CONSTRAINT IF EXISTS ck_findings_severity;")
    op.execute("ALTER TABLE findings ADD CONSTRAINT ck_findings_severity CHECK (severity IN ('low', 'medium', 'high', 'critical'));")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS finding_metadata;")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS reviewed_at;")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS reviewed_by;")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS review_reason;")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS review_status;")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS remediation_recommendation;")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS confidence_score;")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS is_provisional;")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS risk_score;")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS impact_score;")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS likelihood_score;")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS finding_category;")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS defence_analysis_run_id;")
    op.execute("ALTER TABLE findings DROP COLUMN IF EXISTS audit_id;")
    op.execute("ALTER TABLE findings ALTER COLUMN audit_run_id SET NOT NULL;")

    # 7. control_audit_history
    op.execute("DROP TABLE IF EXISTS control_audit_history CASCADE;")

    # 6. control_evidence_references
    op.execute("DROP TABLE IF EXISTS control_evidence_references CASCADE;")

    # 5. control_threat_mappings
    op.execute("DROP TABLE IF EXISTS control_threat_mappings CASCADE;")

    # 4. control_requirement_mappings
    op.execute("DROP TABLE IF EXISTS control_requirement_mappings CASCADE;")

    # 3. alter control_assessments
    op.execute("DROP INDEX IF EXISTS ix_ctrl_assess_review_status;")
    op.execute("DROP INDEX IF EXISTS ix_ctrl_assess_defence_run;")
    op.execute("DROP INDEX IF EXISTS ix_ctrl_assess_control_id;")
    op.execute("DROP INDEX IF EXISTS ix_ctrl_assess_audit_id;")
    op.execute("ALTER TABLE control_assessments DROP CONSTRAINT IF EXISTS ck_ctrl_assess_review_status;")
    op.execute("ALTER TABLE control_assessments DROP CONSTRAINT IF EXISTS ck_ctrl_assess_maturity;")
    op.execute("ALTER TABLE control_assessments DROP CONSTRAINT IF EXISTS ck_ctrl_assess_status;")
    op.execute("""
    ALTER TABLE control_assessments ADD CONSTRAINT ck_ctrl_assess_status
    CHECK (status IN ('satisfied', 'partially_satisfied', 'not_satisfied', 'not_documented', 'not_applicable', 'needs_review'));
    """)
    op.execute("ALTER TABLE control_assessments DROP CONSTRAINT IF EXISTS fk_ctrl_assess_threat_id;")
    op.execute("ALTER TABLE control_assessments DROP CONSTRAINT IF EXISTS fk_ctrl_assess_req_id;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS assessment_metadata;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS reviewed_at;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS reviewed_by;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS review_reason;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS review_status;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS recommended_next_steps;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS contradictions;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS missing_information;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS evidence_limitations;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS evidence_maturity;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS assessment_explanation;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS defence_analysis_run_id;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS control_id;")
    op.execute("ALTER TABLE control_assessments DROP COLUMN IF EXISTS audit_id;")
    op.execute("ALTER TABLE control_assessments ALTER COLUMN rationale SET NOT NULL;")
    op.execute("ALTER TABLE control_assessments ALTER COLUMN requirement_id SET NOT NULL;")
    op.execute("ALTER TABLE control_assessments ALTER COLUMN audit_run_id SET NOT NULL;")

    # 2. discovered_controls
    op.execute("DROP TABLE IF EXISTS discovered_controls CASCADE;")

    # 1. defence_analysis_runs
    op.execute("DROP TABLE IF EXISTS defence_analysis_runs CASCADE;")
