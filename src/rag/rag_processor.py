import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict
from src.core.config import OUTPUT_RAG_DIR, RAG_CHUNK_SIZE, RAG_OVERLAP
from src.core.logger import log


@dataclass
class RAGChunk:
    chunk_id: str
    text: str
    metadata: dict


class RAGProcessor:

    def __init__(self):
        self.chunks: List[RAGChunk] = []

    def process(self, normalized, doc_score, source_path=""):
        try:
            chunks = []

            header_text = (
                f"Invoice {normalized.invoice_no} dated {normalized.date_normalized} "
                f"for customer {normalized.customer_name}. "
                f"Shipped via {normalized.ship_mode}. "
                f"Order ID: {normalized.order_id}."
            )
            chunks.append(self._make_chunk(
                normalized, 0, header_text, "header", source_path
            ))

            financial_text = (
                f"Financial summary for invoice {normalized.invoice_no}: "
                f"Subtotal {normalized.subtotal} {normalized.currency}, "
                f"Discount {normalized.discount} ({normalized.discount_pct}%), "
                f"Shipping {normalized.shipping}, "
                f"Total {normalized.total}, "
                f"Balance Due {normalized.balance_due}."
            )
            chunks.append(self._make_chunk(
                normalized, 1, financial_text, "financial", source_path
            ))

            if normalized.items:
                items_text = self._serialize_items(normalized.items, normalized.invoice_no)
                chunks.append(self._make_chunk(
                    normalized, 2, items_text, "items", source_path
                ))

            if normalized.notes or normalized.terms:
                notes_text = f"Notes: {normalized.notes} Terms: {normalized.terms}"
                chunks.append(self._make_chunk(
                    normalized, 3, notes_text, "notes", source_path
                ))

            self._save_chunks(normalized.filename, chunks, doc_score)
            log.debug(f"  OK RAG chunks created: {normalized.filename} | chunks={len(chunks)}")
            return chunks

        except Exception as e:
            log.error(f"RAGProcessor error: {e}")
            return []

    def _make_chunk(self, normalized, idx, text, chunk_type, source_path):
        chunk_id = f"{normalized.invoice_no}_{chunk_type}_{idx}"
        metadata = {
            "source_document": normalized.filename,
            "source_path": source_path,
            "invoice_no": normalized.invoice_no,
            "chunk_type": chunk_type,
            "chunk_index": idx,
            "page_number": 1,
        }
        return RAGChunk(chunk_id=chunk_id, text=text, metadata=metadata)

    def _serialize_items(self, items, invoice_no):
        lines = [f"Line items for invoice {invoice_no}:"]
        for i, item in enumerate(items, 1):
            lines.append(
                f"Item {i}: {item.get('description','')}, "
                f"quantity {item.get('quantity','')}, "
                f"rate {item.get('rate','')}, "
                f"amount {item.get('amount','')}, "
                f"category {item.get('category','')}."
            )
        return " ".join(lines)

    def _save_chunks(self, filename, chunks, doc_score):
        out_name = Path(filename).stem + "_rag.json"
        out_path = OUTPUT_RAG_DIR / out_name

        data = {
            "filename": filename,
            "confidence_label": doc_score.overall_label,
            "chunks": [
                {"chunk_id": c.chunk_id, "text": c.text, "metadata": c.metadata}
                for c in chunks
            ],
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
