import re
from dataclasses import dataclass, field
from typing import List
from src.core.logger import log


@dataclass
class ExtractedEntities:
    filename: str
    invoice_no: str = ""
    date: str = ""
    order_id: str = ""
    customer_name: str = ""
    bill_to: str = ""
    ship_to: str = ""
    ship_mode: str = ""
    balance_due: str = ""
    subtotal: str = ""
    discount: str = ""
    discount_pct: str = ""
    shipping: str = ""
    total: str = ""
    currency: str = "USD"
    email: str = ""
    phone: str = ""
    notes: str = ""
    terms: str = ""
    items: List[dict] = field(default_factory=list)
    confidence: dict = field(default_factory=dict)


class EntityExtractor:

    INVOICE_NO_RE  = re.compile(r"#\s*(\d{4,6})", re.I)
    DATE_RE        = re.compile(r"Date[:\s]+([A-Za-z]+\s+\d{1,2}\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.I)
    ORDER_ID_RE    = re.compile(r"Order\s*ID\s*[:\-]?\s*([A-Z0-9\-]+)", re.I)
    SHIP_MODE_RE   = re.compile(r"Ship\s*Mode\s*[:\-]?\s*([A-Za-z\s]+?)(?:\n|$)", re.I)
    BALANCE_RE     = re.compile(r"Balance\s*Due\s*[:\-]?\s*(\$[\d,]+\.?\d*)", re.I)
    SUBTOTAL_RE    = re.compile(r"Subtotal\s*[:\-]?\s*(\$[\d,]+\.?\d*)", re.I)
    DISCOUNT_RE    = re.compile(r"Discount\s*(?:\((\d+)%\))?\s*[:\-]?\s*(\$[\d,]+\.?\d*)", re.I)
    SHIPPING_RE    = re.compile(r"Sh[i1]p[op]ing\s*[:\-]?\s*(\$[\d,]+\.?\d*)", re.I)
    TOTAL_RE       = re.compile(r"\bTotal\s*[:\-]?\s*(\$[\d,]+\.?\d*)", re.I)
    EMAIL_RE       = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    PHONE_RE       = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")
    NOTES_RE       = re.compile(r"Notes\s*[:\-]?\s*(.+?)(?:Terms|$)", re.I | re.DOTALL)
    TERMS_RE       = re.compile(r"Terms\s*[:\-]?\s*(.+?)$", re.I | re.DOTALL)
    AMOUNT_RE      = re.compile(r"\$[\d,]+\.?\d*")
    CURRENCY_RE    = re.compile(r"(\$|₹|€|£|USD|INR|EUR|GBP)")
    BILL_TO_NAME_RE = re.compile(r"Bill\s*T[oa]\s*:?\s*\n?\s*([A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+)", re.I)

    BAD_NAME_WORDS = {
        "ship ta", "ship to", "bill ta", "bill to", "balance due",
        "ship mode", "order id", "item quantity",
    }

    def extract(self, text, filename, items=None):
        log.info(f"Entity extraction: {filename}")
        entities = ExtractedEntities(filename=filename)
        if items:
            entities.items = [self._item_to_dict(i) for i in items]

        try:
            m = self.INVOICE_NO_RE.search(text)
            if m:
                entities.invoice_no = m.group(1).strip()
                entities.confidence["invoice_no"] = 0.95

            m = self.DATE_RE.search(text)
            if m:
                entities.date = m.group(1).strip()
                entities.confidence["date"] = 0.95

            m = self.ORDER_ID_RE.search(text)
            if m:
                entities.order_id = m.group(1).strip()
                entities.confidence["order_id"] = 0.95
                if not entities.invoice_no:
                    digits = re.findall(r"\d{4,6}", entities.order_id)
                    if digits:
                        entities.invoice_no = digits[-1]
                        entities.confidence["invoice_no"] = 0.70

            m = self.SHIP_MODE_RE.search(text)
            if m:
                entities.ship_mode = m.group(1).strip()
                entities.confidence["ship_mode"] = 0.90

            m = self.BALANCE_RE.search(text)
            if m:
                entities.balance_due = m.group(1).strip()
                entities.confidence["balance_due"] = 0.95

            m = self.SUBTOTAL_RE.search(text)
            if m:
                entities.subtotal = m.group(1).strip()
                entities.confidence["subtotal"] = 0.95

            m = self.DISCOUNT_RE.search(text)
            if m:
                entities.discount_pct = m.group(1) or ""
                entities.discount = m.group(2).strip()
                entities.confidence["discount"] = 0.90

            m = self.SHIPPING_RE.search(text)
            if m:
                entities.shipping = m.group(1).strip()
                entities.confidence["shipping"] = 0.95

            m = self.TOTAL_RE.search(text)
            if m:
                entities.total = m.group(1).strip()
                entities.confidence["total"] = 0.95

            m = self.EMAIL_RE.search(text)
            if m:
                entities.email = m.group(0)
                entities.confidence["email"] = 0.98

            m = self.PHONE_RE.search(text)
            if m:
                entities.phone = m.group(1).strip()
                entities.confidence["phone"] = 0.80

            m = self.CURRENCY_RE.search(text)
            if m:
                sym = m.group(1)
                entities.currency = {"\$": "USD", "₹": "INR", "€": "EUR", "£": "GBP"}.get(sym, sym)

            m = self.NOTES_RE.search(text)
            if m:
                entities.notes = m.group(1).strip()[:200]
                entities.confidence["notes"] = 0.85

            m = self.TERMS_RE.search(text)
            if m:
                entities.terms = m.group(1).strip()[:200]
                entities.confidence["terms"] = 0.85

            name_from_text = self._name_from_text(text)
            if name_from_text:
                entities.customer_name = name_from_text
                entities.confidence["customer_name"] = 0.85
            else:
                entities.customer_name = self._name_from_filename(filename)
                entities.confidence["customer_name"] = 0.70

            log.debug(
                f"  OK {filename} | invoice={entities.invoice_no} | "
                f"date={entities.date} | total={entities.total} | items={len(entities.items)}"
            )

        except Exception as e:
            log.error(f"EntityExtractor error on {filename}: {e}")

        return entities

    def _name_from_text(self, text):
        m = self.BILL_TO_NAME_RE.search(text)
        if m:
            name = m.group(1).strip()
            if name.lower() not in self.BAD_NAME_WORDS and len(name.split()) >= 2:
                return name
        return ""

    def _name_from_filename(self, filename):
        stem = filename.replace(".pdf", "").replace(".PDF", "")
        stem = re.sub(r"(?i)test_scanned_|test_", "", stem)
        parts = stem.split("_")
        if len(parts) >= 3:
            return parts[1].strip()
        elif len(parts) == 2:
            return parts[1].strip()
        return ""

    def _item_to_dict(self, item):
        return {
            "description": getattr(item, "description", ""),
            "quantity": getattr(item, "quantity", ""),
            "rate": getattr(item, "rate", ""),
            "amount": getattr(item, "amount", ""),
            "category": getattr(item, "category", ""),
            "product_code": getattr(item, "product_code", ""),
        }
