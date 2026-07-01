# src/normalization/normalizer.py

import re
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from src.core.config import DATE_FORMATS
from src.core.logger import log


@dataclass
class NormalizedInvoice:
    """Normalized invoice data."""
    filename        : str
    invoice_no      : str
    date_raw        : str
    date_normalized : str
    customer_name   : str
    ship_mode       : str
    balance_due_raw : str
    balance_due     : float
    subtotal_raw    : str
    subtotal        : float
    discount_raw    : str
    discount        : float
    discount_pct    : str
    shipping_raw    : str
    shipping        : float
    total_raw       : str
    total           : float
    currency        : str
    order_id        : str
    notes           : str
    terms           : str
    items           : list
    confidence      : dict


class Normalizer:
    """
    PHASE 10 — Data Normalization

    Standardizes:
    - Dates → YYYY-MM-DD
    - Amounts → float
    - Text → trimmed, cleaned
    - Currency → USD/INR/EUR
    """

    AMOUNT_RE  = re.compile(r"[\$₹€£]?\s*([\d,]+\.?\d*)")
    SPACES_RE  = re.compile(r"\s+")
    OCR_FIXES  = {
        "O": "0", "l": "1", "I": "1",
        "|": "1", "S": "5", "B": "8",
    }

    def normalize(self, entities, filename: str) -> NormalizedInvoice:
        log.info(f"Normalizing: {filename}")

        try:
            result = NormalizedInvoice(
                filename        = filename,
                invoice_no      = self._clean_text(entities.invoice_no),
                date_raw        = entities.date,
                date_normalized = self._normalize_date(entities.date),
                customer_name   = self._clean_name(entities.customer_name),
                ship_mode       = self._clean_text(entities.ship_mode),
                balance_due_raw = entities.balance_due,
                balance_due     = self._to_float(entities.balance_due),
                subtotal_raw    = entities.subtotal,
                subtotal        = self._to_float(entities.subtotal),
                discount_raw    = entities.discount,
                discount        = self._to_float(entities.discount),
                discount_pct    = self._clean_text(entities.discount_pct),
                shipping_raw    = entities.shipping,
                shipping        = self._to_float(entities.shipping),
                total_raw       = entities.total,
                total           = self._to_float(entities.total),
                currency        = entities.currency or "USD",
                order_id        = self._clean_text(entities.order_id),
                notes           = self._clean_text(entities.notes),
                terms           = self._clean_text(entities.terms),
                items           = self._normalize_items(entities.items),
                confidence      = entities.confidence,
            )

            log.debug(
                f"  ✅ {filename} | "
                f"date={result.date_normalized} | "
                f"total={result.total} | "
                f"items={len(result.items)}"
            )
            return result

        except Exception as e:
            log.error(f"Normalizer error on {filename}: {e}")
            return NormalizedInvoice(
                filename=filename, invoice_no="", date_raw="",
                date_normalized="", customer_name="", ship_mode="",
                balance_due_raw="", balance_due=0.0, subtotal_raw="",
                subtotal=0.0, discount_raw="", discount=0.0,
                discount_pct="", shipping_raw="", shipping=0.0,
                total_raw="", total=0.0, currency="USD",
                order_id="", notes="", terms="",
                items=[], confidence={},
            )

    # ── Date Normalization ────────────────────────────────────
    def _normalize_date(self, date_str: str) -> str:
        if not date_str:
            return ""
        date_str = date_str.strip()
        for fmt in DATE_FORMATS:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        # Return as-is if no format matches
        log.warning(f"Could not normalize date: '{date_str}'")
        return date_str

    # ── Amount Normalization ──────────────────────────────────
    def _to_float(self, amount_str: str) -> float:
        if not amount_str:
            return 0.0
        try:
            m = self.AMOUNT_RE.search(str(amount_str))
            if m:
                clean = m.group(1).replace(",", "")
                return round(float(clean), 2)
        except Exception:
            pass
        return 0.0

    # ── Text Cleaning ─────────────────────────────────────────
    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = str(text).strip()
        text = self.SPACES_RE.sub(" ", text)
        return text

    def _clean_name(self, name: str) -> str:
        if not name:
            return ""
        name = self._clean_text(name)
        # Title case
        return " ".join(w.capitalize() for w in name.split())

    # ── Item Normalization ────────────────────────────────────
    def _normalize_items(self, items: list) -> list:
        normalized = []
        for item in items:
            if isinstance(item, dict):
                normalized.append({
                    "description" : self._clean_text(item.get("description", "")),
                    "quantity"    : self._parse_qty(item.get("quantity", "")),
                    "rate"        : self._to_float(item.get("rate", "")),
                    "amount"      : self._to_float(item.get("amount", "")),
                    "category"    : self._clean_text(item.get("category", "")),
                    "product_code": self._clean_text(item.get("product_code", "")),
                })
        return normalized

    def _parse_qty(self, qty_str: str) -> int:
        try:
            return int(str(qty_str).strip())
        except Exception:
            return 0