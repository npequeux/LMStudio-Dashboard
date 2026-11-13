package com.example.dashboardlmstudio;

import okhttp3.OkHttpClient;
import okhttp3.logging.HttpLoggingInterceptor;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class LMStudioApi {

    private final String baseUrl;
    private final LMStudioService service;
    private final OkHttpClient client;

    public interface LMStudioService {
        @retrofit2.http.GET("/v1/models")
        retrofit2.Call<List<Model>> getModels();

        @retrofit2.http.GET("/api/v1/metrics")
        retrofit2.Call<Metrics> getMetrics();

        @retrofit2.http.GET("/api/v1/errors")
        retrofit2.Call<List<ErrorLogEntry>> getErrors();

        @retrofit2.http.GET("/health")
        retrofit2.Call<String> healthCheck();
    }

    public static class Metrics {
        private double cpuUsage;
        private long memoryUsedMB;
        private double tokenPerSecond;
        private Double gpuUsage;
        private Long gpuMemoryUsedMB;
        private Long gpuMemoryTotalMB;
        private Double liveTokensPerSecond;
        private String liveTokensPerSecondAt;
        private long promptTokens;
        private long completionTokens;
        private int errorCount;
        private List<ErrorLogEntry> errors;

        public double getCpuUsage() { return cpuUsage; }
        public long getMemoryUsedMB() { return memoryUsedMB; }
        public double getTokenPerSecond() { return tokenPerSecond; }
        public Double getGpuUsage() { return gpuUsage; }
        public Long getGpuMemoryUsedMB() { return gpuMemoryUsedMB; }
        public Long getGpuMemoryTotalMB() { return gpuMemoryTotalMB; }
        public Double getLiveTokensPerSecond() { return liveTokensPerSecond; }
        public String getLiveTokensPerSecondAt() { return liveTokensPerSecondAt; }
        public long getPromptTokens() { return promptTokens; }
        public long getCompletionTokens() { return completionTokens; }
        public int getErrorCount() { return errorCount; }
        public List<ErrorLogEntry> getErrors() { return errors != null ? errors : new ArrayList<>(); }
    }

    public static class Model {
        private String id;
        private String name;
        private boolean loaded;

        public String getId() { return id; }
        public String getName() { return name; }
        public boolean isLoaded() { return loaded; }
    }

    public LMStudioApi(String baseUrl, String apiKey) {
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;

        HttpLoggingInterceptor loggingInterceptor = new HttpLoggingInterceptor();
        loggingInterceptor.setLevel(HttpLoggingInterceptor.Level.BASIC);

        OkHttpClient.Builder builder = new OkHttpClient.Builder()
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(10, TimeUnit.SECONDS)
                .addInterceptor(loggingInterceptor);

        if (apiKey != null && !apiKey.trim().isEmpty()) {
            builder.addInterceptor(chain -> chain.proceed(
                    chain.request().newBuilder()
                            .header("Authorization", "Bearer " + apiKey.trim())
                            .build()));
        }

        this.client = builder.build();

        Retrofit retrofit = new Retrofit.Builder()
                .baseUrl(this.baseUrl + "/")
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build();

        this.service = retrofit.create(LMStudioService.class);
    }

    /** Release the underlying OkHttp threads and connections. */
    public void close() {
        client.dispatcher().executorService().shutdown();
        client.connectionPool().evictAll();
    }

    public boolean testConnection() {
        try {
            retrofit2.Response<String> response = service.healthCheck().execute();
            return response.isSuccessful();
        } catch (Exception e) {
            return false;
        }
    }

    public Metrics getMetrics() throws Exception {
        retrofit2.Call<Metrics> call = service.getMetrics();
        retrofit2.Response<Metrics> response = call.execute();
        if (!response.isSuccessful()) {
            throw new RuntimeException("Failed to fetch metrics: " + response.code());
        }
        return response.body();
    }

    public List<Model> getModels() throws Exception {
        retrofit2.Call<List<Model>> call = service.getModels();
        retrofit2.Response<List<Model>> response = call.execute();
        if (!response.isSuccessful()) {
            throw new RuntimeException("Failed to fetch models: " + response.code());
        }
        return response.body();
    }

    public List<ErrorLogEntry> getErrors() throws Exception {
        retrofit2.Call<List<ErrorLogEntry>> call = service.getErrors();
        retrofit2.Response<List<ErrorLogEntry>> response = call.execute();
        if (!response.isSuccessful()) {
            throw new RuntimeException("Failed to fetch errors: " + response.code());
        }
        return response.body();
    }
}
