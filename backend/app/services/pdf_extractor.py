"""PDF extraction service using PyMuPDF (pymupdf).

Extracts page-level text, preserves page numbers, captures document metadata,
and identifies scanned or image-only PDFs requiring manual review or OCR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import pymupdf


class DocumentExtractionError(Exception):
    """Raised when document extraction fails due to formatting, encryption, or corruption."""
    pass


@dataclass
class PageText:
    page_number: int  # 1-indexed
    text: str
    char_start: int
    char_end: int
    has_text: bool


@dataclass
class PDFExtractionResult:
    text: str
    page_count: int
    pages: List[PageText]
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_scanned: bool = False
    requires_ocr: bool = False


class PDFExtractor:
    @staticmethod
    def extract_from_file(file_path: Union[str, Path]) -> PDFExtractionResult:
        """Extract text, page structure, and metadata from a PDF file."""
        path_str = str(file_path)
        try:
            doc = pymupdf.open(path_str)
        except Exception as exc:
            raise DocumentExtractionError(f"Failed to open PDF document: {exc}") from exc

        try:
            if doc.is_encrypted:
                # Attempt to authenticate with empty password
                if not doc.authenticate(""):
                    raise DocumentExtractionError(
                        "Document is password protected or encrypted and cannot be processed without credentials."
                    )

            page_count = len(doc)
            if page_count == 0:
                return PDFExtractionResult(
                    text="",
                    page_count=0,
                    pages=[],
                    metadata={"error": "Document contains 0 pages"},
                    is_scanned=False,
                    requires_ocr=False,
                )

            # Metadata extraction
            raw_meta = doc.metadata or {}
            metadata: Dict[str, Any] = {
                "format": raw_meta.get("format", "PDF"),
                "title": raw_meta.get("title") or None,
                "author": raw_meta.get("author") or None,
                "subject": raw_meta.get("subject") or None,
                "creator": raw_meta.get("creator") or None,
                "producer": raw_meta.get("producer") or None,
                "creation_date": raw_meta.get("creationDate") or None,
                "mod_date": raw_meta.get("modDate") or None,
                "page_count": page_count,
            }

            pages: List[PageText] = []
            full_text_parts: List[str] = []
            running_char_offset = 0
            pages_with_text = 0

            for page_idx in range(page_count):
                page_num = page_idx + 1
                try:
                    page = doc[page_idx]
                    page_text = page.get_text("text").strip()
                except Exception as page_exc:
                    page_text = f"[Page {page_num} extraction failed: {page_exc}]"

                has_text = bool(page_text and len(page_text) > 5)
                if has_text:
                    pages_with_text += 1

                char_start = running_char_offset
                char_end = char_start + len(page_text)

                pages.append(
                    PageText(
                        page_number=page_num,
                        text=page_text,
                        char_start=char_start,
                        char_end=char_end,
                        has_text=has_text,
                    )
                )

                if page_text:
                    full_text_parts.append(page_text)
                    running_char_offset = char_end + 2  # account for page separator "\n\n"

            combined_text = "\n\n".join(full_text_parts)

            # Determine whether the PDF is image-only or scanned
            # If there are pages but virtually no extractable text, mark as scanned
            is_scanned = (page_count > 0 and pages_with_text == 0) or (
                page_count > 2 and (pages_with_text / page_count) < 0.2
            )
            requires_ocr = is_scanned

            metadata["is_scanned_or_image_only"] = is_scanned
            metadata["requires_ocr"] = requires_ocr
            metadata["extracted_pages_with_text"] = pages_with_text
            metadata["extracted_character_count"] = len(combined_text)

            return PDFExtractionResult(
                text=combined_text,
                page_count=page_count,
                pages=pages,
                metadata=metadata,
                is_scanned=is_scanned,
                requires_ocr=requires_ocr,
            )

        except DocumentExtractionError:
            raise
        except Exception as exc:
            raise DocumentExtractionError(f"Unexpected error while extracting PDF: {exc}") from exc
        finally:
            doc.close()


pdf_extractor = PDFExtractor()

