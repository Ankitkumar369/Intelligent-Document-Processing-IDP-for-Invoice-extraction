import pytest
from src.extraction.multiline_handler import MultilineHandler, InvoiceItem
from src.extraction.row_reconstructor import RowReconstructor
from src.extraction.column_detector import ColumnDetector
from src.entity.entity_extractor import EntityExtractor


class TestMultilineHandler:

    def test_build_item_from_complete_row(self):
        handler = MultilineHandler()
        cells = ["Office Chair", "2", "$50.00", "$100.00"]
        item = handler._build_item(cells)
        assert item.description == "Office Chair"
        assert item.quantity == "2"
        assert item.amount == "$100.00"

    def test_is_summary_row_detects_subtotal(self):
        handler = MultilineHandler()
        assert handler._is_summary_row(["Subtotal:", "$48.71"]) is True
        assert handler._is_summary_row(["Item A", "2", "$10.00"]) is False

    def test_is_continuation_row(self):
        handler = MultilineHandler()
        assert handler._is_continuation_row(["Chairs, Furniture, FUR-CH-4421", "", ""]) is True
        assert handler._is_continuation_row(["Item B", "1", "$5.00"]) is False


class TestRowReconstructor:

    def test_merges_partial_rows(self):
        rr = RowReconstructor()
        raw_rows = [
            ["Global Chair", "", ""],
            ["", "1", "$48.71"],
        ]
        headers = ["Item", "Quantity", "Amount"]
        result = rr.reconstruct(raw_rows, headers, "test.pdf")
        assert result.reconstructed_rows == 1
        assert result.rows[0].data["Item"] == "Global Chair"
        assert result.rows[0].data["Quantity"] == "1"

    def test_complete_row_stays_separate(self):
        rr = RowReconstructor()
        raw_rows = [
            ["Item A", "1", "$10.00"],
            ["Item B", "2", "$20.00"],
        ]
        headers = ["Item", "Quantity", "Amount"]
        result = rr.reconstruct(raw_rows, headers, "test.pdf")
        assert result.reconstructed_rows == 2


class TestColumnDetector:

    def test_detects_known_headers(self):
        cd = ColumnDetector()
        raw_table = [
            ["Item", "Quantity", "Rate", "Amount"],
            ["Chair", "1", "$50.00", "$50.00"],
        ]
        result = cd.detect(raw_table, "test.pdf")
        assert result.schema is not None
        assert "Item" in result.schema.headers
        assert result.schema.confidence > 0.5

    def test_infers_amount_column_type(self):
        cd = ColumnDetector()
        values = ["$10.00", "$20.00", "$30.00"]
        col_type = cd._infer_type(values)
        assert col_type == "amount"


class TestEntityExtractor:

    def test_extracts_invoice_number(self):
        ee = EntityExtractor()
        text = "SuperStore INVOICE\n# 36258\nDate: Mar 06 2012"
        entities = ee.extract(text, "test.pdf")
        assert entities.invoice_no == "36258"

    def test_extracts_total_amount(self):
        ee = EntityExtractor()
        text = "Subtotal: $48.71\nTotal: $50.10"
        entities = ee.extract(text, "test.pdf")
        assert entities.total == "$50.10"

    def test_extracts_date(self):
        ee = EntityExtractor()
        text = "Date: Mar 06 2012"
        entities = ee.extract(text, "test.pdf")
        assert entities.date == "Mar 06 2012"

    def test_customer_name_from_filename(self):
        ee = EntityExtractor()
        name = ee._name_from_filename("invoice_Aaron Bergman_36258.pdf")
        assert name == "Aaron Bergman"
