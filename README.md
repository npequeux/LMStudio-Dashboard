# DashboardLMStudio - Android Monitoring App


## Overview
An Android dashboard for viewing metrics from a reachable LM Studio-compatible server.

## Download the app

- [Download the latest temporary debug APK](https://github.com/npequeux/LMStudio-Dashboard/releases/latest/download/app-debug.apk)
- [Latest release notes](https://github.com/npequeux/LMStudio-Dashboard/releases/latest)
- [All releases](https://github.com/npequeux/LMStudio-Dashboard/releases)
- [GitHub Actions builds](https://github.com/npequeux/LMStudio-Dashboard/actions/workflows/build.yml) — temporary debug APK artifacts may require signing in to GitHub.

The direct APK link becomes available after the first successful debug release. This temporary build uses the `.debug` application ID and debug signing, and is for testing only. Each CI run may generate a different debug key; uninstall an older debug build before installing a new one if Android rejects the update. The app requires Android 8.0 (API 26) or later.

## Install on Android

1. Open the [latest release](https://github.com/npequeux/LMStudio-Dashboard/releases/latest) on your Android device and download `app-debug.apk`.
2. If prompted, allow your browser or file manager to install unknown apps. On Android 8+, this permission is under **Settings → Apps → Special app access → Install unknown apps**.
3. Open the downloaded APK and tap **Install**.
4. After installation, you can turn off the install-unknown-apps permission again.

These APKs are sideloaded; they are not distributed through Google Play. Only install APKs from releases you trust.

## Connect and use

1. Start the server on your computer and make it reachable from the phone. The phone and server usually need to be on the same network; allow the server through the computer's firewall.
2. Enter the server's base URL, for example `http://192.168.1.50:1234` (use the computer's LAN IP and actual port, not `localhost`).
3. Tap **Connect**, then **Start Monitoring** after the connection succeeds. Metrics refresh every five seconds.
4. View CPU, memory, token-speed, and error metrics returned by the server.

The app currently calls `GET /health` for connection checks and `GET /api/v1/metrics` for monitoring data. The metrics response should use `cpuUsage`, `memoryUsedMB`, `tokenPerSecond`, `errorCount`, and optionally `errors`. Confirm that your server exposes these routes; this Android project does not provide the metrics service. Plain HTTP is supported for local-network use, so use it only on a network you trust.

### PC requirements

- Install [LM Studio for Windows, macOS, or Linux](https://lmstudio.ai/download).
- Start its API server from the **Developer** tab. See the [LM Studio server guide](https://lmstudio.ai/docs/developer/core/server).
- To connect from a phone, enable [Serve on Local Network](https://lmstudio.ai/docs/developer/core/server/serve-on-network) and use the network address shown by LM Studio.

**Important:** LM Studio alone does not supply the dashboard's `/health` and `/api/v1/metrics` routes for CPU, memory, token speed, and errors. You also need a compatible companion metrics service or proxy running on the PC. This repository does not include that service or provide a download link for one.

## Features
- Live CPU, memory, and token-speed metric cards
- Error count and error log display
- Connection to a server by base URL
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
│          LM Studio REST API             │
│  GET /v1/models                         │
│  GET /api/v1/metrics                    │
│  GET /api/v1/errors                     │
│  GET /health                            │
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

- [Build workflow](https://github.com/npequeux/LMStudio-Dashboard/actions/workflows/build.yml) builds the debug APK on pushes and pull requests.
- Pushes to `main` and `v*` tags create a GitHub Release with `app-debug.apk`.
- The Maven/GitHub Packages publication is paused while releases use the temporary debug-signing setup.

## API endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Connection check |
| `GET /api/v1/metrics` | CPU, memory, token speed, and error metrics |
| `GET /v1/models` | Model list endpoint declared by the client |
| `GET /api/v1/errors` | Error list endpoint declared by the client |

The monitoring screen currently requests `/health` and `/api/v1/metrics`. The model and standalone error routes are declared in the API client but are not currently used by the monitoring screen. This Android project does not implement the server-side metrics endpoints.

## Dependencies
- **Retrofit 2.9** - REST API client
- **OkHttp 4.12** - HTTP client with logging interceptor
- **MPAndroidChart v3.1** - Chart visualization library
- **Kotlin Coroutines** - Async operations
- **Material Components** - UI components

## License
MIT License - See LICENSE file for details.
