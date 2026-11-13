from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from typing import Any


def _nonnegative_int(value: Any) -> int | None:
    try:
        return max(0, int(value)) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _nonnegative_float(value: Any) -> float | None:
    try:
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def parse_lms_log_usage(line: str) -> dict[str, int | float] | None:
    """Parse one `lms log stream --stats --json` prediction-output event."""
    try:
        envelope = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(envelope, dict):
        return None

    event = envelope.get("data", envelope)
    if not isinstance(event, dict):
        return None
    event_type = str(event.get("type", "")).lower()
    if event_type and not event_type.endswith("output"):
        return None
    stats = event.get("stats") or envelope.get("stats")
    if not isinstance(stats, dict):
        return None

    prompt_tokens = _nonnegative_int(
        stats.get("promptTokensCount", stats.get("prompt_tokens", stats.get("prompt_tokens_count")))
    )
    completion_tokens = _nonnegative_int(
        stats.get(
            "predictedTokensCount",
            stats.get("completion_tokens", stats.get("completion_tokens_count")),
        )
    )
    tokens_per_second = _nonnegative_float(
        stats.get("tokensPerSecond", stats.get("tokens_per_second"))
    )

    result: dict[str, int | float] = {}
    if prompt_tokens is not None:
        result["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        result["completion_tokens"] = completion_tokens
    if tokens_per_second is not None:
        result["tokens_per_second"] = tokens_per_second
    return result or None


def resolve_lms_command() -> str | None:
    override = os.environ.get("LM_STUDIO_CLI")
    if override:
        return override
    if command := shutil.which("lms"):
        return command
    for candidate in (
        Path.home() / ".lmstudio" / "bin" / "lms.exe",
        Path.home() / ".lmstudio" / "bin" / "lms",
    ):
        if candidate.is_file():
            return str(candidate)
    return None


class LmsLogMonitor:
    """Optional reader for LM Studio desktop inference stats from its CLI log stream."""

    def __init__(self, state: Any, enabled: bool = True) -> None:
        self._state = state
        self._enabled = enabled
        self._process: subprocess.Popen[str] | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> bool:
        if not self._enabled or self._thread is not None:
            return False
        command = resolve_lms_command()
        if not command:
            return False
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = subprocess.Popen(
                [command, "log", "stream", "--source", "model", "--filter", "output", "--stats", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
        except OSError:
            return False

        with self._lock:
            self._process = process
            self._thread = threading.Thread(target=self._consume, name="lms-log-stream", daemon=True)
            self._thread.start()
        return True

    def _consume(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            usage = parse_lms_log_usage(line)
            if usage is None:
                continue
            self._state.record_usage(
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                elapsed_seconds=0.0,
                tokens_per_second=(
                    float(usage["tokens_per_second"])
                    if "tokens_per_second" in usage
                    else 0.0
                ),
            )

    def stop(self) -> None:
        with self._lock:
            process = self._process
            self._process = None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if process.stdout is not None:
            process.stdout.close()
