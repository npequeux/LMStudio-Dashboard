using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Globalization;
using System.Runtime.CompilerServices;
using DashboardLMStudio.Models;
using DashboardLMStudio.Services;
using Microsoft.Maui.Controls;
using Microsoft.Maui.Graphics;
using Microsoft.Maui.Storage;

namespace DashboardLMStudio.ViewModels;

public class MainViewModel : INotifyPropertyChanged
{
    public enum ConnectionState { Disconnected, Connecting, Connected }

    private const int PollIntervalMs = 5000;
    private static readonly TimeSpan LiveWindow = TimeSpan.FromSeconds(10);
    private const string DefaultServerUrl = "http://192.168.129.35:8000";

    private BridgeClient? _client;
    private string _serverUrl = "";
    private string _apiKey = "";
    private ConnectionState _state = ConnectionState.Disconnected;
    private bool _monitoring;
    private Timer? _timer;
    private int _polling;

    public MainViewModel()
    {
        var savedUrl = Preferences.Get("server_url", "");
        if (string.IsNullOrWhiteSpace(savedUrl)
            || savedUrl.Contains(":1234")
            || savedUrl.EndsWith("/v1", StringComparison.OrdinalIgnoreCase))
        {
            savedUrl = DefaultServerUrl;
        }
        ServerUrl = savedUrl;
        ApiKey = Preferences.Get("bridge_api_key", "");

        ConnectCommand = new Command(async () => await ConnectAsync(), () => CanConnect);
        DisconnectCommand = new Command(Disconnect, () => CanDisconnect);
        ToggleMonitoringCommand = new Command(ToggleMonitoring, () => _state == ConnectionState.Connected);
        UpdateStateProperties();
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public string ServerUrl
    {
        get => _serverUrl;
        set
        {
            if (SetProperty(ref _serverUrl, value))
            {
                OnPropertyChanged(nameof(CanConnect));
                ConnectCommand.ChangeCanExecute();
            }
        }
    }

    public string ApiKey
    {
        get => _apiKey;
        set => SetProperty(ref _apiKey, value);
    }

    public string ConnectionStatusText => _state switch
    {
        ConnectionState.Connected => "Connected",
        ConnectionState.Connecting => "Connecting...",
        _ => "Disconnected",
    };

    public Color ConnectionStatusColor => _state switch
    {
        ConnectionState.Connected => Color.FromRgb(0x4C, 0xAF, 0x50),
        ConnectionState.Connecting => Color.FromRgb(0xFF, 0x98, 0x00),
        _ => Color.FromRgb(0xF4, 0x43, 0x36),
    };

    public bool IsConnecting => _state == ConnectionState.Connecting;
    public bool CanConnect => _state != ConnectionState.Connecting && !string.IsNullOrWhiteSpace(ServerUrl);
    public bool CanDisconnect => _state != ConnectionState.Disconnected;
    public string MonitoringLabel => _monitoring ? "Stop Monitoring" : "Start Monitoring";

    public string CpuText { get; private set; } = "0%";
    public string MemoryText { get; private set; } = "0 MB";
    public string TokenText { get; private set; } = "0/s";
    public string GpuText { get; private set; } = "N/A";
    public string PromptCompletionText { get; private set; } = "0 / 0";
    public string ErrorCountText { get; private set; } = "0";

    public ObservableCollection<ErrorLogEntry> Errors { get; } = new();

    public Command ConnectCommand { get; }
    public Command DisconnectCommand { get; }
    public Command ToggleMonitoringCommand { get; }

    private void UpdateStateProperties()
    {
        OnPropertyChanged(nameof(ConnectionStatusText));
        OnPropertyChanged(nameof(ConnectionStatusColor));
        OnPropertyChanged(nameof(IsConnecting));
        OnPropertyChanged(nameof(CanConnect));
        OnPropertyChanged(nameof(CanDisconnect));
        OnPropertyChanged(nameof(MonitoringLabel));
        ConnectCommand.ChangeCanExecute();
        DisconnectCommand.ChangeCanExecute();
        ToggleMonitoringCommand.ChangeCanExecute();
    }

    private async Task ConnectAsync()
    {
        StopMonitoring();
        _client?.Dispose();
        _client = null;

        var url = ServerUrl.Trim();
        _state = ConnectionState.Connecting;
        UpdateStateProperties();

        Preferences.Set("server_url", url);
        Preferences.Set("bridge_api_key", ApiKey.Trim());

        var client = new BridgeClient(url, ApiKey);
        bool connected;
        try
        {
            connected = await client.TestConnectionAsync();
        }
        catch
        {
            connected = false;
        }

        if (connected && _state == ConnectionState.Connecting)
        {
            _client = client;
            _state = ConnectionState.Connected;
            UpdateStateProperties();
        }
        else
        {
            client.Dispose();
            if (_state != ConnectionState.Connecting)
            {
                return;
            }
            _state = ConnectionState.Disconnected;
            UpdateStateProperties();
            await ShowMessageAsync($"Failed to connect to {url}");
        }
    }

    private void Disconnect()
    {
        StopMonitoring();
        _client?.Dispose();
        _client = null;
        _state = ConnectionState.Disconnected;
        UpdateStateProperties();
    }

    private void ToggleMonitoring()
    {
        if (_monitoring)
        {
            StopMonitoring();
        }
        else
        {
            StartMonitoring();
        }
    }

    private void StartMonitoring()
    {
        if (_client == null || _state != ConnectionState.Connected)
        {
            _ = ShowMessageAsync("Not connected. Please connect first.");
            return;
        }

        StopMonitoring();
        _timer = new Timer(
            async _ => await PollAsync(),
            null,
            TimeSpan.Zero,
            TimeSpan.FromMilliseconds(PollIntervalMs));
        _monitoring = true;
        UpdateStateProperties();
    }

    private void StopMonitoring()
    {
        _timer?.Dispose();
        _timer = null;
        _monitoring = false;
        UpdateStateProperties();
    }

    private async Task PollAsync()
    {
        if (Interlocked.Exchange(ref _polling, 1) == 1)
        {
            return;
        }

        try
        {
            var client = _client;
            if (client == null)
            {
                return;
            }

            var metrics = await client.GetMetricsAsync();
            if (metrics != null)
            {
                RunOnUi(() => ApplyMetrics(metrics));
            }
        }
        catch (Exception ex)
        {
            var message = $"Monitor error: {ex.Message}";
            RunOnUi(() => _ = ShowMessageAsync(message));
        }
        finally
        {
            Interlocked.Exchange(ref _polling, 0);
        }
    }

    private void ApplyMetrics(Metrics metrics)
    {
        CpuText = string.Format(CultureInfo.InvariantCulture, "{0:0.#}%", metrics.CpuUsage);
        MemoryText = metrics.MemoryUsedMB.ToString(CultureInfo.InvariantCulture) + " MB";

        if (metrics.LiveTokensPerSecond is double live && IsFresh(metrics.LiveTokensPerSecondAt, LiveWindow))
        {
            TokenText = string.Format(CultureInfo.InvariantCulture, "{0:0.##}/s", live);
        }
        else
        {
            TokenText = string.Format(CultureInfo.InvariantCulture, "{0:0.##}/s", metrics.TokenPerSecond);
        }

        if (metrics.GpuUsage is double gpu)
        {
            var text = string.Format(CultureInfo.InvariantCulture, "{0:0}%", gpu);
            if (metrics.GpuMemoryUsedMB is long used && metrics.GpuMemoryTotalMB is long total)
            {
                text += $"\n{used}/{total} MB";
            }
            GpuText = text;
        }
        else
        {
            GpuText = "N/A";
        }

        PromptCompletionText = string.Format(
            CultureInfo.InvariantCulture, "{0} / {1}", metrics.PromptTokens, metrics.CompletionTokens);
        ErrorCountText = metrics.ErrorCount.ToString(CultureInfo.InvariantCulture);

        Errors.Clear();
        foreach (var entry in metrics.Errors)
        {
            Errors.Add(entry);
        }

        OnPropertyChanged(nameof(CpuText));
        OnPropertyChanged(nameof(MemoryText));
        OnPropertyChanged(nameof(TokenText));
        OnPropertyChanged(nameof(GpuText));
        OnPropertyChanged(nameof(PromptCompletionText));
        OnPropertyChanged(nameof(ErrorCountText));
    }

    private static bool IsFresh(string? isoTimestamp, TimeSpan maxAge)
    {
        if (string.IsNullOrEmpty(isoTimestamp))
        {
            return false;
        }
        if (!DateTimeOffset.TryParse(isoTimestamp, out var time))
        {
            return false;
        }
        var age = DateTimeOffset.Now - time;
        return age >= TimeSpan.Zero && age <= maxAge;
    }

    private static void RunOnUi(Action action)
    {
        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher != null)
        {
            dispatcher.Dispatch(action);
        }
        else
        {
            action();
        }
    }

    private async Task ShowMessageAsync(string message)
    {
        var page = Application.Current?.Windows.FirstOrDefault()?.Page;
        if (page != null)
        {
            await page.DisplayAlertAsync("LM Studio Monitor", message, "OK");
        }
    }

    protected void OnPropertyChanged([CallerMemberName] string? propertyName = null)
        => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));

    protected bool SetProperty<T>(ref T field, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value))
        {
            return false;
        }
        field = value;
        OnPropertyChanged(propertyName);
        return true;
    }
}
