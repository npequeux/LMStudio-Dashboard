package com.example.dashboardlmstudio;

import android.app.Application;
import android.content.Context;
import androidx.annotation.NonNull;
import androidx.lifecycle.AndroidViewModel;
import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class DashboardViewModel extends AndroidViewModel {

    public enum ConnectionState { DISCONNECTED, CONNECTING, CONNECTED }

    private final MutableLiveData<ConnectionState> connectionStatus = new MutableLiveData<>(ConnectionState.DISCONNECTED);
    private final MutableLiveData<String> cpuUsage = new MutableLiveData<>("0");
    private final MutableLiveData<String> memoryUsage = new MutableLiveData<>("0");
    private final MutableLiveData<String> tokenPerSecond = new MutableLiveData<>("0");
    private final MutableLiveData<String> gpuSummary = new MutableLiveData<>("N/A");
    private final MutableLiveData<String> promptCompletionTokens = new MutableLiveData<>("0 / 0");
    private final MutableLiveData<Integer> errorCount = new MutableLiveData<>(0);
    private final MutableLiveData<List<ErrorLogEntry>> errors = new MutableLiveData<>(new ArrayList<>());
    private final MutableLiveData<String> errorMessage = new MutableLiveData<>();

    private final MutableLiveData<Boolean> monitoring = new MutableLiveData<>(false);
    private ScheduledExecutorService scheduler;
    private ExecutorService connectExecutor;
    private LMStudioApi apiClient;
    private String serverUrl;

    public DashboardViewModel(@NonNull Application application) {
        super(application);
        connectExecutor = Executors.newSingleThreadExecutor();
    }

    public LiveData<ConnectionState> getConnectionStatus() { return connectionStatus; }
    public LiveData<Boolean> getMonitoring() { return monitoring; }
    public LiveData<String> getCpuUsage() { return cpuUsage; }
    public LiveData<String> getMemoryUsage() { return memoryUsage; }
    public LiveData<String> getTokenPerSecond() { return tokenPerSecond; }
    public LiveData<String> getGpuSummary() { return gpuSummary; }
    public LiveData<String> getPromptCompletionTokens() { return promptCompletionTokens; }
    public LiveData<Integer> getErrorCount() { return errorCount; }
    public LiveData<List<ErrorLogEntry>> getErrors() { return errors; }
    public LiveData<String> getErrorMessage() { return errorMessage; }

    private static boolean isFresh(String isoTimestamp, long maxAgeMs) {
        if (isoTimestamp == null || isoTimestamp.isEmpty()) {
            return false;
        }
        try {
            java.time.OffsetDateTime time = java.time.OffsetDateTime.parse(isoTimestamp);
            long age = java.time.Duration.between(time, java.time.OffsetDateTime.now()).toMillis();
            return age >= 0 && age <= maxAgeMs;
        } catch (Exception e) {
            return false;
        }
    }

    public void connect(String url) {
        stopMonitoring();
        if (apiClient != null) {
            apiClient.close();
            apiClient = null;
        }
        this.serverUrl = url;
        connectionStatus.setValue(ConnectionState.CONNECTING);

        String apiKey = getApplication().getSharedPreferences("settings", Context.MODE_PRIVATE)
                .getString("bridge_api_key", null);

        connectExecutor.execute(() -> {
            try {
                apiClient = new LMStudioApi(url, apiKey);
                boolean connected = apiClient.testConnection();

                if (connected) {
                    connectionStatus.postValue(ConnectionState.CONNECTED);
                } else {
                    errorMessage.postValue("Failed to connect to " + url);
                    connectionStatus.postValue(ConnectionState.DISCONNECTED);
                }
            } catch (Exception e) {
                errorMessage.postValue("Connection error: " + e.getMessage());
                connectionStatus.postValue(ConnectionState.DISCONNECTED);
            }
        });
    }

    public void disconnect() {
        stopMonitoring();
        if (apiClient != null) {
            apiClient.close();
        }
        apiClient = null;
        serverUrl = null;
        connectionStatus.postValue(ConnectionState.DISCONNECTED);
    }

    public void startMonitoring(long intervalMs) {
        if (apiClient == null || serverUrl == null || serverUrl.trim().isEmpty()) {
            errorMessage.postValue("Not connected. Please connect first.");
            return;
        }
        if (scheduler != null && !scheduler.isShutdown()) {
            return;
        }

        scheduler = Executors.newScheduledThreadPool(1);
        scheduler.scheduleAtFixedRate(() -> {
            try {
                LMStudioApi.Metrics metrics = apiClient.getMetrics();
                if (metrics != null) {
                    cpuUsage.postValue(String.valueOf(metrics.getCpuUsage()));
                    memoryUsage.postValue(String.valueOf(metrics.getMemoryUsedMB()));
                    Double liveTps = metrics.getLiveTokensPerSecond();
                    if (liveTps != null && isFresh(metrics.getLiveTokensPerSecondAt(), 10_000L)) {
                        tokenPerSecond.postValue(String.valueOf(liveTps));
                    } else {
                        tokenPerSecond.postValue(String.valueOf(metrics.getTokenPerSecond()));
                    }

                    Double gpuUsage = metrics.getGpuUsage();
                    if (gpuUsage == null) {
                        gpuSummary.postValue("N/A");
                    } else {
                        String gpuText = String.format(java.util.Locale.US, "%.0f%%", gpuUsage);
                        Long gpuMemoryUsed = metrics.getGpuMemoryUsedMB();
                        Long gpuMemoryTotal = metrics.getGpuMemoryTotalMB();
                        if (gpuMemoryUsed != null && gpuMemoryTotal != null) {
                            gpuText += "\n" + gpuMemoryUsed + "/" + gpuMemoryTotal + " MB";
                        }
                        gpuSummary.postValue(gpuText);
                    }
                    promptCompletionTokens.postValue(
                            metrics.getPromptTokens() + " / " + metrics.getCompletionTokens());

                    errorCount.postValue(metrics.getErrorCount());
                    List<ErrorLogEntry> newErrors = metrics.getErrors();
                    if (newErrors != null) {
                        errors.postValue(newErrors);
                    }
                }
            } catch (Exception e) {
                errorMessage.postValue("Monitor error: " + e.getMessage());
            }
        }, 0, intervalMs, TimeUnit.MILLISECONDS);
        monitoring.postValue(true);
    }

    public void stopMonitoring() {
        if (scheduler != null) {
            scheduler.shutdown();
            scheduler = null;
        }
        monitoring.postValue(false);
    }

    @Override
    protected void onCleared() {
        super.onCleared();
        stopMonitoring();
        if (apiClient != null) {
            apiClient.close();
        }
        connectExecutor.shutdown();
    }
}
