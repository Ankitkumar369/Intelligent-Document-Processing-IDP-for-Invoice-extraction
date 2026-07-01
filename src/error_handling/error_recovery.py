import traceback
from pathlib import Path
from dataclasses import dataclass, field
from typing import List
from src.core.config import OUTPUT_LOGS_DIR
from src.core.logger import log


@dataclass
class ProcessingError:
    filename: str
    phase: str
    error_type: str
    error_message: str
    traceback_str: str = ""


class ErrorRecovery:

    def __init__(self):
        self.errors: List[ProcessingError] = []
        self.error_log_path = OUTPUT_LOGS_DIR / "error_log.txt"

    def handle(self, filename, phase, exception):
        err = ProcessingError(
            filename=filename,
            phase=phase,
            error_type=type(exception).__name__,
            error_message=str(exception),
            traceback_str=traceback.format_exc(),
        )
        self.errors.append(err)
        log.error(f"  ERROR [{phase}] {filename}: {err.error_type} - {err.error_message}")
        self._write_to_log(err)
        return err

    def _write_to_log(self, err):
        try:
            with open(self.error_log_path, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"File: {err.filename}\n")
                f.write(f"Phase: {err.phase}\n")
                f.write(f"Error Type: {err.error_type}\n")
                f.write(f"Message: {err.error_message}\n")
                f.write(f"Traceback:\n{err.traceback_str}\n")
        except Exception:
            pass

    def is_corrupt_file(self, filepath):
        try:
            path = Path(filepath)
            if not path.exists():
                return True
            if path.stat().st_size == 0:
                return True
            return False
        except Exception:
            return True

    def get_error_summary(self):
        by_phase = {}
        for e in self.errors:
            by_phase[e.phase] = by_phase.get(e.phase, 0) + 1
        return {
            "total_errors": len(self.errors),
            "by_phase": by_phase,
            "failed_files": [e.filename for e in self.errors],
        }

    def retry_safe(self, func, *args, max_attempts=3, **kwargs):
        import time
        last_exception = None
        for attempt in range(1, max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                log.warning(f"  Retry {attempt}/{max_attempts} failed: {e}")
                time.sleep(1)
        raise last_exception
