import csv
from pathlib import Path
from src.core.config import OUTPUT_CSV_DIR, OUTPUT_CSV_FILENAME
from src.core.logger import log


class CSVWriter:

    HEADERS = [
        "filename", "invoice_no", "date", "order_id", "customer_name",
        "ship_mode", "currency", "subtotal", "discount", "discount_pct",
        "shipping", "total", "balance_due", "item_count",
        "validation_passed", "validation_score",
        "confidence_score", "confidence_label",
    ]

    def __init__(self):
        self.out_path = OUTPUT_CSV_DIR / OUTPUT_CSV_FILENAME
        self._ensure_header()

    def _ensure_header(self):
        if not self.out_path.exists():
            with open(self.out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.HEADERS)

    def write(self, normalized, doc_score, validation_report):
        try:
            row = [
                normalized.filename,
                normalized.invoice_no,
                normalized.date_normalized,
                normalized.order_id,
                normalized.customer_name,
                normalized.ship_mode,
                normalized.currency,
                normalized.subtotal,
                normalized.discount,
                normalized.discount_pct,
                normalized.shipping,
                normalized.total,
                normalized.balance_due,
                len(normalized.items),
                validation_report.passed,
                validation_report.score,
                doc_score.overall_score,
                doc_score.overall_label,
            ]
            with open(self.out_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)

            log.debug(f"  OK CSV row appended: {normalized.filename}")
            return str(self.out_path)

        except Exception as e:
            log.error(f"CSVWriter error on {normalized.filename}: {e}")
            return ""

    def write_items_csv(self, normalized):
        items_path = OUTPUT_CSV_DIR / "invoice_items.csv"
        is_new = not items_path.exists()
        try:
            with open(items_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if is_new:
                    writer.writerow([
                        "invoice_no", "filename", "description",
                        "quantity", "rate", "amount", "category", "product_code"
                    ])
                for item in normalized.items:
                    writer.writerow([
                        normalized.invoice_no,
                        normalized.filename,
                        item.get("description", ""),
                        item.get("quantity", ""),
                        item.get("rate", ""),
                        item.get("amount", ""),
                        item.get("category", ""),
                        item.get("product_code", ""),
                    ])
            return str(items_path)
        except Exception as e:
            log.error(f"CSVWriter items error: {e}")
            return ""
