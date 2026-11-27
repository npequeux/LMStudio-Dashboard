@echo off
setlocal
cd /d "%~dp0"

echo Starting LM Studio Metrics Bridge with the LCARS console dashboard...
uv run python -m metrics_server.console --host 0.0.0.0 --port 8000

echo.
echo Bridge stopped. Press any key to close this window.
pause >nul
