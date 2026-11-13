from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import threading


class MetricsState:
    """Thread-safe rolling request metrics and error log."""

    def __init__(self, max_errors: int = 100) -> None:
        self._lock = threading.Lock()
        self._errors: deque[dict[str, str]] = deque(maxlen=max_errors)
        # Usage records keyed by source. Diagnostics come from LM Studio's own
        # measurement; proxy values are a wall-clock fallback.
        self._usage: dict[str, tuple[int, int, float]] = {}

    def record_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        elapsed_seconds: float,
        tokens_per_second: float | None = None,
        source: str = "proxy",
    ) -> None:
        if prompt_tokens < 0 or completion_tokens < 0:
            return
        if tokens_per_second is None:
            tokens_per_second = (
                completion_tokens / elapsed_seconds
                if completion_tokens > 0 and elapsed_seconds > 0
                else 0.0
            )
        with self._lock:
            self._usage[source] = (
                int(prompt_tokens),
                int(completion_tokens),
                max(0.0, float(tokens_per_second)),
            )

    def _preferred_usage(self) -> tuple[int, int, float]:
        """Caller must hold the lock. Prefer the measured diagnostics rate."""
        for source in ("diagnostics", "proxy"):
            if source in self._usage:
                return self._usage[source]
        return (0, 0, 0.0)

    def record_error(self, message: str, source: str = "LM Studio") -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "ERROR",
            "message": message[:1000],
            "source": source,
        }
        with self._lock:
            self._errors.append(entry)

    def has_usage(self) -> bool:
        with self._lock:
            return bool(self._usage)

    def snapshot(
        self,
        cpu_usage: float,
        memory_used_mb: int,
        gpu_usage: float | None = None,
        gpu_memory_used_mb: int | None = None,
        gpu_memory_total_mb: int | None = None,
    ) -> dict[str, object]:
        with self._lock:
            errors = list(self._errors)
            prompt_tokens, completion_tokens, token_per_second = self._preferred_usage()
        return {
            "cpuUsage": round(float(cpu_usage), 1),
            "memoryUsedMB": int(memory_used_mb),
            "gpuUsage": round(float(gpu_usage), 1) if gpu_usage is not None else None,
            "gpuMemoryUsedMB": gpu_memory_used_mb,
            "gpuMemoryTotalMB": gpu_memory_total_mb,
            "tokenPerSecond": round(token_per_second, 2),
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "errorCount": len(errors),
            "errors": errors,
        }

    def errors(self) -> list[dict[str, str]]:
        with self._lock:
            return list(self._errors)
