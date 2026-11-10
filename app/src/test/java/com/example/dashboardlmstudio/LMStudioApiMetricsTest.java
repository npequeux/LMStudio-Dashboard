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
}
