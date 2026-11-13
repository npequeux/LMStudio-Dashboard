package com.example.dashboardlmstudio;

import static org.junit.Assert.assertEquals;

import com.google.gson.Gson;
import org.junit.Test;

public class LMStudioApiMetricsTest {

    @Test
    public void parsesFractionalCpuUsageFromMetricsResponse() {
        String json = "{\"cpuUsage\":23.7,\"memoryUsedMB\":1024,\"tokenPerSecond\":0," +
                "\"errorCount\":0,\"errors\":[]}";
        LMStudioApi.Metrics metrics = new Gson().fromJson(json, LMStudioApi.Metrics.class);
        assertEquals(23.7, metrics.getCpuUsage(), 0.001);
    }

    @Test
    public void parsesGpuAndPromptUsageFromMetricsResponse() {
        String json = "{\"gpuUsage\":46.4,\"gpuMemoryUsedMB\":4096," +
                "\"gpuMemoryTotalMB\":8192,\"promptTokens\":37,\"completionTokens\":15}";

        LMStudioApi.Metrics metrics = new Gson().fromJson(json, LMStudioApi.Metrics.class);

        assertEquals(Double.valueOf(46.4), metrics.getGpuUsage());
        assertEquals(Long.valueOf(4096), metrics.getGpuMemoryUsedMB());
        assertEquals(Long.valueOf(8192), metrics.getGpuMemoryTotalMB());
        assertEquals(37L, metrics.getPromptTokens());
        assertEquals(15L, metrics.getCompletionTokens());
    }
}
