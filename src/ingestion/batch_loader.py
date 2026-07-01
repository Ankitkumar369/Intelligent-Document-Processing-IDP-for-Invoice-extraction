# src/ingestion/batch_loader.py

import time
from pathlib import Path
from typing import List, Generator
from dataclasses import dataclass
from src.core.config import INPUT_DIR, BATCH_SIZE, SUPPORTED_EXTENSIONS
from src.core.logger import log


@dataclass
class BatchStats:
    """Batch processing ki statistics."""
    total_files   : int = 0
    total_batches : int = 0
    processed     : int = 0
    skipped       : int = 0
    failed        : int = 0
    start_time    : float = 0.0

    def elapsed_seconds(self) -> float:
        return round(time.time() - self.start_time, 2)

    def success_rate(self) -> str:
        if self.total_files == 0:
            return "0%"
        return f"{(self.processed / self.total_files * 100):.1f}%"


class BatchLoader:
    """
    PHASE 1 — Batch Processing
    Input folder se saari files load karta hai
    aur BATCH_SIZE ke chunks mein deta hai.
    """

    def __init__(self, input_dir: Path = INPUT_DIR, batch_size: int = BATCH_SIZE):
        self.input_dir  = input_dir
        self.batch_size = batch_size
        self.stats      = BatchStats()

    # ── File Discovery ────────────────────────────────────────
    def discover_files(self, extensions: List[str] = None) -> List[Path]:
        """Input folder se saari supported files dhundho."""

        if extensions is None:
            # Saare supported extensions
            extensions = []
            for exts in SUPPORTED_EXTENSIONS.values():
                extensions.extend(exts)

        found = []
        for ext in extensions:
            found.extend(self.input_dir.glob(f"*{ext}"))
            found.extend(self.input_dir.glob(f"*{ext.upper()}"))

        # Duplicates remove + sort
        found = sorted(set(found))

        self.stats.total_files   = len(found)
        self.stats.total_batches = (len(found) + self.batch_size - 1) // self.batch_size
        self.stats.start_time    = time.time()

        log.info(f"📂 Files discovered  : {len(found)}")
        log.info(f"📦 Batch size        : {self.batch_size}")
        log.info(f"🔢 Total batches     : {self.stats.total_batches}")

        return found

    # ── Batch Generator ───────────────────────────────────────
    def get_batches(self, files: List[Path]) -> Generator[List[Path], None, None]:
        """Files ko BATCH_SIZE ke chunks mein yield karta hai."""
        for i in range(0, len(files), self.batch_size):
            batch = files[i : i + self.batch_size]
            batch_no = (i // self.batch_size) + 1
            log.info(f"📦 Yielding Batch {batch_no}/{self.stats.total_batches} "
                     f"({len(batch)} files)")
            yield batch

    # ── Single File Validator ─────────────────────────────────
    def is_valid_file(self, filepath: Path) -> bool:
        """File valid hai ya nahi check karo."""
        if not filepath.exists():
            log.warning(f"File not found: {filepath.name}")
            return False
        if filepath.stat().st_size == 0:
            log.warning(f"Empty file: {filepath.name}")
            self.stats.skipped += 1
            return False
        return True

    # ── Progress Tracker ──────────────────────────────────────
    def mark_processed(self):
        self.stats.processed += 1

    def mark_failed(self):
        self.stats.failed += 1

    def mark_skipped(self):
        self.stats.skipped += 1

    # ── Summary ───────────────────────────────────────────────
    def print_summary(self):
        log.info("=" * 50)
        log.info("📊 BATCH PROCESSING SUMMARY")
        log.info(f"  Total Files   : {self.stats.total_files}")
        log.info(f"  Processed     : {self.stats.processed}")
        log.info(f"  Failed        : {self.stats.failed}")
        log.info(f"  Skipped       : {self.stats.skipped}")
        log.info(f"  Success Rate  : {self.stats.success_rate()}")
        log.info(f"  Time Elapsed  : {self.stats.elapsed_seconds()}s")
        log.info("=" * 50)

    def get_stats(self) -> dict:
        return {
            "total_files"   : self.stats.total_files,
            "total_batches" : self.stats.total_batches,
            "processed"     : self.stats.processed,
            "failed"        : self.stats.failed,
            "skipped"       : self.stats.skipped,
            "success_rate"  : self.stats.success_rate(),
            "elapsed_sec"   : self.stats.elapsed_seconds(),
        }