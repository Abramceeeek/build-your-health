@echo off
REM Uses ngrok instead of Cloudflare — see docs\NGROK_TUNNEL.md
cd /d "%~dp0.."

echo [1/3] API — leave OPEN
start "Health: API" cmd /k python main.py
timeout /t 10 /nobreak >nul

echo [2/3] ngrok — leave OPEN (install + authtoken required)
start "Health: ngrok" cmd /k python scripts\launch_ngrok.py
timeout /t 18 /nobreak >nul

echo [3/3] Bot — leave OPEN
start "Health: Bot" cmd /k python bot.py

echo Done. Set WEBAPP_URL from ngrok output if needed; restart bot after URL changes.
pause
