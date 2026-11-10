package com.example.dashboardlmstudio;

import android.os.Bundle;
import androidx.appcompat.app.AppCompatActivity;
import com.github.mikephil.charting.charts.LineChart;
import com.github.mikephil.charting.data.Entry;
import com.github.mikephil.charting.data.LineData;
import com.github.mikephil.charting.data.LineDataSet;

public class ChartActivity extends AppCompatActivity {

    private LineChart cpuChart, memoryChart, tokensChart;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_chart);

        cpuChart = findViewById(R.id.cpuChart);
        memoryChart = findViewById(R.id.memoryChart);
        tokensChart = findViewById(R.id.tokensChart);

        setupCharts();
    }

    private void setupCharts() {
        // CPU Chart
        LineDataSet cpuSet = new LineDataSet(null, "CPU %");
        cpuSet.setColor(0xFFFF5722);
        cpuSet.setValueTextColor(0xFFFFFFFF);
        cpuChart.setData(new LineData(cpuSet));

        // Memory Chart
        LineDataSet memSet = new LineDataSet(null, "Memory MB");
        memSet.setColor(0xFF2196F3);
        memSet.setValueTextColor(0xFFFFFFFF);
        memoryChart.setData(new LineData(memSet));

        // Tokens Chart
        LineDataSet tokenSet = new LineDataSet(null, "Tokens/s");
        tokenSet.setColor(0xFF4CAF50);
        tokenSet.setValueTextColor(0xFFFFFFFF);
        tokensChart.setData(new LineData(tokenSet));
    }

    public void updateCpuChart(float[] values) {
        LineDataSet cpuSet = (LineDataSet) cpuChart.getData().getDataSets().get(0);
        cpuSet.setValues(getEntries(values));
        cpuChart.notifyDataSetChanged();
        cpuChart.invalidate();
    }

    private java.util.List<Entry> getEntries(float[] values) {
        java.util.ArrayList<Entry> entries = new java.util.ArrayList<>();
        for (int i = 0; i < values.length; i++) {
            entries.add(new Entry(i, values[i]));
        }
        return entries;
    }
}
