from metrics_server.console import render
import re


def _plain(text: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", text)


def test_console_renders_lcars_metrics():
    frame = render(
        {
            "cpuUsage": 12.3,
            "memoryUsedMB": 2048,
            "gpuUsage": 45.0,
            "gpuMemoryUsedMB": 1000,
            "gpuMemoryTotalMB": 8000,
            "liveTokensPerSecond": 19.4,
            "tokenPerSecond": 8.8,
            "promptTokens": 41,
            "completionTokens": 964,
            "errorCount": 0,
            "modelIdentifier": "model-a",
            "runtimeLogMonitor": "running",
            "liveTimingLines": 7,
            "errors": [],
        },
        connected=True,
    )

    visible = _plain(frame)
    assert "LM STUDIO MONITOR" in visible
    assert "CONNECTED" in visible
    assert "model-a" in visible
    assert "runtime log running" in visible
    assert "TOKENS/SEC" in visible
    assert "19.40/s" in visible
    assert "41 / 964" in visible
    assert "No errors recorded." in visible
    # LCARS palette is emitted as 256-colour ANSI sequences.
    assert "\033[38;5;208m" in frame
    assert "\033[38;5;141m" in frame


def test_console_handles_disconnected_state():
    frame = render(None, connected=False)

    assert "CONNECTING" in frame
    assert "Waiting for the bridge" in frame
