from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import psutil
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from metrics_server.lms_log import LmsLogMonitor, seed_state_from_history
from metrics_server.state import MetricsState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    lm_studio_url: str = field(
        default_factory=lambda: os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234/v1")
    )
    lm_studio_api_key: str | None = field(default_factory=lambda: os.getenv("LM_STUDIO_API_KEY"))


@dataclass(frozen=True)
class HostMetrics:
    cpu_usage: float
    memory_used_mb: int
    gpu_usage: float | None = None
    gpu_memory_used_mb: int | None = None
    gpu_memory_total_mb: int | None = None


def _windows_gpu_metrics_from_samples(samples: list[dict[str, Any]]) -> tuple[float | None, int | None, int | None]:
    engine_usage: dict[tuple[str, str], float] = {}
    memory_used: dict[str, float] = {}
    memory_total: dict[str, float] = {}

    for sample in samples:
        path = str(sample.get("Path", sample.get("path", "")))
        try:
            value = max(0.0, float(sample.get("CookedValue", sample.get("value", 0))))
        except (TypeError, ValueError, OverflowError):
            continue
        lower_path = path.lower()
        instance_match = re.search(r"\(([^)]*)\)", path)
        instance = instance_match.group(1) if instance_match else "default"
        adapter_match = re.search(r"(luid_.*?_phys_\d+)", instance, re.IGNORECASE)
        adapter = adapter_match.group(1).lower() if adapter_match else "default"

        if "gpu engine" in lower_path and "utilization percentage" in lower_path:
            engine_match = re.search(r"engtype_(.*)$", instance, re.IGNORECASE)
            engine = engine_match.group(1).lower() if engine_match else "other"
            key = (adapter, engine)
            engine_usage[key] = engine_usage.get(key, 0.0) + value
        elif "gpu adapter memory" in lower_path and "dedicated usage" in lower_path:
            memory_used[adapter] = value
        elif "gpu adapter memory" in lower_path and "dedicated limit" in lower_path:
            memory_total[adapter] = value

    adapters = set(memory_used) | {key[0] for key in engine_usage}
    if not adapters:
        return None, None, None

    usage_by_adapter: dict[str, float] = {}
    for adapter in adapters:
        engine_values = [value for (key_adapter, _), value in engine_usage.items() if key_adapter == adapter]
        if engine_values:
            # Task Manager-style: report the busiest GPU engine, capped at 100%.
            usage_by_adapter[adapter] = min(100.0, max(engine_values))
    selected = (
        max(usage_by_adapter, key=lambda adapter: usage_by_adapter[adapter])
        if usage_by_adapter
        else next(iter(adapters))
    )
    usage = round(usage_by_adapter[selected], 1) if selected in usage_by_adapter else None
    mb = 1024 * 1024
    used_mb = int(memory_used[selected] / mb) if selected in memory_used else None
    total_mb = int(memory_total[selected] / mb) if selected in memory_total else None
    return usage, used_mb, total_mb


def _collect_windows_gpu_metrics() -> tuple[float | None, int | None, int | None]:
    script = r"""
$ErrorActionPreference = 'Stop'
$paths = @()
try { $paths += (Get-Counter -ListSet 'GPU Engine').PathsWithInstances | Where-Object { $_ -match 'Utilization Percentage$' } } catch {}
try { $paths += (Get-Counter -ListSet 'GPU Adapter Memory').PathsWithInstances | Where-Object { $_ -match 'Dedicated Usage$|Dedicated Limit$' } } catch {}
if ($paths.Count -eq 0) { '[]'; exit 0 }
try {
  $samples = (Get-Counter -Counter $paths -ErrorAction Stop).CounterSamples
  $result = @($samples | ForEach-Object { [PSCustomObject]@{ Path = $_.Path; CookedValue = $_.CookedValue } })
  ConvertTo-Json -InputObject $result -Compress
} catch { '[]' }
"""
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return None, None, None
        samples = json.loads(completed.stdout)
        if isinstance(samples, dict):
            samples = [samples]
        if not isinstance(samples, list):
            return None, None, None
        return _windows_gpu_metrics_from_samples(samples)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return None, None, None


def collect_gpu_metrics(nvml_module: Any | None = None) -> tuple[float | None, int | None, int | None]:
    """Read AMD/any-vendor GPU metrics via Windows counters, with NVML fallback."""
    if nvml_module is None and sys.platform == "win32":
        windows_metrics = _collect_windows_gpu_metrics()
        if any(value is not None for value in windows_metrics):
            return windows_metrics

    nvml = nvml_module
    initialized = False
    try:
        if nvml is None:
            nvml = importlib.import_module("pynvml")
        nvml.nvmlInit()
        initialized = True
        device_count = int(nvml.nvmlDeviceGetCount())
        if device_count <= 0:
            return None, None, None

        utilizations: list[float] = []
        used_bytes = 0
        total_bytes = 0
        for index in range(device_count):
            handle = nvml.nvmlDeviceGetHandleByIndex(index)
            utilization = nvml.nvmlDeviceGetUtilizationRates(handle)
            memory = nvml.nvmlDeviceGetMemoryInfo(handle)
            utilizations.append(float(utilization.gpu))
            used_bytes += int(memory.used)
            total_bytes += int(memory.total)

        mb = 1024 * 1024
        return round(sum(utilizations) / len(utilizations), 1), int(used_bytes / mb), int(total_bytes / mb)
    except Exception:
        return None, None, None
    finally:
        if initialized and nvml is not None:
            try:
                nvml.nvmlShutdown()
            except Exception:
                pass


def collect_system_metrics() -> HostMetrics:
    cpu_usage = psutil.cpu_percent(interval=None)
    memory_used_mb = int(psutil.virtual_memory().used / (1024 * 1024))
    gpu_usage, gpu_memory_used_mb, gpu_memory_total_mb = collect_gpu_metrics()
    return HostMetrics(cpu_usage, memory_used_mb, gpu_usage, gpu_memory_used_mb, gpu_memory_total_mb)


def _int_or_zero(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _usage_from_payload(data: Any) -> dict[str, int | float] | None:
    if not isinstance(data, dict):
        return None
    raw_usage = data.get("usage")
    raw_stats = data.get("stats")
    usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
    stats: dict[str, Any] = raw_stats if isinstance(raw_stats, dict) else {}
    if not usage and not stats:
        return None

    result: dict[str, int | float] = {
        "prompt_tokens": _int_or_zero(usage.get("prompt_tokens", usage.get("input_tokens"))),
        "completion_tokens": _int_or_zero(
            usage.get("completion_tokens", usage.get("output_tokens"))
        ),
    }
    try:
        if stats.get("tokens_per_second") is not None:
            result["tokens_per_second"] = max(0.0, float(stats["tokens_per_second"]))
    except (TypeError, ValueError, OverflowError):
        pass
    return result


def _usage_from_json(body: bytes) -> dict[str, int | float] | None:
    try:
        return _usage_from_payload(json.loads(body))
    except (ValueError, TypeError):
        return None


def _usage_from_sse(body: bytes) -> dict[str, int | float] | None:
    latest_usage: dict[str, int | float] | None = None
    for line in body.decode("utf-8", errors="replace").splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            usage = _usage_from_payload(json.loads(payload))
        except (ValueError, TypeError):
            continue
        if usage is not None:
            latest_usage = usage
    return latest_usage


def _error_message(body: bytes, fallback: str) -> str:
    try:
        data = json.loads(body)
        error = data.get("error", data)
        if isinstance(error, dict):
            return str(error.get("message") or fallback)
        return str(error)
    except (ValueError, TypeError, AttributeError):
        return body.decode("utf-8", errors="replace")[:1000] or fallback


def create_app(
    settings: Settings | None = None,
    *,
    state: MetricsState | None = None,
    metrics_provider: Callable[[], HostMetrics] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    enable_lms_log_stream: bool = True,
    history_reader: Callable[[], dict[str, int | float] | None] | None = None,
) -> FastAPI:
    settings = settings or Settings()
    state = state or MetricsState()
    metrics_provider = metrics_provider or collect_system_metrics
    log_monitor = LmsLogMonitor(state, enabled=enable_lms_log_stream)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        seed_state_from_history(state, reader=history_reader)
        log_monitor.start()
        logger.info("LM Studio log monitor status: %s", log_monitor.status)
        try:
            yield
        finally:
            log_monitor.stop()

    app = FastAPI(title="DashboardLMStudio Metrics Bridge", version="0.2.0", lifespan=lifespan)
    app.state.metrics_state = state

    def target_url(path: str) -> str:
        base_url = settings.lm_studio_url.rstrip("/")
        if base_url.endswith("/v1"):
            if path.startswith("/v1/"):
                return base_url + path[3:]
            if path.startswith("/api/v0/"):
                return base_url[:-3] + path
        return base_url + path

    def upstream_headers(content_type: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if content_type:
            headers["content-type"] = content_type
        if settings.lm_studio_api_key:
            headers["authorization"] = f"Bearer {settings.lm_studio_api_key}"
        return headers

    def client() -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=120.0, transport=transport)

    def relay(response: httpx.Response, content: bytes) -> Response:
        headers: dict[str, str] = {}
        if content_type := response.headers.get("content-type"):
            headers["content-type"] = content_type
        return Response(content=content, status_code=response.status_code, headers=headers)

    async def proxy_get(path: str) -> Response:
        try:
            async with client() as upstream_client:
                upstream = await upstream_client.get(
                    target_url(path), headers=upstream_headers()
                )
        except httpx.HTTPError as exc:
            state.record_error(f"Could not reach LM Studio: {exc}", source="upstream")
            raise HTTPException(status_code=502, detail="Could not reach LM Studio") from exc

        if upstream.status_code >= 400:
            state.record_error(
                _error_message(upstream.content, f"LM Studio returned HTTP {upstream.status_code}"),
                source="upstream",
            )
        return relay(upstream, upstream.content)

    @app.get("/health")
    async def health() -> JSONResponse:
        # Return a JSON string because the Android Retrofit client expects a String body.
        return JSONResponse(content="ok")

    @app.get("/api/v1/metrics")
    async def metrics() -> dict[str, object]:
        try:
            host_metrics = metrics_provider()
        except Exception as exc:  # keep metrics endpoint available if a host counter fails
            state.record_error(f"Could not read host metrics: {exc}", source="system")
            host_metrics = HostMetrics(cpu_usage=0.0, memory_used_mb=0)
        snapshot = state.snapshot(
            cpu_usage=host_metrics.cpu_usage,
            memory_used_mb=host_metrics.memory_used_mb,
            gpu_usage=host_metrics.gpu_usage,
            gpu_memory_used_mb=host_metrics.gpu_memory_used_mb,
            gpu_memory_total_mb=host_metrics.gpu_memory_total_mb,
        )
        snapshot["logMonitor"] = log_monitor.status
        return snapshot

    @app.get("/api/v1/errors")
    async def errors() -> list[dict[str, str]]:
        return state.errors()

    @app.get("/v1/models")
    async def models() -> Response:
        return await proxy_get("/v1/models")

    def record_usage(usage: dict[str, int | float] | None, elapsed_seconds: float) -> None:
        if usage is None:
            return
        state.record_usage(
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            elapsed_seconds=elapsed_seconds,
            tokens_per_second=(
                float(usage["tokens_per_second"])
                if "tokens_per_second" in usage
                else None
            ),
        )

    async def proxy_chat_completion(request: Request, upstream_path: str) -> Response:
        request_body = await request.body()
        try:
            payload: Any = json.loads(request_body)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object")

        started_at = time.perf_counter()
        upstream_client = client()
        upstream_body = request_body
        if payload.get("stream") and "stream_options" not in payload:
            # Ask LM Studio for a final usage chunk so streaming inferences are
            # measured too; clients that already set stream_options are left alone.
            payload = {**payload, "stream_options": {"include_usage": True}}
            upstream_body = json.dumps(payload).encode("utf-8")
        try:
            upstream_request = upstream_client.build_request(
                "POST",
                target_url(upstream_path),
                content=upstream_body,
                headers=upstream_headers(request.headers.get("content-type", "application/json")),
            )
            upstream = await upstream_client.send(upstream_request, stream=True)
        except httpx.HTTPError as exc:
            await upstream_client.aclose()
            state.record_error(f"Could not reach LM Studio: {exc}", source="proxy")
            raise HTTPException(status_code=502, detail="Could not reach LM Studio") from exc

        if upstream.status_code >= 400:
            content = await upstream.aread()
            state.record_error(
                _error_message(content, f"LM Studio returned HTTP {upstream.status_code}"),
                source="inference",
            )
            await upstream.aclose()
            await upstream_client.aclose()
            return relay(upstream, content)

        content_type = upstream.headers.get("content-type", "application/json")
        if not payload.get("stream", False):
            try:
                content = await upstream.aread()
                record_usage(_usage_from_json(content), time.perf_counter() - started_at)
                return relay(upstream, content)
            finally:
                await upstream.aclose()
                await upstream_client.aclose()

        async def stream_body():
            collected = bytearray()
            try:
                async for chunk in upstream.aiter_bytes():
                    collected.extend(chunk)
                    yield chunk
                record_usage(_usage_from_sse(bytes(collected)), time.perf_counter() - started_at)
            except httpx.HTTPError as exc:
                state.record_error(f"Streaming from LM Studio failed: {exc}", source="inference")
                raise
            finally:
                await upstream.aclose()
                await upstream_client.aclose()

        return StreamingResponse(
            stream_body(),
            status_code=upstream.status_code,
            headers={"content-type": content_type},
        )

    @app.get("/api/v0/models")
    async def native_models() -> Response:
        return await proxy_get("/api/v0/models")

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Response:
        return await proxy_chat_completion(request, "/v1/chat/completions")

    @app.post("/api/v0/chat/completions")
    async def native_chat_completions(request: Request) -> Response:
        return await proxy_chat_completion(request, "/api/v0/chat/completions")

    return app


app = create_app()
