# DashboardLMStudio Metrics Bridge

A small FastAPI service for the Android DashboardLMStudio app. It runs beside LM Studio on the PC, exposes the dashboard's metrics routes, and proxies model/inference API requests to LM Studio.

## Why this is needed

LM Studio's built-in OpenAI-compatible server does not implement this dashboard's `/health` or `/api/v1/metrics` endpoints. Pointing the Android app directly at LM Studio therefore returns an unexpected-endpoint/404 response. Point the Android app at this bridge instead; the bridge handles those endpoints and forwards `/v1/models` and `/v1/chat/completions` to LM Studio.

## Requirements

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) (recommended), or Python with pip
- [LM Studio](https://lmstudio.ai/download) installed and its local server running on the PC

By default the bridge connects to LM Studio at `http://127.0.0.1:1234/v1` (the same machine). Start the API server in LM Studio's **Developer** tab. If LM Studio runs elsewhere, set `LM_STUDIO_URL` before starting the bridge. `LM_STUDIO_API_KEY` is optional and is forwarded as a bearer token when set.

## Install and run on Windows

Open PowerShell in the extracted `companion-metrics-server` folder—the folder containing `pyproject.toml`. Verify you are in the correct directory:

```powershell
Test-Path .\pyproject.toml
```

It must return `True`. If it returns `False`, change directory into the extracted `companion-metrics-server` folder before continuing. Install the dependencies:

```powershell
uv sync
```

Alternatively, use Python's built-in virtual environment and pip:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -e .
```

Start the bridge so the Android phone can reach it over the LAN:

```powershell
uv run uvicorn metrics_server.app:app --host 0.0.0.0 --port 8000
```

If you installed with pip instead of uv, run `\.\.venv\Scripts\python -m uvicorn metrics_server.app:app --host 0.0.0.0 --port 8000`.

If LM Studio is not at its default address, set it first:

```powershell
$env:LM_STUDIO_URL = "http://<LM-STUDIO-IP>:1234/v1"
uv run uvicorn metrics_server.app:app --host 0.0.0.0 --port 8000
```

Keep the terminal open while using the dashboard. Allow TCP port `8000` through the PC firewall for **Private networks** if Windows asks. Do not expose the bridge or LM Studio server directly to the public internet; this bridge currently has no client authentication.

To find the PC's LAN IPv4 address, run `ipconfig` and use the IPv4 address of the active Wi-Fi/Ethernet adapter. In the Android app, enter the bridge URL, not LM Studio's port:

```text
http://<PC-LAN-IP>:8000
```

For example: `http://192.168.129.35:8000`.

## Metrics and proxy behavior

- `/health` returns a successful health response for the Android app's connection check.
- `/api/v1/metrics` returns CPU percentage, system RAM used (MB), latest token/s rate, retained error count, and error entries.
- `/api/v1/errors` returns the retained error entries.
- `/v1/models` and `/v1/chat/completions` proxy to LM Studio.

CPU and system memory are measured on the PC. Token metrics come from the LM Studio desktop app as well as from the bridge's own proxy: the bridge listens to `lms log stream --source model --filter output --stats --json` and records each prediction's token speed and prompt/completion counts, and at startup it seeds the dashboard from the most recent prediction in LM Studio's local conversation history. Proxy requests are measured directly; streaming requests get `stream_options.include_usage` added so a final usage chunk is recorded too. The `logMonitor` field in `/api/v1/metrics` reports the diagnostics listener state (`running`, `retrying`, `unavailable`, or `disabled`). Because LM Studio only reports final token stats when a response finishes, the bridge also tails LM Studio's server logs for `tg = X t/s` timing lines and exposes `liveTokensPerSecond` (null when the engine log level does not include those lines), plus `serverLogMonitor` (`running`, `waiting`, or `disabled`) and a `liveTimingLines` counter — `running` with `0` lines means the log level is the blocker, not the code. Proxy errors are kept in an in-memory rolling log (up to 100 entries); restarting the bridge clears it.

## Configuration

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `LM_STUDIO_URL` | `http://127.0.0.1:1234/v1` | LM Studio API base URL; `/v1` is supported |
| `LM_STUDIO_API_KEY` | unset | Optional bearer token for LM Studio |

## Verify and test

With the bridge running, these URLs should respond:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/api/v1/metrics`
- `http://127.0.0.1:8000/v1/models` (requires LM Studio to be running)

Run the automated tests with:

```powershell
uv sync --extra test
uv run pytest -q
```
