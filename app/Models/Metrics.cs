namespace DashboardLMStudio.Models;

/// <summary>
/// Snapshot returned by the companion metrics bridge at /api/v1/metrics.
/// </summary>
public class Metrics
{
    public double CpuUsage { get; set; }
    public long MemoryUsedMB { get; set; }
    public double TokenPerSecond { get; set; }
    public double? GpuUsage { get; set; }
    public long? GpuMemoryUsedMB { get; set; }
    public long? GpuMemoryTotalMB { get; set; }

    /// <summary>Live token rate taken from the LM Studio engine log, if available.</summary>
    public double? LiveTokensPerSecond { get; set; }
    public string? LiveTokensPerSecondAt { get; set; }

    /// <summary>When the last completed prediction's token stats were recorded.</summary>
    public string? LastUsageAt { get; set; }

    /// <summary>Model that produced the last prediction, from the diagnostics stream.</summary>
    public string? ModelIdentifier { get; set; }
    public string? ModelPath { get; set; }

    /// <summary>Model currently loaded in LM Studio, read from /api/v0/models.</summary>
    public LoadedModelInfo? LoadedModel { get; set; }

    /// <summary>State of the listener that supplies the live token rate.</summary>
    public string? RuntimeLogMonitor { get; set; }
    public string? LogMonitor { get; set; }
    public string? ServerLogMonitor { get; set; }
    public int LiveTimingLines { get; set; }

    public long PromptTokens { get; set; }
    public long CompletionTokens { get; set; }
    public int ErrorCount { get; set; }
    public List<ErrorLogEntry> Errors { get; set; } = new();
}
