using Microsoft.Maui.Graphics;

namespace DashboardLMStudio.Models;

public class ErrorLogEntry
{
    public string? Timestamp { get; set; }
    public string? Level { get; set; }
    public string? Message { get; set; }
    public string? Source { get; set; }

    public string SourceLabel => string.IsNullOrEmpty(Source) ? "[unknown]" : $"[{Source}]";

    public Color LevelColor => Level?.ToUpperInvariant() switch
    {
        "ERROR" => Color.FromRgb(0xFF, 0x44, 0x44),
        "WARN" => Color.FromRgb(0xFF, 0xA7, 0x26),
        _ => Color.FromRgb(0x8B, 0xC3, 0x4A),
    };
}
