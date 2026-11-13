# DashboardLMStudio - Android Monitoring App


## Overview
An Android dashboard for viewing metrics from a reachable LM Studio-compatible server.

## Download the app

- [Download the latest temporary debug APK](https://github.com/npequeux/LMStudio-Dashboard/releases/latest/download/app-debug.apk)
- [Download the companion metrics server ZIP](https://github.com/npequeux/LMStudio-Dashboard/releases/latest/download/DashboardLMStudio_MetricsServer.zip)
- [Latest release notes](https://github.com/npequeux/LMStudio-Dashboard/releases/latest)
- [All releases](https://github.com/npequeux/LMStudio-Dashboard/releases)
- [GitHub Actions builds](https://github.com/npequeux/LMStudio-Dashboard/actions/workflows/build.yml) — temporary debug APK artifacts may require signing in to GitHub.

The direct APK and companion ZIP links become available after the next successful GitHub Release. This temporary build uses the `.debug` application ID and debug signing, and is for testing only. Each CI run may generate a different debug key; uninstall an older debug build before installing a new one if Android rejects the update. The app requires Android 8.0 (API 26) or later.

## Install on Android

1. Open the [latest release](https://github.com/npequeux/LMStudio-Dashboard/releases/latest) on your Android device and download `app-debug.apk`.
2. If prompted, allow your browser or file manager to install unknown apps. On Android 8+, this permission is under **Settings → Apps → Special app access → Install unknown apps**.
3. Open the downloaded APK and tap **Install**.
4. After installation, you can turn off the install-unknown-apps permission again.

These APKs are sideloaded; they are not distributed through Google Play. Only install APKs from releases you trust.

## Connect and use

1. Start the companion metrics bridge on the PC and make it reachable from the phone. Keep the PC and phone on the same trusted network, and allow TCP port 8000 through the PC firewall for Private networks.
2. The server URL is prefilled as `http://192.168.129.35:8000`; change it if the PC's LAN IP differs. The app remembers the URL after you connect.
3. Tap **Connect**, then **Start Monitoring** after the connection succeeds. Metrics refresh every five seconds. Use **Stop Monitoring** to pause polling and **Disconnect** to release the connection.
4. If the bridge sets `BRIDGE_API_KEY`, enter the same key in the **Bridge API key** field before connecting.
5. View CPU, memory, GPU, token-speed, prompt/completion, and error metrics returned by the bridge.

The Android app calls `GET /health` and `GET /api/v1/metrics` on the bridge. LM Studio itself does not implement those routes, which is why pointing the app directly to LM Studio produces an unexpected-endpoint response. The bridge proxies LM Studio's model/inference API and supplies the dashboard's metrics routes. Its source and run instructions are in `companion-metrics-server/` in this repository.

Token metrics come from two sources. The bridge listens to LM Studio's live inference diagnostics (`lms log stream`), so predictions made in the LM Studio desktop app are captured while the bridge is running; and at startup the bridge seeds the dashboard from the most recent prediction stored in LM Studio's local conversation history, so the last prediction is visible even when the bridge was started afterwards. Inferences routed through the bridge are measured directly, and streaming requests get `stream_options.include_usage` added so they are measured too. The `logMonitor` field in `/api/v1/metrics` reports whether the live listener is `running`, `retrying`, `unavailable`, or `disabled`. Plain HTTP is used for this local-network setup; do not expose it to public networks.

### PC requirements

- Install [LM Studio for Windows, macOS, or Linux](https://lmstudio.ai/download) and start its API server from the **Developer** tab. The bridge defaults to `http://127.0.0.1:1234/v1` (same machine as LM Studio); configure `LM_STUDIO_URL` if LM Studio runs elsewhere.
- Run the Python companion service from the `companion-metrics-server` folder in this repository, or download and extract the [companion metrics ZIP](https://github.com/npequeux/LMStudio-Dashboard/releases/latest/download/DashboardLMStudio_MetricsServer.zip). Its default upstream is `http://127.0.0.1:1234/v1`.
- Enter the bridge URL (`http://192.168.129.35:8000`) in the Android app. LM Studio must be reachable at the configured upstream address.

### Install the companion metrics service on Windows

1. Download and extract `DashboardLMStudio_MetricsServer.zip`, or use the `companion-metrics-server` folder from the repository.
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if it is not already installed.
3. Open PowerShell in the extracted `companion-metrics-server` folder and install dependencies:

   ```powershell
   uv sync
   ```

4. Start LM Studio's API server. By default the bridge reaches it at `http://127.0.0.1:1234/v1` on the same PC. If LM Studio runs on another machine or port, set `LM_STUDIO_URL` in PowerShell before starting the bridge:

   ```powershell
   $env:LM_STUDIO_URL = "http://<PC-LAN-IP>:1234/v1"
   ```

5. Start the bridge:

   ```powershell
   uv run uvicorn metrics_server.app:app --host 0.0.0.0 --port 8000
   ```

6. Allow TCP port 8000 through Windows Firewall for **Private networks** only. Keep the bridge running while using the Android app.
7. In the app, connect to `http://192.168.129.35:8000` (replace the IP if the PC's LAN address differs). Do not enter LM Studio's `:1234/v1` address in the app; that address is for the bridge's upstream connection.

If using Python/pip instead of uv, from the companion folder run `py -m venv .venv`, then `.\.venv\Scripts\python -m pip install -e .`, and launch with `.\.venv\Scripts\python -m uvicorn metrics_server.app:app --host 0.0.0.0 --port 8000`.

## Features
- Live CPU, memory, GPU, token-speed, and prompt/completion metric cards
- Error count and error log display
- Connection to a bridge by base URL, with optional bearer API key
- Start/stop monitoring and disconnect controls
- Five-second dashboard refresh

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
│        Metrics bridge (FastAPI)          │
│  GET /health                            │
│  GET /api/v1/metrics  (logMonitor)      │
│  GET /api/v1/errors                     │
│  POST /v1/chat/completions  (proxy)     │
└─────────────────────────────────────────┘
              │ httpx
              ▼
┌─────────────────────────────────────────┐
│            LM Studio API                 │
│  GET /v1/models                         │
│  POST /v1/chat/completions              │
└─────────────────────────────────────────┘
```

## Building from source

### Prerequisites

- Android Studio or the included Gradle wrapper
- JDK 17 or later
- Android SDK 35 (`compileSdk = 35`)
- A server reachable from the Android device and exposing the routes described below

Set `sdk.dir` in your local, untracked `local.properties`, or let Android Studio configure it. Build and install a debug APK with:

```bash
./gradlew assembleDebug
./gradlew installDebug
```

On Windows, use `gradlew.bat`. The debug APK is written to `app/build/outputs/apk/debug/app-debug.apk`; it is debug-signed and intended for testing.

## Temporary GitHub releases

For now, GitHub Releases attach the debug APK produced by the build job. This avoids release-keystore secrets and lets you install a test build. It is debug-signed, uses the `.debug` application ID, and is not suitable for production or Google Play. GitHub may generate a different debug key for each run, so uninstall the previous debug build before installing a new one if Android rejects the update.

A production release will require a persistent release keystore and GitHub Actions secrets. Do not distribute this temporary debug build as a production app.

## CI builds

- [Build workflow](https://github.com/npequeux/LMStudio-Dashboard/actions/workflows/build.yml) builds the debug APK and runs the Android and Python bridge tests on pushes and pull requests.
- Pushes to `main` and `v*` tags create a GitHub Release with `app-debug.apk` and the companion metrics server ZIP.

## API endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Connection check |
| `GET /api/v1/metrics` | CPU, memory, token speed, error metrics, and `logMonitor` status |
| `GET /v1/models` | Model list endpoint declared by the client |
| `GET /api/v1/errors` | Error list endpoint declared by the client |

The monitoring screen currently requests `/health` and `/api/v1/metrics`. The model and standalone error routes are declared in the API client but are not currently used by the monitoring screen. This Android project does not implement the server-side metrics endpoints.

## Dependencies
- **Retrofit 2.9** - REST API client
- **OkHttp 4.12** - HTTP client with logging interceptor
- **Gson** - JSON parsing
- **AndroidX Lifecycle** - ViewModel/LiveData
- **Material Components** - UI components

## License
MIT License - See LICENSE file for details.
