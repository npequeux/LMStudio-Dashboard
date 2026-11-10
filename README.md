# DashboardLMStudio - Android Monitoring App


## Overview
An Android dashboard for viewing metrics from a reachable LM Studio-compatible server.

## Download the app

- [Download the latest signed APK](https://github.com/npequeux/LMStudio-Dashboard/releases/latest/download/app-release.apk)
- [Latest release notes](https://github.com/npequeux/LMStudio-Dashboard/releases/latest)
- [All releases](https://github.com/npequeux/LMStudio-Dashboard/releases)
- [GitHub Actions builds](https://github.com/npequeux/LMStudio-Dashboard/actions/workflows/build.yml) — temporary debug APK artifacts may require signing in to GitHub.

The direct APK link becomes available after the first successful signed release. The app requires Android 8.0 (API 26) or later.

## Install on Android

1. Open the [latest release](https://github.com/npequeux/LMStudio-Dashboard/releases/latest) on your Android device and download `app-release.apk`.
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

## Configure signed GitHub releases

The release workflow signs `app-release.apk` with a persistent release keystore. Back up this keystore securely and use the same key for every update. Losing or replacing it prevents existing installs from updating. Never commit the keystore or put it in source control.

Create a key locally with the JDK's `keytool`:

```bash
keytool -genkeypair -v -keystore dashboard-release.jks -alias dashboard-lmstudio -keyalg RSA -keysize 2048 -validity 10000
```

In PowerShell, copy a base64 representation of the keystore:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("dashboard-release.jks")) | Set-Clipboard
```

Add these repository secrets in **GitHub → Settings → Secrets and variables → Actions**:

- `ANDROID_KEYSTORE_BASE64` — the copied base64 value
- `ANDROID_KEYSTORE_PASSWORD` — the keystore password
- `ANDROID_KEY_ALIAS` — `dashboard-lmstudio` (or the alias you chose)
- `ANDROID_KEY_PASSWORD` — the key password

A push to `main` or a `v*` tag builds and publishes a signed APK. The workflow uses GitHub's built-in `GITHUB_TOKEN` for release creation; no personal access token is needed. The release job has to succeed before the latest-APK links above can download a file.

For a local release build, put the keystore at `app/release-key.jks`, set `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, and `ANDROID_KEY_PASSWORD` in the environment, then run `./gradlew assembleRelease`. The `*.jks` pattern is ignored by Git.

## CI artifacts and Maven publication

- [Build workflow](https://github.com/npequeux/LMStudio-Dashboard/actions/workflows/build.yml) builds a debug APK on pushes and pull requests. Debug artifacts are temporary and may require GitHub sign-in.
- Main-branch pushes and `v*` tags create signed GitHub Releases.
- The optional Maven publication publishes the APK artifact to [GitHub Packages](https://github.com/npequeux/LMStudio-Dashboard/packages); it is an APK, not an AAR.

Manual publication (with release signing and GitHub Packages credentials configured):

```bash
./gradlew assembleRelease publishReleasePublicationToGitHubPackagesRepository
```

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
