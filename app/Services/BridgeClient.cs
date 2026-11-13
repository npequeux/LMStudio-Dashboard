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

    public BridgeClient(string baseUrl, string? apiKey)
    {
        _baseUrl = baseUrl.TrimEnd('/');
        _client = new HttpClient { Timeout = TimeSpan.FromSeconds(30) };

        if (!string.IsNullOrWhiteSpace(apiKey))
        {
            _client.DefaultRequestHeaders.Authorization =
                new AuthenticationHeaderValue("Bearer", apiKey.Trim());
        }
    }

    public async Task<bool> TestConnectionAsync(CancellationToken ct = default)
    {
        try
        {
            using var response = await _client.GetAsync($"{_baseUrl}/health", ct);
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

    public async Task<List<ErrorLogEntry>> GetErrorsAsync(CancellationToken ct = default)
    {
        using var response = await _client.GetAsync($"{_baseUrl}/api/v1/errors", ct);
        response.EnsureSuccessStatusCode();
        var errors = await response.Content.ReadFromJsonAsync<List<ErrorLogEntry>>(JsonOptions, ct);
        return errors ?? new List<ErrorLogEntry>();
    }

    public void Dispose() => _client.Dispose();
}
