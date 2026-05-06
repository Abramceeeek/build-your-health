"""claudeGYM — Entry Point.

Starts the FastAPI backend server AND the Telegram bot together.

Usage:
    python main.py
"""

import atexit
import os
import signal
import subprocess
import sys
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from backend.config import get_settings

_ROOT = os.path.dirname(os.path.abspath(__file__))

_bot_process = None


def _start_bot():
    """Launch bot.py as a background subprocess."""
    global _bot_process
    bot_script = os.path.join(_ROOT, "bot.py")
    if not os.path.exists(bot_script):
        print("  [!] bot.py not found -- skipping Telegram bot")
        return

    _bot_process = subprocess.Popen(
        [sys.executable, bot_script],
        cwd=_ROOT,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    atexit.register(_stop_bot)
    print(f"  [BOT] Telegram bot started (PID {_bot_process.pid})")


def _stop_bot():
    """Terminate the bot subprocess on exit."""
    global _bot_process
    if _bot_process and _bot_process.poll() is None:
        _bot_process.terminate()
        try:
            _bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _bot_process.kill()
        print("  [BOT] Telegram bot stopped")


def main():
    settings = get_settings()

    os.makedirs(settings.upload_dir, exist_ok=True)

    print("=" * 50)
    print("  HEALTH TRANSFORM")
    print("  AI-Powered Health & Fitness Mini App")
    print("=" * 50)
    print(f"  Server: http://{settings.host}:{settings.port}")
    print(f"  API Docs: http://localhost:{settings.port}/docs")
    print(f"  Database: {settings.database_url}")

    # Start the Telegram bot in the background
    _start_bot()

    print("=" * 50)

    # Only watch backend + frontend — avoids reload when scripts/.env change (was breaking tunnel runs)
    _reload_dirs = [
        os.path.join(_ROOT, "backend"),
        os.path.join(_ROOT, "frontend"),
    ]

    uvicorn.run(
        "backend.app:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        reload_dirs=[d for d in _reload_dirs if os.path.isdir(d)],
    )


if __name__ == "__main__":
    main()
