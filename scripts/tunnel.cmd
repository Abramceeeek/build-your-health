@echo off
REM Dead-simple Cloudflare quick tunnel. No Python wrapper.
REM Prerequisites: python main.py running in another terminal, cloudflared installed.
REM Usage: double-click this file or run from cmd.

cd /d "%~dp0.."

echo.
echo Checking if API is running on port 8000...
curl -sf http://127.0.0.1:8000/health >nul 2>&1
if errorlevel 1 (
    echo ERROR: Nothing is running on http://127.0.0.1:8000/health
    echo Start the API first:  python main.py
    echo.
    pause
    exit /b 1
)
echo OK: API is responding.
echo.

echo Killing any stale cloudflared processes...
taskkill /F /IM cloudflared.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Starting Cloudflare quick tunnel...
echo The HTTPS URL will appear below. Copy it into WEBAPP_URL in .env
echo Then restart: python bot.py
echo Press Ctrl+C to stop the tunnel.
echo.

REM --config NUL overrides ~/.cloudflared/config.yml which may have ingress rules that return 404
"C:\Program Files (x86)\cloudflared\cloudflared.exe" --config NUL tunnel --url http://127.0.0.1:8000 --protocol http2
