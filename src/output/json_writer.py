# src/output/json_writer.py

import json
from pathlib import Path
from datetime import datetime
from src.core.config import OUTPUT_JSON_DIR
from src.core.logger import log


class JSONWriter:
    """
    PHASE 13 — Structured Output Generation (JSON)
    Har invoice ke liye ek clean JSON file banata hai.
    """

    def write(self, normalized, doc_score, validation_report) -> str:
        try:
            output = {
                "filename"        : normalized.filename,
                "processed_at"    : datetime.now().isoformat(),
                "invoice_no"      : normalized.invoice_no,
                "date"            : normalized.date_normalized,
                "order_id"        : normalized.order_id,
                "customer_name"   : normalized.customer_name,
                "ship_mode"       : normalized.ship_mode,
                "currency"        : normalized.currency,
                "financials"      : {
                    "subtotal"    : normalized.subtotal,
                    "discount"    : normalized.discount,
                    "discount_pct": normalized.discount_pct,
                    "shipping"    : normalized.shipping,
                    "total"       : normalized.total,
                    "balance_due" : normalized.balance_due,
                },
                "items"           : normalized.items,
                "notes"           : normalized.notes,
                "terms"           : normalized.terms,
                "validation"      : {
                    "passed" : validation_report.passed,
                    "score"  : validation_report.score,
                    "summary": validation_report.summary,
                    "issues" : [
                        {"field": i.field, "type": i.issue_type,
                         "message": i.message, "severity": i.severity}
                        for i in validation_report.issues
                    ],
                },
                "confidence"      : {
                    "overall_score": doc_score.overall_score,
                    "overall_label": doc_score.overall_label,
                    "fields": {
                        fs.field_name: {
                            "value": fs.value,
                            "score": fs.final_score,
                            "label": fs.confidence_label,
                        }
                        for fs in doc_score.field_scores
                    },
                },
            }

            out_name = Path(normalized.filename).stem + ".json"
            out_path = OUTPUT_JSON_DIR / out_name

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

            log.debug(f"  ✅ JSON written: {out_path.name}")
            return str(out_path)

        except Exception as e:
            log.error(f"JSONWriter error on {normalized.filename}: {e}")
            return ""