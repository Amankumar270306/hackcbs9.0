import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.findings import (
    Finding,
    EvidenceReference,
    FindingRequirement,
    FindingThreat,
)


class FindingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_finding(
        self,
        organization_id: uuid.UUID,
        audit_run_id: uuid.UUID,
        finding_code: str,
        title: str,
        description: str,
        severity: str,
        evidence_state: str,
        remediation_guidance: Optional[str] = None,
        cvss_score: Optional[float] = None,
    ) -> Finding:
        finding = Finding(
            organization_id=organization_id,
            audit_run_id=audit_run_id,
            finding_code=finding_code,
            title=title,
            description=description,
            severity=severity,
            evidence_state=evidence_state,
            remediation_guidance=remediation_guidance,
            cvss_score=cvss_score,
        )
        self.db.add(finding)
        self.db.flush()
        return finding

    def attach_evidence(
        self,
        organization_id: uuid.UUID,
        audit_run_id: uuid.UUID,
        finding_id: uuid.UUID,
        document_id: uuid.UUID,
        supporting_passage: str,
        evidence_type: str,
        page_number: Optional[int] = None,
        chunk_id: Optional[uuid.UUID] = None,
        start_char_offset: Optional[int] = None,
        end_char_offset: Optional[int] = None,
    ) -> EvidenceReference:
        ev = EvidenceReference(
            organization_id=organization_id,
            audit_run_id=audit_run_id,
            finding_id=finding_id,
            document_id=document_id,
            chunk_id=chunk_id,
            supporting_passage=supporting_passage,
            evidence_type=evidence_type,
            page_number=page_number,
            start_char_offset=start_char_offset,
            end_char_offset=end_char_offset,
        )
        self.db.add(ev)
        self.db.flush()
        return ev

    def link_requirement(
        self,
        organization_id: uuid.UUID,
        audit_run_id: uuid.UUID,
        finding_id: uuid.UUID,
        requirement_id: uuid.UUID,
    ) -> FindingRequirement:
        fr = FindingRequirement(
            organization_id=organization_id,
            audit_run_id=audit_run_id,
            finding_id=finding_id,
            requirement_id=requirement_id,
        )
        self.db.add(fr)
        self.db.flush()
        return fr

    def link_threat(
        self,
        organization_id: uuid.UUID,
        audit_run_id: uuid.UUID,
        finding_id: uuid.UUID,
        threat_id: uuid.UUID,
    ) -> FindingThreat:
        ft = FindingThreat(
            organization_id=organization_id,
            audit_run_id=audit_run_id,
            finding_id=finding_id,
            threat_id=threat_id,
        )
        self.db.add(ft)
        self.db.flush()
        return ft

