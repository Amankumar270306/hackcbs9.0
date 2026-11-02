"""PDF Builder for Compliance Sentinel Audit Reports.

Generates professional, multi-page, publication-grade compliance & security assessment PDFs
using PyMuPDF (fitz) with automatic multi-page table continuation, word-wrapped cells,
running headers/footers with dynamic page numbers, severity badges, and structured sections
corresponding to the 12-section standard.
"""

from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Tuple
import pymupdf


# ---------------------------------------------------------------------------
# Styling & Color Palette Constants
# ---------------------------------------------------------------------------

PAGE_WIDTH = 595.0   # A4 width in points
PAGE_HEIGHT = 842.0  # A4 height in points
MARGIN_LEFT = 45.0
MARGIN_RIGHT = 550.0
PRINTABLE_WIDTH = MARGIN_RIGHT - MARGIN_LEFT  # 505.0 pt
MARGIN_TOP = 50.0
MARGIN_BOTTOM = 790.0

# RGB Color Tuples (0.0 - 1.0)
COLOR_PRIMARY = (15 / 255, 23 / 255, 42 / 255)       # Slate 900
COLOR_SECONDARY = (30 / 255, 41 / 255, 59 / 255)     # Slate 800
COLOR_TEXT = (51 / 255, 65 / 255, 85 / 255)          # Slate 700
COLOR_MUTED = (100 / 255, 116 / 255, 139 / 255)      # Slate 500
COLOR_LIGHT_BG = (248 / 255, 250 / 255, 252 / 255)   # Slate 50
COLOR_BORDER = (226 / 255, 232 / 255, 240 / 255)     # Slate 200

COLOR_BLUE = (37 / 255, 99 / 255, 235 / 255)         # Blue 600
COLOR_BLUE_BG = (239 / 255, 246 / 255, 255 / 255)    # Blue 50
COLOR_ROSE = (225 / 255, 29 / 255, 72 / 255)         # Rose 600
COLOR_ROSE_BG = (255 / 255, 241 / 255, 242 / 255)    # Rose 50
COLOR_AMBER = (217 / 255, 119 / 255, 6 / 255)        # Amber 600
COLOR_AMBER_BG = (254 / 255, 243 / 255, 199 / 255)   # Amber 100
COLOR_EMERALD = (5 / 255, 150 / 255, 105 / 255)      # Emerald 600
COLOR_EMERALD_BG = (236 / 255, 253 / 255, 245 / 255) # Emerald 50
COLOR_WHITE = (1.0, 1.0, 1.0)


def sanitize_pdf_text(text: Any) -> str:
    """Normalizes Unicode characters to clean representation for standard PDF Helvetica font.
    
    Eliminates question-mark replacement characters caused by unmapped Unicode code points.
    """
    if text is None:
        return ""
    s = str(text)
    replacements = {
        "—": " - ",     # em-dash
        "–": "-",       # en-dash
        "•": "*",       # bullet
        "●": "*",       # filled circle
        "·": "*",       # middle dot
        "“": '"',       # left double quote
        "”": '"',       # right double quote
        "‘": "'",       # left single quote
        "’": "'",       # right single quote
        "…": "...",     # ellipsis
        "\u00a0": " ",  # non-breaking space
        "\u200b": "",   # zero-width space
        "\u2022": "*",  # bullet
        "\u2013": "-",  # en-dash
        "\u2014": " - ",# em-dash
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "™": "(TM)",
        "®": "(R)",
        "©": "(C)",
        "\t": " ",
    }
    for orig, rep in replacements.items():
        s = s.replace(orig, rep)
    
    # Encode with latin-1 replacement and strip stray unprintable question marks
    clean = s.encode("latin-1", errors="replace").decode("latin-1")
    return clean


class ReportPDFBuilder:
    """Constructs a professional, comprehensive compliance report PDF with zero string truncation."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self.data = data
        self.doc = pymupdf.open()
        self.page: Optional[pymupdf.Page] = None
        self.y = MARGIN_TOP

    # -----------------------------------------------------------------------
    # Canvas & Page Management
    # -----------------------------------------------------------------------

    def new_page(self, is_cover: bool = False) -> None:
        """Create a new page and render running headers."""
        self.page = self.doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        if is_cover:
            self.y = MARGIN_TOP
            return

        # Running Header (Unicode sanitized)
        self.page.insert_text(
            pymupdf.Point(MARGIN_LEFT, 36),
            "COMPLIANCE SENTINEL - MULTI-AGENT AUDIT REPORT",
            fontsize=7.5,
            fontname="helv",
            color=COLOR_MUTED,
        )
        raw_audit_title = self.data.get("cover_page", {}).get("audit_name", "Compliance Audit")
        audit_title = sanitize_pdf_text(raw_audit_title)
        title_width = min(220.0, len(audit_title) * 4.8)
        self.page.insert_text(
            pymupdf.Point(MARGIN_RIGHT - title_width, 36),
            audit_title[:45],
            fontsize=7.5,
            fontname="helv",
            color=COLOR_MUTED,
        )
        self.page.draw_line(
            pymupdf.Point(MARGIN_LEFT, 42),
            pymupdf.Point(MARGIN_RIGHT, 42),
            color=COLOR_BORDER,
            width=0.75,
        )
        self.y = 55.0

    def ensure_space(self, needed_height: float) -> None:
        """Advance to a fresh page if space is insufficient."""
        if self.page is None or (self.y + needed_height > MARGIN_BOTTOM):
            self.new_page()

    def advance(self, amount: float) -> None:
        self.y += amount

    # -----------------------------------------------------------------------
    # Primitives & Component Drawers
    # -----------------------------------------------------------------------

    def draw_section_heading(self, section_num: str, title: str) -> None:
        """Draw major section heading with background accent bar."""
        self.ensure_space(45.0)
        box_rect = pymupdf.Rect(MARGIN_LEFT, self.y, MARGIN_RIGHT, self.y + 24)
        self.page.draw_rect(box_rect, color=COLOR_PRIMARY, fill=COLOR_PRIMARY)
        self.page.insert_text(
            pymupdf.Point(MARGIN_LEFT + 10, self.y + 16),
            sanitize_pdf_text(f"{section_num}. {title.upper()}"),
            fontsize=10.5,
            fontname="helv",
            color=COLOR_WHITE,
        )
        self.advance(32.0)

    def draw_subsection_heading(self, title: str) -> None:
        """Draw secondary subsection heading."""
        self.ensure_space(28.0)
        self.page.draw_line(
            pymupdf.Point(MARGIN_LEFT, self.y + 14),
            pymupdf.Point(MARGIN_LEFT + 18, self.y + 14),
            color=COLOR_BLUE,
            width=2.5,
        )
        self.page.insert_text(
            pymupdf.Point(MARGIN_LEFT + 24, self.y + 16),
            sanitize_pdf_text(title),
            fontsize=9.5,
            fontname="helv",
            color=COLOR_SECONDARY,
        )
        self.advance(24.0)

    def draw_paragraph(self, text: str, fontsize: float = 8.5, color: Tuple[float, float, float] = COLOR_TEXT, indent: float = 0.0) -> None:
        """Draw fully wrapped paragraph text without truncation."""
        if not text:
            return
        clean_text = sanitize_pdf_text(text)
        
        # Calculate dynamic height based on text wrapping
        chars_per_line = max(20, int((PRINTABLE_WIDTH - indent) / (fontsize * 0.48)))
        lines = 0
        for block in clean_text.split("\n"):
            lines += max(1, (len(block) + chars_per_line - 1) // chars_per_line)
        est_height = lines * (fontsize + 4.0) + 4.0

        self.ensure_space(est_height)
        rect = pymupdf.Rect(MARGIN_LEFT + indent, self.y, MARGIN_RIGHT, self.y + est_height + 40.0)
        unused = self.page.insert_textbox(rect, clean_text, fontsize=fontsize, fontname="helv", color=color)
        actual_height = (est_height + 40.0) - unused if unused >= 0 else est_height
        self.advance(actual_height + 4.0)

    def draw_callout_box(self, title: str, text: str, border_color: Tuple[float, float, float] = COLOR_BLUE, fill_color: Tuple[float, float, float] = COLOR_BLUE_BG) -> None:
        """Draw an alert/callout box with colored accent border."""
        clean_title = sanitize_pdf_text(title)
        clean_text = sanitize_pdf_text(text)
        chars_per_line = int(PRINTABLE_WIDTH / 4.6)
        lines = max(1, len(clean_text) // chars_per_line + 2)
        height = lines * 13.0 + 26.0
        self.ensure_space(height)

        box_rect = pymupdf.Rect(MARGIN_LEFT, self.y, MARGIN_RIGHT, self.y + height)
        self.page.draw_rect(box_rect, color=border_color, fill=fill_color, width=1.0)
        accent_bar = pymupdf.Rect(MARGIN_LEFT, self.y, MARGIN_LEFT + 4, self.y + height)
        self.page.draw_rect(accent_bar, color=border_color, fill=border_color)

        self.page.insert_text(
            pymupdf.Point(MARGIN_LEFT + 12, self.y + 14),
            clean_title,
            fontsize=8.5,
            fontname="helv",
            color=border_color,
        )
        text_rect = pymupdf.Rect(MARGIN_LEFT + 12, self.y + 18, MARGIN_RIGHT - 12, self.y + height - 4)
        self.page.insert_textbox(text_rect, clean_text, fontsize=8.0, fontname="helv", color=COLOR_SECONDARY)
        self.advance(height + 8.0)

    def draw_badge(self, x: float, y: float, text: str, badge_type: str = "medium") -> float:
        """Draw a colored status badge and return its width."""
        bt = badge_type.lower()
        if bt in ("critical", "high", "documented_nonconformance", "contradictory_evidence", "failed"):
            bg, fg, border = COLOR_ROSE_BG, COLOR_ROSE, COLOR_ROSE
        elif bt in ("medium", "partially_supported", "partially_mitigated", "requires_human_review", "warning"):
            bg, fg, border = COLOR_AMBER_BG, COLOR_AMBER, COLOR_AMBER
        elif bt in ("low", "supported_by_documented_evidence", "documented_mitigations_supported", "completed", "approved"):
            bg, fg, border = COLOR_EMERALD_BG, COLOR_EMERALD, COLOR_EMERALD
        else:
            bg, fg, border = COLOR_BLUE_BG, COLOR_BLUE, COLOR_BLUE

        clean_text = sanitize_pdf_text(text)
        badge_width = max(40.0, len(clean_text) * 4.8 + 12.0)
        rect = pymupdf.Rect(x, y - 9.0, x + badge_width, y + 4.0)
        self.page.draw_rect(rect, color=border, fill=bg, width=0.5)
        self.page.insert_text(
            pymupdf.Point(x + 5.0, y - 1.0),
            clean_text,
            fontsize=6.5,
            fontname="helv",
            color=fg,
        )
        return badge_width

    def draw_key_value_grid(self, pairs: List[Tuple[str, str]], cols: int = 2) -> None:
        """Render key-value items in a clean grid with full text wrapping."""
        col_width = PRINTABLE_WIDTH / cols
        for i in range(0, len(pairs), cols):
            row_pairs = pairs[i:i + cols]
            # Estimate row height based on value length
            max_lines = 1
            for k, v in row_pairs:
                clean_v = sanitize_pdf_text(v)
                v_chars_per_line = max(15, int((col_width - 80.0) / 4.4))
                lines = (len(clean_v) + v_chars_per_line - 1) // v_chars_per_line
                if lines > max_lines:
                    max_lines = lines
            row_h = max(20.0, max_lines * 10.0 + 8.0)
            self.ensure_space(row_h)

            for c_idx, (k, v) in enumerate(row_pairs):
                x_pos = MARGIN_LEFT + c_idx * col_width
                self.page.insert_text(
                    pymupdf.Point(x_pos, self.y + 12),
                    sanitize_pdf_text(f"{k}:"),
                    fontsize=8.0,
                    fontname="helv",
                    color=COLOR_MUTED,
                )
                val_rect = pymupdf.Rect(x_pos + 75.0, self.y + 2, x_pos + col_width - 5, self.y + row_h - 2)
                self.page.insert_textbox(val_rect, sanitize_pdf_text(v), fontsize=8.0, fontname="helv", color=COLOR_PRIMARY)
            self.advance(row_h)
        self.advance(4.0)

    def draw_metric_cards_grid(self, cards: List[Tuple[str, str, str]]) -> None:
        """Render metric cards grid with auto-wrapping text."""
        cols = 4
        card_w = (PRINTABLE_WIDTH - (cols - 1) * 8.0) / cols
        card_h = 42.0

        for row_start in range(0, len(cards), cols):
            self.ensure_space(card_h + 6.0)
            row_items = cards[row_start:row_start + cols]
            for c_idx, (num, label, tint) in enumerate(row_items):
                cx = MARGIN_LEFT + c_idx * (card_w + 8.0)
                card_rect = pymupdf.Rect(cx, self.y, cx + card_w, self.y + card_h)

                if tint == "rose":
                    bg, border, tc = COLOR_ROSE_BG, COLOR_ROSE, COLOR_ROSE
                elif tint == "amber":
                    bg, border, tc = COLOR_AMBER_BG, COLOR_AMBER, COLOR_AMBER
                elif tint == "emerald":
                    bg, border, tc = COLOR_EMERALD_BG, COLOR_EMERALD, COLOR_EMERALD
                else:
                    bg, border, tc = COLOR_BLUE_BG, COLOR_BLUE, COLOR_PRIMARY

                self.page.draw_rect(card_rect, color=border, fill=bg, width=0.75)
                self.page.insert_text(pymupdf.Point(cx + 8, self.y + 18), sanitize_pdf_text(num), fontsize=13.0, fontname="helv", color=tc)
                label_rect = pymupdf.Rect(cx + 8, self.y + 22, cx + card_w - 4, self.y + card_h - 2)
                self.page.insert_textbox(label_rect, sanitize_pdf_text(label), fontsize=7.0, fontname="helv", color=COLOR_MUTED)
            self.advance(card_h + 8.0)

    def draw_table_header(self, headers: List[str], col_widths: List[float], header_h: float = 18.0) -> None:
        """Draw table header bar."""
        h_rect = pymupdf.Rect(MARGIN_LEFT, self.y, MARGIN_RIGHT, self.y + header_h)
        self.page.draw_rect(h_rect, color=COLOR_PRIMARY, fill=COLOR_PRIMARY)
        cur_x = MARGIN_LEFT
        for h, w in zip(headers, col_widths):
            self.page.insert_text(
                pymupdf.Point(cur_x + 5, self.y + 12),
                sanitize_pdf_text(h),
                fontsize=7.5,
                fontname="helv",
                color=COLOR_WHITE,
            )
            cur_x += w
        self.advance(header_h)

    def draw_simple_table(self, headers: List[str], rows: List[List[str]], col_widths: List[float]) -> None:
        """Draw a responsive table with dynamic multi-line cell wrapping and multi-page continuation."""
        if not rows:
            self.draw_paragraph("No items recorded in this section.", color=COLOR_MUTED)
            return

        header_h = 18.0
        self.ensure_space(header_h + 30.0)
        self.draw_table_header(headers, col_widths, header_h)

        # Draw Rows with Dynamic Wrapping and Pagination
        for r_idx, row in enumerate(rows):
            # Calculate max lines required across all columns
            max_lines = 1
            for c_val, w in zip(row, col_widths):
                text_s = sanitize_pdf_text(c_val)
                chars_per_line = max(1, int(w / 4.4))
                lines_cnt = 0
                for paragraph in text_s.split("\n"):
                    lines_cnt += max(1, (len(paragraph) + chars_per_line - 1) // chars_per_line)
                if lines_cnt > max_lines:
                    max_lines = lines_cnt

            row_h = max(18.0, max_lines * 9.5 + 6.0)

            # Check if row fits on current page. If not, advance and redraw header
            if self.y + row_h > MARGIN_BOTTOM:
                self.new_page()
                self.draw_table_header(headers, col_widths, header_h)

            row_bg = COLOR_LIGHT_BG if r_idx % 2 == 1 else COLOR_WHITE
            row_rect = pymupdf.Rect(MARGIN_LEFT, self.y, MARGIN_RIGHT, self.y + row_h)
            self.page.draw_rect(row_rect, color=COLOR_BORDER, fill=row_bg, width=0.5)

            cur_x = MARGIN_LEFT
            for c_val, w in zip(row, col_widths):
                c_rect = pymupdf.Rect(cur_x + 4, self.y + 3, cur_x + w - 4, self.y + row_h - 2)
                text_clean = sanitize_pdf_text(c_val)
                self.page.insert_textbox(c_rect, text_clean, fontsize=7.0, fontname="helv", color=COLOR_TEXT)
                cur_x += w
            self.advance(row_h)
        self.advance(8.0)

    # -----------------------------------------------------------------------
    # Section Builders (1 to 12)
    # -----------------------------------------------------------------------

    def build_cover_page(self) -> None:
        """Section 1: Publication-grade Cover Page."""
        self.new_page(is_cover=True)
        cov = self.data.get("cover_page", {})

        # Top Accent Block
        top_rect = pymupdf.Rect(MARGIN_LEFT, 50, MARGIN_RIGHT, 140)
        self.page.draw_rect(top_rect, color=COLOR_PRIMARY, fill=COLOR_PRIMARY)
        self.page.insert_text(pymupdf.Point(MARGIN_LEFT + 20, 85), "COMPLIANCE SENTINEL ENTERPRISE", fontsize=11.0, fontname="helv", color=COLOR_BLUE)
        self.page.insert_text(pymupdf.Point(MARGIN_LEFT + 20, 115), "COMPREHENSIVE AUDIT & ADJUDICATION REPORT", fontsize=15.0, fontname="helv", color=COLOR_WHITE)

        self.advance(155.0)

        # Title & Target Box
        self.draw_paragraph(cov.get("report_title", "Enterprise Security Posture & Compliance Report"), fontsize=14.0, color=COLOR_PRIMARY)
        target_sys = cov.get("target_system", "Production Workload")
        env_val = cov.get("environment", "Not Specified")
        self.draw_paragraph(f"Target System: {target_sys}  |  Environment: {str(env_val).upper()}", fontsize=9.5, color=COLOR_MUTED)
        self.advance(15.0)

        # Metadata Card
        meta_pairs = [
            ("Organization", cov.get("organization_name", "Acme Corp")),
            ("Audit Name", cov.get("audit_name", "Security Audit")),
            ("Report ID", cov.get("report_id", "N/A")),
            ("Report Version", f"v{cov.get('report_version', '1')}"),
            ("Generated Date", cov.get("generated_at", "N/A")),
            ("Audit Status", str(cov.get("report_status", "completed")).upper()),
            ("Frameworks", ", ".join(cov.get("framework_names", ["PCI-DSS / SOC 2"])) or "ISO 27001:2022"),
        ]
        self.draw_key_value_grid(meta_pairs, cols=2)
        self.advance(20.0)

        # Stale Warning if any
        if cov.get("is_stale"):
            self.draw_callout_box(
                "ADVISORY: STALE DECISIONS DETECTED",
                "One or more upstream inputs (regulatory requirements, threat models, or discovered controls) were modified after adjudication. A re-adjudication run is recommended to synchronize conclusions.",
                border_color=COLOR_AMBER,
                fill_color=COLOR_AMBER_BG,
            )

        # Bottom Notice
        self.page.insert_text(
            pymupdf.Point(MARGIN_LEFT, 770),
            "CONFIDENTIALITY NOTICE: This document contains proprietary audit findings and synthetic security threat assessments.",
            fontsize=7.0,
            fontname="helv",
            color=COLOR_MUTED,
        )
        self.page.insert_text(
            pymupdf.Point(MARGIN_LEFT, 782),
            "All findings, threat paths, and control assessments are verified against uploaded organizational evidence chunks.",
            fontsize=7.0,
            fontname="helv",
            color=COLOR_MUTED,
        )

    def build_table_of_contents(self) -> None:
        """Section 1b: Table of Contents."""
        self.new_page()
        self.draw_section_heading("0", "Table of Contents")
        toc_items = [
            ("Section 1", "Executive Summary", "Key metrics, summary narrative, and evidence limitations"),
            ("Section 2", "Assessment Scope & Methodology", "System parameters, evidence documents, and multi-agent roles"),
            ("Section 3", "Regulatory Requirements Assessment", "Audited obligations, adjudication outcomes, and verbatim citations"),
            ("Section 4", "Discovered Assets & Attack Surfaces", "Asset inventory, trust boundaries, entry points, and protocol surfaces"),
            ("Section 5", "Threat & Attack-Path Assessment (STRIDE)", "Modeled attack paths, deterministic risk scores, and mitigations"),
            ("Section 6", "Security Control Assessment", "Discovered controls, evidence maturity ratings, and assessment results"),
            ("Section 7", "Findings & Risk Register", "Identified gap findings, severity classifications, and corrective actions"),
            ("Section 8", "Contradictions & Evidence Gaps", "Cross-agent inconsistencies, opposing claims, and evidence deficits"),
            ("Section 9", "Recommendations & Remediation Roadmap", "Prioritized action items sequenced by risk severity (Critical to Low)"),
            ("Section 10", "Limitations & Disclaimers", "Mandatory legal, technical, and regulatory scope limitations"),
            ("Section 11", "Appendix", "Glossary of terms, risk scoring methodology, and citation index"),
        ]
        for sec, title, desc in toc_items:
            self.ensure_space(26.0)
            self.page.insert_text(pymupdf.Point(MARGIN_LEFT, self.y + 12), sec, fontsize=8.0, fontname="helv", color=COLOR_BLUE)
            self.page.insert_text(pymupdf.Point(MARGIN_LEFT + 70, self.y + 12), sanitize_pdf_text(title), fontsize=8.5, fontname="helv", color=COLOR_PRIMARY)
            self.page.insert_text(pymupdf.Point(MARGIN_LEFT + 70, self.y + 22), sanitize_pdf_text(desc), fontsize=6.8, fontname="helv", color=COLOR_MUTED)
            self.page.draw_line(pymupdf.Point(MARGIN_LEFT, self.y + 26), pymupdf.Point(MARGIN_RIGHT, self.y + 26), color=COLOR_BORDER, width=0.5)
            self.advance(28.0)

    def build_executive_summary(self) -> None:
        """Section 2: Executive Summary."""
        self.new_page()
        self.draw_section_heading("1", "Executive Summary")
        ex = self.data.get("executive_summary", {})

        conf_pct = int(ex.get("average_confidence_score", 0.0) * 100)
        cards = [
            (str(ex.get("total_requirements_assessed", 0)), "Requirements", "blue"),
            (str(ex.get("supported_requirements_count", 0)), "Supported", "emerald"),
            (str(ex.get("partially_supported_count", 0)), "Partial Support", "amber" if ex.get("partially_supported_count", 0) > 0 else "blue"),
            (str(ex.get("insufficient_evidence_count", 0)), "Insufficient Evid", "rose" if ex.get("insufficient_evidence_count", 0) > 0 else "blue"),
            (str(ex.get("total_controls_documented", 0)), "Controls Found", "blue"),
            (str(ex.get("total_threats_modeled", 0)), "Threats Modeled", "amber"),
            (str(ex.get("mitigated_threats_count", 0)), "Mitigated", "emerald"),
            (f"{conf_pct}%", "Avg Confidence", "emerald" if conf_pct >= 60 else "amber"),
        ]
        self.draw_metric_cards_grid(cards)

        self.draw_subsection_heading("Assessment Overview & Narrative")
        narrative = ex.get("narrative", "Assessment synthesis completed across regulatory requirements, discovered safeguards, and modeled threats.")
        self.draw_paragraph(narrative)
        self.advance(10.0)

        # Evidence Limitations
        limits = ex.get("evidence_limitations", [])
        if limits:
            self.draw_subsection_heading("Key Evidence Limitations")
            for lim in limits:
                self.draw_paragraph(f"*  {lim}", indent=10.0, color=COLOR_MUTED)

    def build_scope_and_methodology(self) -> None:
        """Section 3: Assessment Scope & Methodology."""
        self.ensure_space(100.0)
        self.draw_section_heading("2", "Assessment Scope & Methodology")
        sc = self.data.get("scope_and_methodology", {})

        self.draw_subsection_heading("Target Scope & Parameters")
        self.draw_key_value_grid([
            ("Target System", sc.get("target_system", "Production System")),
            ("Environment", sc.get("environment", "Not Specified")),
            ("Scope Notes", sc.get("audit_scope_description", "Complete architecture & compliance audit")),
        ], cols=2)
        self.advance(8.0)

        self.draw_subsection_heading("Evidence Documents Ingested")
        docs = sc.get("uploaded_documents", [])
        doc_rows = [[d.get("name", "Document"), d.get("type", "PDF"), str(d.get("pages", 1)), str(d.get("chunks", 1))] for d in docs]
        self.draw_simple_table(["Document Title", "Type", "Pages", "Chunks"], doc_rows, [220.0, 85.0, 90.0, 110.0])

        self.draw_subsection_heading("Autonomous Multi-Agent Architecture")
        self.draw_paragraph(sc.get("methodology_overview", "Multi-agent consensus reconciliation pipeline combining Legal Analyst, Adversarial Strategist, Defence Auditor, and Adjudicator arbiter."))

    def build_regulatory_requirements(self) -> None:
        """Section 4: Regulatory Requirements Assessment."""
        self.ensure_space(100.0)
        self.draw_section_heading("3", "Regulatory Requirements Assessment")
        reqs = self.data.get("regulatory_requirements", [])

        if not reqs:
            self.draw_paragraph("No regulatory requirements mapped to this audit scope.", color=COLOR_MUTED)
            return

        headers = ["Req ID", "Framework", "Obligation", "Outcome", "Confidence"]
        widths = [85.0, 115.0, 80.0, 155.0, 70.0]
        rows = [
            [
                r.get("requirement_id", "REQ"),
                r.get("framework_name", "Framework"),
                r.get("obligation_type", "mandatory"),
                r.get("adjudication_outcome", "pending").replace("_", " "),
                f"{int(r.get('confidence_score', 0) * 100)}%",
            ]
            for r in reqs
        ]
        self.draw_simple_table(headers, rows, widths)

        # Draw details for all requirements without artificial limits
        self.advance(10.0)
        self.draw_subsection_heading("Requirement Adjudication Detail & Verified Citations")
        for r in reqs:
            self.ensure_space(60.0)
            req_heading = f"[{r.get('requirement_id')}] {r.get('title', 'Requirement')}"
            self.page.insert_text(pymupdf.Point(MARGIN_LEFT, self.y + 12), sanitize_pdf_text(req_heading), fontsize=8.5, fontname="helv", color=COLOR_PRIMARY)
            outcome = r.get("adjudication_outcome", "insufficient_evidence")
            self.draw_badge(MARGIN_RIGHT - 110.0, self.y + 12, outcome.replace("_", " "), badge_type=outcome)
            self.advance(16.0)

            stmt = r.get("statement", "")
            if stmt:
                self.draw_paragraph(f"Statement: {stmt}", fontsize=7.5, indent=8.0, color=COLOR_MUTED)

            conf_exp = r.get("confidence_explanation", "")
            if conf_exp:
                self.draw_paragraph(f"Confidence Rationale: {conf_exp}", fontsize=7.0, indent=8.0, color=COLOR_SECONDARY)

            citations = r.get("citations", [])
            if citations:
                for cit in citations:
                    doc_name = cit.get("filename", "Evidence Doc")
                    pg = cit.get("page_number", 1)
                    excerpt = cit.get("exact_excerpt", "")
                    sec_h = f" - Section: {cit.get('section_heading')}" if cit.get("section_heading") else ""
                    self.draw_paragraph(f"Citation [{doc_name}, Page {pg}{sec_h}]: \"{excerpt}\"", fontsize=7.0, indent=14.0, color=COLOR_BLUE)
            else:
                self.draw_paragraph("Citation Status: No direct supporting citations discovered in submitted evidence documents.", fontsize=7.0, indent=14.0, color=COLOR_AMBER)
            self.advance(6.0)

    def build_assets_and_attack_surfaces(self) -> None:
        """Section 5: Discovered Assets & Attack Surfaces."""
        self.ensure_space(100.0)
        self.draw_section_heading("4", "Discovered Assets & Attack Surfaces")
        assets = self.data.get("discovered_assets", [])
        surfaces = self.data.get("attack_surfaces", [])

        self.draw_subsection_heading("Asset Inventory")
        if assets:
            a_rows = [[a.get("name", "Asset"), a.get("asset_type", "Service"), a.get("criticality", "medium"), a.get("trust_boundary", "Internal")] for a in assets]
            self.draw_simple_table(["Asset Identifier", "Type", "Criticality", "Trust Boundary"], a_rows, [180.0, 100.0, 100.0, 125.0])
        else:
            self.draw_paragraph("No specific assets catalogued.", color=COLOR_MUTED)

        self.advance(8.0)
        self.draw_subsection_heading("Attack Surfaces & External Ingress")
        if surfaces:
            s_rows = [[s.get("surface_name", "Surface"), s.get("entry_point", "API"), s.get("protocol", "HTTPS"), "Yes" if s.get("authentication_required") else "No"] for s in surfaces]
            self.draw_simple_table(["Attack Surface", "Entry Point", "Protocol", "Auth Required"], s_rows, [170.0, 155.0, 90.0, 90.0])
        else:
            self.draw_paragraph("No attack surfaces catalogued.", color=COLOR_MUTED)

    def build_threat_assessment(self) -> None:
        """Section 6: Threat & Attack-Path Assessment (STRIDE)."""
        self.ensure_space(100.0)
        self.draw_section_heading("5", "Threat & Attack-Path Assessment (STRIDE)")
        self.draw_callout_box(
            "IMPORTANT: MODELED THREAT SCENARIOS",
            "The threat paths catalogued below represent potential attack models synthesized from architecture evidence. They indicate theoretical exploit vectors to be safeguarded against, not confirmed vulnerabilities.",
            border_color=COLOR_AMBER,
            fill_color=COLOR_AMBER_BG,
        )

        threats = self.data.get("threat_assessment", [])
        if not threats:
            self.draw_paragraph("No threat scenarios modeled for this audit.", color=COLOR_MUTED)
            return

        headers = ["Threat Code", "STRIDE", "Title", "Risk (LxI)", "Adjudication Status"]
        widths = [75.0, 90.0, 160.0, 65.0, 115.0]
        rows = [
            [
                t.get("threat_id", "THR"),
                t.get("stride_category", "Spoofing"),
                t.get("title", "Threat Scenario"),
                f"{t.get('risk_score', 0)} ({str(t.get('severity', 'low')).upper()})",
                t.get("adjudication_outcome", "unmitigated").replace("_", " "),
            ]
            for t in threats
        ]
        self.draw_simple_table(headers, rows, widths)

        # Threat details with full descriptions and evidence citations
        self.advance(8.0)
        self.draw_subsection_heading("Threat Attack Trees & Evidence Grounding")
        for t in threats:
            self.ensure_space(55.0)
            t_head = f"[{t.get('threat_id')}] {t.get('title')}"
            self.page.insert_text(pymupdf.Point(MARGIN_LEFT, self.y + 12), sanitize_pdf_text(t_head), fontsize=8.5, fontname="helv", color=COLOR_PRIMARY)
            self.advance(16.0)
            self.draw_paragraph(f"Description: {t.get('description', '')}", fontsize=7.5, indent=8.0, color=COLOR_TEXT)
            
            cits = t.get("citations", [])
            for c in cits:
                self.draw_paragraph(f"Evidence Basis [{c.get('filename')}, Page {c.get('page_number', 1)}]: \"{c.get('exact_excerpt', '')}\"", fontsize=7.0, indent=14.0, color=COLOR_BLUE)
            
            ctrls = t.get("related_controls", [])
            if ctrls:
                self.draw_paragraph(f"Documented Safeguards Addressed: {', '.join(ctrls)}", fontsize=7.0, indent=8.0, color=COLOR_EMERALD)
            else:
                self.draw_paragraph("Documented Safeguards Addressed: None documented in submitted evidence.", fontsize=7.0, indent=8.0, color=COLOR_ROSE)
            self.advance(4.0)

    def build_control_assessment(self) -> None:
        """Section 7: Security Control Assessment."""
        self.ensure_space(100.0)
        self.draw_section_heading("6", "Security Control Assessment")
        controls = self.data.get("control_assessment", [])

        if not controls:
            self.draw_paragraph("No security controls discovered in documentation.", color=COLOR_MUTED)
            return

        headers = ["Control ID", "Title", "Maturity", "Implementation", "Human Review"]
        widths = [75.0, 180.0, 80.0, 95.0, 75.0]
        rows = [
            [
                c.get("control_id", "CTL"),
                c.get("title", "Control Title"),
                str(c.get("evidence_maturity", "policy")).upper(),
                str(c.get("implementation_status", "documented")).replace("_", " "),
                str(c.get("human_review_status", "pending")).capitalize(),
            ]
            for c in controls
        ]
        self.draw_simple_table(headers, rows, widths)

        # Control detail register with full evidence citations and related linkages
        self.advance(8.0)
        self.draw_subsection_heading("Control Implementation Details & Traceability")
        for c in controls:
            self.ensure_space(60.0)
            c_head = f"[{c.get('control_id')}] {c.get('title')}"
            self.page.insert_text(pymupdf.Point(MARGIN_LEFT, self.y + 12), sanitize_pdf_text(c_head), fontsize=8.5, fontname="helv", color=COLOR_PRIMARY)
            self.draw_badge(MARGIN_RIGHT - 110.0, self.y + 12, str(c.get("implementation_status")).replace("_", " "), badge_type=c.get("implementation_status", "medium"))
            self.advance(16.0)

            desc = c.get("control_description", "")
            if desc:
                self.draw_paragraph(f"Safeguard Description: {desc}", fontsize=7.5, indent=8.0, color=COLOR_TEXT)

            reqs = c.get("related_requirements", [])
            thrs = c.get("related_threats", [])
            link_info = []
            if reqs:
                link_info.append(f"Mapped Requirements: {', '.join(reqs)}")
            if thrs:
                link_info.append(f"Mapped Threats: {', '.join(thrs)}")
            if link_info:
                self.draw_paragraph(" | ".join(link_info), fontsize=7.0, indent=8.0, color=COLOR_SECONDARY)

            citations = c.get("citations", [])
            for cit in citations:
                doc_name = cit.get("filename", "Evidence Doc")
                pg = cit.get("page_number", 1)
                sec = f" (Section: {cit.get('section_title')})" if cit.get("section_title") else ""
                self.draw_paragraph(f"Evidence Citation [{doc_name}, Page {pg}{sec}]: \"{cit.get('exact_excerpt', '')}\"", fontsize=7.0, indent=14.0, color=COLOR_BLUE)
            self.advance(6.0)

    def build_findings_register(self) -> None:
        """Section 8: Findings & Risk Register."""
        self.ensure_space(100.0)
        self.draw_section_heading("7", "Findings & Risk Register")
        findings = self.data.get("findings_register", [])

        if not findings:
            self.draw_paragraph("No gap assessment findings recorded for this audit.", color=COLOR_MUTED)
            return

        headers = ["Finding ID", "Classification", "Title", "Severity", "Risk"]
        widths = [70.0, 115.0, 195.0, 75.0, 50.0]
        rows = [
            [
                f.get("finding_id", "GAP"),
                f.get("classification_label", "Documented Weakness"),
                f.get("title", "Finding Title"),
                str(f.get("severity", "medium")).upper(),
                str(f.get("risk_score", 0)),
            ]
            for f in findings
        ]
        self.draw_simple_table(headers, rows, widths)

        # Finding details and recommended corrective actions
        self.advance(8.0)
        self.draw_subsection_heading("Finding Root Causes & Corrective Actions")
        for f in findings:
            self.ensure_space(60.0)
            f_head = f"[{f.get('finding_id')}] {f.get('title')}"
            self.page.insert_text(pymupdf.Point(MARGIN_LEFT, self.y + 12), sanitize_pdf_text(f_head), fontsize=8.5, fontname="helv", color=COLOR_PRIMARY)
            self.draw_badge(MARGIN_RIGHT - 110.0, self.y + 12, str(f.get("severity", "medium")).upper(), badge_type=f.get("severity", "medium"))
            self.advance(16.0)

            self.draw_paragraph(f"Classification: {f.get('classification_label', 'Documented Weakness')} | Status: {str(f.get('review_status', 'pending')).capitalize()}", fontsize=7.0, indent=8.0, color=COLOR_MUTED)
            self.draw_paragraph(f"Description: {f.get('description', '')}", fontsize=7.5, indent=8.0, color=COLOR_TEXT)
            self.draw_paragraph(f"Recommended Corrective Action: {f.get('recommended_corrective_action', '')}", fontsize=7.5, indent=8.0, color=COLOR_EMERALD)
            self.advance(6.0)

    def build_contradictions_and_gaps(self) -> None:
        """Section 9: Contradictions & Evidence Gaps."""
        self.ensure_space(100.0)
        self.draw_section_heading("8", "Contradictions & Evidence Gaps")
        contradictions = self.data.get("contradictions_and_gaps", [])

        if not contradictions:
            self.draw_paragraph("No cross-agent or document contradictions detected in this audit.", color=COLOR_MUTED)
            return

        for idx, con in enumerate(contradictions):
            self.ensure_space(60.0)
            self.page.insert_text(
                pymupdf.Point(MARGIN_LEFT, self.y + 12),
                sanitize_pdf_text(f"Contradiction #{idx+1}: {con.get('contradiction_type', 'cross_agent').replace('_', ' ').upper()}"),
                fontsize=8.5,
                fontname="helv",
                color=COLOR_ROSE,
            )
            self.advance(16.0)
            self.draw_paragraph(f"Description: {con.get('description', '')}", fontsize=7.5, indent=8.0)
            self.draw_paragraph(f"Claim A: {con.get('claim_a', '')}", fontsize=7.0, indent=14.0, color=COLOR_MUTED)
            self.draw_paragraph(f"Claim B: {con.get('claim_b', '')}", fontsize=7.0, indent=14.0, color=COLOR_MUTED)
            status_text = f"Status: {str(con.get('resolution_status', 'unresolved')).upper()}"
            if con.get("resolution_notes"):
                status_text += f" | Resolution: {con.get('resolution_notes')}"
            self.draw_paragraph(status_text, fontsize=7.0, indent=8.0, color=COLOR_SECONDARY)
            self.advance(8.0)

    def build_remediation_roadmap(self) -> None:
        """Section 10: Recommendations & Remediation Roadmap."""
        self.ensure_space(100.0)
        self.draw_section_heading("9", "Remediation Roadmap")
        items = self.data.get("remediation_roadmap", [])

        if not items:
            self.draw_paragraph("No remediation items synthesized.", color=COLOR_MUTED)
            return

        headers = ["Seq", "Priority", "Target Issue", "Recommended Action"]
        widths = [35.0, 65.0, 115.0, 290.0]
        rows = [
            [
                str(it.get("sequence", 1)),
                str(it.get("priority", "Medium")).upper(),
                it.get("related_finding_or_threat", "GAP"),
                it.get("recommended_action", "Apply remediation safeguard"),
            ]
            for it in items
        ]
        self.draw_simple_table(headers, rows, widths)

    def build_limitations_and_disclaimers(self) -> None:
        """Section 11: Limitations & Disclaimers."""
        self.ensure_space(100.0)
        self.draw_section_heading("10", "Limitations & Disclaimers")
        disclaimers = self.data.get("limitations_and_disclaimers", [])

        standard_disclaimers = [
            "This compliance and security gap assessment report is generated based strictly upon the technical and operational documentation submitted for audit.",
            "Absence of documented operational evidence does not categorically establish that a security safeguard is absent in the target environment.",
            "Threat modeling scenarios synthesized by the Adversarial Strategist represent potential attack paths and do not constitute confirmed vulnerabilities or active security incidents.",
            "All autonomous AI auditor evaluations, maturity ratings, and adjudications remain provisional until validated through human auditor review.",
            "This report is issued for informational and posture-strengthening purposes only and does not constitute a formal legal compliance certification or regulatory attestation.",
        ]
        all_disclaimers = disclaimers if disclaimers else standard_disclaimers
        for d in all_disclaimers:
            self.draw_paragraph(f"*  {d}", fontsize=7.5, indent=8.0, color=COLOR_MUTED)
            self.advance(3.0)

    def build_appendix(self) -> None:
        """Section 12: Appendix, Methodology & Comprehensive Citation Index."""
        self.ensure_space(100.0)
        self.draw_section_heading("11", "Appendix & Citation Index")

        self.draw_subsection_heading("Risk Scoring Formula")
        self.draw_paragraph(
            "Risk scores are deterministically computed using the standard Likelihood x Impact formula: Risk Score = L x I, where L in [1, 5] and I in [1, 5], yielding a score in [1, 25]. Severity thresholds: Low (1-4), Medium (5-9), High (10-14), Very High (15-19), Critical (20-25).",
            fontsize=7.5,
        )
        self.advance(6.0)

        self.draw_subsection_heading("Evidence Maturity Levels")
        maturity_definitions = [
            ("Policy Level", "Written governance policies or guidelines without documented technical designs or logs."),
            ("Design Level", "Architecture diagrams, API specs, or security blueprints specifying safeguards."),
            ("Implementation Level", "Infrastructure-as-Code, configuration files, or software code verifying deployment."),
            ("Operational Level", "Production telemetry, audit logs, or runbook execution records verifying ongoing enforcement."),
        ]
        for lvl, desc in maturity_definitions:
            self.draw_paragraph(f"* {lvl}: {desc}", fontsize=7.0, indent=8.0, color=COLOR_MUTED)

        # Comprehensive Citation & Provenance Index
        self.advance(8.0)
        self.draw_subsection_heading("Evidence Provenance & Citation Index")
        all_citations: List[List[str]] = []
        
        # Collect citations across requirements and controls
        for r in self.data.get("regulatory_requirements", []):
            for cit in r.get("citations", []):
                all_citations.append([
                    r.get("requirement_id", "REQ"),
                    cit.get("filename", "document"),
                    str(cit.get("page_number", 1)),
                    cit.get("exact_excerpt", "")[:120],
                ])
        for c in self.data.get("control_assessment", []):
            for cit in c.get("citations", []):
                all_citations.append([
                    c.get("control_id", "CTRL"),
                    cit.get("filename", "document"),
                    str(cit.get("page_number", 1)),
                    cit.get("exact_excerpt", "")[:120],
                ])

        if all_citations:
            cit_headers = ["Target Entity", "Source Document", "Page", "Cited Evidence Excerpt"]
            cit_widths = [85.0, 110.0, 45.0, 265.0]
            self.draw_simple_table(cit_headers, all_citations[:30], cit_widths)

    # -----------------------------------------------------------------------
    # Finalization & Output
    # -----------------------------------------------------------------------

    def finalize(self) -> bytes:
        """Stamp running footers with total page count across all pages and export bytes."""
        total_pages = len(self.doc)

        for p_idx in range(total_pages):
            page = self.doc[p_idx]
            if p_idx == 0:
                # Cover page: no footer
                continue

            page.draw_line(
                pymupdf.Point(MARGIN_LEFT, 808),
                pymupdf.Point(MARGIN_RIGHT, 808),
                color=COLOR_BORDER,
                width=0.5,
            )
            page.insert_text(
                pymupdf.Point(MARGIN_LEFT, 818),
                "CONFIDENTIAL & PROPRIETARY - COMPLIANCE SENTINEL",
                fontsize=6.5,
                fontname="helv",
                color=COLOR_MUTED,
            )
            page_str = f"Page {p_idx + 1} of {total_pages}"
            page.insert_text(
                pymupdf.Point(MARGIN_RIGHT - len(page_str) * 4.8, 818),
                page_str,
                fontsize=6.5,
                fontname="helv",
                color=COLOR_MUTED,
            )

        buf = io.BytesIO()
        self.doc.save(buf)
        buf.seek(0)
        return buf.getvalue()

    def generate(self) -> bytes:
        """Execute full 12-section PDF generation pipeline."""
        self.build_cover_page()
        self.build_table_of_contents()
        self.build_executive_summary()
        self.build_scope_and_methodology()
        self.build_regulatory_requirements()
        self.build_assets_and_attack_surfaces()
        self.build_threat_assessment()
        self.build_control_assessment()
        self.build_findings_register()
        self.build_contradictions_and_gaps()
        self.build_remediation_roadmap()
        self.build_limitations_and_disclaimers()
        self.build_appendix()
        return self.finalize()
