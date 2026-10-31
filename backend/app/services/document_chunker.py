"""Document chunker service for Compliance Sentinel.

Implements deterministic, page-aware, and section-aware chunking with
full source traceability back to original document, page range, section titles,
character offsets, and sequential indexes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional

from app.services.docx_extractor import DocxExtractionResult
from app.services.pdf_extractor import PDFExtractionResult


@dataclass
class ChunkData:
    chunk_index: int
    content: str
    page_number: Optional[int]
    page_start: Optional[int]
    page_end: Optional[int]
    section_title: Optional[str]
    token_count: int
    character_count: int
    start_char_offset: int
    end_char_offset: int
    chunk_metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentChunker:
    # Target chunk size: 800-1200 tokens (~3200-4800 chars)
    TARGET_CHUNK_TOKENS: int = 1000
    MAX_CHUNK_TOKENS: int = 1200
    MIN_CHUNK_TOKENS: int = 800
    OVERLAP_TOKENS: int = 125  # 100-150 tokens (~500 chars)

    # Documented approximation: 1 token ~= 4 characters / 0.75 words
    CHARS_PER_TOKEN: float = 4.0

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """Lightweight, deterministic token estimator based on whitespace and character heuristics."""
        if not text:
            return 0
        words = len(text.split())
        chars = len(text)
        # Combine word count and character count for robust estimation across code, numbers, and prose
        token_by_words = int(words * 1.33)
        token_by_chars = int(chars / cls.CHARS_PER_TOKEN)
        return max(1, (token_by_words + token_by_chars) // 2)

    @classmethod
    def _split_text_into_paragraphs(cls, text: str) -> List[str]:
        """Split text by double line breaks or single line breaks while preserving sentences."""
        paragraphs = re.split(r'\n{2,}', text)
        result: List[str] = []
        for p in paragraphs:
            stripped = p.strip()
            if stripped:
                result.append(stripped)
        return result

    @classmethod
    def chunk_pdf(cls, extraction: PDFExtractionResult) -> List[ChunkData]:
        """Chunk PDF content while preserving exact page boundaries and page ranges."""
        if not extraction.pages:
            if extraction.text.strip():
                return cls.chunk_plain_text(extraction.text, default_section="Document Content")
            return []

        chunks: List[ChunkData] = []
        current_chunk_paragraphs: List[str] = []
        current_pages: List[int] = []
        current_char_start: int = 0
        current_tokens: int = 0
        running_char_offset: int = 0
        chunk_idx = 0

        target_char_limit = int(cls.TARGET_CHUNK_TOKENS * cls.CHARS_PER_TOKEN)
        overlap_char_limit = int(cls.OVERLAP_TOKENS * cls.CHARS_PER_TOKEN)

        for page in extraction.pages:
            page_text = page.text.strip()
            if not page_text:
                continue

            paragraphs = cls._split_text_into_paragraphs(page_text)
            for p in paragraphs:
                p_tokens = cls.estimate_tokens(p)
                p_chars = len(p)

                # If single paragraph is larger than max chunk, split it by sentences or characters
                if p_tokens > cls.MAX_CHUNK_TOKENS:
                    # Flush existing buffer first
                    if current_chunk_paragraphs:
                        chunk_content = "\n\n".join(current_chunk_paragraphs)
                        p_min = min(current_pages) if current_pages else page.page_number
                        p_max = max(current_pages) if current_pages else page.page_number
                        chunks.append(
                            ChunkData(
                                chunk_index=chunk_idx,
                                content=chunk_content,
                                page_number=p_min if p_min == p_max else None,
                                page_start=p_min,
                                page_end=p_max,
                                section_title=f"Page {p_min}" if p_min == p_max else f"Pages {p_min}-{p_max}",
                                token_count=cls.estimate_tokens(chunk_content),
                                character_count=len(chunk_content),
                                start_char_offset=current_char_start,
                                end_char_offset=current_char_start + len(chunk_content),
                                chunk_metadata={"page_count": len(set(current_pages))},
                            )
                        )
                        chunk_idx += 1
                        current_chunk_paragraphs = []
                        current_pages = []
                        current_tokens = 0

                    # Sub-split oversized paragraph
                    sentences = re.split(r'(?<=[.?!])\s+', p)
                    sub_buf: List[str] = []
                    sub_tokens = 0
                    sub_start = running_char_offset

                    for s in sentences:
                        s_tokens = cls.estimate_tokens(s)
                        if sub_tokens + s_tokens > cls.TARGET_CHUNK_TOKENS and sub_buf:
                            sub_content = " ".join(sub_buf)
                            chunks.append(
                                ChunkData(
                                    chunk_index=chunk_idx,
                                    content=sub_content,
                                    page_number=page.page_number,
                                    page_start=page.page_number,
                                    page_end=page.page_number,
                                    section_title=f"Page {page.page_number}",
                                    token_count=cls.estimate_tokens(sub_content),
                                    character_count=len(sub_content),
                                    start_char_offset=sub_start,
                                    end_char_offset=sub_start + len(sub_content),
                                    chunk_metadata={"page_count": 1, "sub_split": True},
                                )
                            )
                            chunk_idx += 1
                            # Keep overlap
                            overlap_str = sub_content[-overlap_char_limit:]
                            sub_buf = [overlap_str, s]
                            sub_tokens = cls.estimate_tokens(overlap_str) + s_tokens
                            sub_start += len(sub_content) - len(overlap_str)
                        else:
                            sub_buf.append(s)
                            sub_tokens += s_tokens

                    if sub_buf:
                        sub_content = " ".join(sub_buf)
                        chunks.append(
                            ChunkData(
                                chunk_index=chunk_idx,
                                content=sub_content,
                                page_number=page.page_number,
                                page_start=page.page_number,
                                page_end=page.page_number,
                                section_title=f"Page {page.page_number}",
                                token_count=cls.estimate_tokens(sub_content),
                                character_count=len(sub_content),
                                start_char_offset=sub_start,
                                end_char_offset=sub_start + len(sub_content),
                                chunk_metadata={"page_count": 1},
                            )
                        )
                        chunk_idx += 1

                    running_char_offset += p_chars + 2
                    current_char_start = running_char_offset
                    continue

                # Normal paragraph: check if adding it exceeds TARGET_CHUNK_TOKENS
                if (current_tokens + p_tokens > cls.TARGET_CHUNK_TOKENS and current_chunk_paragraphs) or (
                    current_pages and page.page_number not in current_pages and current_tokens >= cls.MIN_CHUNK_TOKENS
                ):
                    chunk_content = "\n\n".join(current_chunk_paragraphs)
                    p_min = min(current_pages)
                    p_max = max(current_pages)
                    chunks.append(
                        ChunkData(
                            chunk_index=chunk_idx,
                            content=chunk_content,
                            page_number=p_min if p_min == p_max else None,
                            page_start=p_min,
                            page_end=p_max,
                            section_title=f"Page {p_min}" if p_min == p_max else f"Pages {p_min}-{p_max}",
                            token_count=cls.estimate_tokens(chunk_content),
                            character_count=len(chunk_content),
                            start_char_offset=current_char_start,
                            end_char_offset=current_char_start + len(chunk_content),
                            chunk_metadata={"page_count": len(set(current_pages))},
                        )
                    )
                    chunk_idx += 1

                    # Retain overlap from end of current chunk
                    overlap_p = current_chunk_paragraphs[-1] if current_chunk_paragraphs else ""
                    if len(overlap_p) > overlap_char_limit:
                        overlap_p = overlap_p[-overlap_char_limit:]

                    current_chunk_paragraphs = [overlap_p, p] if overlap_p else [p]
                    current_pages = [current_pages[-1], page.page_number] if overlap_p else [page.page_number]
                    current_tokens = cls.estimate_tokens("\n\n".join(current_chunk_paragraphs))
                    current_char_start = running_char_offset
                else:
                    if not current_chunk_paragraphs:
                        current_char_start = running_char_offset
                    current_chunk_paragraphs.append(p)
                    current_pages.append(page.page_number)
                    current_tokens += p_tokens

                running_char_offset += p_chars + 2

        # Final trailing chunk
        if current_chunk_paragraphs:
            chunk_content = "\n\n".join(current_chunk_paragraphs)
            p_min = min(current_pages) if current_pages else 1
            p_max = max(current_pages) if current_pages else 1
            chunks.append(
                ChunkData(
                    chunk_index=chunk_idx,
                    content=chunk_content,
                    page_number=p_min if p_min == p_max else None,
                    page_start=p_min,
                    page_end=p_max,
                    section_title=f"Page {p_min}" if p_min == p_max else f"Pages {p_min}-{p_max}",
                    token_count=cls.estimate_tokens(chunk_content),
                    character_count=len(chunk_content),
                    start_char_offset=current_char_start,
                    end_char_offset=current_char_start + len(chunk_content),
                    chunk_metadata={"page_count": len(set(current_pages))},
                )
            )

        return chunks

    @classmethod
    def chunk_docx(cls, extraction: DocxExtractionResult) -> List[ChunkData]:
        """Chunk DOCX blocks respecting heading hierarchies and structured tables."""
        if not extraction.blocks:
            if extraction.text.strip():
                return cls.chunk_plain_text(extraction.text, default_section="Document Content")
            return []

        chunks: List[ChunkData] = []
        current_block_texts: List[str] = []
        current_section = extraction.blocks[0].section_title or "General"
        current_tokens = 0
        current_char_start = 0
        chunk_idx = 0
        overlap_char_limit = int(cls.OVERLAP_TOKENS * cls.CHARS_PER_TOKEN)

        for block in extraction.blocks:
            block_tokens = cls.estimate_tokens(block.content)
            is_new_major_section = block.block_type == "heading" and block.heading_level == 1

            # When starting a new major section, if we have enough tokens, flush previous chunk
            should_flush = (
                (current_tokens + block_tokens > cls.TARGET_CHUNK_TOKENS and current_block_texts)
                or (is_new_major_section and current_tokens >= cls.MIN_CHUNK_TOKENS)
            )

            if should_flush:
                chunk_content = "\n\n".join(current_block_texts).strip()
                if chunk_content:
                    chunks.append(
                        ChunkData(
                            chunk_index=chunk_idx,
                            content=chunk_content,
                            page_number=None,  # Not available in DOCX
                            page_start=None,
                            page_end=None,
                            section_title=current_section,
                            token_count=cls.estimate_tokens(chunk_content),
                            character_count=len(chunk_content),
                            start_char_offset=current_char_start,
                            end_char_offset=current_char_start + len(chunk_content),
                            chunk_metadata={"section": current_section, "format": "docx"},
                        )
                    )
                    chunk_idx += 1

                # Retain overlap if staying in same general area
                last_text = current_block_texts[-1] if current_block_texts else ""
                overlap_text = last_text[-overlap_char_limit:] if len(last_text) > overlap_char_limit else ""
                current_block_texts = [overlap_text, block.content] if (overlap_text and not is_new_major_section) else [block.content]
                current_tokens = cls.estimate_tokens("\n\n".join(current_block_texts))
                current_char_start = block.char_start
                current_section = block.section_title or current_section
            else:
                if not current_block_texts:
                    current_char_start = block.char_start
                current_block_texts.append(block.content)
                current_tokens += block_tokens
                if block.section_title:
                    current_section = block.section_title

        # Final chunk
        if current_block_texts:
            chunk_content = "\n\n".join(current_block_texts).strip()
            if chunk_content:
                chunks.append(
                    ChunkData(
                        chunk_index=chunk_idx,
                        content=chunk_content,
                        page_number=None,
                        page_start=None,
                        page_end=None,
                        section_title=current_section,
                        token_count=cls.estimate_tokens(chunk_content),
                        character_count=len(chunk_content),
                        start_char_offset=current_char_start,
                        end_char_offset=current_char_start + len(chunk_content),
                        chunk_metadata={"section": current_section, "format": "docx"},
                    )
                )

        return chunks

    @classmethod
    def chunk_plain_text(
        cls,
        text: str,
        default_section: Optional[str] = "Document Content",
        page_number: Optional[int] = None,
    ) -> List[ChunkData]:
        """Fallback chunker for plain text with deterministic boundaries."""
        stripped = text.strip()
        if not stripped:
            return []

        paragraphs = cls._split_text_into_paragraphs(stripped)
        chunks: List[ChunkData] = []
        buf: List[str] = []
        tokens = 0
        char_start = 0
        chunk_idx = 0
        overlap_chars = int(cls.OVERLAP_TOKENS * cls.CHARS_PER_TOKEN)

        for p in paragraphs:
            p_tokens = cls.estimate_tokens(p)
            if tokens + p_tokens > cls.TARGET_CHUNK_TOKENS and buf:
                content = "\n\n".join(buf)
                chunks.append(
                    ChunkData(
                        chunk_index=chunk_idx,
                        content=content,
                        page_number=page_number,
                        page_start=page_number,
                        page_end=page_number,
                        section_title=default_section,
                        token_count=cls.estimate_tokens(content),
                        character_count=len(content),
                        start_char_offset=char_start,
                        end_char_offset=char_start + len(content),
                        chunk_metadata={},
                    )
                )
                chunk_idx += 1
                overlap_text = content[-overlap_chars:] if len(content) > overlap_chars else ""
                buf = [overlap_text, p] if overlap_text else [p]
                tokens = cls.estimate_tokens("\n\n".join(buf))
                char_start += len(content) - len(overlap_text)
            else:
                buf.append(p)
                tokens += p_tokens

        if buf:
            content = "\n\n".join(buf)
            chunks.append(
                ChunkData(
                    chunk_index=chunk_idx,
                    content=content,
                    page_number=page_number,
                    page_start=page_number,
                    page_end=page_number,
                    section_title=default_section,
                    token_count=cls.estimate_tokens(content),
                    character_count=len(content),
                    start_char_offset=char_start,
                    end_char_offset=char_start + len(content),
                    chunk_metadata={},
                )
            )

        return chunks


document_chunker = DocumentChunker()

