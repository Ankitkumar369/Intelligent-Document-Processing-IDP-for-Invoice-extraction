# src/extraction/content_classifier.py

import re
from dataclasses import dataclass, field
from typing import List, Dict
from src.core.logger import log


@dataclass
class ClassifiedBlock:
    """Ek classified content block."""
    block_id    : int
    content     : str
    block_type  : str    # table / header / footer / metadata / paragraph
    confidence  : float
    page_no     : int = 1


@dataclass
class ClassificationResult:
    """Poore document ka classification."""
    filename    : str
    blocks      : List[ClassifiedBlock] = field(default_factory=list)
    summary     : Dict[str, int]        = field(default_factory=dict)
    error       : str = ""


class ContentClassifier:
    """
    PHASE 8 — Table vs Non-Table Detection

    Classifies content into:
    1. TABLE      - Structured tabular data
    2. HEADER     - Document title/heading
    3. FOOTER     - Page footer info
    4. METADATA   - Invoice meta (date, no, address)
    5. PARAGRAPH  - Free text
    """

    # Regex patterns
    AMOUNT_RE   = re.compile(r"\$[\d,]+\.?\d*")
    DATE_RE     = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{4}\b", re.I)
    INVOICE_RE  = re.compile(r"invoice|#\s*\d+|order\s*id|bill\s*to|ship\s*to", re.I)
    HEADER_RE   = re.compile(r"^(superstore|invoice|receipt|tax invoice|quotation)", re.I)
    FOOTER_RE   = re.compile(r"(thank|terms|notes|page \d|www\.|@)", re.I)
    TABLE_KW    = re.compile(r"\b(item|qty|quantity|rate|amount|description|unit)\b", re.I)

    def classify(self, layout, filename: str = "") -> ClassificationResult:
        """
        LayoutAnalyzer ka output lekar har block classify karo.
        """
        log.info(f"Content classification: {filename}")

        try:
            blocks  = []
            bid     = 0
            summary = {
                "table"    : 0,
                "header"   : 0,
                "footer"   : 0,
                "metadata" : 0,
                "paragraph": 0,
            }

            for page in layout.pages:

                # Header zone
                if page.header_text.strip():
                    btype, conf = self._classify_text(
                        page.header_text, zone="header"
                    )
                    blocks.append(ClassifiedBlock(
                        block_id   = bid,
                        content    = page.header_text,
                        block_type = btype,
                        confidence = conf,
                        page_no    = page.page_no,
                    ))
                    summary[btype] = summary.get(btype, 0) + 1
                    bid += 1

                # Table zones
                if page.has_table:
                    blocks.append(ClassifiedBlock(
                        block_id   = bid,
                        content    = f"[TABLE on page {page.page_no}]",
                        block_type = "table",
                        confidence = 0.95,
                        page_no    = page.page_no,
                    ))
                    summary["table"] += 1
                    bid += 1

                # Body text blocks
                if page.body_text.strip():
                    # Split into logical chunks
                    chunks = self._split_into_chunks(page.body_text)
                    for chunk in chunks:
                        if not chunk.strip():
                            continue
                        btype, conf = self._classify_text(chunk, zone="body")
                        blocks.append(ClassifiedBlock(
                            block_id   = bid,
                            content    = chunk,
                            block_type = btype,
                            confidence = conf,
                            page_no    = page.page_no,
                        ))
                        summary[btype] = summary.get(btype, 0) + 1
                        bid += 1

                # Footer zone
                if page.footer_text.strip():
                    btype, conf = self._classify_text(
                        page.footer_text, zone="footer"
                    )
                    blocks.append(ClassifiedBlock(
                        block_id   = bid,
                        content    = page.footer_text,
                        block_type = btype,
                        confidence = conf,
                        page_no    = page.page_no,
                    ))
                    summary[btype] = summary.get(btype, 0) + 1
                    bid += 1

            result = ClassificationResult(
                filename = filename,
                blocks   = blocks,
                summary  = summary,
            )

            log.debug(
                f"  ✅ {filename} | blocks={len(blocks)} | "
                f"summary={summary}"
            )
            return result

        except Exception as e:
            log.error(f"ContentClassifier error: {e}")
            return ClassificationResult(filename=filename, error=str(e))

    # ── Text Classifier ───────────────────────────────────────
    def _classify_text(self, text: str, zone: str = "body"):
        text = text.strip()

        # Zone-based override
        if zone == "header":
            if self.HEADER_RE.search(text):
                return "header", 0.95
            return "header", 0.80

        if zone == "footer":
            if self.FOOTER_RE.search(text):
                return "footer", 0.90
            return "footer", 0.75

        # Table-like content
        if self.TABLE_KW.search(text):
            col_count = len(re.split(r"\s{2,}|\t", text))
            if col_count >= 2:
                return "table", 0.85

        # Metadata (invoice fields)
        if self.INVOICE_RE.search(text):
            return "metadata", 0.90
        if self.DATE_RE.search(text):
            return "metadata", 0.85
        if self.AMOUNT_RE.search(text):
            return "metadata", 0.80

        # Paragraph
        word_count = len(text.split())
        if word_count > 15:
            return "paragraph", 0.75

        return "metadata", 0.65

    # ── Chunk Splitter ────────────────────────────────────────
    def _split_into_chunks(self, text: str) -> List[str]:
        """Body text ko logical chunks mein split karo."""
        chunks = []
        current = []

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                if current:
                    chunks.append(" ".join(current))
                    current = []
            else:
                current.append(line)

        if current:
            chunks.append(" ".join(current))

        return chunks