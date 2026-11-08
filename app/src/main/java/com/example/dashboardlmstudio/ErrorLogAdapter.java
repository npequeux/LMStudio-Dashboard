package com.example.dashboardlmstudio;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.recyclerview.widget.DiffUtil;
import androidx.recyclerview.widget.ListAdapter;
import androidx.recyclerview.widget.RecyclerView;

public class ErrorLogAdapter extends ListAdapter<ErrorLogEntry, ErrorLogAdapter.ViewHolder> {

    public ErrorLogAdapter() {
        super(new DiffUtil.ItemCallback<ErrorLogEntry>() {
            @Override
            public boolean areItemsTheSame(@NonNull ErrorLogEntry oldItem, @NonNull ErrorLogEntry newItem) {
                return oldItem.getTimestamp().equals(newItem.getTimestamp()) &&
                       oldItem.getMessage().equals(newItem.getMessage());
            }

            @Override
            public boolean areContentsTheSame(@NonNull ErrorLogEntry oldItem, @NonNull ErrorLogEntry newItem) {
                return oldItem.equals(newItem);
            }
        });
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_error_log, parent, false);
        return new ViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        ErrorLogEntry entry = getItem(position);
        holder.tvTimestamp.setText(entry.getTimestamp());
        holder.tvLevel.setText(entry.getLevel().toUpperCase());
        holder.tvMessage.setText(entry.getMessage());
        holder.tvSource.setText("[" + (entry.getSource() != null ? entry.getSource() : "unknown") + "]");

        // Color code by level
        if ("ERROR".equals(entry.getLevel())) {
            holder.tvLevel.setTextColor(0xFFFF4444);
        } else if ("WARN".equals(entry.getLevel())) {
            holder.tvLevel.setTextColor(0xFFFFA726);
        } else {
            holder.tvLevel.setTextColor(0xFF8BC34A);
        }
    }

    static class ViewHolder extends RecyclerView.ViewHolder {
        TextView tvTimestamp, tvLevel, tvMessage, tvSource;

        ViewHolder(View itemView) {
            super(itemView);
            tvTimestamp = itemView.findViewById(R.id.tvErrorTimestamp);
            tvLevel = itemView.findViewById(R.id.tvErrorLevel);
            tvMessage = itemView.findViewById(R.id.tvErrorMessage);
            tvSource = itemView.findViewById(R.id.tvErrorSource);
        }
    }
}
