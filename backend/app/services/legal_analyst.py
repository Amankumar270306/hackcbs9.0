"""Legal Analyst AI agent service.

Executes evidence-grounded compliance requirement extraction from regulatory
document chunks, enforces anti-hallucination constraints, creates requirement sources,
and maintains full extraction audit trails.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models.regulatory import (
    RegulatoryDocument,
    RegulatoryDocumentChunk,
    RegulatoryExtractionJob,
    RegulatoryFramework,
    RequirementAuditHistory,
    RequirementSource,
)
from app.database.models.assessments import Requirement
from app.services.ai.gemini_client import get_gemini_client
from app.services.ai.prompt_manager import (
    LEGAL_ANALYST_SYSTEM_PROMPT,
    build_chunk_extraction_prompt,
)
from app.services.ai.structured_output import (
    ExtractedRequirementItem,
    GeminiExtractionResponse,
)

logger = logging.getLogger(__name__)


class LegalAnalystService:
    """Legal Analyst orchestration service for regulatory compliance extraction."""

    @staticmethod
    def run_extraction_sync(
        session: Session,
        regulatory_document_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> RegulatoryExtractionJob:
        """Synchronously executes the Legal Analyst extraction pipeline for a regulatory document."""
        start_time = time.time()

        # 1. Fetch document and parent framework
        doc_stmt = (
            select(RegulatoryDocument)
            .where(RegulatoryDocument.id == regulatory_document_id)
        )
        document = session.execute(doc_stmt).scalar_one_or_none()
        if not document:
            raise ValueError(f"Regulatory document {regulatory_document_id} not found.")

        framework_stmt = (
            select(RegulatoryFramework)
            .where(RegulatoryFramework.id == document.framework_id)
        )
        framework = session.execute(framework_stmt).scalar_one_or_none()
        if not framework:
            raise ValueError(f"Regulatory framework {document.framework_id} not found.")

        # 2. Initialize extraction job record
        job = RegulatoryExtractionJob(
            regulatory_document_id=document.id,
            status="running",
            model_name=settings.GEMINI_MODEL,
            prompt_version="v1.0",
            chunks_total=0,
            chunks_processed=0,
            requirements_extracted=0,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        try:
            # 3. Retrieve chunks
            chunk_stmt = (
                select(RegulatoryDocumentChunk)
                .where(RegulatoryDocumentChunk.regulatory_document_id == document.id)
                .order_by(RegulatoryDocumentChunk.chunk_index.asc())
            )
            chunks: List[RegulatoryDocumentChunk] = list(session.execute(chunk_stmt).scalars().all())

            job.chunks_total = len(chunks)
            session.commit()

            if not chunks:
                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                job.execution_duration_ms = int((time.time() - start_time) * 1000)
                session.commit()
                return job

            client = get_gemini_client()
            total_extracted = 0
            seen_excerpts = set()

            # 4. Process each chunk
            for chunk in chunks:
                chunk_text = (chunk.content or "").strip()
                if not chunk_text:
                    job.chunks_processed += 1
                    session.commit()
                    continue

                prompt = build_chunk_extraction_prompt(
                    chunk_text=chunk_text,
                    framework_name=framework.name,
                    document_title=document.title,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                )

                try:
                    import asyncio
                    try:
                        raw_response = asyncio.run(
                            client.generate_structured(
                                prompt=prompt,
                                system_instruction=LEGAL_ANALYST_SYSTEM_PROMPT,
                            )
                        )
                    except RuntimeError:
                        loop = asyncio.get_event_loop()
                        raw_response = loop.run_until_complete(
                            client.generate_structured(
                                prompt=prompt,
                                system_instruction=LEGAL_ANALYST_SYSTEM_PROMPT,
                            )
                        )

                    parsed_response = GeminiExtractionResponse.model_validate(raw_response)
                except Exception as llm_err:
                    logger.warning(
                        f"Failed LLM extraction on chunk {chunk.chunk_index} for doc {document.id}: {str(llm_err)}"
                    )
                    job.chunks_processed += 1
                    session.commit()
                    continue

                # 5. Transform and persist extracted requirements
                for item in parsed_response.requirements:
                    excerpt_key = item.source_excerpt.strip().lower()
                    if excerpt_key in seen_excerpts:
                        continue  # Deduplicate exact duplicate excerpts across overlapping chunks
                    seen_excerpts.add(excerpt_key)

                    req_code = item.requirement_code.strip()
                    if not req_code:
                        req_code = f"REQ-{chunk.chunk_index:03d}-{len(seen_excerpts):02d}"

                    # Create canonical Requirement record
                    requirement = Requirement(
                        organization_id=document.organization_id,
                        audit_run_id=None,
                        framework_id=framework.id,
                        regulatory_document_id=document.id,
                        framework=framework.short_name,
                        framework_version=framework.version,
                        identifier=req_code,
                        requirement_code=req_code,
                        title=item.title.strip(),
                        description=item.requirement_statement.strip(),
                        requirement_statement=item.requirement_statement.strip(),
                        detailed_description=item.detailed_description or item.requirement_statement.strip(),
                        obligation_type=item.obligation_type,
                        category=item.category,
                        subcategory=item.subcategory,
                        applicability=item.applicability,
                        applicability_conditions=item.applicability_conditions,
                        jurisdiction=item.jurisdiction or framework.jurisdiction,
                        source_section=item.source_section or chunk.section_title,
                        source_page=item.source_page or chunk.page_number,
                        source_excerpt=item.source_excerpt.strip(),
                        source_chunk_id=chunk.id,
                        confidence_score=item.confidence_score,
                        extraction_status="completed",
                        review_status="pending_review",
                        extraction_metadata={
                            "extracted_by": "LegalAnalyst",
                            "model": job.model_name,
                            "chunk_index": chunk.chunk_index,
                            "prompt_version": job.prompt_version,
                        },
                    )
                    session.add(requirement)
                    session.flush()  # Obtain requirement.id

                    # Create primary RequirementSource
                    source = RequirementSource(
                        requirement_id=requirement.id,
                        regulatory_document_id=document.id,
                        document_chunk_id=chunk.id,
                        section_reference=item.source_section or chunk.section_title,
                        page_number=item.source_page or chunk.page_number,
                        exact_excerpt=item.source_excerpt.strip(),
                        source_type="primary_clause",
                    )
                    session.add(source)

                    # Create initial audit history entry
                    history = RequirementAuditHistory(
                        requirement_id=requirement.id,
                        reviewer_id=user_id,
                        action="created",
                        previous_status=None,
                        new_status="pending_review",
                        changes={
                            "event": "extracted_by_legal_analyst",
                            "chunk_index": chunk.chunk_index,
                            "confidence": item.confidence_score,
                        },
                        reason="Legal Analyst automated extraction from regulatory chunk.",
                    )
                    session.add(history)

                    total_extracted += 1

                job.chunks_processed += 1
                job.requirements_extracted = total_extracted
                session.commit()

            # 6. Finalize job success
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.execution_duration_ms = int((time.time() - start_time) * 1000)
            session.commit()
            return job

        except Exception as e:
            logger.error(f"Legal Analyst extraction failed on document {document.id}: {str(e)}", exc_info=True)
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            job.execution_duration_ms = int((time.time() - start_time) * 1000)
            session.commit()
            raise
