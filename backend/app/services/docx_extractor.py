"""DOCX extraction service using python-docx.

Extracts paragraphs, heading hierarchies, section structures, and tables in
a structured markdown format. Page numbers are left as None since DOCX format
does not possess static physical page layout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.services.pdf_extractor import DocumentExtractionError


@dataclass
class DocxBlock:
    block_type: str  # 'heading', 'paragraph', 'table'
    heading_level: Optional[int]
    section_title: Optional[str]
    content: str
    char_start: int
    char_end: int


@dataclass
class DocxExtractionResult:
    text: str
    blocks: List[DocxBlock]
    headings: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    table_count: int = 0
    paragraph_count: int = 0


class DocxExtractor:
    @staticmethod
    def _format_table(table: Table) -> str:
        """Render a Word table into a readable markdown table representation."""
        rows_data: List[List[str]] = []
        for row in table.rows:
            row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            rows_data.append(row_cells)

        if not rows_data:
            return ""

        # Normalize column count across rows
        col_count = max(len(r) for r in rows_data)
        for r in rows_data:
            while len(r) < col_count:
                r.append("")

        lines: List[str] = []
        header = rows_data[0]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * col_count) + " |")

        for r in rows_data[1:]:
            lines.append("| " + " | ".join(r) + " |")

        return "\n".join(lines)

    @classmethod
    def extract_from_file(cls, file_path: Union[str, Path]) -> DocxExtractionResult:
        """Extract text, heading hierarchy, and structured tables from a DOCX file."""
        path_str = str(file_path)
        try:
            doc = docx.Document(path_str)
        except Exception as exc:
            raise DocumentExtractionError(f"Failed to open DOCX document: {exc}") from exc

        try:
            blocks: List[DocxBlock] = []
            headings: List[str] = []
            full_text_parts: List[str] = []
            running_char_offset = 0

            current_section = "Introduction / Overview"
            table_count = 0
            paragraph_count = 0

            # Iterate through body elements in document order (paragraphs and tables)
            for element in doc.element.body:
                tag = element.tag
                if tag.endswith("p"):  # Paragraph or Heading
                    p = Paragraph(element, doc)
                    text = p.text.strip()
                    if not text:
                        continue

                    style_name = p.style.name if p.style else ""
                    is_heading = "Heading" in style_name or style_name in ["Title", "Subtitle"]
                    heading_level = None

                    if is_heading:
                        if "Heading 1" in style_name:
                            heading_level = 1
                        elif "Heading 2" in style_name:
                            heading_level = 2
                        elif "Heading 3" in style_name:
                            heading_level = 3
                        else:
                            heading_level = 1
                        current_section = text
                        headings.append(text)
                        formatted_content = f"\n### {text}\n"
                    else:
                        paragraph_count += 1
                        formatted_content = text

                    char_start = running_char_offset
                    char_end = char_start + len(formatted_content)

                    blocks.append(
                        DocxBlock(
                            block_type="heading" if is_heading else "paragraph",
                            heading_level=heading_level,
                            section_title=current_section,
                            content=formatted_content,
                            char_start=char_start,
                            char_end=char_end,
                        )
                    )
                    full_text_parts.append(formatted_content)
                    running_char_offset = char_end + 1

                elif tag.endswith("tbl"):  # Table
                    t = Table(element, doc)
                    table_str = cls._format_table(t)
                    if not table_str:
                        continue

                    table_count += 1
                    formatted_content = f"\n[TABLE]\n{table_str}\n[/TABLE]\n"
                    char_start = running_char_offset
                    char_end = char_start + len(formatted_content)

                    blocks.append(
                        DocxBlock(
                            block_type="table",
                            heading_level=None,
                            section_title=current_section,
                            content=formatted_content,
                            char_start=char_start,
                            char_end=char_end,
                        )
                    )
                    full_text_parts.append(formatted_content)
                    running_char_offset = char_end + 1

            combined_text = "\n\n".join(full_text_parts)

            # Metadata extraction from core properties
            metadata: Dict[str, Any] = {
                "format": "DOCX",
                "paragraph_count": paragraph_count,
                "table_count": table_count,
                "heading_count": len(headings),
                "headings": headings[:20],
                "extracted_character_count": len(combined_text),
            }

            try:
                core_props = doc.core_properties
                if core_props:
                    metadata["title"] = core_props.title or None
                    metadata["author"] = core_props.author or None
                    metadata["subject"] = core_props.subject or None
                    metadata["created"] = str(core_props.created) if core_props.created else None
                    metadata["modified"] = str(core_props.modified) if core_props.modified else None
            except Exception:
                pass

            return DocxExtractionResult(
                text=combined_text,
                blocks=blocks,
                headings=headings,
                metadata=metadata,
                table_count=table_count,
                paragraph_count=paragraph_count,
            )

        except DocumentExtractionError:
            raise
        except Exception as exc:
            raise DocumentExtractionError(f"Unexpected error while extracting DOCX: {exc}") from exc


docx_extractor = DocxExtractor()

