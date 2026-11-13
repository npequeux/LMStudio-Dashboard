from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
import re
import shutil
import subprocess
import threading
from typing import Any

logger = logging.getLogger(__name__)


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


def parse_lms_log_event(line: str) -> tuple[str, dict[str, int | float] | None] | None:
    """Parse one diagnostics event into (event_type, usage)."""
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
    stats = event.get("stats") or envelope.get("stats")
    usage = _parse_stats(stats) if isinstance(stats, dict) else None
    return event_type, usage


def parse_lms_log_usage(line: str) -> dict[str, int | float] | None:
    """Parse one `lms log stream --stats --json` prediction-output event."""
    parsed = parse_lms_log_event(line)
    if parsed is None:
        return None
    event_type, usage = parsed
    if event_type and not event_type.endswith("output"):
        return None
    return usage


def _parse_stats(stats: dict[str, Any]) -> dict[str, int | float] | None:
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
    """Reader for LM Studio inference stats from its CLI log stream.

    The monitor supervises the `lms log stream` process and restarts it when it
    exits, so a bridge that started before LM Studio (or survives an LM Studio
    restart) still ends up capturing token metrics.
    """

    def __init__(self, state: Any, enabled: bool = True) -> None:
        self._state = state
        self._enabled = enabled
        self._process: subprocess.Popen[str] | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._status = "disabled" if not enabled else "stopped"

    @property
    def status(self) -> str:
        return self._status

    def start(self) -> bool:
        if not self._enabled:
            self._status = "disabled"
            return False
        with self._lock:
            if self._thread is not None:
                return False
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._supervise, name="lms-log-monitor", daemon=True
            )
            self._thread.start()
        return True

    def _supervise(self) -> None:
        backoff = 1.0
        while not self._stop_event.is_set():
            command = resolve_lms_command()
            if not command:
                self._status = "unavailable"
                logger.warning(
                    "LM Studio CLI not found; token metrics from desktop inference are disabled. "
                    "Set LM_STUDIO_CLI to the lms executable if it is installed elsewhere."
                )
                return

            try:
                process = subprocess.Popen(
                    [
                        command,
                        "log",
                        "stream",
                        "--source",
                        "model",
                        "--filter",
                        "output",
                        "--stats",
                        "--json",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as exc:
                self._status = "error"
                logger.warning("Could not start LM Studio log stream: %s", exc)
                self._stop_event.wait(backoff)
                backoff = min(backoff * 2.0, 30.0)
                continue

            with self._lock:
                self._process = process
            self._status = "running"
            logger.info("Listening to LM Studio inference stats via %s", command)
            backoff = 1.0

            self._consume(process)

            with self._lock:
                if self._process is process:
                    self._process = None
            if self._stop_event.is_set():
                break

            self._status = "retrying"
            logger.info("LM Studio log stream stopped; retrying in %.0fs", backoff)
            self._stop_event.wait(backoff)
            backoff = min(backoff * 2.0, 30.0)

    def _consume(self, process: subprocess.Popen[str]) -> None:
        if process.stdout is None:
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
                source="diagnostics",
            )

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            process = self._process
            self._process = None
            thread = self._thread
            self._thread = None

        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    pass
        if process is not None and process.stdout is not None:
            try:
                process.stdout.close()
            except OSError:
                pass
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5)
        self._status = "stopped"


_TIMING_PATTERN = re.compile(
    r"(?:tg\s*=\s*([0-9.]+)\s*t/s|([0-9.]+)\s*tokens per second)",
    re.IGNORECASE,
)


def parse_timing_line(line: str) -> float | None:
    """Extract a live generation rate from an LM Studio server log line."""
    match = _TIMING_PATTERN.search(line)
    if not match:
        return None
    raw = match.group(1) or match.group(2)
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


def _latest_server_log() -> Path | None:
    base = Path.home() / ".lmstudio" / "server-logs"
    if not base.is_dir():
        return None
    try:
        files = sorted(
            base.rglob("*.log"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return None
    return files[0] if files else None


class ServerLogMonitor:
    """Tails LM Studio's server logs for a live generation rate.

    LM Studio's diagnostics stream only reports token stats when a prediction
    finishes. The server logs carry `tg = X t/s` / `tokens per second` timing
    lines while a generation is running, when the runtime log verbosity is high
    enough to include them.
    """

    def __init__(self, state: Any, enabled: bool = True) -> None:
        self._state = state
        self._enabled = enabled
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._status = "disabled" if not enabled else "stopped"
        self.timing_lines = 0

    @property
    def status(self) -> str:
        return self._status

    def start(self) -> bool:
        if not self._enabled:
            self._status = "disabled"
            return False
        if self._thread is not None:
            return False
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="lms-server-log-monitor", daemon=True
        )
        self._thread.start()
        return True

    def _run(self) -> None:
        while not self._stop_event.is_set():
            path = _latest_server_log()
            if path is None:
                self._status = "waiting"
                self._stop_event.wait(5.0)
                continue
            self._status = "running"
            try:
                self._tail(path)
            except OSError as exc:
                logger.debug("LM Studio server log tail failed: %s", exc)
                self._stop_event.wait(5.0)

    def _tail(self, path: Path) -> None:
        with path.open(encoding="utf-8", errors="replace") as handle:
            handle.seek(0, os.SEEK_END)
            while not self._stop_event.is_set():
                line = handle.readline()
                if not line:
                    self._stop_event.wait(1.0)
                    if _latest_server_log() != path:
                        return
                    continue
                rate = parse_timing_line(line)
                if rate is not None:
                    self.timing_lines += 1
                    self._state.record_live_rate(rate)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._status = "stopped"


def _stats_from_conversation(data: Any) -> dict[str, int | float] | None:
    """Return the most recent prediction stats recorded in a conversation file."""
    if not isinstance(data, dict):
        return None
    messages = data.get("messages")
    if not isinstance(messages, list):
        return None

    latest: dict[str, int | float] | None = None
    for message in messages:
        if not isinstance(message, dict):
            continue
        versions = message.get("versions")
        if not isinstance(versions, list):
            continue
        for version in versions:
            if not isinstance(version, dict):
                continue
            steps = version.get("steps")
            if not isinstance(steps, list):
                continue
            for step in steps:
                if not isinstance(step, dict):
                    continue
                gen_info = step.get("genInfo")
                if not isinstance(gen_info, dict):
                    continue
                stats = gen_info.get("stats")
                if not isinstance(stats, dict):
                    continue
                parsed = _parse_stats(stats)
                if parsed is not None:
                    latest = parsed
    return latest


def read_last_prediction_stats() -> dict[str, int | float] | None:
    """Read the latest prediction stats from LM Studio's local conversation history."""
    base = Path.home() / ".lmstudio" / "conversations"
    if not base.is_dir():
        return None
    try:
        files = sorted(
            base.glob("*.conversation.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return None

    for path in files[:20]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        stats = _stats_from_conversation(data)
        if stats is not None:
            return stats
    return None


def seed_state_from_history(
    state: Any,
    reader: Callable[[], dict[str, int | float] | None] | None = None,
) -> bool:
    """Seed the metrics state from the last LM Studio prediction.

    The CLI log stream only reports predictions that happen after it starts, so
    without this the dashboard stays at zero when the bridge is started after
    inference. Only seeds when no usage has been recorded yet.
    """
    if state.has_usage():
        return False
    history_reader = reader if reader is not None else read_last_prediction_stats
    stats = history_reader()
    if not stats:
        return False
    state.record_usage(
        prompt_tokens=int(stats.get("prompt_tokens", 0)),
        completion_tokens=int(stats.get("completion_tokens", 0)),
        elapsed_seconds=0.0,
        tokens_per_second=(
            float(stats["tokens_per_second"]) if "tokens_per_second" in stats else None
        ),
        source="diagnostics",
    )
    logger.info(
        "Seeded token metrics from the last LM Studio prediction: "
        "%s tok/s, %s prompt tokens, %s completion tokens",
        stats.get("tokens_per_second", 0.0),
        stats.get("prompt_tokens", 0),
        stats.get("completion_tokens", 0),
    )
    return True
