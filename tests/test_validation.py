import pytest
from src.validation.validator import Validator
from src.normalization.normalizer import NormalizedInvoice


def make_invoice(**overrides):
    defaults = dict(
        filename="test.pdf", invoice_no="123", date_raw="Mar 06 2012",
        date_normalized="2012-03-06", customer_name="John Doe",
        ship_mode="First Class", balance_due_raw="$50.00", balance_due=50.0,
        subtotal_raw="$45.00", subtotal=45.0, discount_raw="$0", discount=0.0,
        discount_pct="", shipping_raw="$5.00", shipping=5.0,
        total_raw="$50.00", total=50.0, currency="USD", order_id="ORD-1",
        notes="", terms="", items=[{"description": "Item A", "amount": 50.0}],
        confidence={},
    )
    defaults.update(overrides)
    return NormalizedInvoice(**defaults)


class TestValidator:

    def test_passes_valid_invoice(self):
        validator = Validator()
        invoice = make_invoice()
        report = validator.validate(invoice, "test.pdf")
        assert report.passed is True
        assert report.score == 1.0

    def test_fails_on_missing_invoice_no(self):
        validator = Validator()
        invoice = make_invoice(invoice_no="")
        report = validator.validate(invoice, "test.pdf")
        assert report.passed is False
        assert any(i.field == "invoice_no" for i in report.issues)

    def test_warns_on_math_mismatch(self):
        validator = Validator()
        invoice = make_invoice(subtotal=100.0, total=50.0)
        report = validator.validate(invoice, "test.pdf")
        mismatch_issues = [i for i in report.issues if i.issue_type == "mismatch"]
        assert len(mismatch_issues) > 0

    def test_warns_on_empty_items(self):
        validator = Validator()
        invoice = make_invoice(items=[])
        report = validator.validate(invoice, "test.pdf")
        assert any(i.field == "items" for i in report.issues)

    def test_detects_duplicate_items(self):
        validator = Validator()
        items = [
            {"description": "Item A", "amount": 10.0},
            {"description": "Item A", "amount": 10.0},
        ]
        invoice = make_invoice(items=items)
        report = validator.validate(invoice, "test.pdf")
        dup_issues = [i for i in report.issues if i.issue_type == "duplicate"]
        assert len(dup_issues) > 0

    def test_rejects_negative_amount(self):
        validator = Validator()
        invoice = make_invoice(total=-10.0)
        report = validator.validate(invoice, "test.pdf")
        assert report.passed is False
