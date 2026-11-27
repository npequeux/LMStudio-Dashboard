from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

import httpx
import uvicorn

from metrics_server.app import create_app

RESET = "\033[0m"
BOLD = "\033[1m"
CLEAR = "\033[H\033[2J"
COLORS = {
    "orange": "\033[38;5;208m",
    "blue": "\033[38;5;75m",
    "purple": "\033[38;5;141m",
    "red": "\033[38;5;196m",
    "green": "\033[38;5;46m",
    "dim": "\033[38;5;245m",
    "white": "\033[38;5;255m",
}

CARD_WIDTH = 24
_INNER = CARD_WIDTH - 2


def _paint(text: str, color: str) -> str:
    return f"{COLORS[color]}{text}{RESET}"


def _card(label: str, value: str, color: str) -> list[str]:
    """One LCARS 'padd' rendered as three terminal lines."""
    title = f"─ {label} "
    top = _paint("╭" + title + "─" * max(0, _INNER - len(title)) + "╮", color)
    middle = _paint("│", color) + value.center(_INNER) + _paint("│", color)
    bottom = _paint("╰" + "─" * _INNER + "╯", color)
    return [top, middle, bottom]


def _card_row(cards: list[list[str]]) -> str:
    return "\n".join(" ".join(line) for line in zip(*cards, strict=True))


def _fmt(value: Any, suffix: str = "", digits: int = 1) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:,.{digits}f}{suffix}" if digits else f"{int(value):,}{suffix}"
    return f"{value}{suffix}"


def render(data: dict[str, Any] | None, connected: bool, interval: float = 2.0) -> str:
    """Build one full-screen LCARS frame from a metrics payload."""
    status_text = "● CONNECTED" if connected else "○ CONNECTING…"
    status = _paint(status_text, "green" if connected else "orange")
    title = "LM STUDIO MONITOR"
    pad = max(1, 62 - (1 + len(title) + len(status_text) + 1))
    lines = [
        _paint("╭" + "─" * 62 + "╮", "blue"),
        _paint("│", "blue") + " " + _paint(BOLD + title + RESET, "orange")
        + " " * pad + status + " " + _paint("│", "blue"),
        _paint("╰" + "─" * 62 + "╯", "blue"),
    ]

    if data is None:
        lines += ["", _paint("  Waiting for the bridge…", "dim")]
        return "\n".join(lines) + "\n"

    model = data.get("modelIdentifier") or (data.get("loadedModel") or {}).get("id") or "none loaded"
    lines.append(
        " " + _paint("MODEL ", "blue") + _paint(str(model), "white")
        + "  " + _paint("runtime log ", "blue") + str(data.get("runtimeLogMonitor") or "—")
        + "  " + _paint("lines ", "blue") + str(data.get("liveTimingLines") or 0)
    )
    lines.append("")

    live = data.get("liveTokensPerSecond")
    tps = live if live is not None else data.get("tokenPerSecond")
    gpu = data.get("gpuUsage")
    vram = ""
    if data.get("gpuMemoryUsedMB") is not None and data.get("gpuMemoryTotalMB") is not None:
        vram = f"\n{data['gpuMemoryUsedMB']}/{data['gpuMemoryTotalMB']} MB"

    lines.append(_card_row([
        _card("CPU USAGE", _fmt(data.get("cpuUsage"), "%"), "orange"),
        _card("MEMORY", _fmt(data.get("memoryUsedMB"), " MB", 0), "blue"),
        _card("TOKENS/SEC", _fmt(tps, "/s", 2), "purple"),
    ]))
    lines.append(_card_row([
        _card("GPU / VRAM", (_fmt(gpu, "%") + vram) if gpu is not None else "N/A", "purple"),
        _card("PROMPT / COMPLETION",
              f"{data.get('promptTokens', 0)} / {data.get('completionTokens', 0)}", "orange"),
        _card("ERRORS", _fmt(data.get("errorCount"), "", 0), "red"),
    ]))
    lines.append("")

    errors = data.get("errors") or []
    if errors:
        lines.append(_paint(" ERROR LOG " + "─" * 50, "red"))
        for entry in errors[-3:]:
            lines.append("  " + _paint(str(entry.get("timestamp", ""))[:19], "dim")
                         + "  " + str(entry.get("source", "")) + ": "
                         + str(entry.get("message", ""))[:80])
    else:
        lines.append(_paint(" No errors recorded.", "dim"))

    lines.append("")
    lines.append(_paint(
        f" Ctrl+C to stop  ·  refreshes every {interval:g}s  ·  start.bat runs the bridge without the console",
        "dim",
    ))
    return "\n".join(lines) + "\n"


async def _tui(url: str, interval: float) -> None:
    async with httpx.AsyncClient(timeout=3.0) as client:
        while True:
            data: dict[str, Any] | None = None
            connected = False
            try:
                response = await client.get(url)
                if response.is_success:
                    data = response.json()
                    connected = isinstance(data, dict)
            except (httpx.HTTPError, ValueError):
                pass

            sys.stdout.write(CLEAR + render(data, connected, interval))
            sys.stdout.flush()
            await asyncio.sleep(interval)


async def _run(host: str, port: int, interval: float) -> None:
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(),
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
        )
    )
    tui = asyncio.create_task(_tui(f"http://127.0.0.1:{port}/api/v1/metrics", interval))
    try:
        await server.serve()
    finally:
        tui.cancel()
        try:
            await tui
        except asyncio.CancelledError:
            pass
        sys.stdout.write(RESET)
        sys.stdout.flush()
        print("Bridge stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="LM Studio bridge with a live LCARS terminal dashboard")
    parser.add_argument("--host", default="0.0.0.0", help="Bridge bind address")
    parser.add_argument("--port", type=int, default=8000, help="Bridge port")
    parser.add_argument("--interval", type=float, default=2.0, help="Dashboard refresh seconds")
    args = parser.parse_args()
    try:
        asyncio.run(_run(args.host, args.port, args.interval))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
