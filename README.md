# IDP System v2 — Intelligent Document Processing for Invoices

Production-grade Intelligent Document Processing (IDP) system that converts unstructured invoice PDFs (digital or scanned) into clean, validated, structured data — JSON, CSV, Excel, and RAG-ready chunks.

## Features

- Automatic document type detection (digital PDF vs scanned)
- OCR engine (Tesseract) for scanned documents with image preprocessing (deskew, denoise, sharpen)
- Table detection and multiline cell handling
- Irregular row and column reconstruction
- Entity extraction (invoice number, date, customer, amounts, line items)
- Data normalization (dates, currencies, text)
- Validation engine with business rule checks (math consistency, required fields, duplicates)
- Confidence scoring per field and per document
- Structured output: JSON, CSV, Excel (styled reports), RAG-ready chunks
- REST API (FastAPI) for single and bulk invoice processing
- Audit trail and error recovery
- Docker-ready for deployment

## Tested Results

- 1,007 invoice PDFs processed — 100% pipeline success rate
- 992 real invoices (15 empty source templates excluded)
- 978/992 passed validation (98.6%)
- Average confidence score: 0.948 (HIGH)
- Processing speed: ~0.13s per invoice

## Project Structure

\\\
idp_system_v2/
├── data/
│   ├── input/              # Place invoice PDFs here
│   └── output/
│       ├── json/            # Per-invoice JSON
│       ├── csv/              # Consolidated CSV reports
│       ├── excel/            # Styled Excel reports
│       ├── rag/               # RAG-ready chunk files
│       └── logs/              # Logs, audit trail, error log
├── src/
│   ├── ingestion/            # File detection, batch loading
│   ├── analysis/              # Layout analysis
│   ├── ocr/                    # OCR engine, image preprocessing
│   ├── extraction/             # Table, multiline, row/column handling
│   ├── entity/                  # Entity extraction
│   ├── normalization/           # Data normalization
│   ├── validation/               # Validation engine
│   ├── scoring/                   # Confidence scoring
│   ├── output/                     # JSON/CSV/Excel writers
│   ├── rag/                         # RAG chunk processor
│   ├── error_handling/               # Error recovery
│   └── core/                          # Config, logger, audit, pipeline orchestrator
├── api/                       # FastAPI REST API
├── tests/                     # Unit and integration tests
├── docker/                    # Dockerfile and docker-compose
├── main.py                    # CLI entry point
└── requirements.txt
\\\

## Setup

\\\ash
python -m venv venv
venv\Scripts\Activate.ps1        # Windows
pip install -r requirements.txt
\\\

Tesseract OCR engine must be installed separately (system-level):
\\\ash
winget install -e --id UB-Mannheim.TesseractOCR
\\\

## Usage

### CLI — Process all invoices in data/input/
\\\ash
python main.py
\\\

### CLI — Process limited number (testing)
\\\ash
python main.py --limit 20
\\\

### REST API
\\\ash
python -m uvicorn api.main:app --port 8000
\\\
Then open \http://127.0.0.1:8000/docs\ for interactive API documentation.

Endpoints:
- \GET /health\ — health check
- \GET /stats\ — processing statistics
- \POST /process/single\ — upload one PDF, get structured JSON
- \POST /process/bulk\ — upload multiple PDFs, get batch results

### Tests
\\\ash
python -m pytest tests/ -v
\\\

### Docker
\\\ash
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up
\\\

## Tech Stack

Python, pdfplumber, PyMuPDF, Tesseract OCR, OpenCV, FastAPI, pandas, openpyxl, Loguru, pytest, Streamlit (planned)
