from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import threading


class MetricsState:
    """Thread-safe rolling request metrics and error log."""

    def __init__(self, max_errors: int = 100) -> None:
        self._lock = threading.Lock()
        self._errors: deque[dict[str, str]] = deque(maxlen=max_errors)
        self._token_per_second = 0.0

    def record_tokens(self, completion_tokens: int, elapsed_seconds: float) -> None:
        if completion_tokens <= 0 or elapsed_seconds <= 0:
            return
        with self._lock:
            self._token_per_second = completion_tokens / elapsed_seconds

    def record_error(self, message: str, source: str = "LM Studio") -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "ERROR",
            "message": message[:1000],
            "source": source,
        }
        with self._lock:
            self._errors.append(entry)

    def snapshot(self, cpu_usage: float, memory_used_mb: int) -> dict[str, object]:
        with self._lock:
            errors = list(self._errors)
            token_per_second = self._token_per_second
        return {
            "cpuUsage": round(float(cpu_usage), 1),
            "memoryUsedMB": int(memory_used_mb),
            "tokenPerSecond": round(token_per_second, 2),
            "errorCount": len(errors),
            "errors": errors,
        }

    def errors(self) -> list[dict[str, str]]:
        with self._lock:
            return list(self._errors)
