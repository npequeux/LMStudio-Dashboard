@echo off
setlocal

rem Works whether this file is at the extraction root or inside companion-metrics-server.
cd /d "%~dp0"
if exist "%~dp0companion-metrics-server\pyproject.toml" cd /d "%~dp0companion-metrics-server"

echo Starting LM Studio Metrics Bridge on http://0.0.0.0:8000
uv run uvicorn metrics_server.app:app --host 0.0.0.0 --port 8000

echo.
echo Bridge stopped. Press any key to close this window.
pause >nul
