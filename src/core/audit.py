# src/core/audit.py

import json
import uuid
from datetime import datetime
from pathlib import Path
from src.core.config import OUTPUT_LOGS_DIR
from src.core.logger import log

AUDIT_FILE = OUTPUT_LOGS_DIR / "audit_trail.jsonl"


class AuditTrail:
    """
    Har file ke processing ka complete record rakhta hai.
    JSONL format mein — ek line = ek event.
    """

    def __init__(self):
        self.audit_file = AUDIT_FILE
        self.session_id = str(uuid.uuid4())[:8].upper()
        self._write_event("SESSION_START", {
            "session_id": self.session_id,
            "timestamp" : datetime.now().isoformat(),
        })
        log.info(f"Audit Trail started | Session: {self.session_id}")

    # ── Internal writer ───────────────────────────────────────
    def _write_event(self, event_type: str, data: dict):
        record = {
            "session_id" : self.session_id,
            "event_type" : event_type,
            "timestamp"  : datetime.now().isoformat(),
            **data,
        }
        with open(self.audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    # ── Public methods ────────────────────────────────────────
    def log_file_start(self, filename: str) -> str:
        """File processing shuru hone par call karo."""
        file_id = str(uuid.uuid4())[:8].upper()
        self._write_event("FILE_START", {
            "file_id"  : file_id,
            "filename" : filename,
        })
        log.debug(f"Audit → FILE_START | {filename} | ID: {file_id}")
        return file_id

    def log_file_success(self, file_id: str, filename: str, fields_extracted: int):
        """File successfully process hone par call karo."""
        self._write_event("FILE_SUCCESS", {
            "file_id"          : file_id,
            "filename"         : filename,
            "fields_extracted" : fields_extracted,
        })
        log.debug(f"Audit → FILE_SUCCESS | {filename} | Fields: {fields_extracted}")

    def log_file_failure(self, file_id: str, filename: str, error: str):
        """File fail hone par call karo."""
        self._write_event("FILE_FAILURE", {
            "file_id"  : file_id,
            "filename" : filename,
            "error"    : error,
        })
        log.warning(f"Audit → FILE_FAILURE | {filename} | Error: {error}")

    def log_phase(self, file_id: str, phase_no: int, phase_name: str, status: str, duration_ms: float = 0):
        """Har phase ka record."""
        self._write_event("PHASE_COMPLETE", {
            "file_id"     : file_id,
            "phase_no"    : phase_no,
            "phase_name"  : phase_name,
            "status"      : status,
            "duration_ms" : round(duration_ms, 2),
        })

    def log_validation(self, file_id: str, filename: str, passed: bool, issues: list):
        """Validation result record."""
        self._write_event("VALIDATION", {
            "file_id"  : file_id,
            "filename" : filename,
            "passed"   : passed,
            "issues"   : issues,
        })

    def log_session_end(self, total: int, success: int, failed: int):
        """Session khatam hone par summary."""
        self._write_event("SESSION_END", {
            "session_id"    : self.session_id,
            "total_files"   : total,
            "success_count" : success,
            "failed_count"  : failed,
            "success_rate"  : f"{(success/total*100):.1f}%" if total > 0 else "0%",
        })
        log.info(f"Session {self.session_id} END | Total: {total} | ✅ {success} | ❌ {failed}")

    def get_session_summary(self) -> dict:
        """Current session ki summary return karo."""
        events = []
        if self.audit_file.exists():
            with open(self.audit_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        e = json.loads(line.strip())
                        if e.get("session_id") == self.session_id:
                            events.append(e)
                    except Exception:
                        continue

        success = sum(1 for e in events if e.get("event_type") == "FILE_SUCCESS")
        failure = sum(1 for e in events if e.get("event_type") == "FILE_FAILURE")

        return {
            "session_id"    : self.session_id,
            "total_events"  : len(events),
            "files_success" : success,
            "files_failed"  : failure,
        }