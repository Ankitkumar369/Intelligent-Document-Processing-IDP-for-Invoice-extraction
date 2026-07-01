# src/extraction/column_detector.py

import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from src.core.logger import log


@dataclass
class ColumnSchema:
    """Detected column schema."""
    headers         : List[str]
    col_count       : int
    col_types       : Dict[str, str]   # col_name → "text/numeric/amount/date"
    confidence      : float
    shifted_cols    : List[str] = field(default_factory=list)
    missing_cols    : List[str] = field(default_factory=list)


@dataclass
class ColumnDetectionResult:
    """Column detection ka result."""
    filename        : str
    schema          : Optional[ColumnSchema]
    aligned_rows    : List[Dict[str, str]] = field(default_factory=list)
    error           : str = ""


class ColumnDetector:
    """
    PHASE 7 — Irregular Column Detection

    Problems solved:
    1. Missing columns
    2. Shifted columns
    3. Dynamic column count
    4. Column type detection
    5. Adaptive schema generation
    """

    # SuperStore invoice expected columns
    KNOWN_HEADERS = {
        "item"       : ["item", "description", "product", "particulars"],
        "quantity"   : ["quantity", "qty", "units", "nos"],
        "rate"       : ["rate", "price", "unit price", "unit rate"],
        "amount"     : ["amount", "total", "value", "net amount"],
    }

    AMOUNT_RE = re.compile(r"^\$?[\d,]+\.?\d*$")
    DATE_RE   = re.compile(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}")
    QTY_RE    = re.compile(r"^\d{1,5}$")

    def detect(
        self,
        raw_table   : List[List[str]],
        filename    : str = ""
    ) -> ColumnDetectionResult:

        log.info(f"Column detection: {filename}")

        if not raw_table:
            return ColumnDetectionResult(filename=filename, schema=None)

        try:
            # Step 1: Find header row
            header_idx, headers = self._find_headers(raw_table)

            if not headers:
                headers   = self._generate_schema(raw_table)
                header_idx = -1

            # Step 2: Detect column types
            data_rows = raw_table[header_idx + 1:] if header_idx >= 0 else raw_table
            col_types = self._detect_col_types(headers, data_rows)

            # Step 3: Find missing/shifted columns
            missing = self._find_missing_cols(headers)
            shifted = self._find_shifted_cols(headers, data_rows)

            # Step 4: Confidence score
            confidence = self._calc_confidence(headers, missing, shifted)

            schema = ColumnSchema(
                headers      = headers,
                col_count    = len(headers),
                col_types    = col_types,
                confidence   = confidence,
                shifted_cols = shifted,
                missing_cols = missing,
            )

            # Step 5: Align rows to schema
            aligned = self._align_rows(data_rows, headers, col_types)

            result = ColumnDetectionResult(
                filename     = filename,
                schema       = schema,
                aligned_rows = aligned,
            )

            log.debug(
                f"  ✅ {filename} | cols={len(headers)} | "
                f"confidence={confidence:.2f} | "
                f"aligned_rows={len(aligned)}"
            )
            return result

        except Exception as e:
            log.error(f"ColumnDetector error: {e}")
            return ColumnDetectionResult(
                filename = filename,
                schema   = None,
                error    = str(e),
            )

    # ── Header Detection ──────────────────────────────────────
    def _find_headers(
        self, table: List[List[str]]
    ) -> Tuple[int, List[str]]:

        for i, row in enumerate(table[:5]):   # Sirf pehle 5 rows check
            if row is None:
                continue
            cells = [str(c).strip().lower() if c else "" for c in row]
            matches = 0
            for known_variants in self.KNOWN_HEADERS.values():
                if any(v in cells for v in known_variants):
                    matches += 1
            if matches >= 2:
                clean = [str(c).strip() if c else "" for c in row]
                return i, clean

        return -1, []

    # ── Schema Generation ─────────────────────────────────────
    def _generate_schema(self, table: List[List[str]]) -> List[str]:
        """Header nahi mila to data se schema generate karo."""
        if not table:
            return []

        max_cols = max(len(r) for r in table if r)

        # Guess based on SuperStore pattern
        if max_cols == 4:
            return ["Item", "Quantity", "Rate", "Amount"]
        elif max_cols == 3:
            return ["Item", "Quantity", "Amount"]
        elif max_cols == 2:
            return ["Item", "Amount"]
        else:
            return [f"Column_{i+1}" for i in range(max_cols)]

    # ── Column Type Detection ─────────────────────────────────
    def _detect_col_types(
        self,
        headers  : List[str],
        data_rows: List[List[str]]
    ) -> Dict[str, str]:

        col_types = {}
        for i, header in enumerate(headers):
            values = []
            for row in data_rows:
                if row and i < len(row) and row[i]:
                    values.append(str(row[i]).strip())

            col_types[header] = self._infer_type(values)

        return col_types

    def _infer_type(self, values: List[str]) -> str:
        if not values:
            return "text"

        amount_count  = sum(1 for v in values if self.AMOUNT_RE.match(v.replace(",", "")))
        qty_count     = sum(1 for v in values if self.QTY_RE.match(v))
        date_count    = sum(1 for v in values if self.DATE_RE.search(v))

        total = len(values)
        if amount_count / total >= 0.6:
            return "amount"
        if qty_count / total >= 0.6:
            return "numeric"
        if date_count / total >= 0.5:
            return "date"
        return "text"

    # ── Missing/Shifted Detection ─────────────────────────────
    def _find_missing_cols(self, headers: List[str]) -> List[str]:
        missing = []
        header_lower = [h.lower() for h in headers]
        for canonical, variants in self.KNOWN_HEADERS.items():
            if not any(v in header_lower for v in variants):
                missing.append(canonical)
        return missing

    def _find_shifted_cols(
        self,
        headers  : List[str],
        data_rows: List[List[str]]
    ) -> List[str]:
        shifted = []
        for i, header in enumerate(headers):
            col_type = self._infer_type([
                str(row[i]).strip()
                for row in data_rows
                if row and i < len(row) and row[i]
            ])
            h_lower = header.lower()
            if ("amount" in h_lower or "rate" in h_lower) and col_type == "text":
                shifted.append(header)
            elif ("qty" in h_lower or "quantity" in h_lower) and col_type == "amount":
                shifted.append(header)
        return shifted

    # ── Row Alignment ─────────────────────────────────────────
    def _align_rows(
        self,
        data_rows: List[List[str]],
        headers  : List[str],
        col_types: Dict[str, str],
    ) -> List[Dict[str, str]]:

        aligned = []
        for row in data_rows:
            if not row or not any(row):
                continue
            cells  = [str(c).strip() if c else "" for c in row]
            mapped = {}
            for i, header in enumerate(headers):
                mapped[header] = cells[i] if i < len(cells) else ""
            aligned.append(mapped)

        return aligned

    # ── Confidence ────────────────────────────────────────────
    def _calc_confidence(
        self,
        headers: List[str],
        missing: List[str],
        shifted: List[str],
    ) -> float:
        base     = 1.0
        base    -= len(missing) * 0.15
        base    -= len(shifted) * 0.10
        if not headers:
            base = 0.0
        return round(max(0.0, min(1.0, base)), 2)