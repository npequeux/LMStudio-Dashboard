package com.example.dashboardlmstudio;

import java.util.Date;

public class ErrorLogEntry {
    private String timestamp;
    private String level;
    private String message;
    private String source;

    public ErrorLogEntry() {}

    public ErrorLogEntry(String timestamp, String level, String message, String source) {
        this.timestamp = timestamp;
        this.level = level;
        this.message = message;
        this.source = source;
    }

    public String getTimestamp() { return timestamp; }
    public void setTimestamp(String timestamp) { this.timestamp = timestamp; }
    public String getLevel() { return level; }
    public void setLevel(String level) { this.level = level; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }

    @Override
    public String toString() {
        return "[" + timestamp + "] " + level + ": " + message;
    }
}
