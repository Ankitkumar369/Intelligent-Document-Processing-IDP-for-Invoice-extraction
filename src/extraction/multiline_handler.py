# src/extraction/multiline_handler.py

import re
import pdfplumber
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from src.core.logger import log


@dataclass
class InvoiceItem:
    description : str
    quantity    : str
    rate        : str
    amount      : str
    category    : str = ""
    product_code: str = ""


@dataclass
class MultilineResult:
    filename    : str
    items       : List[InvoiceItem] = field(default_factory=list)
    raw_rows    : List[List[str]]   = field(default_factory=list)
    error       : str = ""


class MultilineHandler:

    AMOUNT_RE    = re.compile(r"\$[\d,]+\.?\d*")
    PROD_CODE_RE = re.compile(r"[A-Z]{2,}-[A-Z]{2,}-\d{4,}")
    QTY_RE       = re.compile(r"^\d+$")

    def extract_items(self, filepath: str) -> MultilineResult:
        path = Path(filepath)
        log.info(f"Multiline handling: {path.name}")
        try:
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    items = self._extract_from_page(page)
                    if items:
                        return MultilineResult(filename=path.name, items=items)
            return MultilineResult(filename=path.name)
        except Exception as e:
            log.error(f"MultilineHandler error on {path.name}: {e}")
            return MultilineResult(filename=path.name, error=str(e))

    def _extract_from_page(self, page) -> List[InvoiceItem]:
        settings = {
            "vertical_strategy"  : "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance"     : 5,
        }
        tables = page.extract_tables(settings)
        if not tables:
            tables = page.extract_tables({
                "vertical_strategy"  : "text",
                "horizontal_strategy": "text",
            })
        items = []
        for table in tables:
            items.extend(self._process_table_rows(table))
        if not items:
            items = self._text_based_extraction(page)
        return items

    def _process_table_rows(self, table: list) -> List[InvoiceItem]:
        if not table:
            return []
        items    = []
        pending  = None
        in_items = False
        for row in table:
            if row is None:
                continue
            cells = [str(c).strip() if c else "" for c in row]
            if not any(cells):
                continue
            if self._is_header_row(cells):
                in_items = True
                continue
            if self._is_summary_row(cells):
                if pending is not None:
                    items.append(pending)
                    pending = None
                in_items = False
                continue
            if not in_items:
                continue
            if self._is_main_item_row(cells):
                if pending is not None:
                    items.append(pending)
                pending = self._build_item(cells)
            elif pending is not None and self._is_continuation_row(cells):
                pending = self._merge_continuation(pending, cells)
        if pending is not None:
            items.append(pending)
        return items

    def _text_based_extraction(self, page) -> List[InvoiceItem]:
        text  = page.extract_text() or ""
        items = []
        lines = text.split("\n")
        in_items = False
        pending  = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if re.search(r"\bItem\b.*\bQuantity\b|\bItem\b.*\bQty\b", line, re.I):
                in_items = True
                continue
            if in_items and re.search(r"Subtotal|Discount|Shipping|Total|Notes|Terms", line, re.I):
                if pending is not None:
                    items.append(pending)
                    pending = None
                break
            if not in_items:
                continue
            amounts = self.AMOUNT_RE.findall(line)
            if len(amounts) >= 2:
                if pending is not None:
                    items.append(pending)
                pending = self._parse_text_line(line)
            elif pending is not None and self.PROD_CODE_RE.search(line):
                cat_parts = line.split(",")
                if len(cat_parts) >= 2:
                    pending.category     = cat_parts[0].strip()
                    pending.product_code = cat_parts[-1].strip()
        if pending is not None:
            items.append(pending)
        return items

    def _is_header_row(self, cells: list) -> bool:
        headers = {"item", "quantity", "rate", "amount", "qty", "description"}
        matches = sum(1 for c in cells if c.lower() in headers)
        return matches >= 2

    def _is_summary_row(self, cells: list) -> bool:
        summary = {"subtotal", "discount", "shipping", "total", "tax", "notes", "terms"}
        return any(c.lower().split(":")[0].strip() in summary for c in cells)

    def _is_main_item_row(self, cells: list) -> bool:
        has_amount = any(self.AMOUNT_RE.search(c) for c in cells)
        has_text   = any(len(c) > 3 and not self.AMOUNT_RE.search(c) for c in cells)
        return has_amount and has_text

    def _is_continuation_row(self, cells: list) -> bool:
        amounts = sum(1 for c in cells if self.AMOUNT_RE.search(c))
        empty   = sum(1 for c in cells if not c.strip())
        return amounts == 0 and empty >= len(cells) - 1

    def _build_item(self, cells: list) -> InvoiceItem:
        amounts    = [c for c in cells if self.AMOUNT_RE.search(c)]
        qty_cells  = [c for c in cells if self.QTY_RE.match(c.strip())]
        desc_cells = [c for c in cells if c and not self.AMOUNT_RE.search(c) and not self.QTY_RE.match(c.strip())]
        return InvoiceItem(
            description = " ".join(desc_cells),
            quantity    = qty_cells[0] if qty_cells else "",
            rate        = amounts[0]  if len(amounts) >= 1 else "",
            amount      = amounts[-1] if len(amounts) >= 1 else "",
        )

    def _merge_continuation(self, item: InvoiceItem, cells: list) -> InvoiceItem:
        text_parts = [c for c in cells if c.strip()]
        if text_parts:
            combined   = " ".join(text_parts)
            prod_match = self.PROD_CODE_RE.search(combined)
            if prod_match:
                item.product_code = prod_match.group()
            parts = combined.split(",")
            if len(parts) >= 2:
                item.category = parts[0].strip()
            else:
                item.description += " " + combined
        return item

    def _parse_text_line(self, line: str) -> InvoiceItem:
        amounts = self.AMOUNT_RE.findall(line)
        clean   = self.AMOUNT_RE.sub("", line).strip()
        parts   = clean.split()
        qty     = ""
        desc    = clean
        if parts and self.QTY_RE.match(parts[-1]):
            qty  = parts[-1]
            desc = " ".join(parts[:-1])
        return InvoiceItem(
            description = desc.strip(),
            quantity    = qty,
            rate        = amounts[0]  if len(amounts) >= 1 else "",
            amount      = amounts[-1] if amounts else "",
        )
