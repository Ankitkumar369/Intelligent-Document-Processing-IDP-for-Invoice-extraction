import time
import pdfplumber
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

from src.core.config import INPUT_DIR, BATCH_SIZE
from src.core.logger import log
from src.core.audit import AuditTrail
from src.ingestion.file_detector import FileDetector
from src.ingestion.batch_loader import BatchLoader
from src.ocr.preprocessor import ImagePreprocessor
from src.ocr.ocr_engine import OCREngine
from src.extraction.multiline_handler import MultilineHandler
from src.entity.entity_extractor import EntityExtractor
from src.normalization.normalizer import Normalizer
from src.validation.validator import Validator
from src.scoring.confidence_scorer import ConfidenceScorer
from src.output.json_writer import JSONWriter
from src.output.csv_writer import CSVWriter
from src.output.excel_writer import ExcelWriter
from src.rag.rag_processor import RAGProcessor
from src.error_handling.error_recovery import ErrorRecovery


@dataclass
class PipelineResult:
    total_files: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    ocr_used: int = 0
    elapsed_sec: float = 0.0
    failed_files: List[str] = field(default_factory=list)


class IDPPipeline:

    def __init__(self):
        self.detector = FileDetector()
        self.loader = BatchLoader()
        self.preprocessor = ImagePreprocessor()
        self.ocr_engine = OCREngine()
        self.multiline = MultilineHandler()
        self.entity_extractor = EntityExtractor()
        self.normalizer = Normalizer()
        self.validator = Validator()
        self.scorer = ConfidenceScorer()
        self.json_writer = JSONWriter()
        self.csv_writer = CSVWriter()
        self.excel_writer = ExcelWriter()
        self.rag = RAGProcessor()
        self.error_recovery = ErrorRecovery()
        self.audit = AuditTrail()

    def run(self, limit=None):
        start_time = time.time()
        log.info("=" * 60)
        log.info("IDP PIPELINE STARTED")
        log.info("=" * 60)

        files = self.loader.discover_files([".pdf"])
        if limit:
            files = files[:limit]

        result = PipelineResult(total_files=len(files))

        for idx, filepath in enumerate(files, start=1):
            filename = filepath.name
            file_id = self.audit.log_file_start(filename)

            log.info(f"[{idx}/{len(files)}] Processing: {filename}")

            try:
                if self.error_recovery.is_corrupt_file(filepath):
                    log.warning(f"  Skipping corrupt/empty file: {filename}")
                    result.skipped += 1
                    self.loader.mark_skipped()
                    continue

                doc_info = self.detector.detect(str(filepath))

                if doc_info.file_type == "unknown":
                    result.skipped += 1
                    self.loader.mark_skipped()
                    continue

                ocr_confidence = 1.0

                if doc_info.is_scanned:
                    # SCANNED PATH - use OCR
                    log.info(f"  Scanned document detected - using OCR engine")
                    img = self.preprocessor.pdf_page_to_image(str(filepath), page_no=0)
                    processed_img = self.preprocessor.preprocess(img)
                    ocr_result = self.ocr_engine.extract(processed_img)
                    text = ocr_result.full_text
                    ocr_confidence = ocr_result.avg_confidence / 100.0
                    result.ocr_used += 1
                else:
                    # DIGITAL PATH - use pdfplumber
                    with pdfplumber.open(str(filepath)) as pdf:
                        text = pdf.pages[0].extract_text() or ""

                items_result = self.multiline.extract_items(str(filepath))

                # If digital extraction got no items and doc is scanned, items stay empty (acceptable)
                entities = self.entity_extractor.extract(
                    text, filename, items_result.items
                )

                normalized = self.normalizer.normalize(entities, filename)

                validation_report = self.validator.validate(normalized, filename)

                doc_score = self.scorer.score(
                    normalized, validation_report,
                    entities.confidence,
                    ocr_confidence=ocr_confidence,
                )

                self.json_writer.write(normalized, doc_score, validation_report)
                self.csv_writer.write(normalized, doc_score, validation_report)
                self.csv_writer.write_items_csv(normalized)
                self.excel_writer.add_record(normalized, doc_score, validation_report)
                self.rag.process(normalized, doc_score, str(filepath))

                self.audit.log_file_success(
                    file_id, filename, len(normalized.items) + 10
                )
                self.audit.log_validation(
                    file_id, filename,
                    validation_report.passed,
                    [i.message for i in validation_report.issues],
                )

                result.success += 1
                self.loader.mark_processed()

                if idx % 50 == 0 or idx == len(files):
                    log.info(f"Progress: {idx}/{len(files)} | Success: {result.success} | Failed: {result.failed}")

            except Exception as e:
                self.error_recovery.handle(filename, "pipeline", e)
                self.audit.log_file_failure(file_id, filename, str(e))
                result.failed += 1
                result.failed_files.append(filename)
                self.loader.mark_failed()

        excel_path = self.excel_writer.save()

        result.elapsed_sec = round(time.time() - start_time, 2)

        self.audit.log_session_end(result.total_files, result.success, result.failed)
        self.loader.print_summary()

        log.info("=" * 60)
        log.info("IDP PIPELINE COMPLETED")
        log.info(f"  Total      : {result.total_files}")
        log.info(f"  Success    : {result.success}")
        log.info(f"  Failed     : {result.failed}")
        log.info(f"  Skipped    : {result.skipped}")
        log.info(f"  OCR Used   : {result.ocr_used}")
        log.info(f"  Time       : {result.elapsed_sec}s")
        log.info(f"  Excel      : {excel_path}")
        log.info("=" * 60)

        return result
