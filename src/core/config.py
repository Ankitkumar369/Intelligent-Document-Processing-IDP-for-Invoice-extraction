# src/core/config.py

import os
from pathlib import Path

# ============================================================
# BASE PATHS
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATA_DIR        = BASE_DIR / "data"
INPUT_DIR       = DATA_DIR / "input"
OUTPUT_DIR      = DATA_DIR / "output"

OUTPUT_JSON_DIR  = OUTPUT_DIR / "json"
OUTPUT_CSV_DIR   = OUTPUT_DIR / "csv"
OUTPUT_EXCEL_DIR = OUTPUT_DIR / "excel"
OUTPUT_RAG_DIR   = OUTPUT_DIR / "rag"
OUTPUT_LOGS_DIR  = OUTPUT_DIR / "logs"

# ============================================================
# AUTO CREATE DIRECTORIES
# ============================================================
for _dir in [
    INPUT_DIR, OUTPUT_JSON_DIR, OUTPUT_CSV_DIR,
    OUTPUT_EXCEL_DIR, OUTPUT_RAG_DIR, OUTPUT_LOGS_DIR
]:
    _dir.mkdir(parents=True, exist_ok=True)

# ============================================================
# SUPPORTED FILE TYPES
# ============================================================
SUPPORTED_EXTENSIONS = {
    "pdf"   : [".pdf"],
    "image" : [".jpg", ".jpeg", ".png", ".tiff", ".bmp"],
    "excel" : [".xlsx", ".xls"],
    "csv"   : [".csv"],
    "word"  : [".docx", ".doc"],
    "text"  : [".txt"],
}

# ============================================================
# BATCH PROCESSING
# ============================================================
BATCH_SIZE        = 50     # Ek baar mein kitne files process hon
MAX_WORKERS       = 4      # Parallel workers
RETRY_ATTEMPTS    = 3      # Failure pe retry count
RETRY_DELAY_SEC   = 2      # Retry ke beech delay

# ============================================================
# OCR SETTINGS
# ============================================================
OCR_ENGINE        = "tesseract"   # "tesseract" ya "easyocr"
OCR_LANGUAGE      = "eng"
OCR_DPI           = 300
OCR_CONFIDENCE_THRESHOLD = 60.0   # % se kam = low confidence

# ============================================================
# PDF EXTRACTION
# ============================================================
PDF_ENGINE        = "pdfplumber"  # Digital PDFs ke liye
MIN_TEXT_LENGTH   = 10            # Is se kam text = scanned maano

# ============================================================
# CONFIDENCE SCORING
# ============================================================
CONFIDENCE_HIGH   = 0.90
CONFIDENCE_MEDIUM = 0.70
CONFIDENCE_LOW    = 0.50

# ============================================================
# INVOICE FIELD SCHEMA
# (SuperStore invoices ke expected fields)
# ============================================================
REQUIRED_FIELDS = [
    "invoice_no",
    "date",
    "customer_name",
    "ship_mode",
    "balance_due",
    "order_id",
    "items",
    "subtotal",
    "total",
]

OPTIONAL_FIELDS = [
    "discount",
    "shipping",
    "tax",
    "notes",
    "terms",
    "bill_to",
    "ship_to",
]

# ============================================================
# DATE FORMATS TO DETECT
# ============================================================
DATE_FORMATS = [
    "%b %d %Y",    # Mar 06 2012
    "%d/%m/%Y",    # 06/03/2012
    "%m/%d/%Y",    # 03/06/2012
    "%Y-%m-%d",    # 2012-03-06
    "%d-%m-%Y",    # 06-03-2012
    "%B %d, %Y",   # March 06, 2012
]

# ============================================================
# OUTPUT SETTINGS
# ============================================================
OUTPUT_EXCEL_FILENAME  = "invoices_extracted.xlsx"
OUTPUT_CSV_FILENAME    = "invoices_extracted.csv"
OUTPUT_REPORT_FILENAME = "processing_report.xlsx"

# ============================================================
# LOGGING
# ============================================================
LOG_LEVEL         = "DEBUG"
LOG_ROTATION      = "10 MB"
LOG_RETENTION     = "7 days"
LOG_FILENAME      = OUTPUT_LOGS_DIR / "idp_system.log"

# ============================================================
# RAG SETTINGS
# ============================================================
RAG_CHUNK_SIZE    = 512    # tokens per chunk
RAG_OVERLAP       = 50     # overlap between chunks

# ============================================================
# VALIDATION RULES
# ============================================================
VALIDATION_RULES = {
    "invoice_no"    : {"type": "string",  "required": True,  "min_length": 1},
    "date"          : {"type": "date",    "required": True},
    "customer_name" : {"type": "string",  "required": True,  "min_length": 2},
    "total"         : {"type": "float",   "required": True,  "min_value": 0.0},
    "items"         : {"type": "list",    "required": True,  "min_items": 1},
    "order_id"      : {"type": "string",  "required": False},
}