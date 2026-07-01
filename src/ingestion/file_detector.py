# src/ingestion/file_detector.py

import os
import fitz                      # PyMuPDF
import pdfplumber
from pathlib import Path
from dataclasses import dataclass, field
from src.core.config import SUPPORTED_EXTENSIONS, MIN_TEXT_LENGTH
from src.core.logger import log


@dataclass
class DocumentInfo:
    """Ek document ki saari detected properties."""
    filepath        : str
    filename        : str
    file_type       : str          # pdf, image, excel, csv, word, text
    file_size_kb    : float
    extension       : str
    is_scanned      : bool         # True = OCR chahiye
    page_count      : int
    language        : str
    orientation     : str          # portrait / landscape
    quality         : str          # good / low / unknown
    has_text_layer  : bool
    has_tables      : bool
    has_images      : bool
    error           : str          = ""
    raw_text_sample : str          = ""


class FileDetector:
    """
    PHASE 1 — Document Ingestion
    Har file ka type, format, quality aur properties detect karta hai.
    """

    def detect(self, filepath: str) -> DocumentInfo:
        path = Path(filepath)
        log.info(f"Detecting file: {path.name}")

        # Basic info
        ext          = path.suffix.lower()
        file_size_kb = round(path.stat().st_size / 1024, 2)
        file_type    = self._get_file_type(ext)

        if file_type == "unknown":
            log.warning(f"Unsupported file type: {ext}")
            return self._unknown_doc(filepath, path.name, ext, file_size_kb)

        # PDF specific detection
        if file_type == "pdf":
            return self._detect_pdf(filepath, path.name, ext, file_size_kb)

        # Non-PDF files
        return DocumentInfo(
            filepath       = filepath,
            filename       = path.name,
            file_type      = file_type,
            file_size_kb   = file_size_kb,
            extension      = ext,
            is_scanned     = False,
            page_count     = 1,
            language       = "eng",
            orientation    = "portrait",
            quality        = "good",
            has_text_layer = True,
            has_tables     = False,
            has_images     = False,
        )

    # ── PDF Detection ─────────────────────────────────────────
    def _detect_pdf(self, filepath, filename, ext, file_size_kb) -> DocumentInfo:
        try:
            page_count     = 0
            has_text_layer = False
            has_images     = False
            has_tables     = False
            raw_sample     = ""
            orientation    = "portrait"
            quality        = "good"

            # PyMuPDF se basic info
            with fitz.open(filepath) as doc:
                page_count = len(doc)

                for i, page in enumerate(doc):
                    if i >= 3:   # Sirf pehle 3 pages check karo
                        break

                    text = page.get_text("text").strip()
                    if len(text) >= MIN_TEXT_LENGTH:
                        has_text_layer = True
                        if not raw_sample:
                            raw_sample = text[:300]

                    # Image check
                    if page.get_images():
                        has_images = True

                    # Orientation check
                    rect = page.rect
                    if rect.width > rect.height:
                        orientation = "landscape"

            # pdfplumber se table check
            with pdfplumber.open(filepath) as pdf:
                for i, page in enumerate(pdf.pages):
                    if i >= 2:
                        break
                    tables = page.find_tables()
                    if tables:
                        has_tables = True
                        break

            # Scanned detect
            is_scanned = not has_text_layer

            # Quality
            if is_scanned:
                quality = "scanned"
            elif len(raw_sample) < 50:
                quality = "low"

            info = DocumentInfo(
                filepath       = filepath,
                filename       = filename,
                file_type      = "pdf",
                file_size_kb   = file_size_kb,
                extension      = ext,
                is_scanned     = is_scanned,
                page_count     = page_count,
                language       = "eng",
                orientation    = orientation,
                quality        = quality,
                has_text_layer = has_text_layer,
                has_tables     = has_tables,
                has_images     = has_images,
                raw_text_sample= raw_sample,
            )

            log.debug(
                f"  ✅ {filename} | pages={page_count} | "
                f"scanned={is_scanned} | tables={has_tables} | "
                f"quality={quality}"
            )
            return info

        except Exception as e:
            log.error(f"FileDetector error on {filename}: {e}")
            return self._unknown_doc(filepath, filename, ext, file_size_kb, str(e))

    # ── Helpers ───────────────────────────────────────────────
    def _get_file_type(self, ext: str) -> str:
        for ftype, exts in SUPPORTED_EXTENSIONS.items():
            if ext in exts:
                return ftype
        return "unknown"

    def _unknown_doc(self, filepath, filename, ext, size, error="") -> DocumentInfo:
        return DocumentInfo(
            filepath       = filepath,
            filename       = filename,
            file_type      = "unknown",
            file_size_kb   = size,
            extension      = ext,
            is_scanned     = False,
            page_count     = 0,
            language       = "unknown",
            orientation    = "unknown",
            quality        = "unknown",
            has_text_layer = False,
            has_tables     = False,
            has_images     = False,
            error          = error,
        )