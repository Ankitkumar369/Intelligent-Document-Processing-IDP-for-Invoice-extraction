import pytest
from pathlib import Path
from src.core.config import INPUT_DIR
from src.core.pipeline import IDPPipeline
from src.ingestion.file_detector import FileDetector
from src.ingestion.batch_loader import BatchLoader


class TestFileDetector:

    def test_detects_pdf_files(self):
        pdfs = list(INPUT_DIR.glob("*.pdf"))
        if not pdfs:
            pytest.skip("No PDFs in input directory")
        detector = FileDetector()
        info = detector.detect(str(pdfs[0]))
        assert info.file_type == "pdf"
        assert info.page_count >= 1


class TestBatchLoader:

    def test_discovers_pdf_files(self):
        loader = BatchLoader()
        files = loader.discover_files([".pdf"])
        assert isinstance(files, list)

    def test_batches_are_correct_size(self):
        loader = BatchLoader(batch_size=10)
        files = loader.discover_files([".pdf"])
        if len(files) < 10:
            pytest.skip("Not enough files to test batching")
        batches = list(loader.get_batches(files))
        assert len(batches[0]) == 10


class TestPipelineIntegration:

    def test_pipeline_processes_files_successfully(self):
        pdfs = list(INPUT_DIR.glob("*.pdf"))
        if len(pdfs) < 3:
            pytest.skip("Not enough PDFs for integration test")

        pipeline = IDPPipeline()
        result = pipeline.run(limit=3)

        assert result.total_files == 3
        assert result.success >= 1
        assert result.failed == 0

    def test_pipeline_handles_empty_limit(self):
        pipeline = IDPPipeline()
        result = pipeline.run(limit=1)
        assert result.total_files == 1
