# src/validation/validator.py

import re
from dataclasses import dataclass, field
from typing import List, Dict
from src.core.config import VALIDATION_RULES
from src.core.logger import log


@dataclass
class ValidationIssue:
    """Ek validation problem."""
    field       : str
    issue_type  : str    # missing / invalid / mismatch / duplicate
    message     : str
    severity    : str    # error / warning / info


@dataclass
class ValidationReport:
    """Ek invoice ka validation report."""
    filename    : str
    passed      : bool
    score       : float          # 0.0 - 1.0
    issues      : List[ValidationIssue] = field(default_factory=list)
    summary     : Dict[str, int]        = field(default_factory=dict)


class Validator:
    """
    PHASE 11 — Validation Engine

    Validates:
    - Required fields present
    - Amount formats correct
    - Date format valid
    - Math checks (subtotal + shipping - discount = total)
    - Duplicate items
    - Schema compliance
    """

    DATE_RE   = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    AMOUNT_RE = re.compile(r"^\d+(\.\d{1,2})?$")

    def validate(self, normalized, filename: str) -> ValidationReport:
        log.info(f"Validating: {filename}")

        issues  = []

        # ── 1. Required Fields ────────────────────────────────
        issues += self._check_required_fields(normalized)

        # ── 2. Date Format ────────────────────────────────────
        issues += self._check_date(normalized.date_normalized)

        # ── 3. Amount Formats ─────────────────────────────────
        issues += self._check_amounts(normalized)

        # ── 4. Math Validation ────────────────────────────────
        issues += self._check_math(normalized)

        # ── 5. Items Validation ───────────────────────────────
        issues += self._check_items(normalized.items)

        # ── 6. Duplicate Items ────────────────────────────────
        issues += self._check_duplicates(normalized.items)

        # ── Score ─────────────────────────────────────────────
        errors   = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")
        score    = max(0.0, 1.0 - (errors * 0.15) - (warnings * 0.05))
        passed   = errors == 0

        summary = {
            "errors"  : errors,
            "warnings": warnings,
            "info"    : sum(1 for i in issues if i.severity == "info"),
        }

        report = ValidationReport(
            filename = filename,
            passed   = passed,
            score    = round(score, 2),
            issues   = issues,
            summary  = summary,
        )

        status = "✅ PASSED" if passed else "❌ FAILED"
        log.debug(
            f"  {status} | {filename} | "
            f"score={score:.2f} | "
            f"errors={errors} | warnings={warnings}"
        )
        return report

    # ── Validators ────────────────────────────────────────────
    def _check_required_fields(self, normalized) -> List[ValidationIssue]:
        issues = []
        checks = {
            "invoice_no"   : normalized.invoice_no,
            "date"         : normalized.date_normalized,
            "customer_name": normalized.customer_name,
            "total"        : normalized.total,
        }
        for field_name, value in checks.items():
            if not value and value != 0.0:
                issues.append(ValidationIssue(
                    field      = field_name,
                    issue_type = "missing",
                    message    = f"Required field '{field_name}' is missing",
                    severity   = "error",
                ))
        return issues

    def _check_date(self, date_str: str) -> List[ValidationIssue]:
        issues = []
        if not date_str:
            return issues
        if not self.DATE_RE.match(date_str):
            issues.append(ValidationIssue(
                field      = "date",
                issue_type = "invalid",
                message    = f"Date '{date_str}' not in YYYY-MM-DD format",
                severity   = "warning",
            ))
        return issues

    def _check_amounts(self, normalized) -> List[ValidationIssue]:
        issues = []
        amount_fields = {
            "subtotal"   : normalized.subtotal,
            "total"      : normalized.total,
            "shipping"   : normalized.shipping,
            "discount"   : normalized.discount,
            "balance_due": normalized.balance_due,
        }
        for fname, val in amount_fields.items():
            if val < 0:
                issues.append(ValidationIssue(
                    field      = fname,
                    issue_type = "invalid",
                    message    = f"'{fname}' cannot be negative: {val}",
                    severity   = "error",
                ))
            if val > 1_000_000:
                issues.append(ValidationIssue(
                    field      = fname,
                    issue_type = "invalid",
                    message    = f"'{fname}' suspiciously large: {val}",
                    severity   = "warning",
                ))
        return issues

    def _check_math(self, normalized) -> List[ValidationIssue]:
        issues = []
        if normalized.subtotal <= 0:
            return issues

        # Expected: subtotal - discount + shipping ≈ total
        expected = round(
            normalized.subtotal
            - normalized.discount
            + normalized.shipping,
            2
        )
        actual = normalized.total
        diff   = abs(expected - actual)

        if diff > 1.0:
            issues.append(ValidationIssue(
                field      = "total",
                issue_type = "mismatch",
                message    = (
                    f"Math check failed: "
                    f"subtotal({normalized.subtotal}) "
                    f"- discount({normalized.discount}) "
                    f"+ shipping({normalized.shipping}) "
                    f"= {expected} ≠ total({actual})"
                ),
                severity   = "warning",
            ))
        return issues

    def _check_items(self, items: list) -> List[ValidationIssue]:
        issues = []
        if not items:
            issues.append(ValidationIssue(
                field      = "items",
                issue_type = "missing",
                message    = "No line items found in invoice",
                severity   = "warning",
            ))
            return issues

        for i, item in enumerate(items):
            desc = item.get("description", "")
            amt  = item.get("amount", 0)
            if not desc:
                issues.append(ValidationIssue(
                    field      = f"items[{i}].description",
                    issue_type = "missing",
                    message    = f"Item {i+1} has no description",
                    severity   = "warning",
                ))
            if amt == 0:
                issues.append(ValidationIssue(
                    field      = f"items[{i}].amount",
                    issue_type = "invalid",
                    message    = f"Item {i+1} has zero amount",
                    severity   = "info",
                ))
        return issues

    def _check_duplicates(self, items: list) -> List[ValidationIssue]:
        issues = []
        seen   = set()
        for i, item in enumerate(items):
            desc = item.get("description", "").lower().strip()
            if desc and desc in seen:
                issues.append(ValidationIssue(
                    field      = f"items[{i}]",
                    issue_type = "duplicate",
                    message    = f"Duplicate item: '{desc}'",
                    severity   = "warning",
                ))
            seen.add(desc)
        return issues