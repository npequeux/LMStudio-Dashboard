using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using DashboardLMStudio.Models;

namespace DashboardLMStudio.Services;

/// <summary>
/// Thin HTTP client for the companion metrics bridge.
/// </summary>
public class BridgeClient : IDisposable
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    private readonly HttpClient _client;
    private readonly string _baseUrl;

    public BridgeClient(string baseUrl, string? apiKey, HttpMessageHandler? handler = null)
    {
        _baseUrl = baseUrl.TrimEnd('/');
        _client = handler is null
            ? new HttpClient { Timeout = TimeSpan.FromSeconds(30) }
            : new HttpClient(handler, disposeHandler: false) { Timeout = TimeSpan.FromSeconds(30) };

        if (!string.IsNullOrWhiteSpace(apiKey))
        {
            _client.DefaultRequestHeaders.Authorization =
                new AuthenticationHeaderValue("Bearer", apiKey.Trim());
        }
    }

    /// <summary>
    /// Probes an authenticated route, not /health: the bridge leaves /health open
    /// for liveness, so a wrong API key would otherwise still report "Connected".
    /// </summary>
    public async Task<bool> TestConnectionAsync(CancellationToken ct = default)
    {
        try
        {
            using var response = await _client.GetAsync($"{_baseUrl}/api/v1/metrics", ct);
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    public async Task<Metrics?> GetMetricsAsync(CancellationToken ct = default)
    {
        using var response = await _client.GetAsync($"{_baseUrl}/api/v1/metrics", ct);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<Metrics>(JsonOptions, ct);
    }

    public void Dispose() => _client.Dispose();
}
