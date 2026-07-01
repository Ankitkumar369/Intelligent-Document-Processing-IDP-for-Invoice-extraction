# src/analysis/layout_analyzer.py

import pdfplumber
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from src.core.logger import log


@dataclass
class PageLayout:
    """Ek page ki complete layout information."""
    page_no         : int
    width           : float
    height          : float
    header_text     : str
    footer_text     : str
    body_text       : str
    table_regions   : List[Dict]
    kv_pairs        : Dict[str, str]
    raw_words       : List[Dict]
    total_chars     : int
    has_table       : bool
    has_header      : bool
    has_footer      : bool


@dataclass
class DocumentLayout:
    """Poore document ki layout."""
    filename        : str
    total_pages     : int
    pages           : List[PageLayout] = field(default_factory=list)
    all_kv_pairs    : Dict[str, str]   = field(default_factory=dict)
    error           : str              = ""


class LayoutAnalyzer:
    """
    PHASE 2 — Document Analysis
    PDF ke har page ka layout analyze karta hai.
    Headers, footers, tables, key-value pairs detect karta hai.
    """

    # Header = top 15% of page
    HEADER_RATIO = 0.15
    # Footer = bottom 10% of page
    FOOTER_RATIO = 0.10

    def analyze(self, filepath: str) -> DocumentLayout:
        path = Path(filepath)
        log.info(f"Layout analysis: {path.name}")

        try:
            with pdfplumber.open(filepath) as pdf:
                total_pages = len(pdf.pages)
                pages       = []
                all_kv      = {}

                for page_no, page in enumerate(pdf.pages, start=1):
                    layout = self._analyze_page(page, page_no)
                    pages.append(layout)
                    all_kv.update(layout.kv_pairs)

                doc_layout = DocumentLayout(
                    filename    = path.name,
                    total_pages = total_pages,
                    pages       = pages,
                    all_kv_pairs= all_kv,
                )

                log.debug(
                    f"  ✅ {path.name} | pages={total_pages} | "
                    f"kv_pairs={len(all_kv)}"
                )
                return doc_layout

        except Exception as e:
            log.error(f"LayoutAnalyzer error on {path.name}: {e}")
            return DocumentLayout(
                filename    = path.name,
                total_pages = 0,
                error       = str(e),
            )

    # ── Page Analysis ─────────────────────────────────────────
    def _analyze_page(self, page, page_no: int) -> PageLayout:
        width  = float(page.width)
        height = float(page.height)

        # Zone boundaries
        header_bottom = height * self.HEADER_RATIO
        footer_top    = height * (1 - self.FOOTER_RATIO)

        # Words with coordinates
        words = page.extract_words() or []

        header_words = []
        footer_words = []
        body_words   = []

        for w in words:
            y = float(w.get("top", 0))
            if y <= header_bottom:
                header_words.append(w["text"])
            elif y >= footer_top:
                footer_words.append(w["text"])
            else:
                body_words.append(w["text"])

        header_text = " ".join(header_words)
        footer_text = " ".join(footer_words)
        body_text   = " ".join(body_words)

        # Tables
        table_regions = []
        tables = page.find_tables()
        for t in tables:
            bbox = t.bbox
            table_regions.append({
                "x0"    : bbox[0],
                "top"   : bbox[1],
                "x1"    : bbox[2],
                "bottom": bbox[3],
            })

        # Key-Value pairs
        full_text = page.extract_text() or ""
        kv_pairs  = self._extract_kv_pairs(full_text)

        # Raw words metadata
        raw_words = [
            {
                "text"  : w.get("text", ""),
                "x0"    : w.get("x0", 0),
                "top"   : w.get("top", 0),
                "x1"    : w.get("x1", 0),
                "bottom": w.get("bottom", 0),
            }
            for w in words
        ]

        return PageLayout(
            page_no       = page_no,
            width         = width,
            height        = height,
            header_text   = header_text,
            footer_text   = footer_text,
            body_text     = body_text,
            table_regions = table_regions,
            kv_pairs      = kv_pairs,
            raw_words     = raw_words,
            total_chars   = len(full_text),
            has_table     = len(table_regions) > 0,
            has_header    = len(header_text.strip()) > 0,
            has_footer    = len(footer_text.strip()) > 0,
        )

    # ── KV Pair Extractor ─────────────────────────────────────
    def _extract_kv_pairs(self, text: str) -> Dict[str, str]:
        """
        Text se key:value pairs nikalo.
        Example: "Invoice # 36258" → {"Invoice #": "36258"}
        """
        kv = {}
        lines = text.split("\n")

        import re
        # Pattern: "Key: Value" ya "Key # Value"
        pattern = re.compile(
            r"^(.{2,40}?)\s*[:﹕#]\s*(.+)$"
        )

        for line in lines:
            line = line.strip()
            if not line:
                continue
            m = pattern.match(line)
            if m:
                k = m.group(1).strip()
                v = m.group(2).strip()
                if len(k) < 50 and len(v) < 200:
                    kv[k] = v

        return kv