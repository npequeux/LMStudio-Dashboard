import json

import httpx
from fastapi.testclient import TestClient

from metrics_server.app import Settings, create_app
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
        metrics_provider=lambda: (37.5, 2048),
    ) as client:
        response = client.get("/api/v1/metrics")

    assert response.status_code == 200
    assert response.json() == {
        "cpuUsage": 37.5,
        "memoryUsedMB": 2048,
        "tokenPerSecond": 0.0,
        "errorCount": 0,
        "errors": [],
    }


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
            json={"choices": [{"message": {"content": "hello"}}], "usage": {"completion_tokens": 12}},
        )

    with make_client(handler) as client:
        response = client.post("/v1/chat/completions", json={"model": "test-model", "messages": []})
        metrics = client.get("/api/v1/metrics").json()

    assert response.status_code == 200
    assert metrics["tokenPerSecond"] > 0


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
        'data: {"choices":[],"usage":{"completion_tokens":2}}\n\n'
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
    assert metrics["tokenPerSecond"] > 0
