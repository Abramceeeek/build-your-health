@echo off
REM Three windows: API (main.py) -> tunnel (--tunnel-only) -> bot
REM This avoids port 8000 conflict: launch_tunnel.py must NOT start a second uvicorn while main.py runs.
cd /d "%~dp0.."

echo [1/3] Starting FastAPI (python main.py) - LEAVE THIS OPEN
start "Health: API (main.py)" cmd /k python main.py

echo Waiting for http://127.0.0.1:8000/health ...
timeout /t 10 /nobreak >nul

echo [2/3] Starting Cloudflare tunnel only - LEAVE THIS OPEN
start "Health: Tunnel" cmd /k python scripts\launch_tunnel.py --tunnel-only

echo Waiting for tunnel URL and .env update...
timeout /t 22 /nobreak >nul

echo [3/3] Starting Telegram bot - LEAVE THIS OPEN
start "Health: Telegram bot" cmd /k python bot.py

echo.
echo Three windows should have opened. Test the trycloudflare URL in Chrome before Telegram.
pause
