# DashboardLMStudio - Android Monitoring App

## Overview
A real-time monitoring dashboard application for LM Studio servers running on your local network or remote machines.

## Features
- **Real-time CPU Usage** - Monitor processor utilization of the LM Studio server
- **Memory Usage Tracking** - Track RAM consumption in MB
- **Tokens/sec Display** - View inference speed metrics
- **Error Logging** - Automatic error detection and logging with severity levels
- **Connection Management** - Connect/disconnect from any LM Studio instance
- **Configurable Refresh Rate** - Adjust monitoring interval (1-20 seconds)
- **Visual Charts** - Historical data visualization using MPAndroidChart

## Architecture
```
┌─────────────────────────────────────────┐
│              MainActivity                │
│  ┌──────────┬──────────┬──────────────┐ │
│  │   CPU    │ Memory   │ Tokens/sec   │ │
│  │  Card    │ Card     │   Card       │ │
│  └──────────┴──────────┴──────────────┘ │
│  ┌─────────────────────────────────────┐│
│  │         Error Log (RecyclerView)    ││
│  └─────────────────────────────────────┘│
└─────────────────────────────────────────┘
              │ Retrofit + OkHttp
              ▼
┌─────────────────────────────────────────┐
│          LM Studio REST API             │
│  GET /v1/models                         │
│  GET /api/v1/metrics                    │
│  GET /api/v1/errors                     │
│  GET /health                            │
└─────────────────────────────────────────┘
```

## Setup

### Prerequisites
- Android Studio Hedgehog (2023.1.1) or later
- JDK 17+
- Android SDK 34 (API level 34)
- LM Studio running on a network-accessible machine

### Configuration
1. Open the project in Android Studio
2. Update `local.properties` with your Android SDK path:
   ```
   sdk.dir=C\:\\Users\\YourUsername\\AppData\\Local\\Android\\Sdk
   ```
3. Run the app and enter your LM Studio server URL (e.g., `http://192.168.1.100:1234`)

### Building from Command Line
```bash
# Debug build
./gradlew assembleDebug

# Release build
./gradlew assembleRelease

# Install debug APK to connected device
./gradlew installDebug

# Build and publish to GitHub Packages
./gradlew publishReleasePublicationTo-github-packages
```

## CI/CD Pipeline (GitHub Actions)

The project includes a complete CI/CD pipeline in `.github/workflows/build.yml`:

- **Build Job**: Compiles debug APK on every push/PR
- **Release Job**: Creates GitHub Release with signed APK on main branch pushes
- **Publish Job**: Publishes AAR to GitHub Packages
- **Notify Job**: Sends status notifications

### Required Secrets (for release)
```
GITHUB_TOKEN - Personal Access Token with repo scope
```

## LM Studio API Endpoints Used

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check endpoint |
| `/v1/models` | GET | List available models |
| `/api/v1/metrics` | GET | Get CPU, memory, tokens/sec metrics |
| `/api/v1/errors` | GET | Get error log entries |

## Dependencies
- **Retrofit 2.9** - REST API client
- **OkHttp 4.12** - HTTP client with logging interceptor
- **MPAndroidChart v3.1** - Chart visualization library
- **Kotlin Coroutines** - Async operations
- **Material Components** - UI components

## License
MIT License - See LICENSE file for details.
