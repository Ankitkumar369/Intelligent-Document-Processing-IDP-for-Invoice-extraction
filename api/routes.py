import tempfile
import time
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

import pdfplumber
from src.ingestion.file_detector import FileDetector
from src.ocr.preprocessor import ImagePreprocessor
from src.ocr.ocr_engine import OCREngine
from src.extraction.multiline_handler import MultilineHandler
from src.entity.entity_extractor import EntityExtractor
from src.normalization.normalizer import Normalizer
from src.validation.validator import Validator
from src.scoring.confidence_scorer import ConfidenceScorer
from src.core.logger import log

router = APIRouter()

detector = FileDetector()
preprocessor = ImagePreprocessor()
ocr_engine = OCREngine()
multiline = MultilineHandler()
entity_extractor = EntityExtractor()
normalizer = Normalizer()
validator = Validator()
scorer = ConfidenceScorer()

STATS = {"total_processed": 0, "total_success": 0, "total_failed": 0}


def process_single_pdf(filepath: str, filename: str) -> dict:
    doc_info = detector.detect(filepath)

    if doc_info.file_type == "unknown":
        raise ValueError("Unsupported or unreadable file type")

    ocr_confidence = 1.0

    if doc_info.is_scanned:
        img = preprocessor.pdf_page_to_image(filepath, page_no=0)
        processed_img = preprocessor.preprocess(img)
        ocr_result = ocr_engine.extract(processed_img)
        text = ocr_result.full_text
        ocr_confidence = ocr_result.avg_confidence / 100.0
    else:
        with pdfplumber.open(filepath) as pdf:
            text = pdf.pages[0].extract_text() or ""

    items_result = multiline.extract_items(filepath)
    entities = entity_extractor.extract(text, filename, items_result.items)
    normalized = normalizer.normalize(entities, filename)
    report = validator.validate(normalized, filename)
    doc_score = scorer.score(normalized, report, entities.confidence, ocr_confidence)

    return {
        "filename": normalized.filename,
        "is_scanned": doc_info.is_scanned,
        "invoice_no": normalized.invoice_no,
        "date": normalized.date_normalized,
        "order_id": normalized.order_id,
        "customer_name": normalized.customer_name,
        "ship_mode": normalized.ship_mode,
        "currency": normalized.currency,
        "financials": {
            "subtotal": normalized.subtotal,
            "discount": normalized.discount,
            "discount_pct": normalized.discount_pct,
            "shipping": normalized.shipping,
            "total": normalized.total,
            "balance_due": normalized.balance_due,
        },
        "items": normalized.items,
        "notes": normalized.notes,
        "terms": normalized.terms,
        "validation": {
            "passed": report.passed,
            "score": report.score,
            "issues": [
                {"field": i.field, "type": i.issue_type, "message": i.message, "severity": i.severity}
                for i in report.issues
            ],
        },
        "confidence": {
            "overall_score": doc_score.overall_score,
            "overall_label": doc_score.overall_label,
        },
    }


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "IDP Invoice Processing API"}


@router.get("/stats")
def get_stats():
    return STATS


@router.post("/process/single")
async def process_single(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    tmp_path = None
    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        result = process_single_pdf(tmp_path, file.filename)

        STATS["total_processed"] += 1
        STATS["total_success"] += 1

        return JSONResponse(content=result)

    except Exception as e:
        STATS["total_processed"] += 1
        STATS["total_failed"] += 1
        log.error(f"API error processing {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


@router.post("/process/bulk")
async def process_bulk(files: list[UploadFile] = File(...)):
    if len(files) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 files per bulk request")

    results = []
    start = time.time()

    for file in files:
        tmp_path = None
        try:
            if not file.filename.lower().endswith(".pdf"):
                results.append({"filename": file.filename, "error": "Not a PDF file"})
                continue

            content = await file.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            result = process_single_pdf(tmp_path, file.filename)
            results.append(result)

            STATS["total_processed"] += 1
            STATS["total_success"] += 1

        except Exception as e:
            results.append({"filename": file.filename, "error": str(e)})
            STATS["total_processed"] += 1
            STATS["total_failed"] += 1
            log.error(f"API bulk error on {file.filename}: {e}")

        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

    elapsed = round(time.time() - start, 2)
    success_count = sum(1 for r in results if "error" not in r)

    return {
        "total_files": len(files),
        "success_count": success_count,
        "failed_count": len(files) - success_count,
        "elapsed_seconds": elapsed,
        "results": results,
    }
