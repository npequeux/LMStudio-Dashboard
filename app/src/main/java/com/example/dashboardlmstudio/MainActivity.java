package com.example.dashboardlmstudio;

import android.os.Bundle;
import androidx.appcompat.app.AppCompatActivity;
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
        Button btnConnect = findViewById(R.id.btnConnect);
        Button btnStartMonitoring = findViewById(R.id.btnStartMonitoring);
        ProgressBar progressBar = findViewById(R.id.progressBar);
        TextView tvStatus = findViewById(R.id.tvConnectionStatus);

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
            viewModel.connect(url);
        });

        btnStartMonitoring.setOnClickListener(v -> {
            viewModel.startMonitoring(5000); // 5 second interval
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

        viewModel.getErrorCount().observe(this, count -> {
            TextView tvErrors = findViewById(R.id.tvErrorCount);
            if (tvErrors != null) tvErrors.setText(String.valueOf(count));
        });

        viewModel.getConnectionStatus().observe(this, status -> {
            TextView tvStatus = findViewById(R.id.tvConnectionStatus);
            Button btnConnect = findViewById(R.id.btnConnect);
            ProgressBar progressBar = findViewById(R.id.progressBar);

            if (status == DashboardViewModel.ConnectionState.CONNECTED) {
                tvStatus.setText("Connected");
                tvStatus.setTextColor(getResources().getColor(android.R.color.holo_green_light));
                btnConnect.setEnabled(false);
                progressBar.setVisibility(View.GONE);
            } else if (status == DashboardViewModel.ConnectionState.DISCONNECTED) {
                tvStatus.setText("Disconnected");
                tvStatus.setTextColor(getResources().getColor(android.R.color.holo_red_dark));
                btnConnect.setEnabled(true);
                progressBar.setVisibility(View.GONE);
            } else if (status == DashboardViewModel.ConnectionState.CONNECTING) {
                tvStatus.setText("Connecting...");
                tvStatus.setTextColor(getResources().getColor(android.R.color.holo_orange_dark));
                progressBar.setVisibility(View.VISIBLE);
            }
        });

        viewModel.getErrors().observe(this, errors -> {
            if (errors != null && errorLogAdapter != null) {
                errorLogAdapter.submitList(errors);
            }
        });
    }
}
