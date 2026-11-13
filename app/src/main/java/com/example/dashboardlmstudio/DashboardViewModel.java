package com.example.dashboardlmstudio;

import android.app.Application;
import androidx.annotation.NonNull;
import androidx.lifecycle.AndroidViewModel;
import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;
import androidx.lifecycle.Transformations;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class DashboardViewModel extends AndroidViewModel {

    public enum ConnectionState { DISCONNECTED, CONNECTING, CONNECTED }

    private final MutableLiveData<ConnectionState> connectionStatus = new MutableLiveData<>(ConnectionState.DISCONNECTED);
    private final MutableLiveData<String> cpuUsage = new MutableLiveData<>("0");
    private final MutableLiveData<String> memoryUsage = new MutableLiveData<>("0");
    private final MutableLiveData<String> tokenPerSecond = new MutableLiveData<>("0");
    private final MutableLiveData<Integer> errorCount = new MutableLiveData<>(0);
    private final MutableLiveData<List<ErrorLogEntry>> errors = new MutableLiveData<>(new ArrayList<>());
    private final MutableLiveData<String> errorMessage = new MutableLiveData<>();

    private ScheduledExecutorService scheduler;
    private LMStudioApi apiClient;
    private String serverUrl;

    public DashboardViewModel(@NonNull Application application) {
        super(application);
    }

    public LiveData<ConnectionState> getConnectionStatus() { return connectionStatus; }
    public LiveData<String> getCpuUsage() { return cpuUsage; }
    public LiveData<String> getMemoryUsage() { return memoryUsage; }
    public LiveData<String> getTokenPerSecond() { return tokenPerSecond; }
    public LiveData<Integer> getErrorCount() { return errorCount; }
    public LiveData<List<ErrorLogEntry>> getErrors() { return errors; }
    public LiveData<String> getErrorMessage() { return errorMessage; }

    public void connect(String url) {
        this.serverUrl = url;
        connectionStatus.setValue(ConnectionState.CONNECTING);

        Executors.newSingleThreadExecutor().execute(() -> {
            try {
                apiClient = new LMStudioApi(url, getApplication());
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
                    tokenPerSecond.postValue(String.valueOf(metrics.getTokenPerSecond()));

                    if (metrics.getErrorCount() > 0) {
                        errorCount.postValue(metrics.getErrorCount());
                        List<ErrorLogEntry> newErrors = metrics.getErrors();
                        if (newErrors != null && !newErrors.isEmpty()) {
                            errors.postValue(newErrors);
                        }
                    }
                }
            } catch (Exception e) {
                errorMessage.postValue("Monitor error: " + e.getMessage());
            }
        }, 0, intervalMs, TimeUnit.MILLISECONDS);
    }

    public void stopMonitoring() {
        if (scheduler != null) {
            scheduler.shutdown();
            scheduler = null;
        }
    }

    @Override
    protected void onCleared() {
        super.onCleared();
        stopMonitoring();
    }
}
