# src/extraction/row_reconstructor.py

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from src.core.logger import log


@dataclass
class ReconstructedRow:
    """Ek reconstructed complete row."""
    row_index   : int
    data        : Dict[str, str]
    is_complete : bool
    missing_cols: List[str] = field(default_factory=list)


@dataclass
class ReconstructionResult:
    """Row reconstruction ka result."""
    filename          : str
    original_rows     : int
    reconstructed_rows: int
    rows              : List[ReconstructedRow] = field(default_factory=list)
    error             : str = ""


class RowReconstructor:
    """
    PHASE 6 — Irregular Row Detection & Reconstruction

    Problem:
    ┌──────┬─────┐
    │ ABC  │     │  ← Qty missing
    │      │ 10  │  ← Item missing
    └──────┴─────┘

    Solution:
    Item=ABC, Qty=10  ← Merged into one complete row
    """

    AMOUNT_RE = re.compile(r"\$[\d,]+\.?\d*")
    QTY_RE    = re.compile(r"^\d+(\.\d+)?$")

    def reconstruct(
        self,
        raw_rows : List[List[str]],
        headers  : List[str],
        filename : str = ""
    ) -> ReconstructionResult:

        log.info(f"Row reconstruction: {filename} | raw_rows={len(raw_rows)}")

        if not raw_rows:
            return ReconstructionResult(
                filename           = filename,
                original_rows      = 0,
                reconstructed_rows = 0,
            )

        try:
            reconstructed = self._reconstruct_rows(raw_rows, headers)

            result = ReconstructionResult(
                filename           = filename,
                original_rows      = len(raw_rows),
                reconstructed_rows = len(reconstructed),
                rows               = reconstructed,
            )

            log.debug(
                f"  ✅ {filename} | "
                f"original={len(raw_rows)} → "
                f"reconstructed={len(reconstructed)}"
            )
            return result

        except Exception as e:
            log.error(f"RowReconstructor error: {e}")
            return ReconstructionResult(
                filename      = filename,
                original_rows = len(raw_rows),
                reconstructed_rows = 0,
                error         = str(e),
            )

    # ── Core Reconstruction ───────────────────────────────────
    def _reconstruct_rows(
        self,
        raw_rows: List[List[str]],
        headers : List[str]
    ) -> List[ReconstructedRow]:

        results  = []
        pending  = None   # Incomplete row buffer
        idx      = 0

        for row in raw_rows:
            cells = [str(c).strip() if c else "" for c in row]

            # Skip totally empty
            if not any(cells):
                continue

            filled = [c for c in cells if c]

            # Complete row — has most columns filled
            if self._is_complete_row(cells, headers):
                if pending is not None:
                    # Save pending before starting new
                    results.append(pending)
                    pending = None
                row_data = self._map_to_headers(cells, headers)
                results.append(ReconstructedRow(
                    row_index    = idx,
                    data         = row_data,
                    is_complete  = True,
                    missing_cols = self._find_missing(row_data),
                ))
                idx += 1

            # Partial row — needs merging
            elif self._is_partial_row(cells, headers):
                if pending is None:
                    # Start new pending
                    pending = ReconstructedRow(
                        row_index   = idx,
                        data        = self._map_to_headers(cells, headers),
                        is_complete = False,
                    )
                else:
                    # Merge into pending
                    pending = self._merge_rows(pending, cells, headers)

                    # Check if now complete
                    if self._is_now_complete(pending, headers):
                        pending.is_complete  = True
                        pending.missing_cols = []
                        results.append(pending)
                        pending = None
                        idx += 1

            # Continuation text row
            else:
                if pending is not None:
                    # Append text to description
                    desc_key = self._find_desc_key(headers)
                    if desc_key and filled:
                        existing = pending.data.get(desc_key, "")
                        pending.data[desc_key] = (
                            existing + " " + " ".join(filled)
                        ).strip()

        # Flush remaining pending
        if pending is not None:
            pending.missing_cols = self._find_missing(pending.data)
            results.append(pending)

        return results

    # ── Row Classifiers ───────────────────────────────────────
    def _is_complete_row(self, cells: List[str], headers: List[str]) -> bool:
        """Row complete hai agar >= 75% cells filled hain."""
        if not headers:
            return sum(1 for c in cells if c) >= max(1, len(cells) * 0.75)
        filled = sum(1 for c in cells if c)
        return filled >= max(1, len(headers) * 0.75)

    def _is_partial_row(self, cells: List[str], headers: List[str]) -> bool:
        """Row partial hai agar kuch cells filled hain."""
        filled = sum(1 for c in cells if c)
        return 0 < filled < max(1, len(headers) * 0.75)

    def _is_now_complete(
        self, row: ReconstructedRow, headers: List[str]
    ) -> bool:
        filled = sum(1 for v in row.data.values() if v)
        return filled >= max(1, len(headers) * 0.75)

    # ── Mapping & Merging ─────────────────────────────────────
    def _map_to_headers(
        self, cells: List[str], headers: List[str]
    ) -> Dict[str, str]:
        """Cells ko headers ke saath map karo."""
        if not headers:
            return {f"col_{i}": c for i, c in enumerate(cells)}

        mapped = {}
        for i, header in enumerate(headers):
            mapped[header] = cells[i] if i < len(cells) else ""
        return mapped

    def _merge_rows(
        self,
        pending : ReconstructedRow,
        cells   : List[str],
        headers : List[str]
    ) -> ReconstructedRow:
        """Partial row ko pending mein merge karo."""
        for i, header in enumerate(headers):
            if i < len(cells) and cells[i]:
                existing = pending.data.get(header, "")
                if not existing:
                    pending.data[header] = cells[i]
                else:
                    pending.data[header] = existing + " " + cells[i]
        return pending

    def _find_missing(self, data: Dict[str, str]) -> List[str]:
        return [k for k, v in data.items() if not v.strip()]

    def _find_desc_key(self, headers: List[str]) -> Optional[str]:
        for h in headers:
            if h.lower() in {"item", "description", "product", "name"}:
                return h
        return headers[0] if headers else None