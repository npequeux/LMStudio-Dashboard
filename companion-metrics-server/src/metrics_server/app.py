from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import json
import os
import time
from collections.abc import Callable
from typing import Any

import httpx
import psutil
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from metrics_server.state import MetricsState


@dataclass(frozen=True)
class Settings:
    lm_studio_url: str = field(
        default_factory=lambda: os.getenv("LM_STUDIO_URL", "http://192.168.129.35:1234/v1")
    )
    lm_studio_api_key: str | None = field(default_factory=lambda: os.getenv("LM_STUDIO_API_KEY"))


@dataclass(frozen=True)
class HostMetrics:
    cpu_usage: float
    memory_used_mb: int
    gpu_usage: float | None = None
    gpu_memory_used_mb: int | None = None
    gpu_memory_total_mb: int | None = None


def collect_gpu_metrics(nvml_module: Any | None = None) -> tuple[float | None, int | None, int | None]:
    """Return NVIDIA utilization and aggregate VRAM, or None values if unavailable."""
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
        # NVML is unavailable on non-NVIDIA systems or when the driver is not running.
        return None, None, None
    finally:
        if initialized:
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
) -> FastAPI:
    settings = settings or Settings()
    state = state or MetricsState()
    metrics_provider = metrics_provider or collect_system_metrics
    app = FastAPI(title="DashboardLMStudio Metrics Bridge", version="0.1.0")
    app.state.metrics_state = state

    def target_url(path: str) -> str:
        base_url = settings.lm_studio_url.rstrip("/")
        if base_url.endswith("/v1") and path.startswith("/v1/"):
            return base_url + path[3:]
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
            cpu_usage, memory_used_mb = metrics_provider()
        except Exception as exc:  # defensive: keep endpoint available if a host counter fails
            state.record_error(f"Could not read PC metrics: {exc}", source="system")
            cpu_usage, memory_used_mb = 0.0, 0
        return state.snapshot(cpu_usage, memory_used_mb)

    @app.get("/api/v1/errors")
    async def errors() -> list[dict[str, str]]:
        return state.errors()

    @app.get("/v1/models")
    async def models() -> Response:
        return await proxy_get("/v1/models")

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Response:
        request_body = await request.body()
        try:
            payload: Any = json.loads(request_body)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object")

        started_at = time.perf_counter()
        upstream_client = client()
        try:
            upstream_request = upstream_client.build_request(
                "POST",
                target_url("/v1/chat/completions"),
                content=request_body,
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
                state.record_tokens(
                    _completion_tokens_from_json(content), time.perf_counter() - started_at
                )
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
                state.record_tokens(
                    _completion_tokens_from_sse(bytes(collected)), time.perf_counter() - started_at
                )
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

    return app


app = create_app()
