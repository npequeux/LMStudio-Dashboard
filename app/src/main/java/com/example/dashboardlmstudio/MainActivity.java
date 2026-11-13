package com.example.dashboardlmstudio;

import android.os.Bundle;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.lifecycle.ViewModelProvider;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends AppCompatActivity {

    private DashboardViewModel viewModel;
    private ErrorLogAdapter errorLogAdapter;
    private RecyclerView errorRecyclerView;
    private TextView tvConnectionStatus;
    private Button btnConnect;
    private Button btnDisconnect;
    private Button btnStartMonitoring;
    private ProgressBar progressBar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        viewModel = new ViewModelProvider(this).get(DashboardViewModel.class);

        setupViews();
        observeData();
    }

    private void setupViews() {
        EditText serverUrlInput = findViewById(R.id.etServerUrl);
        EditText apiKeyInput = findViewById(R.id.etApiKey);
        android.content.SharedPreferences preferences = getSharedPreferences("settings", MODE_PRIVATE);
        String savedServerUrl = preferences.getString("server_url", null);
        if (savedServerUrl == null || savedServerUrl.trim().isEmpty()
                || savedServerUrl.contains(":1234") || savedServerUrl.endsWith("/v1")) {
            savedServerUrl = getString(R.string.hint_server_url);
            preferences.edit().putString("server_url", savedServerUrl).apply();
        }
        serverUrlInput.setText(savedServerUrl);
        apiKeyInput.setText(preferences.getString("bridge_api_key", ""));

        btnConnect = findViewById(R.id.btnConnect);
        btnDisconnect = findViewById(R.id.btnDisconnect);
        btnStartMonitoring = findViewById(R.id.btnStartMonitoring);
        progressBar = findViewById(R.id.progressBar);
        tvConnectionStatus = findViewById(R.id.tvConnectionStatus);

        // Setup error log RecyclerView
        errorRecyclerView = findViewById(R.id.recyclerViewErrors);
        errorRecyclerView.setLayoutManager(new LinearLayoutManager(this));
        errorLogAdapter = new ErrorLogAdapter();
        errorRecyclerView.setAdapter(errorLogAdapter);

        viewModel.getErrorMessage().observe(this, errorMessage -> {
            if (errorMessage != null && !errorMessage.isEmpty()) {
                Toast.makeText(this, errorMessage, Toast.LENGTH_LONG).show();
            }
        });

        btnConnect.setOnClickListener(v -> {
            String url = serverUrlInput.getText().toString().trim();
            if (url.isEmpty()) {
                Toast.makeText(this, "Please enter server URL", Toast.LENGTH_SHORT).show();
                return;
            }
            getSharedPreferences("settings", MODE_PRIVATE)
                    .edit()
                    .putString("server_url", url)
                    .putString("bridge_api_key", apiKeyInput.getText().toString().trim())
                    .apply();
            viewModel.connect(url);
        });

        btnDisconnect.setOnClickListener(v -> viewModel.disconnect());

        btnStartMonitoring.setOnClickListener(v -> {
            Boolean monitoring = viewModel.getMonitoring().getValue();
            if (monitoring != null && monitoring) {
                viewModel.stopMonitoring();
            } else {
                viewModel.startMonitoring(5000); // 5 second interval
            }
        });
    }

    private void observeData() {
        viewModel.getCpuUsage().observe(this, cpu -> {
            TextView tvCpu = findViewById(R.id.tvCpuValue);
            if (tvCpu != null) tvCpu.setText(cpu + "%");
        });

        viewModel.getMemoryUsage().observe(this, memory -> {
            TextView tvMemory = findViewById(R.id.tvMemoryValue);
            if (tvMemory != null) tvMemory.setText(memory + " MB");
        });

        viewModel.getTokenPerSecond().observe(this, tokens -> {
            TextView tvTokens = findViewById(R.id.tvTokensValue);
            if (tvTokens != null) tvTokens.setText(tokens + "/s");
        });

        viewModel.getGpuSummary().observe(this, gpu -> {
            TextView tvGpu = findViewById(R.id.tvGpuValue);
            if (tvGpu != null) tvGpu.setText(gpu);
        });

        viewModel.getPromptCompletionTokens().observe(this, tokens -> {
            TextView tvPromptTokens = findViewById(R.id.tvPromptCompletionTokensValue);
            if (tvPromptTokens != null) tvPromptTokens.setText(tokens);
        });

        viewModel.getErrorCount().observe(this, count -> {
            TextView tvErrors = findViewById(R.id.tvErrorCount);
            if (tvErrors != null) tvErrors.setText(String.valueOf(count));
        });

        viewModel.getConnectionStatus().observe(this, status -> {
            if (status == DashboardViewModel.ConnectionState.CONNECTED) {
                tvConnectionStatus.setText("Connected");
                tvConnectionStatus.setTextColor(ContextCompat.getColor(this, android.R.color.holo_green_light));
                btnConnect.setEnabled(false);
                btnDisconnect.setEnabled(true);
                progressBar.setVisibility(View.GONE);
            } else if (status == DashboardViewModel.ConnectionState.DISCONNECTED) {
                tvConnectionStatus.setText("Disconnected");
                tvConnectionStatus.setTextColor(ContextCompat.getColor(this, android.R.color.holo_red_dark));
                btnConnect.setEnabled(true);
                btnDisconnect.setEnabled(false);
                progressBar.setVisibility(View.GONE);
            } else if (status == DashboardViewModel.ConnectionState.CONNECTING) {
                tvConnectionStatus.setText("Connecting...");
                tvConnectionStatus.setTextColor(ContextCompat.getColor(this, android.R.color.holo_orange_dark));
                btnDisconnect.setEnabled(true);
                progressBar.setVisibility(View.VISIBLE);
            }
        });

        viewModel.getMonitoring().observe(this, monitoring -> {
            if (monitoring != null && monitoring) {
                btnStartMonitoring.setText(R.string.btn_stop_monitoring);
            } else {
                btnStartMonitoring.setText(R.string.btn_start_monitoring);
            }
        });

        viewModel.getErrors().observe(this, errors -> {
            if (errors != null && errorLogAdapter != null) {
                errorLogAdapter.submitList(errors);
            }
        });
    }
}
