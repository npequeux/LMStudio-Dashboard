package com.example.dashboardlmstudio;

import android.os.Bundle;
import androidx.appcompat.app.AppCompatActivity;
import android.widget.EditText;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

public class SettingsActivity extends AppCompatActivity {

    private EditText etServerUrl;
    private SeekBar seekBarRefreshInterval;
    private TextView tvRefreshValue;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        etServerUrl = findViewById(R.id.etSettingsServerUrl);
        seekBarRefreshInterval = findViewById(R.id.seekBarRefreshInterval);
        tvRefreshValue = findViewById(R.id.tvRefreshValue);

        // Load saved settings (simplified - use SharedPreferences in production)
        String savedUrl = getSharedPreferences("settings", MODE_PRIVATE)
                .getString("server_url", "http://192.168.129.35:8000");
        etServerUrl.setText(savedUrl);

        seekBarRefreshInterval.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                tvRefreshValue.setText((progress + 1) + "s");
            }
            @Override
            public void onStartTrackingTouch(SeekBar seekBar) {}
            @Override
            public void onStopTrackingTouch(SeekBar seekBar) {}
        });

        findViewById(R.id.btnSaveSettings).setOnClickListener(v -> {
            String url = etServerUrl.getText().toString().trim();
            int interval = seekBarRefreshInterval.getProgress() + 1;

            getSharedPreferences("settings", MODE_PRIVATE)
                    .edit()
                    .putString("server_url", url)
                    .putInt("refresh_interval", interval)
                    .apply();

            Toast.makeText(this, "Settings saved!", Toast.LENGTH_SHORT).show();
        });
    }
}
