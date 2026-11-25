namespace DashboardLMStudio.Models;

/// <summary>Subset of LM Studio's /api/v0/models entry for the loaded model.</summary>
public class LoadedModelInfo
{
    public string? Id { get; set; }
    public string? Arch { get; set; }
    public string? Quantization { get; set; }
    public int MaxContextLength { get; set; }
}
