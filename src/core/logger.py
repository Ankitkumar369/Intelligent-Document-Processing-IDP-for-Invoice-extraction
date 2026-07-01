# src/core/logger.py

import sys
from loguru import logger
from src.core.config import LOG_LEVEL, LOG_FILENAME, LOG_ROTATION, LOG_RETENTION

def setup_logger() -> logger:
    """
    Centralized logger setup using Loguru.
    Console + File dono mein logs jayenge.
    """

    # Remove default logger
    logger.remove()

    # ── Console Handler ──────────────────────────────────────
    logger.add(
        sys.stdout,
        level=LOG_LEVEL,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
    )

    # ── File Handler ─────────────────────────────────────────
    logger.add(
        str(LOG_FILENAME),
        level=LOG_LEVEL,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        encoding="utf-8",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{line} | "
            "{message}"
        ),
    )

    return logger


# ── Module-level logger instance ─────────────────────────────
log = setup_logger()


# ── Convenience helpers ───────────────────────────────────────
def log_phase_start(phase_no: int, phase_name: str, file: str = ""):
    log.info(f"{'='*50}")
    log.info(f"PHASE {phase_no} START → {phase_name}")
    if file:
        log.info(f"File: {file}")
    log.info(f"{'='*50}")


def log_phase_end(phase_no: int, phase_name: str, status: str = "SUCCESS"):
    log.info(f"PHASE {phase_no} END → {phase_name} [{status}]")
    log.info(f"{'='*50}")


def log_field_extracted(field: str, value: str, confidence: float):
    log.debug(f"  ✅ {field}: '{value}' (confidence: {confidence:.2f})")


def log_field_missing(field: str, reason: str = ""):
    log.warning(f"  ⚠️  MISSING → {field}" + (f" | Reason: {reason}" if reason else ""))


def log_error(file: str, error: str):
    log.error(f"  ❌ ERROR in '{file}': {error}")


def log_batch_progress(current: int, total: int, filename: str):
    pct = (current / total) * 100
    log.info(f"[{current}/{total}] ({pct:.1f}%) Processing: {filename}")