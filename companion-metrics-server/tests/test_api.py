import json
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from metrics_server.app import (
    HostMetrics,
    Settings,
    _windows_gpu_metrics_from_samples,
    collect_gpu_metrics,
    create_app,
)
from metrics_server.state import MetricsState


def make_client(handler, *, state=None, metrics_provider=None):
    transport = httpx.MockTransport(handler)
    app = create_app(
        Settings(lm_studio_url="http://lm-studio.test"),
        state=state,
        metrics_provider=metrics_provider,
        transport=transport,
    )
    return TestClient(app)


def test_health_reports_bridge_ready():
    def handler(request):
        raise AssertionError("health should not need to contact LM Studio")

    with make_client(handler) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == "ok"


def test_metrics_match_android_app_contract():
    def handler(request):
        raise AssertionError("metrics should not contact LM Studio")

    with make_client(
        handler,
        metrics_provider=lambda: HostMetrics(37.5, 2048, 62.5, 5120, 8192),
    ) as client:
        response = client.get("/api/v1/metrics")

    assert response.status_code == 200
    assert response.json() == {
        "cpuUsage": 37.5,
        "memoryUsedMB": 2048,
        "gpuUsage": 62.5,
        "gpuMemoryUsedMB": 5120,
        "gpuMemoryTotalMB": 8192,
        "tokenPerSecond": 0.0,
        "promptTokens": 0,
        "completionTokens": 0,
        "errorCount": 0,
        "errors": [],
    }


def test_gpu_metrics_average_utilization_and_sum_vram():
    class FakeNvml:
        def __init__(self):
            self.shutdown = False

        def nvmlInit(self):
            pass

        def nvmlDeviceGetCount(self):
            return 2

        def nvmlDeviceGetHandleByIndex(self, index):
            return index

        def nvmlDeviceGetUtilizationRates(self, handle):
            return SimpleNamespace(gpu=(60, 80)[handle])

        def nvmlDeviceGetMemoryInfo(self, handle):
            used, total = ((1024, 4096), (2048, 8192))[handle]
            return SimpleNamespace(used=used * 1024 * 1024, total=total * 1024 * 1024)

        def nvmlShutdown(self):
            self.shutdown = True

    nvml = FakeNvml()
    assert collect_gpu_metrics(nvml) == (70.0, 3072, 12288)
    assert nvml.shutdown


def test_windows_gpu_counters_read_amd_gpu_utilization_and_vram():
    gpu_engine = (
        r"\\PC\GPU Engine(pid_123_luid_0x00000000_0x0000abcd_phys_0_eng_0_engtype_3D)"
        r"\Utilization Percentage"
    )
    adapter_usage = r"\\PC\GPU Adapter Memory(luid_0x00000000_0x0000abcd_phys_0)\Dedicated Usage"
    adapter_limit = r"\\PC\GPU Adapter Memory(luid_0x00000000_0x0000abcd_phys_0)\Dedicated Limit"

    metrics = _windows_gpu_metrics_from_samples(
        [
            {"Path": gpu_engine, "CookedValue": 42.5},
            {"Path": adapter_usage, "CookedValue": 2 * 1024**3},
            {"Path": adapter_limit, "CookedValue": 8 * 1024**3},
        ]
    )

    assert metrics == (42.5, 2048, 8192)


def test_models_endpoint_proxies_to_lm_studio():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "test-model"}]})

    with make_client(handler) as client:
        response = client.get("/v1/models")

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "test-model"


def test_models_proxy_accepts_lm_studio_v1_base_url():
    def handler(request):
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": []})

    app = create_app(Settings(lm_studio_url="http://192.168.129.35:1234/v1"), transport=httpx.MockTransport(handler))
    with TestClient(app) as client:
        response = client.get("/v1/models")

    assert response.status_code == 200


def test_models_proxy_accepts_base_url_with_v1_suffix():
    def handler(request):
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "test-model"}]})

    app = create_app(
        Settings(lm_studio_url="http://lm-studio.test/v1"),
        transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        response = client.get("/v1/models")

    assert response.status_code == 200


def test_non_streaming_chat_updates_token_rate():
    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 12},
                "stats": {"tokens_per_second": 41.8},
            },
        )

    with make_client(handler) as client:
        response = client.post("/v1/chat/completions", json={"model": "test-model", "messages": []})
        metrics = client.get("/api/v1/metrics").json()

    assert response.status_code == 200
    assert metrics["promptTokens"] == 7
    assert metrics["completionTokens"] == 12
    assert metrics["tokenPerSecond"] == 41.8


def test_native_lmstudio_v0_chat_records_prompt_and_native_stats():
    def handler(request):
        assert request.url.path == "/api/v0/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 24, "completion_tokens": 53},
                "stats": {"tokens_per_second": 51.4},
            },
        )

    app = create_app(
        Settings(lm_studio_url="http://lm-studio.test/v1"),
        transport=httpx.MockTransport(handler),
    )
    with TestClient(app) as client:
        response = client.post("/api/v0/chat/completions", json={"model": "test-model", "messages": []})
        metrics = client.get("/api/v1/metrics").json()

    assert response.status_code == 200
    assert metrics["promptTokens"] == 24
    assert metrics["completionTokens"] == 53
    assert metrics["tokenPerSecond"] == 51.4


def test_upstream_errors_are_exposed_to_dashboard():
    def handler(request):
        return httpx.Response(503, json={"error": {"message": "model server unavailable"}})

    with make_client(handler) as client:
        response = client.post("/v1/chat/completions", json={"model": "test-model", "messages": []})
        metrics = client.get("/api/v1/metrics").json()
        errors = client.get("/api/v1/errors").json()

    assert response.status_code == 503
    assert metrics["errorCount"] == 1
    assert errors[0]["level"] == "ERROR"
    assert "model server unavailable" in errors[0]["message"]


def test_streaming_chat_is_forwarded_and_records_usage():
    stream = (
        'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
        'data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":2},"stats":{"tokens_per_second":11.5}}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request):
        payload = json.loads(request.content)
        assert payload["stream"] is True
        return httpx.Response(200, text=stream, headers={"content-type": "text/event-stream"})

    with make_client(handler) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"model": "test-model", "messages": [], "stream": True},
        )
        metrics = client.get("/api/v1/metrics").json()

    assert response.status_code == 200
    assert response.text == stream
    assert metrics["promptTokens"] == 5
    assert metrics["completionTokens"] == 2
    assert metrics["tokenPerSecond"] == 11.5
