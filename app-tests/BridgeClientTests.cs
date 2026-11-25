using System.Net;
using DashboardLMStudio.Services;
using Xunit;

namespace DashboardLMStudio.Models
{
    // Minimal stand-in so Metrics.cs can compile without MAUI.Graphics.
    public class ErrorLogEntry
    {
        public string? Timestamp { get; set; }
        public string? Level { get; set; }
        public string? Message { get; set; }
        public string? Source { get; set; }
    }
}

namespace DashboardLMStudio.Tests
{
    public class BridgeClientTests
    {
        private sealed class StubHandler : HttpMessageHandler
        {
            private readonly Func<HttpRequestMessage, HttpResponseMessage> _respond;

            public StubHandler(Func<HttpRequestMessage, HttpResponseMessage> respond)
                => _respond = respond;

            public List<HttpRequestMessage> Requests { get; } = new();

            protected override Task<HttpResponseMessage> SendAsync(
                HttpRequestMessage request, CancellationToken cancellationToken)
            {
                Requests.Add(request);
                return Task.FromResult(_respond(request));
            }
        }

        [Fact]
        public async Task Connect_probe_uses_authenticated_route_not_health()
        {
            var handler = new StubHandler(_ => new HttpResponseMessage(HttpStatusCode.OK));
            using var client = new BridgeClient("http://bridge.test:8000/", null, handler);

            Assert.True(await client.TestConnectionAsync());
            Assert.Equal("/api/v1/metrics", Assert.Single(handler.Requests).RequestUri?.AbsolutePath);
        }

        [Fact]
        public async Task Connect_probe_rejects_unauthorized()
        {
            var handler = new StubHandler(_ => new HttpResponseMessage(HttpStatusCode.Unauthorized));
            using var client = new BridgeClient("http://bridge.test:8000", "wrong-key", handler);

            Assert.False(await client.TestConnectionAsync());
            Assert.Equal(
                "Bearer wrong-key",
                Assert.Single(handler.Requests).Headers.Authorization?.ToString());
        }

        [Fact]
        public async Task Metrics_deserializes_new_fields()
        {
            const string body = """
            {"cpuUsage":12.5,"memoryUsedMB":2048,"tokenPerSecond":8.8,
             "liveTokensPerSecond":19.4,"liveTokensPerSecondAt":"2026-11-25T10:00:00Z",
             "lastUsageAt":"2026-11-25T09:59:00Z","modelIdentifier":"model-a",
             "loadedModel":{"id":"model-a","arch":"qwen35","quantization":"IQ4_NL","maxContextLength":262144},
             "runtimeLogMonitor":"running","liveTimingLines":7,
             "promptTokens":41,"completionTokens":964,"errorCount":0,"errors":[]}
            """;
            var handler = new StubHandler(_ => new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(body)
            });
            using var client = new BridgeClient("http://bridge.test:8000", null, handler);

            var metrics = await client.GetMetricsAsync();

            Assert.NotNull(metrics);
            Assert.Equal("model-a", metrics!.ModelIdentifier);
            Assert.Equal("model-a", metrics.LoadedModel?.Id);
            Assert.Equal("running", metrics.RuntimeLogMonitor);
            Assert.Equal(7, metrics.LiveTimingLines);
            Assert.Equal(19.4, metrics.LiveTokensPerSecond);
        }
    }
}
