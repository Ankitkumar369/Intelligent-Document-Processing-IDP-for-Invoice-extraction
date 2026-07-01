# src/scoring/confidence_scorer.py

from dataclasses import dataclass, field
from typing import Dict, List
from src.core.config import CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW
from src.core.logger import log


@dataclass
class FieldScore:
    """Ek field ka confidence breakdown."""
    field_name      : str
    value           : str
    extraction_score: float    # Entity extraction ke time ka confidence
    validation_score: float    # Validation pass/fail ka effect
    final_score     : float
    confidence_label: str      # HIGH / MEDIUM / LOW
    source          : str      # regex / table / filename / computed


@dataclass
class DocumentScore:
    """Poore document ka overall confidence."""
    filename        : str
    field_scores    : List[FieldScore] = field(default_factory=list)
    overall_score   : float = 0.0
    overall_label   : str   = "LOW"
    extraction_source: str  = "pdfplumber"
    ocr_confidence  : float = 1.0       # Digital PDF = 1.0, OCR docs = actual OCR score
    validation_status: str  = "UNKNOWN"


class ConfidenceScorer:
    """
    PHASE 12 — Confidence Scoring

    Har field ke liye:
    - Extraction Confidence (kaise extract hua)
    - Validation Status (sahi hai ya nahi)
    - OCR Confidence (agar scanned document)
    - Final combined score
    """

    # Field source mapping
    FIELD_SOURCES = {
        "invoice_no"   : "regex",
        "date"         : "regex",
        "customer_name": "filename",
        "ship_mode"    : "regex",
        "order_id"     : "regex",
        "subtotal"     : "regex",
        "discount"     : "regex",
        "shipping"     : "regex",
        "total"        : "regex",
        "balance_due"  : "regex",
        "items"        : "table",
    }

    def score(
        self,
        normalized,
        validation_report,
        entity_confidence: Dict[str, float],
        ocr_confidence: float = 1.0,
    ) -> DocumentScore:

        log.info(f"Confidence scoring: {normalized.filename}")

        try:
            field_scores = []

            checks = {
                "invoice_no"   : normalized.invoice_no,
                "date"         : normalized.date_normalized,
                "customer_name": normalized.customer_name,
                "ship_mode"    : normalized.ship_mode,
                "order_id"     : normalized.order_id,
                "subtotal"     : str(normalized.subtotal),
                "discount"     : str(normalized.discount),
                "shipping"     : str(normalized.shipping),
                "total"        : str(normalized.total),
                "balance_due"  : str(normalized.balance_due),
            }

            for fname, value in checks.items():
                extraction_score = entity_confidence.get(fname, 0.5 if value else 0.0)
                validation_score = self._get_validation_score(fname, validation_report)
                final = self._combine_scores(extraction_score, validation_score, ocr_confidence)

                field_scores.append(FieldScore(
                    field_name       = fname,
                    value            = value,
                    extraction_score = round(extraction_score, 2),
                    validation_score = round(validation_score, 2),
                    final_score      = round(final, 2),
                    confidence_label = self._get_label(final),
                    source           = self.FIELD_SOURCES.get(fname, "computed"),
                ))

            # Items score
            items_score = 0.9 if normalized.items else 0.3
            field_scores.append(FieldScore(
                field_name       = "items",
                value            = f"{len(normalized.items)} items",
                extraction_score = items_score,
                validation_score = 1.0 if normalized.items else 0.5,
                final_score      = round(items_score * ocr_confidence, 2),
                confidence_label = self._get_label(items_score),
                source           = "table",
            ))

            overall = (
                sum(fs.final_score for fs in field_scores) / len(field_scores)
                if field_scores else 0.0
            )

            doc_score = DocumentScore(
                filename          = normalized.filename,
                field_scores      = field_scores,
                overall_score     = round(overall, 2),
                overall_label     = self._get_label(overall),
                ocr_confidence    = ocr_confidence,
                validation_status = "PASSED" if validation_report.passed else "FAILED",
            )

            log.debug(
                f"  ✅ {normalized.filename} | "
                f"overall={overall:.2f} | "
                f"label={doc_score.overall_label}"
            )
            return doc_score

        except Exception as e:
            log.error(f"ConfidenceScorer error: {e}")
            return DocumentScore(filename=normalized.filename)

    # ── Helpers ───────────────────────────────────────────────
    def _get_validation_score(self, field_name: str, report) -> float:
        """Field se related koi validation issue hai to score kam karo."""
        related_issues = [
            i for i in report.issues
            if field_name in i.field
        ]
        if not related_issues:
            return 1.0

        errors   = sum(1 for i in related_issues if i.severity == "error")
        warnings = sum(1 for i in related_issues if i.severity == "warning")
        return max(0.0, 1.0 - errors * 0.5 - warnings * 0.2)

    def _combine_scores(
        self,
        extraction: float,
        validation: float,
        ocr: float
    ) -> float:
        """Weighted combination of all confidence sources."""
        combined = (extraction * 0.5) + (validation * 0.3) + (ocr * 0.2)
        return min(1.0, max(0.0, combined))

    def _get_label(self, score: float) -> str:
        if score >= CONFIDENCE_HIGH:
            return "HIGH"
        elif score >= CONFIDENCE_MEDIUM:
            return "MEDIUM"
        elif score >= CONFIDENCE_LOW:
            return "LOW"
        return "VERY_LOW"