# src/extraction/table_detector.py

import pdfplumber
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from src.core.logger import log


@dataclass
class ExtractedTable:
    """Ek extracted table ki complete info."""
    page_no     : int
    table_index : int
    headers     : List[str]
    rows        : List[List[str]]
    raw_data    : List[List]
    row_count   : int
    col_count   : int
    has_headers : bool
    bbox        : tuple


@dataclass
class TableExtractionResult:
    """Poore document ke tables."""
    filename        : str
    total_tables    : int
    tables          : List[ExtractedTable] = field(default_factory=list)
    error           : str = ""


class TableDetector:
    """
    PHASE 4 — Table Detection
    PDF se saare tables extract karta hai.
    Border aur borderless dono handle karta hai.
    """

    # pdfplumber table settings
    TABLE_SETTINGS = {
        "vertical_strategy"  : "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance"     : 5,
        "join_tolerance"     : 3,
        "edge_min_length"    : 10,
        "min_words_vertical" : 3,
        "min_words_horizontal": 1,
    }

    FALLBACK_SETTINGS = {
        "vertical_strategy"  : "text",
        "horizontal_strategy": "text",
        "snap_tolerance"     : 8,
        "join_tolerance"     : 5,
    }

    def extract(self, filepath: str) -> TableExtractionResult:
        path = Path(filepath)
        log.info(f"Table extraction: {path.name}")

        try:
            all_tables = []

            with pdfplumber.open(filepath) as pdf:
                for page_no, page in enumerate(pdf.pages, start=1):

                    # Strategy 1: Line-based (border tables)
                    tables = page.extract_tables(self.TABLE_SETTINGS)

                    # Strategy 2: Fallback text-based (borderless)
                    if not tables:
                        tables = page.extract_tables(self.FALLBACK_SETTINGS)

                    if not tables:
                        log.debug(f"  No tables on page {page_no}")
                        continue

                    for t_idx, raw_table in enumerate(tables):
                        extracted = self._process_table(
                            raw_table, page_no, t_idx, page
                        )
                        if extracted:
                            all_tables.append(extracted)

            result = TableExtractionResult(
                filename     = path.name,
                total_tables = len(all_tables),
                tables       = all_tables,
            )

            log.debug(f"  ✅ {path.name} | tables={len(all_tables)}")
            return result

        except Exception as e:
            log.error(f"TableDetector error on {path.name}: {e}")
            return TableExtractionResult(
                filename     = path.name,
                total_tables = 0,
                error        = str(e),
            )

    # ── Table Processor ───────────────────────────────────────
    def _process_table(
        self, raw_table: List, page_no: int,
        t_idx: int, page
    ) -> Optional[ExtractedTable]:

        if not raw_table:
            return None

        # Clean: None → ""
        cleaned = []
        for row in raw_table:
            if row is None:
                continue
            clean_row = [
                str(cell).strip() if cell is not None else ""
                for cell in row
            ]
            # Skip completely empty rows
            if any(c for c in clean_row):
                cleaned.append(clean_row)

        if not cleaned:
            return None

        # Header detection
        headers    = []
        data_rows  = cleaned
        has_headers = False

        if cleaned:
            first_row = cleaned[0]
            # First row = header agar mostly non-numeric hai
            non_numeric = sum(
                1 for c in first_row
                if c and not self._is_numeric(c)
            )
            if non_numeric >= len(first_row) * 0.5:
                headers     = first_row
                data_rows   = cleaned[1:]
                has_headers = True

        # Bbox
        try:
            bbox = page.find_tables()[t_idx].bbox
        except Exception:
            bbox = (0, 0, 0, 0)

        return ExtractedTable(
            page_no     = page_no,
            table_index = t_idx,
            headers     = headers,
            rows        = data_rows,
            raw_data    = cleaned,
            row_count   = len(data_rows),
            col_count   = len(headers) if headers else (
                len(data_rows[0]) if data_rows else 0
            ),
            has_headers = has_headers,
            bbox        = bbox,
        )

    def _is_numeric(self, text: str) -> bool:
        import re
        return bool(re.match(r"^[\d,.\$\%\+\-\s]+$", text.strip()))